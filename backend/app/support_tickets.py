"""Tenant-isolated support tickets, owner desk, and notification outbox.

Ticket writes, audit rows, and outbox jobs share one database transaction.
Delivery runs later via Celery (or an explicit worker call) and does not
block ticket create or reply on SMTP.
"""

from __future__ import annotations

import hashlib
import html
import logging
import os
import re
import uuid
from datetime import datetime, timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit, emailer, models as m, packages as packages_svc, storage as storage_svc
from app.config import settings
from app.rbac import PLATFORM_ROLES, has_permission, is_platform_role

logger = logging.getLogger(__name__)

DEFAULT_SUPPORT_EMAIL = "support@ribdigihouse.com"
PRIORITIES = ("low", "normal", "high", "urgent")
STATUSES = ("new", "in_progress", "waiting_for_tenant", "resolved", "closed")
TRANSITIONS: dict[str, set[str]] = {
    "new": {"in_progress", "waiting_for_tenant", "resolved", "closed"},
    "in_progress": {"waiting_for_tenant", "resolved", "closed"},
    "waiting_for_tenant": {"in_progress", "resolved", "closed"},
    "resolved": {"closed", "in_progress"},
    "closed": {"in_progress"},
}
OWNER_ACTIONS = frozenset({"view_all", "assign", "manage", "internal_note", "notification_manage"})
REF_RE = re.compile(r"^RIB-\d{4}-\d{6}$")
_EMAIL_RE = re.compile(
    r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9](?:[A-Za-z0-9\-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9\-]{0,61}[A-Za-z0-9])?)+$"
)
_SECRET_RE = re.compile(r"(?i)\b(password|secret|token|authorization|api[_-]?key)\b\s*[:=]\s*\S+")
_BLOCKED_EXT = frozenset(
    {
        "exe",
        "bat",
        "cmd",
        "com",
        "js",
        "mjs",
        "msi",
        "dll",
        "sh",
        "ps1",
        "html",
        "htm",
        "svg",
        "php",
        "py",
        "jar",
        "apk",
        "dmg",
        "scr",
        "vbs",
        "wsf",
    }
)

# code, label, required module or any-of modules. None = every industry.
CATEGORY_DEFS: tuple[tuple[str, str, str | tuple[str, ...] | None], ...] = (
    ("account_login", "Account and login", None),
    ("pos_sales", "POS and sales", "pos"),
    ("inventory_stock", "Inventory and stock", "inventory"),
    ("purchases_suppliers", "Purchases and suppliers", "purchasing"),
    ("finance_reports", "Finance and reports", ("accounting", "reports", "expenses")),
    ("printing_barcode_receipt", "Printing, barcode, and receipt", "printers"),
    ("settings_configuration", "Settings and configuration", None),
    ("bug_other", "Bug or other", None),
)
# Same desks as the sidebar. Package modules stay shared; these industries do not operate POS.
_POS_TICKET_INDUSTRIES = frozenset({"retail", "retail_wholesale", "pharmacy", "restaurant", "hotel"})
_SALES_DESK_INDUSTRIES = frozenset({"wholesale", "fmcg"})
_OPERATING_INDUSTRIES = _POS_TICKET_INDUSTRIES | _SALES_DESK_INDUSTRIES | frozenset({"hospital"})
CATEGORY_CODES = {code for code, _label, _mods in CATEGORY_DEFS}
CATEGORY_LABELS = {code: label for code, label, _mods in CATEGORY_DEFS}

_EVENT_LABELS = {
    "tenant_created": "New support ticket",
    "tenant_replied": "Tenant reply",
    "tenant_reopened": "Tenant reopened a ticket",
    "assigned": "Ticket assignment",
    "status_needs_action": "Ticket needs support",
    "public_reply": "Support reply",
    "tenant_status": "Ticket status update",
    "test_email": "Support notification test",
}


def support_can(claims: dict, action: str) -> bool:
    role = str(claims.get("role") or "")
    if action in OWNER_ACTIONS and not is_platform_role(role):
        return False
    overrides = claims.get("permissions") if isinstance(claims.get("permissions"), dict) else None
    return has_permission(role, "support", action, overrides=overrides)


def can_see_ticket(claims: dict, ticket: m.SupportTicket) -> bool:
    role = str(claims.get("role") or "")
    if is_platform_role(role) and support_can(claims, "view_all"):
        return True
    if ticket.tenant_id != claims.get("tenant_id"):
        return False
    if support_can(claims, "view_tenant"):
        return True
    return bool(support_can(claims, "view_own") and ticket.created_by == claims.get("sub"))


async def enforce_rate_limit(action: str, user_id: str) -> None:
    if not settings.RATE_LIMIT_ENABLED:
        return
    from app.rate_limit import rate_limiter

    limit = min(30, max(1, int(settings.RATE_LIMIT_PER_MINUTE)))
    allowed, retry_after, _remaining = await rate_limiter.allow(
        f"support:{action}:{user_id}", limit, 60.0
    )
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail={
                "code": "RATE_LIMIT_EXCEEDED",
                "message": "Too many support requests. Try again shortly.",
                "retry_after": retry_after,
            },
        )


def clean_text(value: Any, *, min_len: int, max_len: int, label: str, allow_newlines: bool = True) -> str:
    raw = str(value or "").replace("\x00", "")
    if not allow_newlines:
        raw = " ".join(raw.splitlines())
    else:
        raw = raw.replace("\r\n", "\n").replace("\r", "\n")
    raw = raw.strip()
    if len(raw) < min_len or len(raw) > max_len:
        raise HTTPException(status_code=422, detail=f"{label} must be {min_len}-{max_len} characters")
    if not re.search(r"[A-Za-z0-9]", raw):
        raise HTTPException(status_code=422, detail=f"{label} must include a letter or number")
    if re.search(r"<\s*script", raw, re.I):
        raise HTTPException(status_code=422, detail=f"{label} contains unsafe content")
    return raw


def normalize_email(value: str) -> str:
    compact = re.sub(r"\s+", "", str(value or ""))
    if not compact or len(compact) > 254 or not _EMAIL_RE.match(compact):
        raise HTTPException(status_code=422, detail="Enter a valid email address")
    return compact.lower()


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.replace(microsecond=0).isoformat() + "Z"


def _summary(*parts: str | None) -> str:
    text = " ".join(part for part in parts if part)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:180]


def safe_error(exc: Any) -> str:
    text = str(exc or "Email delivery failed")
    text = _SECRET_RE.sub(r"\1=[redacted]", text)
    text = re.sub(r"\s+", " ", text).strip()
    return (text or "Email delivery failed")[:500]


