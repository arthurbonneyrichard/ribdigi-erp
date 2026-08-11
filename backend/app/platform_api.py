"""Platform-owner HTTP API (ADR-137). Isolated from tenant ERP modules."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit, health as health_svc, platform as platform_svc
from app import models as m
from app import tenants as tenants_svc
from app.db import get_db
from app.platform_const import (
    PLATFORM_ADMIN,
    PLATFORM_ROLES,
    PLATFORM_SUPER_ADMIN,
    PLATFORM_TENANT_ID,
)
from app.rbac import permissions_for_role, serialize_user
from app.security import (
    hash_password,
    require_platform_permission,
    validate_password_strength,
)

router = APIRouter(prefix="/api/v1/platform", tags=["platform"])


def env(data: Any = None, message: str = "ok", success: bool = True) -> dict[str, Any]:
    return {"success": success, "data": data, "message": message}


def _client_meta(request: Request) -> tuple[str | None, str | None]:
    return request.client.host if request.client else None, request.headers.get("user-agent")


class PlatformUserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=200)
    password: str
    role: str = PLATFORM_ADMIN


class PlatformUserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    role: str | None = None
    is_active: bool | None = None
    password: str | None = None


class PlatformPlanUpdate(BaseModel):
    plan_code: str


class PlatformSettingsUpdate(BaseModel):
    inactivity_timeout_minutes: int | None = Field(default=None, ge=5, le=480)
    company_name: str | None = Field(default=None, min_length=2, max_length=200)
    support_email: str | None = None
    support_phone: str | None = None


@router.get("/dashboard")
async def platform_dashboard(
    claims: dict = Depends(require_platform_permission("platform_dashboard", "read")),
    db: AsyncSession = Depends(get_db),
):
    data = await platform_svc.platform_dashboard_kpis(db)
    # Attach chart payloads for single-request UI load (also available as sub-routes).
    data["tenant_growth"] = await platform_svc.platform_tenant_growth(db)
    data["tenant_status"] = await platform_svc.platform_tenant_status_chart(db)
    data["plan_distribution"] = await platform_svc.platform_plan_distribution(db)
    data["industry_distribution"] = await platform_svc.platform_industry_distribution(db)
    data["user_growth"] = await platform_svc.platform_user_growth(db)
    return env(data)


@router.get("/dashboard/summary")
async def platform_dashboard_summary(
    claims: dict = Depends(require_platform_permission("platform_dashboard", "read")),
    db: AsyncSession = Depends(get_db),
):
    return env(await platform_svc.platform_dashboard_kpis(db))


@router.get("/dashboard/tenant-growth")
async def platform_dashboard_tenant_growth(
    months: int = Query(12, ge=1, le=36),
    claims: dict = Depends(require_platform_permission("platform_dashboard", "read")),
    db: AsyncSession = Depends(get_db),
):
    return env(await platform_svc.platform_tenant_growth(db, months=months))


@router.get("/dashboard/tenant-status")
async def platform_dashboard_tenant_status(
    claims: dict = Depends(require_platform_permission("platform_dashboard", "read")),
    db: AsyncSession = Depends(get_db),
):
    return env(await platform_svc.platform_tenant_status_chart(db))


@router.get("/dashboard/industry-distribution")
async def platform_dashboard_industry_distribution(
    claims: dict = Depends(require_platform_permission("platform_dashboard", "read")),
    db: AsyncSession = Depends(get_db),
):
    return env(await platform_svc.platform_industry_distribution(db))


@router.get("/dashboard/plan-distribution")
async def platform_dashboard_plan_distribution(
    claims: dict = Depends(require_platform_permission("platform_dashboard", "read")),
    db: AsyncSession = Depends(get_db),
):
    return env(await platform_svc.platform_plan_distribution(db))


@router.get("/dashboard/user-growth")
async def platform_dashboard_user_growth(
    months: int = Query(12, ge=1, le=36),
    claims: dict = Depends(require_platform_permission("platform_dashboard", "read")),
    db: AsyncSession = Depends(get_db),
):
    return env(await platform_svc.platform_user_growth(db, months=months))


@router.get("/tenants")
async def platform_list_tenants(
    claims: dict = Depends(require_platform_permission("platform_tenants", "read")),
    db: AsyncSession = Depends(get_db),
    q: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    items, total = await platform_svc.list_customer_tenants(
        db, q=q, status=status, limit=limit, offset=offset
    )
    return env({"items": items, "total": total, "limit": limit, "offset": offset})


@router.get("/tenants/{tenant_id}")
async def platform_get_tenant(
    tenant_id: str,
    claims: dict = Depends(require_platform_permission("platform_tenants", "read")),
    db: AsyncSession = Depends(get_db),
):
    if tenant_id == PLATFORM_TENANT_ID:
        raise HTTPException(status_code=404, detail="Tenant not found")
    data = await platform_svc.get_customer_tenant(db, tenant_id)
    if not data:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return env(data)


@router.post("/tenants/{tenant_id}/suspend")
async def platform_suspend_tenant(
    tenant_id: str,
    request: Request,
    claims: dict = Depends(require_platform_permission("platform_tenants", "write")),
    db: AsyncSession = Depends(get_db),
):
    if tenant_id == PLATFORM_TENANT_ID:
        raise HTTPException(status_code=400, detail="Cannot suspend the platform tenant")
    row = await db.get(m.Tenant, tenant_id)
    if not row or row.id == PLATFORM_TENANT_ID:
        raise HTTPException(status_code=404, detail="Tenant not found")
    if row.status == "suspended":
        return env({"id": row.id, "status": row.status}, message="already suspended")
    prev = row.status
    row = await tenants_svc.suspend_tenant(db, row, reason="Suspended by Ribdigi House platform")
    ip, ua = _client_meta(request)
    await audit.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims.get("sub"),
        action="platform.tenant.suspend",
        entity="tenant",
        entity_id=tenant_id,
        details={"previous_status": prev, "target_tenant_id": tenant_id, "sessions_revoked": True},
        ip_address=ip,
        user_agent=ua,
        module="platform_tenants",
    )
    await db.commit()
    return env({"id": row.id, "status": row.status}, message="tenant suspended")


@router.post("/tenants/{tenant_id}/activate")
async def platform_activate_tenant(
    tenant_id: str,
    request: Request,
    claims: dict = Depends(require_platform_permission("platform_tenants", "write")),
    db: AsyncSession = Depends(get_db),
):
    if tenant_id == PLATFORM_TENANT_ID:
        raise HTTPException(status_code=400, detail="Cannot change platform tenant status here")
    row = await db.get(m.Tenant, tenant_id)
    if not row or row.id == PLATFORM_TENANT_ID:
        raise HTTPException(status_code=404, detail="Tenant not found")
    if row.status == "active":
        return env({"id": row.id, "status": row.status}, message="already active")
    prev = row.status
    row = await tenants_svc.activate_tenant(db, row)
    ip, ua = _client_meta(request)
    await audit.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims.get("sub"),
        action="platform.tenant.activate",
        entity="tenant",
        entity_id=tenant_id,
        details={"previous_status": prev, "target_tenant_id": tenant_id},
        ip_address=ip,
        user_agent=ua,
        module="platform_tenants",
    )
    await db.commit()
    return env({"id": row.id, "status": row.status}, message="tenant activated")


@router.patch("/tenants/{tenant_id}/plan")
async def platform_set_tenant_plan(
    tenant_id: str,
    payload: PlatformPlanUpdate,
    request: Request,
    claims: dict = Depends(require_platform_permission("platform_plans", "write")),
    db: AsyncSession = Depends(get_db),
):
    """Metadata-only plan_code update (ADR-002 — no payment collection)."""
    if tenant_id == PLATFORM_TENANT_ID:
        raise HTTPException(status_code=400, detail="Cannot change platform tenant plan here")
    row = await db.get(m.Tenant, tenant_id)
    if not row or row.id == PLATFORM_TENANT_ID:
        raise HTTPException(status_code=404, detail="Tenant not found")
    plan = (payload.plan_code or "").strip().lower()
    if plan not in tenants_svc.VALID_PLAN_CODES:
        raise HTTPException(
            status_code=400,
            detail=f"plan_code must be one of: {sorted(tenants_svc.VALID_PLAN_CODES)}",
        )
    prev = (getattr(row, "plan_code", None) or "trial").strip().lower()
    row.plan_code = plan
    ip, ua = _client_meta(request)
    await audit.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims.get("sub"),
        action="platform.tenant.plan_code_changed",
        entity="tenant",
        entity_id=tenant_id,
        details={
            "target_tenant_id": tenant_id,
            "from": prev,
            "to": plan,
            "billing_deferred": True,
        },
        ip_address=ip,
        user_agent=ua,
        module="platform_plans",
    )
    await db.commit()
    data = await platform_svc.get_customer_tenant(db, tenant_id)
    return env(data, message="plan_code updated (billing deferred)")


@router.get("/plans")
async def platform_plans_catalog(
    claims: dict = Depends(require_platform_permission("platform_plans", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Metadata plan catalog + distribution (ADR-002 — no payment / fabricated MRR)."""
    distribution = await platform_svc.platform_plan_distribution(db)
    return env(
        {
            "deferred_billing": True,
            "mrr": None,
            "checkout_enabled": False,
            "message": (
                "Plan codes are commercial metadata only. Subscription billing is deferred "
                "(ADR-002); no payment provider and no fabricated MRR."
            ),
            "plan_codes": sorted(tenants_svc.VALID_PLAN_CODES),
            "distribution": distribution,
        }
    )


