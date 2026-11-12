"""Email center: the software owner writes to the companies that use Ribdigi ERP.

Each person gets their own message, so no address is shown to anyone else.
A send is recorded in the owner's audit log when it starts and when it ends;
that record is the history. Mail goes through the platform SMTP settings, never a
company's own mail server.
"""

from __future__ import annotations

import asyncio
import html
import logging
import re
from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy import select

from app import audit as audit_svc
from app import emailer
from app import models as m
from app.desk_routing import rows_on_every_desk
from app.models import uid
from app.tenants import PROTECTED_TENANT_SLUGS

logger = logging.getLogger(__name__)

MAX_RECIPIENTS = 2000
SEND_CONCURRENCY = 4
ACTION_STARTED = "platform_bulk_email_started"
ACTION_FINISHED = "platform_bulk_email_finished"
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PLACEHOLDER = "{company_name}"


@dataclass
class Recipient:
    email: str
    tenant_id: str
    company_name: str


def _clean_email(value: str | None) -> str | None:
    text = (value or "").strip().lower()
    return text if _EMAIL_RE.match(text) else None


async def audience(
    db,
    *,
    statuses: list[str] | None,
    industries: list[str] | None,
    packages: list[str] | None,
    include_company_email: bool,
    exclude_tenant_id: str | None,
) -> list[Recipient]:
    """Company admins (and optionally each company's own email) for the chosen companies."""
    stmt = select(
        m.Tenant.id, m.Tenant.slug, m.Tenant.company_name, m.Tenant.status,
        m.Tenant.industry, m.Tenant.package_code, m.Tenant.email,
    )
    tenants = await rows_on_every_desk(db, stmt)
    chosen: dict[str, tuple[str, str | None]] = {}
    for tid, slug, name, status, industry, package, company_email in tenants:
        if tid == exclude_tenant_id or (slug or "") in PROTECTED_TENANT_SLUGS:
            continue
        if statuses and (status or "") not in statuses:
            continue
        if industries and (industry or "") not in industries:
            continue
        if packages and (package or "") not in packages:
            continue
        chosen[tid] = (name or slug or "your company", company_email)
    if not chosen:
        return []
    admins = await rows_on_every_desk(
        db,
        select(m.User.tenant_id, m.User.email).where(
            m.User.role == "company_admin",
            m.User.is_active == True,  # noqa: E712
        ),
    )
    out: list[Recipient] = []
    seen: set[str] = set()

    def add(email: str | None, tid: str) -> None:
        clean = _clean_email(email)
        if clean and clean not in seen:
            seen.add(clean)
            out.append(Recipient(email=clean, tenant_id=tid, company_name=chosen[tid][0]))

    for tid, email in admins:
        if tid in chosen:
            add(email, tid)
    if include_company_email:
        for tid, (_, company_email) in chosen.items():
            add(company_email, tid)
    return out


def summarize(recipients: list[Recipient]) -> dict:
    return {
        "recipient_count": len(recipients),
        "company_count": len({r.tenant_id for r in recipients}),
        "sample": [{"email": r.email, "company_name": r.company_name} for r in recipients[:8]],
        "too_many": len(recipients) > MAX_RECIPIENTS,
        "max_recipients": MAX_RECIPIENTS,
    }


def render(subject: str, body: str, company_name: str) -> tuple[str, str, str]:
    """Subject, text and branded HTML with {company_name} filled in."""
    name = company_name or "your company"
    subject_out = subject.replace(_PLACEHOLDER, name)
    text = body.replace(_PLACEHOLDER, name)
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    inner = "".join(
        f"<p>{html.escape(p).replace(chr(10), '<br>')}</p>" for p in paragraphs
    )
    inner += (
        '<p style="color:#4D5D56;font-size:12px;margin-top:24px">'
        "You are receiving this because your company uses Ribdigi ERP.</p>"
    )
    html_body = emailer.render_branded_html(
        body_html=inner, company_name="Ribdigi House", tenant=None, title=subject_out,
        allow_platform_logo=True,
    )
    footer = "\n\nYou are receiving this because your company uses Ribdigi ERP."
    return subject_out, text + footer, html_body