def _link(kind: str) -> str:
    base = (settings.FRONTEND_URL or "http://localhost:3000").rstrip("/")
    return f"{base}/platform/support" if kind == "staff" else f"{base}/support"


def _parse_day(value: str | None, *, end: bool = False) -> datetime | None:
    if value is None or not str(value).strip():
        return None
    raw = str(value).strip()[:10]
    try:
        day = datetime.strptime(raw, "%Y-%m-%d")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid date") from exc
    if end:
        return day + timedelta(days=1)
    return day


def _like(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _module_any(tenant: m.Tenant | None, modules: str | tuple[str, ...] | None) -> bool:
    if modules is None:
        return True
    if tenant is None:
        return False
    needed = (modules,) if isinstance(modules, str) else modules
    return any(packages_svc.module_allowed(tenant, mod) for mod in needed)


def _category_visible(
    tenant: m.Tenant | None,
    industry: str | None,
    code: str,
    modules: str | tuple[str, ...] | None,
) -> bool:
    """Ticket categories follow the industry desk, not a retail menu."""
    if modules is None:
        return True
    if code == "finance_reports":
        return _module_any(tenant, modules)
    if industry not in _OPERATING_INDUSTRIES:
        return False
    if code == "pos_sales":
        if industry in _POS_TICKET_INDUSTRIES:
            return _module_any(tenant, "pos")
        if industry in _SALES_DESK_INDUSTRIES:
            return _module_any(tenant, "sales")
        return False
    if industry == "hospital" and code in {"inventory_stock", "purchases_suppliers", "printing_barcode_receipt"}:
        return False
    if industry == "fmcg" and code == "printing_barcode_receipt":
        return False
    return _module_any(tenant, modules)


def categories_for(tenant: m.Tenant | None, *, all_categories: bool = False) -> list[dict[str, str]]:
    industry = packages_svc.canonicalize_industry(getattr(tenant, "industry", None)) if tenant is not None else None
    rows: list[dict[str, str]] = []
    for code, label, modules in CATEGORY_DEFS:
        if all_categories:
            rows.append({"code": code, "label": label})
            continue
        if not _category_visible(tenant, industry, code, modules):
            continue
        shown = "Sales" if code == "pos_sales" and industry in _SALES_DESK_INDUSTRIES else label
        rows.append({"code": code, "label": shown})
    return rows


def category_label_for(tenant: m.Tenant | None, code: str) -> str:
    for row in categories_for(tenant):
        if row["code"] == code:
            return row["label"]
    return CATEGORY_LABELS.get(code, code)


def public_email_status() -> dict[str, Any]:
    mode = emailer._delivery_mode()
    warning = None
    if mode == "disabled":
        warning = "Email is turned off. Messages stay queued until email is enabled."
    elif mode == "console":
        warning = "SMTP is not configured. Messages are handed to the console sink and stay queued if that handoff is not confirmed."
    return {"mode": mode, "configured": mode == "smtp", "warning": warning}


async def ensure_default_recipient(db: AsyncSession) -> None:
    count = await db.scalar(select(func.count()).select_from(m.SupportNotificationRecipient))
    if count:
        return
    try:
        async with db.begin_nested():
            db.add(m.SupportNotificationRecipient(email=DEFAULT_SUPPORT_EMAIL, is_active=True))
            await db.flush()
    except IntegrityError:
        return


async def _active_recipient_count(db: AsyncSession, *, excluding: str | None = None) -> int:
    stmt = select(func.count()).select_from(m.SupportNotificationRecipient).where(
        m.SupportNotificationRecipient.is_active == True  # noqa: E712
    )
    if excluding:
        stmt = stmt.where(m.SupportNotificationRecipient.id != excluding)
    return int(await db.scalar(stmt) or 0)


async def allocate_reference(db: AsyncSession, *, when: datetime | None = None) -> str:
    year = (when or datetime.utcnow()).year
    for _attempt in range(5):
        issued = await _bump_sequence(db, year)
        if issued is not None:
            return f"RIB-{year}-{int(issued):06d}"
        try:
            async with db.begin_nested():
                await db.execute(
                    text("INSERT INTO support_ticket_sequences (year, next_number) VALUES (:y, 0)"),
                    {"y": year},
                )
        except IntegrityError:
            continue
    raise HTTPException(status_code=500, detail="Could not allocate a ticket reference")


async def _bump_sequence(db: AsyncSession, year: int) -> int | None:
    result = await db.execute(
        text(
            "UPDATE support_ticket_sequences SET next_number = next_number + 1 "
            "WHERE year = :y RETURNING next_number"
        ),
        {"y": year},
    )
    return result.scalar_one_or_none()


async def _audit(
    db: AsyncSession,
    *,
    tenant_id: str,
    actor: dict,
    action: str,
    entity: str,
    entity_id: str,
    before: dict | None,
    after: dict | None,
    ticket_id: str | None = None,
) -> None:
    await audit.record_event(
        db,
        tenant_id=tenant_id,
        action=action,
        entity=entity,
        user_id=actor.get("user_id"),
        entity_id=entity_id,
        details={"before": before, "after": after},
        module="support",
        ip_address=actor.get("ip"),
        user_agent=actor.get("user_agent"),
    )
    if ticket_id:
        db.add(
            m.SupportTicketEvent(
                tenant_id=tenant_id,
                ticket_id=ticket_id,
                actor_user_id=actor.get("user_id"),
                action=action,
                before=before,
                after=after,
            )
        )


async def _user_map(db: AsyncSession, ids: set[str]) -> dict[str, m.User]:
    if not ids:
        return {}
    rows = (await db.execute(select(m.User).where(m.User.id.in_(ids)))).scalars().all()
    return {row.id: row for row in rows}


def _person(user: m.User | None) -> dict | None:
    if user is None:
        return None
    return {"id": user.id, "full_name": user.full_name, "role": user.role}


def tenant_brief(tenant: m.Tenant | None) -> dict | None:
    if tenant is None:
        return None
    return {
        "id": tenant.id,
        "company_name": tenant.company_name,
        "slug": tenant.slug,
        "industry": tenant.industry,
        "status": tenant.status,
        "email": tenant.email,
        "phone": tenant.phone,
    }


def _ticket_dict(
    ticket: m.SupportTicket,
    users: dict[str, m.User],
    *,
    desk: bool,
) -> dict:
    assignee = users.get(ticket.assignee_user_id or "")
    payload = {
        "id": ticket.id,
        "reference": ticket.reference,
        "tenant_id": ticket.tenant_id,
        "subject": ticket.subject,
        "description": ticket.description,
        "category": ticket.category,
        "category_label": CATEGORY_LABELS.get(ticket.category, ticket.category),
        "priority": ticket.priority,
        "status": ticket.status,
        "created_by": ticket.created_by,
        "creator": _person(users.get(ticket.created_by)),
        "assignee_user_id": ticket.assignee_user_id,
        "assignee": _person(assignee),
        "created_at": _iso(ticket.created_at),
        "updated_at": _iso(ticket.updated_at),
        "resolved_at": _iso(ticket.resolved_at),
        "closed_at": _iso(ticket.closed_at),
    }
    if desk and assignee is not None:
        payload["assignee_email"] = assignee.email
    return payload


def _message_dict(row: m.SupportTicketMessage, users: dict[str, m.User]) -> dict:
    return {
        "id": row.id,
        "visibility": row.visibility,
        "body": row.body,
        "created_at": _iso(row.created_at),
        "author": _person(users.get(row.author_user_id or "")),
    }


def _attachment_dict(row: m.SupportTicketAttachment) -> dict:
    return {
        "id": row.id,
        "ticket_id": row.ticket_id,
        "filename": row.filename,
        "content_type": row.content_type,
        "size_bytes": row.size_bytes,
        "created_at": _iso(row.created_at),
    }


def _event_dict(row: m.SupportTicketEvent, users: dict[str, m.User]) -> dict:
    return {
        "id": row.id,
        "action": row.action,
        "before": row.before,
        "after": row.after,
        "created_at": _iso(row.created_at),
        "actor": _person(users.get(row.actor_user_id or "")),
    }


async def ticket_detail(db: AsyncSession, ticket: m.SupportTicket, *, desk: bool, include_internal: bool) -> dict:
    messages = (
        await db.execute(
            select(m.SupportTicketMessage)
            .where(m.SupportTicketMessage.ticket_id == ticket.id)
            .order_by(m.SupportTicketMessage.created_at.asc())
        )
    ).scalars().all()
    if not include_internal:
        messages = [row for row in messages if row.visibility == "public"]
    attachments = (
        await db.execute(
            select(m.SupportTicketAttachment)
            .where(m.SupportTicketAttachment.ticket_id == ticket.id)
            .order_by(m.SupportTicketAttachment.created_at.asc())
        )
    ).scalars().all()
    events = (
        await db.execute(
            select(m.SupportTicketEvent)
            .where(m.SupportTicketEvent.ticket_id == ticket.id)
            .order_by(m.SupportTicketEvent.created_at.asc())
        )
    ).scalars().all()
    if not include_internal:
        events = [row for row in events if row.action != "support_ticket_internal_note"]
    ids = {ticket.created_by}
    if ticket.assignee_user_id:
        ids.add(ticket.assignee_user_id)
    ids.update(row.author_user_id for row in messages if row.author_user_id)
    ids.update(row.actor_user_id for row in events if row.actor_user_id)
    users = await _user_map(db, ids)
    payload = {
        "ticket": _ticket_dict(ticket, users, desk=desk),
        "messages": [_message_dict(row, users) for row in messages],
        "attachments": [_attachment_dict(row) for row in attachments],
        "events": [_event_dict(row, users) for row in events],
    }
    if desk:
        tenant = await db.get(m.Tenant, ticket.tenant_id)
        payload["tenant"] = tenant_brief(tenant)
        allowed = categories_for(tenant)
        payload["allowed_categories"] = allowed
        payload["ticket"]["category_label"] = category_label_for(tenant, ticket.category)
    return payload


async def require_ticket(db: AsyncSession, claims: dict, ticket_id: str) -> m.SupportTicket:
    ticket = await db.get(m.SupportTicket, (ticket_id or "").strip())
    if ticket is None or not can_see_ticket(claims, ticket):
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


async def require_ticket_by_reference(db: AsyncSession, claims: dict, reference: str) -> m.SupportTicket:
    ref = (reference or "").strip().upper()
    if not REF_RE.match(ref):
        raise HTTPException(status_code=404, detail="Ticket not found")
    ticket = (
        await db.execute(select(m.SupportTicket).where(m.SupportTicket.reference == ref))
    ).scalar_one_or_none()
    if ticket is None or not can_see_ticket(claims, ticket):
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


async def list_tickets(
    db: AsyncSession,
    claims: dict,
    *,
    desk: bool,
    status: str | None,
    priority: str | None,
    category: str | None,
    assignee: str | None,
    q: str | None,
    from_date: str | None,
    to_date: str | None,
    limit: int,
    offset: int,
    industry: str | None = None,
) -> dict:
    if status and status not in STATUSES:
        raise HTTPException(status_code=422, detail="Invalid status")
    if priority and priority not in PRIORITIES:
        raise HTTPException(status_code=422, detail="Invalid priority")
    if category and category not in CATEGORY_CODES:
        raise HTTPException(status_code=422, detail="Invalid category")
    industry_code = None
    if industry and str(industry).strip():
        if not desk:
            raise HTTPException(status_code=422, detail="Invalid industry")
        industry_code = packages_svc.canonicalize_industry(industry)
        if industry_code is None:
            raise HTTPException(status_code=422, detail="Invalid industry")
    filters = []
    joined = False
    if not desk:
        filters.append(m.SupportTicket.tenant_id == claims["tenant_id"])
        if not support_can(claims, "view_tenant"):
            filters.append(m.SupportTicket.created_by == claims["sub"])
    if status:
        filters.append(m.SupportTicket.status == status)
    if priority:
        filters.append(m.SupportTicket.priority == priority)
    if category:
        filters.append(m.SupportTicket.category == category)
    if assignee == "unassigned":
        filters.append(m.SupportTicket.assignee_user_id.is_(None))
    elif assignee:
        filters.append(m.SupportTicket.assignee_user_id == assignee.strip())
    start = _parse_day(from_date)
    end = _parse_day(to_date, end=True)
    if start:
        filters.append(m.SupportTicket.created_at >= start)
    if end:
        filters.append(m.SupportTicket.created_at < end)
    stmt = select(m.SupportTicket)
    count_stmt = select(func.count()).select_from(m.SupportTicket)
    if desk and (industry_code or (q and q.strip())):
        stmt = stmt.join(m.Tenant, m.Tenant.id == m.SupportTicket.tenant_id)
        count_stmt = count_stmt.join(m.Tenant, m.Tenant.id == m.SupportTicket.tenant_id)
        joined = True
    if industry_code:
        filters.append(func.lower(m.Tenant.industry) == industry_code)
    if desk and q and q.strip():
        like = _like(q.strip()[:120])
        filters.append(
            or_(
                m.SupportTicket.reference.ilike(like, escape="\\"),
                m.SupportTicket.subject.ilike(like, escape="\\"),
                m.Tenant.company_name.ilike(like, escape="\\"),
                m.Tenant.slug.ilike(like, escape="\\"),
            )
        )
    elif q and q.strip():
        like = _like(q.strip()[:120])
        filters.append(
            or_(
                m.SupportTicket.reference.ilike(like, escape="\\"),
                m.SupportTicket.subject.ilike(like, escape="\\"),
            )
        )
    if filters:
        stmt = stmt.where(*filters)
        count_stmt = count_stmt.where(*filters)
    total = int(await db.scalar(count_stmt) or 0)
    rows = (
        await db.execute(
            stmt.order_by(m.SupportTicket.created_at.desc()).limit(limit).offset(offset)
        )
    ).scalars().all()
    ids: set[str] = set()
    for row in rows:
        ids.add(row.created_by)
        if row.assignee_user_id:
            ids.add(row.assignee_user_id)
    users = await _user_map(db, ids)
    items = [_ticket_dict(row, users, desk=desk) for row in rows]
    if desk:
        tenant_ids = {row.tenant_id for row in rows}
        tenants = (
            await db.execute(select(m.Tenant).where(m.Tenant.id.in_(tenant_ids)))
        ).scalars().all() if tenant_ids else []
        briefs = {tenant.id: tenant_brief(tenant) for tenant in tenants}
        by_id = {tenant.id: tenant for tenant in tenants}
        for item in items:
            company = by_id.get(item["tenant_id"])
            item["tenant"] = briefs.get(item["tenant_id"])
            item["category_label"] = category_label_for(company, item["category"])
    _ = joined
    return {"items": items, "total": total, "limit": limit, "offset": offset}


async def desk_counts(db: AsyncSession) -> dict[str, int]:
    rows = (
        await db.execute(select(m.SupportTicket.status, func.count()).group_by(m.SupportTicket.status))
    ).all()
    by_status = {status: int(count) for status, count in rows}
    failed = await db.scalar(
        select(func.count()).select_from(m.SupportEmailOutbox).where(m.SupportEmailOutbox.status == "failed")
    )
    return {
        "new": by_status.get("new", 0),
        "in_progress": by_status.get("in_progress", 0),
        "waiting_for_tenant": by_status.get("waiting_for_tenant", 0),
        "resolved": by_status.get("resolved", 0),
        "failed_notifications": int(failed or 0),
    }


async def _queue_email(
    db: AsyncSession,
    *,
    tenant_id: str | None,
    ticket: m.SupportTicket | None,
    event_type: str,
    token: str,
    email: str,
    link_kind: str,
    summary: str,
) -> None:
    norm = normalize_email(email)
    digest = hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]
    ticket_id = ticket.id if ticket else "none"
    key = f"{event_type}:{ticket_id}:{token}:{digest}"
    reference = ticket.reference if ticket else "TEST"
    label = _EVENT_LABELS.get(event_type, "Support update")
    link = _link(link_kind)
    subject = f"[{reference}] {label}"[:200]
    body = (
        f"Reference: {reference}\n"
        f"Event: {event_type}\n"
        f"{summary}\n\n"
        f"Sign in: {link}\n\n"
        "This message does not include attachments. Sign in to view the ticket."
    )
    existing = (
        await db.execute(select(m.SupportEmailOutbox.id).where(m.SupportEmailOutbox.idempotency_key == key))
    ).scalar_one_or_none()
    if existing:
        return
    row = m.SupportEmailOutbox(
        tenant_id=tenant_id,
        ticket_id=ticket.id if ticket else None,
        idempotency_key=key,
        event_type=event_type,
        recipient_email=norm,
        subject=subject,
        body_text=body,
        link_url=link,
        status="pending",
        attempts=0,
    )
    try:
        async with db.begin_nested():
            db.add(row)
            await db.flush()
    except IntegrityError:
        return