@router.get("/billing")
async def platform_billing_honesty(
    claims: dict = Depends(require_platform_permission("platform_billing", "read")),
):
    """ADR-002 deferred billing surface — no fabricated MRR."""
    return env(
        {
            "deferred": True,
            "provider": None,
            "mrr": None,
            "outstanding_payments": None,
            "active_subscriptions": None,
            "checkout_enabled": False,
            "message": (
                "Subscription billing is deferred (ADR-002). Plan codes are commercial "
                "metadata only until a payment provider ships."
            ),
            "plan_codes": sorted(tenants_svc.VALID_PLAN_CODES),
        }
    )


def _serialize_platform_settings(tenant: m.Tenant) -> dict:
    return {
        "tenant_id": tenant.id,
        "slug": tenant.slug,
        "company_name": tenant.company_name,
        "inactivity_timeout_minutes": int(
            getattr(tenant, "inactivity_timeout_minutes", None) or 30
        ),
        "support_email": getattr(tenant, "email", None),
        "support_phone": getattr(tenant, "phone", None),
        "status": tenant.status,
        "plan_code": getattr(tenant, "plan_code", None) or "enterprise",
    }


@router.get("/settings")
async def platform_get_settings(
    claims: dict = Depends(require_platform_permission("platform_settings", "read")),
    db: AsyncSession = Depends(get_db),
):
    tenant = await platform_svc.ensure_platform_tenant(db)
    return env(_serialize_platform_settings(tenant))


