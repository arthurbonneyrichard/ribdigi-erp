"""Email center routes for the software owner console."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints
from sqlalchemy.ext.asyncio import AsyncSession

from app import platform_email as svc
from app.db import get_db
from app.packages import VALID_PACKAGE_CODES
from app.rbac import is_platform_owner_role
from app.schemas import UuidIdValue
from app.security import require_platform_permission
from app.email_design import EmailDesignPreview as EmailDesignPreviewBody
from app.email_design import EmailDesignUpdate as EmailDesignUpdateBody
from app.tenants import VALID_INDUSTRIES, VALID_STATUSES

router = APIRouter(prefix="/platform/email", tags=["platform"])

StatusValue = Literal["trial", "active", "grace", "suspended"]
IndustryValue = Literal["retail", "wholesale", "hotel", "restaurant", "fmcg", "bakery", "gym", "hrm", "pharmacy", "mart"]
PackageValue = Literal["trial", "starter", "professional", "enterprise"]
SubjectValue = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=200)]
BodyValue = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=20000)]

assert set(StatusValue.__args__) == set(VALID_STATUSES)
assert set(PackageValue.__args__) == set(VALID_PACKAGE_CODES)
assert set(VALID_INDUSTRIES) <= set(IndustryValue.__args__)


class AudienceBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    statuses: list[StatusValue] = Field(default_factory=list)
    industries: list[IndustryValue] = Field(default_factory=list)
    packages: list[PackageValue] = Field(default_factory=list)
    tenant_ids: list[UuidIdValue] = Field(default_factory=list, max_length=svc.MAX_RECIPIENTS)
    include_company_email: bool = False


class MessageBody(AudienceBody):
    subject: SubjectValue
    body: BodyValue


class SendBody(MessageBody):
    confirm: bool = False


class RenderBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject: SubjectValue
    body: BodyValue
    company_name: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] | None = None


class RetryBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirm: bool = False


class TestBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject: SubjectValue
    body: BodyValue
    to: EmailStr | None = None


def env(data=None, message: str = "Operation completed successfully"):
    return {"success": True, "data": data, "message": message}


def _sender(claims: dict) -> dict:
    """Owner and platform admins only: a bulk email speaks for Ribdigi House."""
    role = claims.get("role") or ""
    if not (is_platform_owner_role(role) or role == "platform_admin"):
        raise HTTPException(status_code=403, detail="Only the software owner or a platform admin can send bulk email")
    return claims


async def _my_email(db, claims: dict) -> str | None:
    from app import models as m

    user = await db.get(m.User, str(claims.get("sub") or ""))
    return (user.email or "").strip() or None if user else None


def _actor(request: Request, claims: dict, email: str | None) -> dict:
    return {
        "user_id": claims.get("sub"),
        "tenant_id": claims.get("tenant_id"),
        "email": email,
        "ip": request.client.host if request.client else None,
        "user_agent": (request.headers.get("user-agent") or "")[:255],
    }


async def _recipients(db, body: AudienceBody, claims: dict):
    return await svc.audience(
        db,
        statuses=list(body.statuses),
        industries=list(body.industries),
        packages=list(body.packages),
        include_company_email=body.include_company_email,
        exclude_tenant_id=claims.get("tenant_id"),
        tenant_ids=list(body.tenant_ids),
    )


def _filters(body: AudienceBody) -> dict:
    return {
        "statuses": list(body.statuses),
        "industries": list(body.industries),
        "packages": list(body.packages),
        "tenant_ids": list(body.tenant_ids),
        "include_company_email": body.include_company_email,
    }


@router.get("/status")
async def email_center_status(claims=Depends(require_platform_permission("platform", "read"))):
    _sender(claims)
    from app.email_settings import resolve_smtp_config

    mode = svc.mail_mode()
    cfg = resolve_smtp_config(None)
    return env(
        {
            "mode": mode,
            "ready": mode == "smtp",
            "max_recipients": svc.MAX_RECIPIENTS,
            "from_name": cfg.from_name,
            "from_email": cfg.from_email,
        }
    )


@router.get("/companies")
async def email_center_companies(
    claims=Depends(require_platform_permission("platform", "read")),
    db: AsyncSession = Depends(get_db),
):
    _sender(claims)
    return env(await svc.companies(db, exclude_tenant_id=claims.get("tenant_id")))


@router.post("/render")
async def email_center_render(
    payload: RenderBody,
    claims=Depends(require_platform_permission("platform", "read")),
):
    """The message exactly as a company will see it, for the preview pane."""
    _sender(claims)
    from app import emailer
    from app.email_design import refresh_platform_style

    await refresh_platform_style()
    subject, text, html_body = svc.render(payload.subject, payload.body, payload.company_name or "Example Company")
    return env({"subject": subject, "text": text, "html": emailer.inline_preview(html_body)})


@router.post("/preview")
async def email_center_preview(
    payload: AudienceBody,
    claims=Depends(require_platform_permission("platform", "read")),
    db: AsyncSession = Depends(get_db),
):
    _sender(claims)
    return env(svc.summarize(await _recipients(db, payload, claims)))


@router.post("/test")
async def email_center_test(
    payload: TestBody,
    claims=Depends(require_platform_permission("platform", "write")),
    db: AsyncSession = Depends(get_db),
):
    _sender(claims)
    svc.require_mail_ready()
    to = str(payload.to or await _my_email(db, claims) or "").strip()
    if not to:
        raise HTTPException(status_code=422, detail="Enter an address for the test email")
    ok, reason = await svc.send_one(to, f"[Test] {payload.subject}", payload.body, "Example Company")
    if not ok:
        raise HTTPException(status_code=502, detail=f"The test email was not sent: {reason or 'unknown reason'}")
    return env({"to": to}, f"Test email sent to {to}")


@router.post("/send")
async def email_center_send(
    payload: SendBody,
    request: Request,
    background: BackgroundTasks,
    claims=Depends(require_platform_permission("platform", "write")),
    db: AsyncSession = Depends(get_db),
):
    _sender(claims)
    if not payload.confirm:
        raise HTTPException(status_code=422, detail="Confirm the send before it goes out")
    svc.require_mail_ready()
    recipients = await _recipients(db, payload, claims)
    summary = svc.summarize(recipients)
    if not recipients:
        raise HTTPException(status_code=422, detail="No companies match these filters")
    if summary["too_many"]:
        raise HTTPException(
            status_code=422,
            detail=f"That is {len(recipients)} people; one send can reach at most {svc.MAX_RECIPIENTS}. Narrow the filters.",
        )
    actor = _actor(request, claims, await _my_email(db, claims))
    send_id = await svc.record_start(
        db, actor=actor, subject=payload.subject, body=payload.body, filters=_filters(payload), summary=summary
    )
    await db.commit()
    background.add_task(
        svc.deliver, send_id=send_id, actor=actor, subject=payload.subject, body=payload.body, recipients=recipients
    )
    return env(
        {"id": send_id, **summary},
        f"Sending to {summary['recipient_count']} people at {summary['company_count']} companies",
    )


@router.get("/history")
async def email_center_history(
    claims=Depends(require_platform_permission("platform", "read")),
    db: AsyncSession = Depends(get_db),
):
    _sender(claims)
    return env(await svc.history(db, tenant_id=claims.get("tenant_id")))


async def _send_or_404(db, claims: dict, send_id: str) -> dict:
    send = await svc.get_send(db, tenant_id=claims.get("tenant_id"), send_id=send_id)
    if send is None:
        raise HTTPException(status_code=404, detail="Send not found")
    return send


@router.get("/history/{send_id}")
async def email_center_send_detail(
    send_id: UuidIdValue,
    claims=Depends(require_platform_permission("platform", "read")),
    db: AsyncSession = Depends(get_db),
):
    _sender(claims)
    return env(await _send_or_404(db, claims, send_id))


@router.post("/history/{send_id}/retry")
async def email_center_retry(
    send_id: UuidIdValue,
    payload: RetryBody,
    request: Request,
    background: BackgroundTasks,
    claims=Depends(require_platform_permission("platform", "write")),
    db: AsyncSession = Depends(get_db),
):
    """Send the same message again, only to the people the first send did not reach."""
    _sender(claims)
    if not payload.confirm:
        raise HTTPException(status_code=422, detail="Confirm the send before it goes out")
    send = await _send_or_404(db, claims, send_id)
    if send["status"] != "finished":
        raise HTTPException(status_code=409, detail="That send has not finished, so there is nothing to retry yet")
    if not send.get("body_complete"):
        raise HTTPException(
            status_code=409,
            detail="This send is older than full-message history, so only its opening lines were kept. Write it again instead.",
        )
    recipients = svc.retry_recipients(send)
    if not recipients:
        raise HTTPException(status_code=409, detail="Everyone got that email; there is nobody to send it to again")
    svc.require_mail_ready()
    body = send.get("body") or ""
    subject = send.get("subject") or ""
    summary = svc.summarize(recipients)
    actor = _actor(request, claims, await _my_email(db, claims))
    new_id = await svc.record_start(
        db,
        actor=actor,
        subject=subject,
        body=body,
        filters={**(send.get("filters") or {}), "retry_of": send_id},
        summary=summary,
    )
    await db.commit()
    background.add_task(svc.deliver, send_id=new_id, actor=actor, subject=subject, body=body, recipients=recipients)
    return env(
        {"id": new_id, **summary},
        f"Sending again to {summary['recipient_count']} {'person' if summary['recipient_count'] == 1 else 'people'}",
    )


# ---- Ribdigi House email design (the owner's own layout, separate from companies') ----


async def _platform_row(db, claims: dict):
    """The platform company row that keeps the owner's design (the owner's own company otherwise)."""
    from sqlalchemy import select

    from app import models as m
    from app.tenants import PROTECTED_TENANT_SLUGS

    row = (
        await db.execute(select(m.Tenant).where(m.Tenant.slug.in_(sorted(PROTECTED_TENANT_SLUGS))).limit(1))
    ).scalar_one_or_none()
    return row or await db.get(m.Tenant, claims.get("tenant_id"))


@router.get("/design")
async def email_design_get(
    claims=Depends(require_platform_permission("platform", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app import email_design

    _sender(claims)
    row = await _platform_row(db, claims)
    raw = ((row.print_branding or {}) if row else {}).get(email_design.PLATFORM_KEY)
    return env(
        {
            "style": email_design.normalize(raw, platform=True),
            "defaults": email_design.PLATFORM_DEFAULT,
            "options": email_design.options(),
            "layout": "platform",
        }
    )


@router.patch("/design")
async def email_design_put(
    payload: EmailDesignUpdateBody,
    claims=Depends(require_platform_permission("platform", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app import email_design

    _sender(claims)
    row = await _platform_row(db, claims)
    if row is None:
        raise HTTPException(status_code=404, detail="Platform company not found")
    current = (row.print_branding or {}).get(email_design.PLATFORM_KEY)
    style = email_design.merged(current or {}, payload.model_dump(exclude_unset=True), platform=True)
    email_design.save(row, style, platform=True)
    await db.commit()
    return env({"style": style}, "Ribdigi House email design saved")


@router.post("/design/preview")
async def email_design_preview(
    payload: EmailDesignPreviewBody,
    claims=Depends(require_platform_permission("platform", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app import email_design, emailer

    _sender(claims)
    data = payload.model_dump(exclude_unset=True)
    sample = data.pop("sample", "document")
    style = email_design.merged(email_design.platform_style(), data, platform=True)
    title, inner = email_design.sample_body(sample, company="Golden Crust Bread")
    html_body = emailer.render_branded_html(
        body_html=inner, company_name="Golden Crust Bread", tenant=None, title=title,
        allow_platform_logo=True, style=style,
    )
    return env({"html": emailer.inline_preview(html_body), "style": style})