async def _support_recipients(db: AsyncSession) -> list[str]:
    await ensure_default_recipient(db)
    rows = (
        await db.execute(
            select(m.SupportNotificationRecipient.email).where(
                m.SupportNotificationRecipient.is_active == True  # noqa: E712
            )
        )
    ).scalars().all()
    return list(rows)


async def _tenant_emails(db: AsyncSession, ticket: m.SupportTicket) -> list[str]:
    emails: list[str] = []
    creator = await db.get(m.User, ticket.created_by)
    if creator and creator.is_active and creator.email:
        emails.append(creator.email)
    admins = (
        await db.execute(
            select(m.User).where(
                m.User.tenant_id == ticket.tenant_id,
                m.User.role == "company_admin",
                m.User.is_active == True,  # noqa: E712
            )
        )
    ).scalars().all()
    emails.extend(admin.email for admin in admins if admin.email)
    return emails


async def _assignee_email(db: AsyncSession, ticket: m.SupportTicket) -> str | None:
    if not ticket.assignee_user_id:
        return None
    user = await db.get(m.User, ticket.assignee_user_id)
    if user and user.is_active and user.email:
        return user.email
    return None


async def _notify(
    db: AsyncSession,
    ticket: m.SupportTicket,
    event_type: str,
    *,
    token: str,
    summary: str,
    audience: str,
) -> None:
    """audience: support | tenant | tenant_and_assignee."""
    pairs: list[tuple[str, str]] = []
    if audience == "support":
        for email in await _support_recipients(db):
            pairs.append((email, "staff"))
        if event_type in {"assigned", "status_needs_action"}:
            assignee = await _assignee_email(db, ticket)
            if assignee:
                pairs.append((assignee, "staff"))
    else:
        for email in await _tenant_emails(db, ticket):
            pairs.append((email, "tenant"))
        if audience == "tenant_and_assignee":
            assignee = await _assignee_email(db, ticket)
            if assignee:
                pairs.append((assignee, "staff"))
    seen: set[str] = set()
    for email, kind in pairs:
        try:
            norm = normalize_email(email)
        except HTTPException:
            continue
        if norm in seen:
            continue
        seen.add(norm)
        await _queue_email(
            db,
            tenant_id=ticket.tenant_id,
            ticket=ticket,
            event_type=event_type,
            token=token,
            email=norm,
            link_kind=kind,
            summary=summary,
        )