@router.patch("/settings")
async def platform_patch_settings(
    payload: PlatformSettingsUpdate,
    request: Request,
    claims: dict = Depends(require_platform_permission("platform_settings", "write")),
    db: AsyncSession = Depends(get_db),
):
    if claims.get("role") != PLATFORM_SUPER_ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Only platform_super_admin can update platform settings",
        )
    tenant = await platform_svc.ensure_platform_tenant(db)
    changes: dict[str, Any] = {}
    if payload.inactivity_timeout_minutes is not None:
        tenant.inactivity_timeout_minutes = int(payload.inactivity_timeout_minutes)
        changes["inactivity_timeout_minutes"] = tenant.inactivity_timeout_minutes
    if payload.company_name is not None:
        tenant.company_name = payload.company_name.strip()
        changes["company_name"] = tenant.company_name
    if payload.support_email is not None:
        email = payload.support_email.strip() or None
        tenant.email = email
        changes["support_email"] = email
    if payload.support_phone is not None:
        phone = payload.support_phone.strip() or None
        tenant.phone = phone
        changes["support_phone"] = phone
    if not changes:
        return env(_serialize_platform_settings(tenant), message="no changes")
    ip, ua = _client_meta(request)
    await audit.record_event(
        db,
        tenant_id=PLATFORM_TENANT_ID,
        user_id=claims.get("sub"),
        action="platform.settings.update",
        entity="tenant",
        entity_id=PLATFORM_TENANT_ID,
        details=changes,
        ip_address=ip,
        user_agent=ua,
        module="platform_settings",
    )
    await db.commit()
    await db.refresh(tenant)
    return env(_serialize_platform_settings(tenant), message="platform settings updated")


@router.get("/users")
async def platform_list_users(
    claims: dict = Depends(require_platform_permission("platform_users", "read")),
    db: AsyncSession = Depends(get_db),
):
    await platform_svc.ensure_platform_tenant(db)
    rows = (
        await db.execute(
            select(m.User)
            .where(m.User.tenant_id == PLATFORM_TENANT_ID)
            .order_by(m.User.full_name.asc())
        )
    ).scalars().all()
    return env([serialize_user(u) for u in rows])


@router.post("/users")
async def platform_create_user(
    payload: PlatformUserCreate,
    request: Request,
    claims: dict = Depends(require_platform_permission("platform_users", "write")),
    db: AsyncSession = Depends(get_db),
):
    if claims.get("role") != PLATFORM_SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Only platform_super_admin can create platform users")
    role = (payload.role or "").strip()
    if role not in PLATFORM_ROLES:
        raise HTTPException(
            status_code=400,
            detail=f"role must be one of: {sorted(PLATFORM_ROLES)}",
        )
    validate_password_strength(payload.password)
    await platform_svc.ensure_platform_tenant(db)
    email = str(payload.email).strip().lower()
    exists = (
        await db.execute(
            select(m.User).where(m.User.tenant_id == PLATFORM_TENANT_ID, m.User.email == email)
        )
    ).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="User email already exists on platform tenant")
    user = m.User(
        tenant_id=PLATFORM_TENANT_ID,
        email=email,
        full_name=payload.full_name.strip(),
        password_hash=hash_password(payload.password),
        role=role,
        permissions=permissions_for_role(role),
        email_verified=True,
        is_active=True,
        totp_enabled=False,
    )
    db.add(user)
    await db.flush()
    ip, ua = _client_meta(request)
    await audit.record_event(
        db,
        tenant_id=PLATFORM_TENANT_ID,
        user_id=claims.get("sub"),
        action="platform.user.create",
        entity="user",
        entity_id=user.id,
        details={"email": user.email, "role": user.role},
        ip_address=ip,
        user_agent=ua,
        module="platform_users",
    )
    await db.commit()
    return env(serialize_user(user), message="platform user created")


