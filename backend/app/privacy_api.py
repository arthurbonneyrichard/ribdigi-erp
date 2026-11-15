"""Privacy routes: marketing unsubscribe (public, signed links) and data deletion requests."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, StringConstraints
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app import privacy as svc
from app.db import SessionLocal, get_db, on_desk
from app.desks import separate_databases
from app.rbac import is_platform_owner_role
from app.schemas import UuidIdValue
from app.security import current_claims, require_platform_permission

router = APIRouter(tags=["privacy"])

TokenValue = Annotated[str, StringConstraints(strip_whitespace=True, min_length=10, max_length=600, pattern=r"^[A-Za-z0-9_-]+$")]
ReasonValue = Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)]
PasswordValue = Annotated[str, StringConstraints(min_length=1, max_length=128)]


def env(data=None, message: str = "Operation completed successfully"):
    return {"success": True, "data": data, "message": message}


@asynccontextmanager
async def _main_db(db: AsyncSession):
    """The main database, where the platform-wide unsubscribe list lives."""
    if not separate_databases():
        yield db
        return
    with on_desk(None):
        async with SessionLocal() as session:
            yield session


@asynccontextmanager
async def _desk_db(db: AsyncSession, tenant_id: str):
    """The database holding a company's rows."""
    if not separate_databases():
        yield db
        return
    from app.desk_routing import locate_desk

    desk = await locate_desk(tenant_id)
    with on_desk(desk):
        async with SessionLocal() as session:
            yield session


def _verified(e: str, t: str) -> str:
    email = svc.verify_link(e, t)
    if not email:
        # Same answer for a changed link and an unknown one: nothing to learn from it.
        raise HTTPException(status_code=400, detail="This unsubscribe link is not valid. Use the link from the newest email.")
    return email


# ---- Public unsubscribe -------------------------------------------------------------


class LinkBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    e: TokenValue
    t: TokenValue


@router.get("/email/unsubscribe")
async def unsubscribe_status(
    e: Annotated[TokenValue, Query()],
    t: Annotated[TokenValue, Query()],
    db: AsyncSession = Depends(get_db),
):
    email = _verified(e, t)
    async with _main_db(db) as main:
        suppressed = await svc.is_suppressed(main, email)
    return env({"email": svc.mask_email(email), "subscribed": not suppressed})


@router.post("/email/unsubscribe")
async def unsubscribe(
    e: Annotated[TokenValue, Query()],
    t: Annotated[TokenValue, Query()],
    db: AsyncSession = Depends(get_db),
):
    """Stop marketing email. Also the RFC 8058 one-click target (mail apps POST here)."""
    email = _verified(e, t)
    async with _main_db(db) as main:
        await svc.set_marketing(main, email, subscribed=False, source="link")
    return env({"email": svc.mask_email(email), "subscribed": False}, "You will not get Ribdigi House news and offers by email any more")


@router.post("/email/resubscribe")
async def resubscribe(payload: LinkBody, db: AsyncSession = Depends(get_db)):
    email = _verified(payload.e, payload.t)
    async with _main_db(db) as main:
        await svc.set_marketing(main, email, subscribed=True, source="link")
    return env({"email": svc.mask_email(email), "subscribed": True}, "Ribdigi House news and offers are back on")


# ---- Signed-in: my marketing email choice ------------------------------------------------


class MarketingBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subscribed: bool


async def _signed_in_email(db: AsyncSession, claims: dict) -> str:
    user = await db.get(m.User, str(claims.get("login_user_id") or claims.get("sub") or ""))
    email = svc.normalize_email(user.email if user else None)
    if not email:
        raise HTTPException(status_code=404, detail="Your account has no email address")
    return email


@router.get("/me/marketing-email")
async def my_marketing_email(claims=Depends(current_claims), db: AsyncSession = Depends(get_db)):
    email = await _signed_in_email(db, claims)
    async with _main_db(db) as main:
        suppressed = await svc.is_suppressed(main, email)
    return env({"email": email, "subscribed": not suppressed})