async def create_ticket(
    db: AsyncSession,
    claims: dict,
    actor: dict,
    *,
    subject: str,
    description: str,
    category: str,
    priority: str,
) -> m.SupportTicket:
    tenant = await db.get(m.Tenant, claims["tenant_id"])
    if tenant is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    allowed = {row["code"] for row in categories_for(tenant)}
    if category not in allowed:
        raise HTTPException(status_code=422, detail="That category is not available for this company")
    if priority not in PRIORITIES:
        raise HTTPException(status_code=422, detail="Invalid priority")
    subject_text = clean_text(subject, min_len=2, max_len=200, label="Subject", allow_newlines=False)
    description_text = clean_text(description, min_len=2, max_len=8000, label="Description")
    now = datetime.utcnow()
    reference = await allocate_reference(db, when=now)
    ticket = m.SupportTicket(
        reference=reference,
        tenant_id=claims["tenant_id"],
        created_by=claims["sub"],
        subject=subject_text,
        description=description_text,
        category=category,
        priority=priority,
        status="new",
        created_at=now,
        updated_at=now,
    )
    db.add(ticket)
    await db.flush()
    await _audit(
        db,
        tenant_id=ticket.tenant_id,
        actor=actor,
        action="support_ticket_created",
        entity="support_ticket",
        entity_id=ticket.id,
        before=None,
        after={
            "reference": ticket.reference,
            "subject": ticket.subject,
            "category": ticket.category,
            "priority": ticket.priority,
            "status": ticket.status,
        },
        ticket_id=ticket.id,
    )
    await _notify(
        db,
        ticket,
        "tenant_created",
        token=ticket.id,
        summary=_summary(ticket.subject),
        audience="support",
    )
    return ticket