@router.patch("/users/{user_id}")
async def platform_update_user(
    user_id: str,
    payload: PlatformUserUpdate,
    request: Request,
    claims: dict = Depends(require_platform_permission("platform_users", "write")),
    db: AsyncSession = Depends(get_db),
):
    if claims.get("role") != PLATFORM_SUPER_ADMIN and user_id != claims.get("sub"):
        # platform_admin may only update self (limited); role changes need super
        raise HTTPException(status_code=403, detail="Insufficient permission to update this user")
    user = await db.get(m.User, user_id)
    if not user or user.tenant_id != PLATFORM_TENANT_ID:
        raise HTTPException(status_code=404, detail="User not found")
    changes: dict[str, Any] = {}
    if payload.full_name is not None:
        user.full_name = payload.full_name.strip()
        changes["full_name"] = user.full_name
    if payload.role is not None:
        if claims.get("role") != PLATFORM_SUPER_ADMIN:
            raise HTTPException(status_code=403, detail="Only platform_super_admin can change roles")
        role = payload.role.strip()
        if role not in PLATFORM_ROLES:
            raise HTTPException(
                status_code=400,
                detail=f"role must be one of: {sorted(PLATFORM_ROLES)}",
            )
        if user.id == claims.get("sub") and role != user.role:
            raise HTTPException(status_code=400, detail="Cannot change your own platform role")
        if user.role != role:
            changes["role"] = {"from": user.role, "to": role}
            user.role = role
            user.permissions = permissions_for_role(role)
    if payload.is_active is not None:
        if claims.get("role") != PLATFORM_SUPER_ADMIN:
            raise HTTPException(status_code=403, detail="Only platform_super_admin can deactivate users")
        if user.id == claims.get("sub") and payload.is_active is False:
            raise HTTPException(status_code=400, detail="Cannot deactivate your own account")
        if bool(user.is_active) != bool(payload.is_active):
            user.is_active = bool(payload.is_active)
            changes["is_active"] = user.is_active
            if not user.is_active:
                from datetime import datetime

                sessions = (
                    await db.execute(
                        select(m.AuthSession).where(
                            m.AuthSession.tenant_id == PLATFORM_TENANT_ID,
                            m.AuthSession.user_id == user.id,
                            m.AuthSession.revoked_at.is_(None),
                        )
                    )
                ).scalars().all()
                now = datetime.utcnow()
                for s in sessions:
                    s.revoked_at = now
                changes["sessions_revoked"] = len(sessions)
    if payload.password is not None:
        if claims.get("role") != PLATFORM_SUPER_ADMIN and user.id != claims.get("sub"):
            raise HTTPException(status_code=403, detail="Cannot reset another user's password")
        validate_password_strength(payload.password)
        user.password_hash = hash_password(payload.password)
        changes["password_reset"] = True
    if not changes:
        return env(serialize_user(user), message="no changes")
    ip, ua = _client_meta(request)
    await audit.record_event(
        db,
        tenant_id=PLATFORM_TENANT_ID,
        user_id=claims.get("sub"),
        action="platform.user.update",
        entity="user",
        entity_id=user.id,
        details=changes,
        ip_address=ip,
        user_agent=ua,
        module="platform_users",
    )
    await db.commit()
    return env(serialize_user(user), message="platform user updated")


@router.get("/health")
async def platform_health(
    claims: dict = Depends(require_platform_permission("platform_health", "read")),
):
    report, _status = await health_svc.assemble_health(deep=True)
    return env(report)


@router.get("/audit")
async def platform_audit(
    claims: dict = Depends(require_platform_permission("platform_audit", "read")),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    rows = await audit.query_logs(
        db,
        tenant_id=PLATFORM_TENANT_ID,
        limit=min(limit + offset, 1000),
    )
    sliced = rows[offset : offset + limit]
    items = [audit.serialize_audit(r) for r in sliced]
    return env({"items": items, "total": len(rows), "limit": limit, "offset": offset})