@router.patch("/me/marketing-email")
async def set_my_marketing_email(
    payload: MarketingBody, claims=Depends(current_claims), db: AsyncSession = Depends(get_db)
):
    email = await _signed_in_email(db, claims)
    async with _main_db(db) as main:
        await svc.set_marketing(main, email, subscribed=payload.subscribed, source="settings")
    return env({"email": email, "subscribed": payload.subscribed}, "Email choice saved")


# ---- Signed-in: deletion requests ---------------------------------------------------------


class DeletionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope: Literal["my_account", "company"]
    password: PasswordValue
    reason: ReasonValue | None = None


@router.get("/privacy/deletion-requests")
async def my_deletion_requests(claims=Depends(current_claims), db: AsyncSession = Depends(get_db)):
    return env(await svc.list_for_company(db, claims=claims))


@router.post("/privacy/deletion-requests")
async def create_deletion_request(
    payload: DeletionCreate, claims=Depends(current_claims), db: AsyncSession = Depends(get_db)
):
    row = await svc.create_request(
        db, claims=claims, scope=payload.scope, password=payload.password, reason=payload.reason
    )
    return env(svc.serialize_request(row), "Request sent to Ribdigi House")


@router.post("/privacy/deletion-requests/{request_id}/cancel")
async def cancel_deletion_request(
    request_id: UuidIdValue, claims=Depends(current_claims), db: AsyncSession = Depends(get_db)
):
    row = await svc.cancel_request(db, claims=claims, request_id=request_id)
    return env(svc.serialize_request(row), "Request cancelled")


# ---- Ribdigi House: review deletion requests ----------------------------------------------


class DecisionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["approve", "reject", "complete"]
    note: ReasonValue | None = None


def _reviewer(claims: dict) -> dict:
    role = claims.get("role") or ""
    if not (is_platform_owner_role(role) or role == "platform_admin"):
        raise HTTPException(status_code=403, detail="Only the software owner or a platform admin can decide deletion requests")
    return claims


@router.get("/platform/privacy/deletion-requests")
async def platform_deletion_requests(
    status: Annotated[Literal["pending", "approved", "rejected", "completed", "cancelled"] | None, Query()] = None,
    claims=Depends(require_platform_permission("platform", "read")),
    db: AsyncSession = Depends(get_db),
):
    _reviewer(claims)
    from app.desk_routing import rows_on_every_desk

    stmt = select(m.DataDeletionRequest, m.Tenant.company_name, m.Tenant.slug).join(
        m.Tenant, m.Tenant.id == m.DataDeletionRequest.tenant_id
    )
    if status:
        stmt = stmt.where(m.DataDeletionRequest.status == status)
    rows = await rows_on_every_desk(db, stmt)
    out = [{**svc.serialize_request(r), "company_name": name, "company_slug": slug} for r, name, slug in rows]
    out.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    return env(out[:200])


@router.post("/platform/privacy/deletion-requests/{request_id}/decide")
async def platform_decide_deletion(
    request_id: UuidIdValue,
    payload: DecisionBody,
    claims=Depends(require_platform_permission("platform", "write")),
    db: AsyncSession = Depends(get_db),
):
    _reviewer(claims)
    from app.desk_routing import rows_on_every_desk

    found = await rows_on_every_desk(
        db, select(m.DataDeletionRequest.tenant_id).where(m.DataDeletionRequest.id == request_id)
    )
    if not found:
        raise HTTPException(status_code=404, detail="Request not found")
    tenant_id = found[0][0]
    async with _desk_db(db, tenant_id) as desk:
        row = await desk.get(m.DataDeletionRequest, request_id)
        if not row:
            raise HTTPException(status_code=404, detail="Request not found")
        row = await svc.decide(
            desk,
            row=row,
            decision=payload.decision,
            note=payload.note,
            actor_id=str(claims.get("sub") or ""),
            actor_tenant_id=str(claims.get("tenant_id") or ""),
            platform_db=db if desk is not db else None,
        )
        data = svc.serialize_request(row)
    messages = {
        "completed": "Done. The account and its personal details are deleted" if data["scope"] == "my_account" else "Marked as completed",
        "approved": "Approved. Let the company download its data, then delete it from Tenants",
        "rejected": "Request refused",
    }
    return env(data, messages.get(data["status"], "Saved"))