async def add_public_reply(
    db: AsyncSession,
    claims: dict,
    actor: dict,
    ticket: m.SupportTicket,
    body: str,
    *,
    from_staff: bool,
) -> m.SupportTicketMessage:
    if not from_staff and ticket.tenant_id != claims.get("tenant_id"):
        raise HTTPException(status_code=404, detail="Ticket not found")
    if not can_see_ticket(claims, ticket) or not support_can(claims, "reply"):
        raise HTTPException(status_code=403, detail="Missing permission: support:reply")
    text_body = clean_text(body, min_len=1, max_len=8000, label="Reply")
    reopened = False
    if not from_staff:
        if ticket.status == "closed":
            raise HTTPException(
                status_code=409,
                detail={"code": "INVALID_STATUS_TRANSITION", "message": "A closed ticket cannot be reopened by a reply"},
            )
        if ticket.status == "resolved":
            await apply_status(
                db,
                actor,
                ticket,
                "in_progress",
                action="support_ticket_reopened",
                notify=None,
            )
            reopened = True
    now = datetime.utcnow()
    message = m.SupportTicketMessage(
        tenant_id=ticket.tenant_id,
        ticket_id=ticket.id,
        author_user_id=claims["sub"],
        visibility="public",
        body=text_body,
        created_at=now,
    )
    db.add(message)
    ticket.updated_at = now
    await db.flush()
    preview = _summary(text_body)[:80]
    await _audit(
        db,
        tenant_id=ticket.tenant_id,
        actor=actor,
        action="support_ticket_replied",
        entity="support_ticket",
        entity_id=ticket.id,
        before=None,
        after={"visibility": "public", "length": len(text_body), "preview": preview},
        ticket_id=ticket.id,
    )
    if not from_staff:
        await _notify(
            db,
            ticket,
            "tenant_reopened" if reopened else "tenant_replied",
            token=message.id,
            summary=_summary(ticket.subject, preview),
            audience="support",
        )
    else:
        await _notify(
            db,
            ticket,
            "public_reply",
            token=message.id,
            summary=_summary(ticket.subject, preview),
            audience="tenant_and_assignee",
        )
    return message


async def add_internal_note(
    db: AsyncSession,
    claims: dict,
    actor: dict,
    ticket: m.SupportTicket,
    body: str,
) -> m.SupportTicketMessage:
    if not support_can(claims, "internal_note"):
        raise HTTPException(status_code=403, detail="Missing permission: support:internal_note")
    text_body = clean_text(body, min_len=1, max_len=8000, label="Internal note")
    now = datetime.utcnow()
    message = m.SupportTicketMessage(
        tenant_id=ticket.tenant_id,
        ticket_id=ticket.id,
        author_user_id=claims["sub"],
        visibility="internal",
        body=text_body,
        created_at=now,
    )
    db.add(message)
    ticket.updated_at = now
    await db.flush()
    await _audit(
        db,
        tenant_id=ticket.tenant_id,
        actor=actor,
        action="support_ticket_internal_note",
        entity="support_ticket",
        entity_id=ticket.id,
        before=None,
        after={"visibility": "internal", "length": len(text_body)},
        ticket_id=ticket.id,
    )
    return message


async def apply_status(
    db: AsyncSession,
    actor: dict,
    ticket: m.SupportTicket,
    target: str,
    *,
    action: str | None = None,
    notify: str | None = "auto",
) -> bool:
    if target not in STATUSES:
        raise HTTPException(status_code=422, detail="Invalid status")
    if target == ticket.status:
        return False
    allowed = TRANSITIONS.get(ticket.status, set())
    if target not in allowed:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "INVALID_STATUS_TRANSITION",
                "message": f"Cannot change status from {ticket.status} to {target}",
            },
        )
    before = ticket.status
    now = datetime.utcnow()
    ticket.status = target
    ticket.updated_at = now
    if target == "resolved":
        ticket.resolved_at = now
        ticket.resolved_by = actor.get("user_id")
    elif target == "closed":
        ticket.closed_at = now
        ticket.closed_by = actor.get("user_id")
        if ticket.resolved_at is None:
            ticket.resolved_at = now
            ticket.resolved_by = actor.get("user_id")
    elif target == "in_progress" and before in {"resolved", "closed"}:
        ticket.resolved_at = None
        ticket.resolved_by = None
        ticket.closed_at = None
        ticket.closed_by = None
    if action:
        chosen = action
    elif target == "resolved":
        chosen = "support_ticket_resolved"
    elif target == "closed":
        chosen = "support_ticket_closed"
    elif before in {"resolved", "closed"} and target == "in_progress":
        chosen = "support_ticket_reopened"
    else:
        chosen = "support_ticket_status_changed"
    await _audit(
        db,
        tenant_id=ticket.tenant_id,
        actor=actor,
        action=chosen,
        entity="support_ticket",
        entity_id=ticket.id,
        before={"status": before},
        after={"status": target},
        ticket_id=ticket.id,
    )
    if notify == "auto":
        if target == "in_progress":
            notify = "support"
        elif target in {"waiting_for_tenant", "resolved", "closed"}:
            notify = "tenant"
        else:
            notify = None
    if notify == "support":
        await _notify(
            db,
            ticket,
            "status_needs_action",
            token=f"{ticket.id}:{target}:{now.isoformat()}",
            summary=_summary(ticket.subject, target),
            audience="support",
        )
    elif notify == "tenant":
        await _notify(
            db,
            ticket,
            "tenant_status",
            token=f"{ticket.id}:{target}:{now.isoformat()}",
            summary=_summary(ticket.subject, target.replace("_", " ")),
            audience="tenant",
        )
    return True


