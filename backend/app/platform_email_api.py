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
from app.security import require_platform_permission
from app.tenants import VALID_INDUSTRIES, VALID_STATUSES

router = APIRouter(prefix="/platform/email", tags=["platform"])

StatusValue = Literal["trial", "active", "grace", "suspended"]
IndustryValue = Literal["retail", "hotel", "restaurant", "fmcg", "bakery", "gym", "hrm", "pharmacy", "mart"]
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
    include_company_email: bool = False


class MessageBody(AudienceBody):
    subject: SubjectValue
    body: BodyValue


class SendBody(MessageBody):
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
    )


def _filters(body: AudienceBody) -> dict:
    return {
        "statuses": list(body.statuses),
        "industries": list(body.industries),
        "packages": list(body.packages),
        "include_company_email": body.include_company_email,
    }


@router.get("/status")
async def email_center_status(claims=Depends(require_platform_permission("platform", "read"))):
    _sender(claims)
    mode = svc.mail_mode()
    return env({"mode": mode, "ready": mode == "smtp", "max_recipients": svc.MAX_RECIPIENTS})


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