def mail_mode() -> str:
    """smtp sends for real; console only logs (development); disabled sends nothing."""
    return emailer._delivery_mode(None)


def require_mail_ready() -> None:
    from app.config import settings

    mode = mail_mode()
    live = (settings.APP_ENV or "").lower() == "production"
    if mode == "disabled" or (live and mode != "smtp"):
        raise HTTPException(
            status_code=503,
            detail="Platform email is not set up. Turn email on and set the SMTP settings for Ribdigi House before sending.",
        )


async def send_one(email: str, subject: str, body: str, company_name: str) -> tuple[bool, str | None]:
    subject_out, text, html_body = render(subject, body, company_name)
    result = await emailer.send_email(to=email, subject=subject_out, text_body=text, html_body=html_body)
    return bool(result.sent), (result.error or result.mode if not result.sent else None)


async def record_start(db, *, actor: dict, subject: str, body: str, filters: dict, summary: dict) -> str:
    send_id = uid()
    await audit_svc.record_event(
        db,
        tenant_id=actor["tenant_id"],
        user_id=actor.get("user_id"),
        module="platform",
        action=ACTION_STARTED,
        entity="bulk_email",
        entity_id=send_id,
        details={
            "subject": subject[:200],
            "body_preview": body[:300],
            "filters": filters,
            "recipient_count": summary["recipient_count"],
            "company_count": summary["company_count"],
            "sent_by": actor.get("email"),
        },
        ip_address=actor.get("ip"),
        user_agent=actor.get("user_agent"),
    )
    return send_id


async def deliver(*, send_id: str, actor: dict, subject: str, body: str, recipients: list[Recipient]) -> None:
    """Background job: send to everyone, then write the outcome to the audit log."""
    from app.db import SessionLocal

    gate = asyncio.Semaphore(SEND_CONCURRENCY)
    failures: list[dict] = []
    sent = 0

    async def one(r: Recipient) -> None:
        nonlocal sent
        async with gate:
            try:
                ok, reason = await send_one(r.email, subject, body, r.company_name)
            except Exception as exc:  # one bad address must not stop the rest
                logger.exception("bulk email to %s failed", r.email)
                ok, reason = False, str(exc)[:200]
        if ok:
            sent += 1
        else:
            failures.append({"email": r.email, "reason": (reason or "not sent")[:200]})

    await asyncio.gather(*(one(r) for r in recipients))
    async with SessionLocal() as db:
        await audit_svc.record_event(
            db,
            tenant_id=actor["tenant_id"],
            user_id=actor.get("user_id"),
            module="platform",
            action=ACTION_FINISHED,
            entity="bulk_email",
            entity_id=send_id,
            details={"sent": sent, "failed": len(failures), "failures": failures[:50]},
        )
        await db.commit()


async def history(db, *, tenant_id: str, limit: int = 30) -> list[dict]:
    rows = (
        await db.execute(
            select(m.AuditLog)
            .where(
                m.AuditLog.tenant_id == tenant_id,
                m.AuditLog.entity == "bulk_email",
                m.AuditLog.action.in_([ACTION_STARTED, ACTION_FINISHED]),
            )
            .order_by(m.AuditLog.created_at.desc())
            .limit(limit * 2)
        )
    ).scalars().all()
    finished = {r.entity_id: r.details or {} for r in rows if r.action == ACTION_FINISHED}
    out = []
    for r in rows:
        if r.action != ACTION_STARTED:
            continue
        d = r.details or {}
        done = finished.get(r.entity_id)
        out.append(
            {
                "id": r.entity_id,
                "created_at": r.created_at,
                "subject": d.get("subject"),
                "body_preview": d.get("body_preview"),
                "filters": d.get("filters") or {},
                "recipient_count": d.get("recipient_count", 0),
                "company_count": d.get("company_count", 0),
                "sent_by": d.get("sent_by"),
                "status": "finished" if done is not None else "sending",
                "sent": (done or {}).get("sent"),
                "failed": (done or {}).get("failed"),
                "failures": (done or {}).get("failures") or [],
            }
        )
    return out[:limit]