async def update_ticket(
    db: AsyncSession,
    actor: dict,
    ticket: m.SupportTicket,
    *,
    status: str | None,
    priority: str | None,
    category: str | None,
    assignee_user_id: str | None,
    assignee_set: bool,
) -> m.SupportTicket:
    if category is not None and category != ticket.category:
        tenant = await db.get(m.Tenant, ticket.tenant_id)
        allowed = {row["code"] for row in categories_for(tenant)}
        if category not in allowed:
            raise HTTPException(status_code=422, detail="That category is not available for this company")
    if priority is not None and priority not in PRIORITIES:
        raise HTTPException(status_code=422, detail="Invalid priority")
    if category is not None and category != ticket.category:
        before = ticket.category
        ticket.category = category
        ticket.updated_at = datetime.utcnow()
        await _audit(
            db,
            tenant_id=ticket.tenant_id,
            actor=actor,
            action="support_ticket_category_changed",
            entity="support_ticket",
            entity_id=ticket.id,
            before={"category": before},
            after={"category": category},
            ticket_id=ticket.id,
        )
    if priority is not None and priority != ticket.priority:
        before = ticket.priority
        ticket.priority = priority
        ticket.updated_at = datetime.utcnow()
        await _audit(
            db,
            tenant_id=ticket.tenant_id,
            actor=actor,
            action="support_ticket_priority_changed",
            entity="support_ticket",
            entity_id=ticket.id,
            before={"priority": before},
            after={"priority": priority},
            ticket_id=ticket.id,
        )
    if assignee_set:
        new_id = None
        if assignee_user_id:
            try:
                new_id = str(uuid.UUID(str(assignee_user_id).strip()))
            except ValueError as exc:
                raise HTTPException(status_code=422, detail="Invalid assignee") from exc
            user = await db.get(m.User, new_id)
            if user is None or not user.is_active or not is_platform_role(user.role):
                raise HTTPException(status_code=422, detail="Assignee must be an active software-owner user")
        if new_id != ticket.assignee_user_id:
            before = ticket.assignee_user_id
            ticket.assignee_user_id = new_id
            ticket.assigned_at = datetime.utcnow() if new_id else None
            ticket.updated_at = datetime.utcnow()
            await _audit(
                db,
                tenant_id=ticket.tenant_id,
                actor=actor,
                action="support_ticket_assigned",
                entity="support_ticket",
                entity_id=ticket.id,
                before={"assignee_user_id": before},
                after={"assignee_user_id": new_id},
                ticket_id=ticket.id,
            )
            if new_id:
                await _notify(
                    db,
                    ticket,
                    "assigned",
                    token=f"{ticket.id}:{new_id}:{ticket.assigned_at.isoformat() if ticket.assigned_at else ''}",
                    summary=_summary(ticket.subject, "assigned"),
                    audience="support",
                )
    if status is not None:
        await apply_status(db, actor, ticket, status)
    return ticket


def sniff_upload(filename: str, data: bytes) -> str:
    if not data:
        raise HTTPException(status_code=422, detail="The file is empty")
    max_bytes = int(settings.SUPPORT_ATTACHMENT_MAX_BYTES or 10_000_000)
    if len(data) > max_bytes:
        raise HTTPException(status_code=422, detail="File is too large")
    safe_name = storage_svc.sanitize_filename(filename)
    parts = [part for part in safe_name.lower().split(".") if part]
    if len(parts) < 2:
        raise HTTPException(status_code=422, detail="This file type is not allowed")
    if any(part in _BLOCKED_EXT for part in parts[1:]):
        raise HTTPException(status_code=422, detail="This file type is not allowed")
    if data.startswith(b"MZ") or data.startswith(b"\x7fELF"):
        raise HTTPException(status_code=422, detail="This file type is not allowed")
    ext = parts[-1]
    if ext == "png" and data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if ext in {"jpg", "jpeg"} and data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if ext == "pdf" and data.startswith(b"%PDF-"):
        return "application/pdf"
    if ext == "txt" and _is_plain_text(data):
        return "text/plain"
    raise HTTPException(
        status_code=422,
        detail="File content does not match an allowed type (PNG, JPG, PDF, TXT)",
    )


def _is_plain_text(data: bytes) -> bool:
    if b"\x00" in data:
        return False
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


async def save_attachment(
    db: AsyncSession,
    actor: dict,
    ticket: m.SupportTicket,
    *,
    filename: str,
    data: bytes,
) -> m.SupportTicketAttachment:
    content_type = sniff_upload(filename, data)
    safe_name = storage_svc.sanitize_filename(filename)
    key = storage_svc.build_key(ticket.tenant_id, "support", content_type, safe_name)
    storage_svc._put_bytes(key, data, content_type)
    row = m.SupportTicketAttachment(
        tenant_id=ticket.tenant_id,
        ticket_id=ticket.id,
        storage_key=key,
        filename=safe_name,
        content_type=content_type,
        size_bytes=len(data),
        uploaded_by=actor.get("user_id"),
    )
    db.add(row)
    ticket.updated_at = datetime.utcnow()
    await db.flush()
    await _audit(
        db,
        tenant_id=ticket.tenant_id,
        actor=actor,
        action="support_ticket_attachment",
        entity="support_ticket",
        entity_id=ticket.id,
        before=None,
        after={"filename": safe_name, "content_type": content_type, "size_bytes": len(data)},
        ticket_id=ticket.id,
    )
    return row


async def read_attachment(
    db: AsyncSession, ticket: m.SupportTicket, attachment_id: str
) -> tuple[bytes, str, str]:
    row = await db.get(m.SupportTicketAttachment, (attachment_id or "").strip())
    if row is None or row.ticket_id != ticket.id or row.tenant_id != ticket.tenant_id:
        raise HTTPException(status_code=404, detail="Attachment not found")
    try:
        obj = storage_svc.read_object(row.storage_key, tenant_id=row.tenant_id)
    except HTTPException as exc:
        raise HTTPException(status_code=404, detail="Attachment not found") from exc
    return obj.data, row.content_type, row.filename


async def list_staff(db: AsyncSession) -> list[dict]:
    rows = (
        await db.execute(
            select(m.User)
            .where(m.User.is_active == True, m.User.role.in_(tuple(PLATFORM_ROLES)))  # noqa: E712
            .order_by(m.User.full_name.asc())
        )
    ).scalars().all()
    return [{"id": row.id, "full_name": row.full_name, "email": row.email, "role": row.role} for row in rows]


def _recipient_dict(row: m.SupportNotificationRecipient, latest: dict | None) -> dict:
    return {
        "id": row.id,
        "email": row.email,
        "is_active": bool(row.is_active),
        "last_test_status": row.last_test_status,
        "last_test_at": _iso(row.last_test_at),
        "last_test_error": row.last_test_error,
        "latest_delivery": latest,
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
    }


async def _latest_delivery_map(db: AsyncSession, emails: list[str]) -> dict[str, dict]:
    if not emails:
        return {}
    rows = (
        await db.execute(
            select(m.SupportEmailOutbox)
            .where(m.SupportEmailOutbox.recipient_email.in_(emails))
            .order_by(m.SupportEmailOutbox.created_at.desc())
        )
    ).scalars().all()
    found: dict[str, dict] = {}
    for row in rows:
        if row.recipient_email in found:
            continue
        found[row.recipient_email] = {
            "id": row.id,
            "status": row.status,
            "event_type": row.event_type,
            "updated_at": _iso(row.updated_at),
            "last_error": row.last_error,
        }
    return found


async def list_recipients(db: AsyncSession) -> dict:
    await ensure_default_recipient(db)
    rows = (
        await db.execute(
            select(m.SupportNotificationRecipient).order_by(m.SupportNotificationRecipient.email.asc())
        )
    ).scalars().all()
    latest = await _latest_delivery_map(db, [row.email for row in rows])
    return {
        "recipients": [_recipient_dict(row, latest.get(row.email)) for row in rows],
        "email": public_email_status(),
    }


async def _require_other_active(db: AsyncSession, row: m.SupportNotificationRecipient) -> None:
    if not row.is_active:
        return
    others = await _active_recipient_count(db, excluding=row.id)
    if others < 1:
        raise HTTPException(status_code=422, detail="At least one support recipient must stay active")


async def add_recipient(db: AsyncSession, actor: dict, email: str) -> m.SupportNotificationRecipient:
    await ensure_default_recipient(db)
    norm = normalize_email(email)
    existing = (
        await db.execute(
            select(m.SupportNotificationRecipient).where(m.SupportNotificationRecipient.email == norm)
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=422, detail="That email is already a support recipient")
    row = m.SupportNotificationRecipient(
        email=norm,
        is_active=True,
        created_by=actor.get("user_id"),
        updated_by=actor.get("user_id"),
    )
    db.add(row)
    await db.flush()
    await _audit(
        db,
        tenant_id=actor["tenant_id"],
        actor=actor,
        action="support_recipient_created",
        entity="support_recipient",
        entity_id=row.id,
        before=None,
        after={"email": norm, "is_active": True},
    )
    return row


async def update_recipient(
    db: AsyncSession,
    actor: dict,
    recipient_id: str,
    *,
    email: str | None,
    is_active: bool | None,
) -> m.SupportNotificationRecipient:
    row = await db.get(m.SupportNotificationRecipient, recipient_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Recipient not found")
    before = {"email": row.email, "is_active": bool(row.is_active)}
    if email is not None:
        norm = normalize_email(email)
        if norm != row.email:
            taken = (
                await db.execute(
                    select(m.SupportNotificationRecipient.id).where(
                        m.SupportNotificationRecipient.email == norm,
                        m.SupportNotificationRecipient.id != row.id,
                    )
                )
            ).scalar_one_or_none()
            if taken:
                raise HTTPException(status_code=422, detail="That email is already a support recipient")
            row.email = norm
    if is_active is False and row.is_active:
        await _require_other_active(db, row)
        row.is_active = False
    elif is_active is True:
        row.is_active = True
    row.updated_by = actor.get("user_id")
    row.updated_at = datetime.utcnow()
    await db.flush()
    await _audit(
        db,
        tenant_id=actor["tenant_id"],
        actor=actor,
        action="support_recipient_updated",
        entity="support_recipient",
        entity_id=row.id,
        before=before,
        after={"email": row.email, "is_active": bool(row.is_active)},
    )
    return row


async def remove_recipient(db: AsyncSession, actor: dict, recipient_id: str) -> None:
    row = await db.get(m.SupportNotificationRecipient, recipient_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Recipient not found")
    await _require_other_active(db, row)
    before = {"email": row.email, "is_active": bool(row.is_active)}
    await db.delete(row)
    await db.flush()
    await _audit(
        db,
        tenant_id=actor["tenant_id"],
        actor=actor,
        action="support_recipient_removed",
        entity="support_recipient",
        entity_id=recipient_id,
        before=before,
        after=None,
    )


async def send_recipient_test(db: AsyncSession, actor: dict, recipient_id: str) -> dict:
    row = await db.get(m.SupportNotificationRecipient, recipient_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Recipient not found")
    if not row.is_active:
        raise HTTPException(status_code=422, detail="Activate the recipient before sending a test")
    token = str(uuid.uuid4())
    await _queue_email(
        db,
        tenant_id=actor.get("tenant_id"),
        ticket=None,
        event_type="test_email",
        token=token,
        email=row.email,
        link_kind="staff",
        summary="This is a test of support ticket notifications.",
    )
    await db.flush()
    outbox = (
        await db.execute(
            select(m.SupportEmailOutbox)
            .where(m.SupportEmailOutbox.event_type == "test_email")
            .where(m.SupportEmailOutbox.recipient_email == row.email)
            .order_by(m.SupportEmailOutbox.created_at.desc())
        )
    ).scalars().first()
    if outbox is None:
        raise HTTPException(status_code=500, detail="Could not queue the test email")
    await _deliver_one(db, outbox.id)
    await db.refresh(outbox)
    row.last_test_status = outbox.status
    row.last_test_at = datetime.utcnow()
    row.last_test_error = outbox.last_error
    row.updated_at = row.last_test_at
    await _audit(
        db,
        tenant_id=actor["tenant_id"],
        actor=actor,
        action="support_test_email",
        entity="support_recipient",
        entity_id=row.id,
        before=None,
        after={"email": row.email, "status": outbox.status},
    )
    warning = public_email_status().get("warning")
    if outbox.status != "sent" and not warning:
        warning = outbox.last_error or "The test email was not confirmed. It stays queued for retry."
    return {
        "recipient": _recipient_dict(
            row,
            {
                "id": outbox.id,
                "status": outbox.status,
                "event_type": outbox.event_type,
                "updated_at": _iso(outbox.updated_at),
                "last_error": outbox.last_error,
            },
        ),
        "delivery": _outbox_dict(outbox),
        "warning": warning,
    }


def _outbox_dict(row: m.SupportEmailOutbox) -> dict:
    return {
        "id": row.id,
        "ticket_id": row.ticket_id,
        "event_type": row.event_type,
        "recipient_email": row.recipient_email,
        "subject": row.subject,
        "status": row.status,
        "attempts": row.attempts,
        "last_error": row.last_error,
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
        "sent_at": _iso(row.sent_at),
        "failed_at": _iso(row.failed_at),
    }


async def list_deliveries(db: AsyncSession, *, status: str | None, limit: int, offset: int) -> dict:
    filters = []
    if status in {None, "", "actionable"}:
        filters.append(m.SupportEmailOutbox.status.in_(("pending", "failed", "sending")))
    elif status != "all":
        if status not in {"pending", "sending", "sent", "failed"}:
            raise HTTPException(status_code=422, detail="Invalid delivery status")
        filters.append(m.SupportEmailOutbox.status == status)
    stmt = select(m.SupportEmailOutbox)
    count_stmt = select(func.count()).select_from(m.SupportEmailOutbox)
    if filters:
        stmt = stmt.where(*filters)
        count_stmt = count_stmt.where(*filters)
    total = int(await db.scalar(count_stmt) or 0)
    rows = (
        await db.execute(
            stmt.order_by(m.SupportEmailOutbox.created_at.desc()).limit(limit).offset(offset)
        )
    ).scalars().all()
    return {
        "items": [_outbox_dict(row) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
        "email": public_email_status(),
    }


async def retry_delivery(db: AsyncSession, actor: dict, outbox_id: str) -> dict:
    row = await db.get(m.SupportEmailOutbox, outbox_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Delivery not found")
    before = row.status
    if row.status == "sent":
        return {"delivery": _outbox_dict(row), "resent": False}
    row.status = "pending"
    row.last_error = None
    row.updated_at = datetime.utcnow()
    await db.flush()
    await _deliver_one(db, row.id)
    await db.refresh(row)
    await _audit(
        db,
        tenant_id=row.tenant_id or actor["tenant_id"],
        actor=actor,
        action="support_email_retried",
        entity="support_email",
        entity_id=row.id,
        before={"status": before},
        after={"status": row.status},
        ticket_id=row.ticket_id,
    )
    return {"delivery": _outbox_dict(row), "resent": row.status == "sent"}


async def _deliver_one(db: AsyncSession, outbox_id: str) -> str:
    now = datetime.utcnow()
    claimed = (
        await db.execute(
            text(
                "UPDATE support_email_outbox "
                "SET status = 'sending', attempts = attempts + 1, updated_at = :now "
                "WHERE id = :id AND status IN ('pending', 'failed') "
                "RETURNING id"
            ),
            {"id": outbox_id, "now": now},
        )
    ).scalar_one_or_none()
    if not claimed:
        return "skipped"
    row = await db.get(m.SupportEmailOutbox, outbox_id)
    if row is None:
        return "skipped"
    db.expire(row)
    await db.refresh(row)
    inner = html.escape(row.body_text).replace("\n", "<br>")
    html_body = None
    try:
        html_body = emailer.render_branded_html(
            body_html=f"<p>{inner}</p>",
            company_name="Ribdigi House",
            title=row.subject,
            allow_platform_logo=True,
        )
    except Exception:
        logger.warning("support email branding skipped", exc_info=True)
        html_body = None
    try:
        result = await emailer.send_email(
            to=row.recipient_email,
            subject=row.subject,
            text_body=row.body_text,
            html_body=html_body,
        )
    except Exception as exc:
        result = emailer.EmailResult(
            sent=False,
            mode="error",
            error=safe_error(exc),
            recipients=[row.recipient_email],
        )
    finished = datetime.utcnow()
    if result.sent:
        row.status = "sent"
        row.sent_at = finished
        row.failed_at = None
        row.last_error = None
    else:
        row.status = "failed"
        row.failed_at = finished
        row.last_error = safe_error(result.error or "Email delivery was not confirmed")
    row.updated_at = finished
    await db.flush()
    return row.status


async def deliver_pending_support_emails(db: AsyncSession, *, limit: int = 50) -> dict[str, int]:
    now = datetime.utcnow()
    pending_ids = (
        await db.execute(
            select(m.SupportEmailOutbox.id)
            .where(m.SupportEmailOutbox.status == "pending")
            .order_by(m.SupportEmailOutbox.created_at.asc())
            .limit(limit)
        )
    ).scalars().all()
    failed_rows = (
        await db.execute(
            select(m.SupportEmailOutbox)
            .where(m.SupportEmailOutbox.status == "failed", m.SupportEmailOutbox.attempts < 5)
            .order_by(m.SupportEmailOutbox.failed_at.asc())
            .limit(limit)
        )
    ).scalars().all()
    due_failed: list[str] = []
    for row in failed_rows:
        wait = max(1, int(row.attempts or 1)) * 60
        if row.failed_at is None or (now - row.failed_at).total_seconds() >= wait:
            due_failed.append(row.id)
    ids: list[str] = []
    for oid in [*pending_ids, *due_failed]:
        if oid not in ids:
            ids.append(oid)
        if len(ids) >= limit:
            break
    sent = failed = skipped = 0
    for oid in ids:
        outcome = await _deliver_one(db, oid)
        if outcome == "sent":
            sent += 1
        elif outcome == "failed":
            failed += 1
        else:
            skipped += 1
    return {"sent": sent, "failed": failed, "skipped": skipped}


async def deliver_outbox_job() -> dict[str, int]:
    from app.db import SessionLocal

    async with SessionLocal() as db:
        result = await deliver_pending_support_emails(db)
        await db.commit()
        return result


def enqueue_support_delivery() -> None:
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return
    if not settings.CELERY_ENABLED or settings.CELERY_TASK_ALWAYS_EAGER:
        return

    def _go() -> None:
        try:
            from app.tasks import deliver_support_outbox

            deliver_support_outbox.apply_async(ignore_result=True)
        except Exception:
            logger.warning("support outbox enqueue skipped", exc_info=True)

    import threading

    threading.Thread(target=_go, daemon=True, name="support-outbox-enqueue").start()
