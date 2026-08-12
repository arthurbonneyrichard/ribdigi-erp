"""Platform-owner HTTP API (ADR-137). Isolated from tenant ERP modules."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from email_validator import EmailNotValidError, validate_email
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit, health as health_svc, platform as platform_svc
from app import models as m
from app import platform_catalog_export as platform_catalog_export_svc
from app import platform_ops_export as platform_ops_export_svc
from app import platform_staff_export as platform_staff_export_svc
from app import reports as reports_svc
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
    issue_one_time_token,
    require_platform_permission,
    validate_password_strength,
)
from app.config import settings
from app.security_runtime import security_posture

router = APIRouter(prefix="/api/v1/platform", tags=["platform"])


def env(data: Any = None, message: str = "ok", success: bool = True) -> dict[str, Any]:
    return {"success": success, "data": data, "message": message}


def _client_meta(request: Request) -> tuple[str | None, str | None]:
    return request.client.host if request.client else None, request.headers.get("user-agent")


class PlatformUserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=200)
    password: str | None = None
    role: str = PLATFORM_ADMIN


class PlatformUserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    role: str | None = None
    is_active: bool | None = None
    password: str | None = None


class PlatformTenantCreate(BaseModel):
    company_name: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=2, max_length=80)
    industry: str = "retail"
    currency: str = "GHS"
    timezone: str | None = None
    tax_jurisdiction: str | None = None
    admin_email: EmailStr
    admin_password: str
    admin_full_name: str = "Company Administrator"
    plan_code: str = "trial"


class PlatformPlanUpdate(BaseModel):
    plan_code: str


class PlatformTenantNotesUpdate(BaseModel):
    platform_notes: str | None = Field(default=None, max_length=2000)


class PlatformTenantLifecycleUpdate(BaseModel):
    extend_trial_days: int | None = Field(default=None, ge=1, le=365)


class PlatformSuspendBody(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class PlatformSettingsUpdate(BaseModel):
    inactivity_timeout_minutes: int | None = Field(default=None, ge=5, le=480)
    company_name: str | None = Field(default=None, min_length=2, max_length=200)
    support_email: str | None = None
    support_phone: str | None = None
    timezone: str | None = Field(default=None, min_length=1, max_length=64)
    date_format: str | None = None
    time_format: str | None = None
    number_format: str | None = None


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
    plan_code: str | None = Query(None),
    industry: str | None = Query(None),
    created_this_month: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Stage 93 M1: ``created_this_month`` filters to tenants created in the current UTC month."""
    items, total = await platform_svc.list_customer_tenants(
        db,
        q=q,
        status=status,
        plan_code=plan_code,
        industry=industry,
        created_this_month=created_this_month,
        limit=limit,
        offset=offset,
    )
    return env(
        {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
            "filters": {
                "q": q,
                "status": status,
                "plan_code": plan_code,
                "industry": industry,
                "created_this_month": created_this_month,
            },
        }
    )


@router.get("/industries")
async def platform_industries_catalog(
    claims: dict = Depends(require_platform_permission("platform_tenants", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 93 M1 — canonical industry catalog for House roster filters/provisioning."""
    await platform_svc.ensure_platform_tenant(db)
    return env(
        {
            "catalog": tenants_svc.industry_catalog_items(),
            "codes": sorted(tenants_svc.VALID_INDUSTRIES),
        }
    )


@router.get("/tenants/export")
async def platform_tenants_export(
    claims: dict = Depends(require_platform_permission("platform_tenants", "read")),
    db: AsyncSession = Depends(get_db),
    q: str | None = Query(None),
    status: str | None = Query(None),
    plan_code: str | None = Query(None),
    industry: str | None = Query(None),
    created_this_month: bool = Query(False),
    format: str = Query("csv"),
):
    """Stage 88 R1 — export customer tenant roster (csv/pdf). Stage 89 F1 adds plan/industry filters."""
    items, _total = await platform_svc.list_customer_tenants(
        db,
        q=q,
        status=status,
        plan_code=plan_code,
        industry=industry,
        created_this_month=created_this_month,
        limit=500,
        offset=0,
    )
    fmt = (format or "csv").strip().lower()
    if fmt == "pdf":
        return Response(
            content=platform_svc.customer_tenants_to_pdf(items),
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=platform-tenants.pdf"},
        )
    if fmt != "csv":
        raise HTTPException(status_code=400, detail="format must be csv or pdf")
    return PlainTextResponse(
        content=platform_svc.customer_tenants_to_csv(items),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=platform-tenants.csv"},
    )


@router.get("/tenants/at-risk")
async def platform_tenants_at_risk(
    claims: dict = Depends(require_platform_permission("platform_tenants", "read")),
    db: AsyncSession = Depends(get_db),
    within_days: int = Query(14, ge=1, le=90),
):
    """Stage 88 R1 — trial/grace tenants nearing expiry."""
    return env(await platform_svc.list_at_risk_tenants(db, within_days=within_days))


@router.get("/tenants/at-risk/export")
async def platform_tenants_at_risk_export(
    claims: dict = Depends(require_platform_permission("platform_tenants", "read")),
    db: AsyncSession = Depends(get_db),
    within_days: int = Query(14, ge=1, le=90),
):
    """Stage 151 A1 — at-risk tenants CSV (same queue as GET /platform/tenants/at-risk)."""
    payload = await platform_svc.list_at_risk_tenants(db, within_days=within_days)
    text = platform_ops_export_svc.export_platform_at_risk_tenants_csv(
        items=payload.get("items") or [],
        within_days=payload.get("within_days"),
    )
    return Response(
        content=text,
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="platform_at_risk_tenants_export.csv"'
        },
    )


@router.post("/tenants")
async def platform_create_tenant(
    payload: PlatformTenantCreate,
    request: Request,
    claims: dict = Depends(require_platform_permission("platform_tenants", "write")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 86 P1 — House-provisioned customer tenant (public /register remains)."""
    if claims.get("role") != PLATFORM_SUPER_ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Only platform_super_admin can provision customer tenants",
        )
    await platform_svc.ensure_platform_tenant(db)
    industry = (payload.industry or "retail").strip().lower()
    if industry not in tenants_svc.VALID_INDUSTRIES:
        raise HTTPException(
            status_code=400,
            detail=f"industry must be one of: {sorted(tenants_svc.VALID_INDUSTRIES)}",
        )
    tenant, admin, raw = await platform_svc.provision_customer_tenant(
        db,
        slug=payload.slug,
        company_name=payload.company_name,
        industry=industry,
        currency=payload.currency,
        timezone=(payload.timezone or "Africa/Accra").strip() or "Africa/Accra",
        tax_jurisdiction=(payload.tax_jurisdiction or "GH").strip().upper() or "GH",
        admin_email=str(payload.admin_email),
        admin_password=payload.admin_password,
        admin_full_name=payload.admin_full_name or "Company Administrator",
        plan_code=payload.plan_code or "trial",
    )
    ip, ua = _client_meta(request)
    await audit.record_event(
        db,
        tenant_id=PLATFORM_TENANT_ID,
        user_id=claims.get("sub"),
        action="platform.tenant.create",
        entity="tenant",
        entity_id=tenant.id,
        details={
            "slug": tenant.slug,
            "company_name": tenant.company_name,
            "plan_code": getattr(tenant, "plan_code", None),
            "admin_email": admin.email,
            "admin_user_id": admin.id,
        },
        ip_address=ip,
        user_agent=ua,
        module="platform_tenants",
    )
    await db.commit()
    await db.refresh(tenant)

    from app import emailer

    email_result = await emailer.send_verification_email(
        to=str(payload.admin_email), token=raw, company_name=tenant.company_name
    )
    await platform_svc.record_platform_email_delivery(
        db,
        actor_user_id=claims.get("sub"),
        purpose="email_verify",
        recipient=str(payload.admin_email),
        related_action="platform.tenant.create",
        email_result=email_result,
        extra={
            "target_tenant_id": tenant.id,
            "admin_user_id": admin.id,
        },
        ip_address=ip,
        user_agent=ua,
    )
    await db.commit()
    data = {
        "tenant_id": tenant.id,
        "slug": tenant.slug,
        "status": tenant.status,
        "plan_code": getattr(tenant, "plan_code", None) or "trial",
        "admin_user_id": admin.id,
        "email": {
            "sent": email_result.sent,
            "mode": email_result.mode,
            "error": email_result.error,
        },
        "email_delivery": {
            "sent": email_result.sent,
            "mode": email_result.mode,
            "error": email_result.error,
            "fabricated_success": False,
        },
    }
    if settings.DEBUG or settings.APP_ENV.lower() != "production":
        data["email_verification_token"] = raw
    return env(data, "Customer tenant provisioned by Ribdigi House")


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
    payload: PlatformSuspendBody | None = None,
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
    reason = (payload.reason if payload else None) or "Suspended by Ribdigi House platform"
    row = await tenants_svc.suspend_tenant(db, row, reason=reason.strip())
    ip, ua = _client_meta(request)
    await audit.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims.get("sub"),
        action="platform.tenant.suspend",
        entity="tenant",
        entity_id=tenant_id,
        details={
            "previous_status": prev,
            "target_tenant_id": tenant_id,
            "sessions_revoked": True,
            "reason": row.suspended_reason,
        },
        ip_address=ip,
        user_agent=ua,
        module="platform_tenants",
    )
    await db.commit()
    data = await platform_svc.get_customer_tenant(db, tenant_id)
    return env(data or {"id": row.id, "status": row.status}, message="tenant suspended")


@router.patch("/tenants/{tenant_id}/lifecycle")
async def platform_tenant_lifecycle(
    tenant_id: str,
    payload: PlatformTenantLifecycleUpdate,
    request: Request,
    claims: dict = Depends(require_platform_permission("platform_tenants", "write")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 88 L1 — extend trial / reopen trial window (not paid billing)."""
    if tenant_id == PLATFORM_TENANT_ID:
        raise HTTPException(status_code=400, detail="Cannot alter platform tenant lifecycle here")
    row = await db.get(m.Tenant, tenant_id)
    if not row or row.id == PLATFORM_TENANT_ID:
        raise HTTPException(status_code=404, detail="Tenant not found")
    if payload.extend_trial_days is None:
        raise HTTPException(status_code=400, detail="extend_trial_days is required")
    prev = {
        "status": row.status,
        "trial_ends_at": row.trial_ends_at.isoformat() + "Z" if row.trial_ends_at else None,
    }
    row = await tenants_svc.extend_trial(db, row, days=payload.extend_trial_days)
    ip, ua = _client_meta(request)
    await audit.record_event(
        db,
        tenant_id=PLATFORM_TENANT_ID,
        user_id=claims.get("sub"),
        action="platform.tenant.lifecycle_extended",
        entity="tenant",
        entity_id=tenant_id,
        details={
            "target_tenant_id": tenant_id,
            "extend_trial_days": payload.extend_trial_days,
            "previous": prev,
            "billing_deferred": True,
        },
        ip_address=ip,
        user_agent=ua,
        module="platform_tenants",
    )
    await db.commit()
    data = await platform_svc.get_customer_tenant(db, tenant_id)
    return env(data, message="tenant lifecycle updated (billing deferred)")


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


@router.post("/tenants/{tenant_id}/admin/password-reset-email")
async def platform_tenant_admin_password_reset_email(
    tenant_id: str,
    request: Request,
    claims: dict = Depends(require_platform_permission("platform_tenants", "write")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 89 A1 — House-initiated password reset for customer Tenant Admin (no impersonation)."""
    if tenant_id == PLATFORM_TENANT_ID:
        raise HTTPException(status_code=400, detail="Use platform users for House staff reset")
    row = await db.get(m.Tenant, tenant_id)
    if not row or row.id == PLATFORM_TENANT_ID:
        raise HTTPException(status_code=404, detail="Tenant not found")
    admin = await platform_svc.get_customer_tenant_admin(db, tenant_id)
    if not admin:
        raise HTTPException(status_code=404, detail="Tenant Admin not found")
    raw, token_hash, expires = issue_one_time_token()
    db.add(
        m.AuthToken(
            tenant_id=tenant_id,
            user_id=admin.id,
            purpose="password_reset",
            token_hash=token_hash,
            expires_at=expires,
        )
    )
    ip, ua = _client_meta(request)
    await audit.record_event(
        db,
        tenant_id=PLATFORM_TENANT_ID,
        user_id=claims.get("sub"),
        action="platform.tenant.admin_password_reset_email",
        entity="user",
        entity_id=admin.id,
        details={
            "target_tenant_id": tenant_id,
            "admin_email": admin.email,
            "impersonation": False,
        },
        ip_address=ip,
        user_agent=ua,
        module="platform_tenants",
    )
    await db.commit()
    from app import emailer

    email_result = await emailer.send_password_reset_email(to=admin.email, token=raw)
    await platform_svc.record_platform_email_delivery(
        db,
        actor_user_id=claims.get("sub"),
        purpose="password_reset",
        recipient=admin.email,
        related_action="platform.tenant.admin_password_reset_email",
        email_result=email_result,
        extra={"target_tenant_id": tenant_id, "admin_user_id": admin.id},
        ip_address=ip,
        user_agent=ua,
    )
    await db.commit()
    data: dict[str, Any] = {
        "tenant_id": tenant_id,
        "admin_user_id": admin.id,
        "email": admin.email,
        "impersonation": False,
        "email_delivery": {
            "sent": email_result.sent,
            "mode": email_result.mode,
            "error": email_result.error,
        },
    }
    if settings.DEBUG or settings.APP_ENV.lower() != "production":
        data["reset_token"] = raw
    return env(data, "Tenant Admin password reset email issued")


@router.post("/tenants/{tenant_id}/admin/resend-verification")
async def platform_tenant_admin_resend_verification(
    tenant_id: str,
    request: Request,
    claims: dict = Depends(require_platform_permission("platform_tenants", "write")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 89 A1 — House resend email verification for customer Tenant Admin."""
    if tenant_id == PLATFORM_TENANT_ID:
        raise HTTPException(status_code=400, detail="Platform staff emails are already verified")
    row = await db.get(m.Tenant, tenant_id)
    if not row or row.id == PLATFORM_TENANT_ID:
        raise HTTPException(status_code=404, detail="Tenant not found")
    admin = await platform_svc.get_customer_tenant_admin(db, tenant_id)
    if not admin:
        raise HTTPException(status_code=404, detail="Tenant Admin not found")
    if bool(admin.email_verified):
        return env(
            {
                "tenant_id": tenant_id,
                "admin_user_id": admin.id,
                "email": admin.email,
                "already_verified": True,
                "impersonation": False,
            },
            "Tenant Admin email already verified",
        )
    raw, token_hash, expires = issue_one_time_token()
    db.add(
        m.AuthToken(
            tenant_id=tenant_id,
            user_id=admin.id,
            purpose="email_verify",
            token_hash=token_hash,
            expires_at=expires,
        )
    )
    ip, ua = _client_meta(request)
    await audit.record_event(
        db,
        tenant_id=PLATFORM_TENANT_ID,
        user_id=claims.get("sub"),
        action="platform.tenant.admin_resend_verification",
        entity="user",
        entity_id=admin.id,
        details={
            "target_tenant_id": tenant_id,
            "admin_email": admin.email,
            "impersonation": False,
        },
        ip_address=ip,
        user_agent=ua,
        module="platform_tenants",
    )
    await db.commit()
    from app import emailer

    email_result = await emailer.send_verification_email(
        to=admin.email, token=raw, company_name=row.company_name
    )
    await platform_svc.record_platform_email_delivery(
        db,
        actor_user_id=claims.get("sub"),
        purpose="email_verify",
        recipient=admin.email,
        related_action="platform.tenant.admin_resend_verification",
        email_result=email_result,
        extra={"target_tenant_id": tenant_id, "admin_user_id": admin.id},
        ip_address=ip,
        user_agent=ua,
    )
    await db.commit()
    data: dict[str, Any] = {
        "tenant_id": tenant_id,
        "admin_user_id": admin.id,
        "email": admin.email,
        "already_verified": False,
        "impersonation": False,
        "email_delivery": {
            "sent": email_result.sent,
            "mode": email_result.mode,
            "error": email_result.error,
        },
    }
    if settings.DEBUG or settings.APP_ENV.lower() != "production":
        data["email_verification_token"] = raw
    return env(data, "Tenant Admin verification email issued")


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


@router.patch("/tenants/{tenant_id}/notes")
async def platform_set_tenant_notes(
    tenant_id: str,
    payload: PlatformTenantNotesUpdate,
    request: Request,
    claims: dict = Depends(require_platform_permission("platform_tenants", "write")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 87 Y1 — House operator notes (not customer company profile)."""
    if tenant_id == PLATFORM_TENANT_ID:
        raise HTTPException(status_code=400, detail="Cannot set notes on the platform tenant here")
    row = await db.get(m.Tenant, tenant_id)
    if not row or row.id == PLATFORM_TENANT_ID:
        raise HTTPException(status_code=404, detail="Tenant not found")
    notes = payload.platform_notes
    if notes is not None:
        notes = notes.strip() or None
    prev = getattr(row, "platform_notes", None)
    row.platform_notes = notes
    ip, ua = _client_meta(request)
    await audit.record_event(
        db,
        tenant_id=PLATFORM_TENANT_ID,
        user_id=claims.get("sub"),
        action="platform.tenant.notes_updated",
        entity="tenant",
        entity_id=tenant_id,
        details={"target_tenant_id": tenant_id, "changed": prev != notes},
        ip_address=ip,
        user_agent=ua,
        module="platform_tenants",
    )
    await db.commit()
    data = await platform_svc.get_customer_tenant(db, tenant_id)
    return env(data, message="operator notes updated")


@router.get("/plans")
async def platform_plans_catalog(
    claims: dict = Depends(require_platform_permission("platform_plans", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Metadata plan catalog + distribution (ADR-002 — no payment / fabricated MRR).

    Stage 89 C1: enriched catalog labels/blurbs/soft limits (still not checkout).
    """
    distribution = await platform_svc.platform_plan_distribution(db)
    catalog = tenants_svc.plan_catalog_items()
    return env(
        {
            "deferred_billing": True,
            "mrr": None,
            "checkout_enabled": False,
            "subscriptions_live": False,
            "message": (
                "Plan codes are commercial metadata only. Subscription billing is deferred "
                "(ADR-002); no payment provider and no fabricated MRR."
            ),
            "plan_codes": sorted(tenants_svc.VALID_PLAN_CODES),
            "catalog": catalog,
            "distribution": distribution,
        }
    )


@router.get("/plans/export")
async def platform_plans_catalog_export(
    claims: dict = Depends(require_platform_permission("platform_plans", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 150 P1 — plan catalog CSV (metadata honesty; no fabricated MRR)."""
    text = await platform_catalog_export_svc.export_platform_plans_csv(db)
    return Response(
        content=text,
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="platform_plans_export.csv"'
        },
    )


@router.get("/billing")
async def platform_billing_honesty(
    claims: dict = Depends(require_platform_permission("platform_billing", "read")),
    db: AsyncSession = Depends(get_db),
):
    """ADR-002 deferred billing surface — no fabricated MRR.

    Stage 85 R1: includes tenant×plan subscriptions roster as metadata only.
    """
    roster = await platform_svc.platform_subscriptions_roster(db)
    return env(
        {
            "deferred": True,
            "provider": None,
            "mrr": None,
            "outstanding_payments": None,
            "active_subscriptions": roster["items"],
            "subscriptions_live": False,
            "checkout_enabled": False,
            "message": (
                "Subscription billing is deferred (ADR-002). The roster below is "
                "tenant×plan commercial metadata only — not live checkout or MRR."
            ),
            "plan_codes": sorted(tenants_svc.VALID_PLAN_CODES),
            "distribution": roster.get("distribution"),
            "roster_total": roster.get("total"),
        }
    )


@router.get("/subscriptions")
async def platform_subscriptions_roster(
    claims: dict = Depends(require_platform_permission("platform_billing", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 85 R1 — customer tenant × plan_code roster (metadata honesty)."""
    return env(await platform_svc.platform_subscriptions_roster(db))


@router.get("/subscriptions/export")
async def platform_subscriptions_roster_export(
    claims: dict = Depends(require_platform_permission("platform_billing", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 150 R1 — subscriptions roster CSV (metadata only; no fabricated MRR)."""
    text = await platform_catalog_export_svc.export_platform_subscriptions_csv(db)
    return Response(
        content=text,
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="platform_subscriptions_export.csv"'
        },
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
        "timezone": getattr(tenant, "timezone", None) or "Africa/Accra",
        "date_format": getattr(tenant, "date_format", None) or "DD/MM/YYYY",
        "time_format": getattr(tenant, "time_format", None) or "24h",
        "number_format": getattr(tenant, "number_format", None) or "1,234.56",
        "status": tenant.status,
        "plan_code": getattr(tenant, "plan_code", None) or "enterprise",
    }


def _house_runtime(tenant: m.Tenant | None) -> dict[str, Any]:
    """Stage 93 V1 — protected House runtime posture for health/evidence."""
    if not tenant:
        return {
            "timezone": None,
            "date_format": None,
            "time_format": None,
            "number_format": None,
            "inactivity_timeout_minutes": None,
        }
    return {
        "timezone": getattr(tenant, "timezone", None) or "Africa/Accra",
        "date_format": getattr(tenant, "date_format", None) or "DD/MM/YYYY",
        "time_format": getattr(tenant, "time_format", None) or "24h",
        "number_format": getattr(tenant, "number_format", None) or "1,234.56",
        "inactivity_timeout_minutes": int(
            getattr(tenant, "inactivity_timeout_minutes", None) or 30
        ),
    }


def _runtime_identity() -> dict[str, Any]:
    """Stage 94 H1 — protected release identity (honest null build when unset)."""
    build = (settings.APP_BUILD_ID or "").strip() or None
    return {
        "version": (settings.APP_VERSION or "").strip() or "1.0.0",
        "build_id": build,
        "app_env": settings.APP_ENV,
        "debug": bool(settings.DEBUG),
    }


def _platform_security_detail() -> dict[str, Any]:
    """Stage 92 K1 — protected health/evidence security detail (not public /health)."""
    posture = security_posture()
    sec = dict(posture.get("security") or {})
    origins = list(settings.cors_origins)
    sec["cors_origins"] = origins
    sec["cors_origins_count"] = len(origins)
    sec["cors_allows_wildcard"] = any(o == "*" for o in origins)
    return sec


@router.get("/settings")
async def platform_get_settings(
    claims: dict = Depends(require_platform_permission("platform_settings", "read")),
    db: AsyncSession = Depends(get_db),
):
    tenant = await platform_svc.ensure_platform_tenant(db)
    return env(_serialize_platform_settings(tenant))


@router.get("/settings/export")
async def platform_settings_export(
    claims: dict = Depends(require_platform_permission("platform_settings", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 150 S1 — Ribdigi House settings CSV (secret-free)."""
    text = await platform_catalog_export_svc.export_platform_settings_csv(db)
    return Response(
        content=text,
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="platform_settings_export.csv"'
        },
    )


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
        if email is not None:
            try:
                email = validate_email(email, check_deliverability=False).normalized
            except EmailNotValidError as exc:
                raise HTTPException(
                    status_code=400,
                    detail=f"support_email is invalid: {exc}",
                ) from exc
        tenant.email = email
        changes["support_email"] = email
    if payload.support_phone is not None:
        phone = payload.support_phone.strip() or None
        tenant.phone = phone
        changes["support_phone"] = phone
    if payload.timezone is not None:
        tz = payload.timezone.strip()
        if not tz:
            raise HTTPException(status_code=400, detail="timezone cannot be empty")
        try:
            ZoneInfo(tz)
        except ZoneInfoNotFoundError as exc:
            raise HTTPException(
                status_code=400,
                detail="timezone must be a valid IANA timezone (e.g. Africa/Accra)",
            ) from exc
        tenant.timezone = tz
        changes["timezone"] = tenant.timezone
    if payload.date_format is not None:
        fmt = payload.date_format.strip().upper()
        if fmt not in tenants_svc.VALID_DATE_FORMATS:
            raise HTTPException(
                status_code=400,
                detail="date_format must be one of: DD/MM/YYYY, MM/DD/YYYY, YYYY-MM-DD",
            )
        tenant.date_format = fmt
        changes["date_format"] = tenant.date_format
    if payload.time_format is not None:
        tfmt = payload.time_format.strip().lower()
        if tfmt not in tenants_svc.VALID_TIME_FORMATS:
            raise HTTPException(status_code=400, detail="time_format must be 24h or 12h")
        tenant.time_format = tfmt
        changes["time_format"] = tenant.time_format
    if payload.number_format is not None:
        nfmt = payload.number_format.strip()
        if nfmt not in tenants_svc.VALID_NUMBER_FORMATS:
            raise HTTPException(
                status_code=400,
                detail="number_format must be one of: 1,234.56, 1.234,56, 1 234.56",
            )
        tenant.number_format = nfmt
        changes["number_format"] = tenant.number_format
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
    q: str | None = Query(None),
    role: str | None = Query(None),
    is_active: bool | None = Query(None),
):
    """Stage 91 P1 — includes last_session_at + active_session_count rollups.

    Stage 94 W1 — optional q / role / is_active discovery filters.
    """
    await platform_svc.ensure_platform_tenant(db)
    q_filter = (q or "").strip() or None
    role_filter = (role or "").strip() or None
    if role_filter and role_filter not in PLATFORM_ROLES:
        raise HTTPException(
            status_code=400,
            detail=f"role must be one of: {sorted(PLATFORM_ROLES)}",
        )
    filters = [m.User.tenant_id == PLATFORM_TENANT_ID]
    if q_filter:
        like = f"%{q_filter}%"
        filters.append(or_(m.User.email.ilike(like), m.User.full_name.ilike(like)))
    if role_filter:
        filters.append(m.User.role == role_filter)
    if is_active is not None:
        filters.append(m.User.is_active.is_(bool(is_active)))
    rows = (
        await db.execute(select(m.User).where(*filters).order_by(m.User.full_name.asc()))
    ).scalars().all()
    now = datetime.utcnow()
    last_by_user = {
        uid: created
        for uid, created in (
            await db.execute(
                select(m.AuthSession.user_id, func.max(m.AuthSession.created_at))
                .where(m.AuthSession.tenant_id == PLATFORM_TENANT_ID)
                .group_by(m.AuthSession.user_id)
            )
        ).all()
    }
    active_by_user = {
        uid: int(cnt or 0)
        for uid, cnt in (
            await db.execute(
                select(m.AuthSession.user_id, func.count())
                .where(
                    m.AuthSession.tenant_id == PLATFORM_TENANT_ID,
                    m.AuthSession.revoked_at.is_(None),
                    m.AuthSession.expires_at > now,
                )
                .group_by(m.AuthSession.user_id)
            )
        ).all()
    }
    invites = await platform_svc.latest_staff_invite_deliveries(db, [u.id for u in rows])
    out = []
    for u in rows:
        payload = serialize_user(u)
        last = last_by_user.get(u.id)
        payload["last_session_at"] = last.isoformat() + "Z" if last else None
        payload["active_session_count"] = active_by_user.get(u.id, 0)
        payload["last_invite_delivery"] = invites.get(u.id)
        out.append(payload)
    return env(out)


@router.get("/users/export")
async def platform_users_export(
    claims: dict = Depends(require_platform_permission("platform_users", "read")),
    db: AsyncSession = Depends(get_db),
    q: str | None = Query(None),
    role: str | None = Query(None),
    is_active: bool | None = Query(None),
):
    """Stage 149 U1 — platform staff users CSV (no password/TOTP secrets)."""
    text = await platform_staff_export_svc.export_platform_users_csv(
        db, q=q, role=role, is_active=is_active
    )
    return Response(
        content=text,
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="platform_users_export.csv"'
        },
    )


@router.get("/users/sessions")
async def platform_list_staff_sessions(
    claims: dict = Depends(require_platform_permission("platform_users", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 88 S1 — active AuthSessions for platform staff (House ops)."""
    await platform_svc.ensure_platform_tenant(db)
    rows = (
        await db.execute(
            select(m.AuthSession, m.User)
            .join(m.User, m.User.id == m.AuthSession.user_id)
            .where(
                m.AuthSession.tenant_id == PLATFORM_TENANT_ID,
                m.AuthSession.revoked_at.is_(None),
            )
            .order_by(m.AuthSession.created_at.desc())
            .limit(200)
        )
    ).all()
    return env(
        [
            {
                "id": s.id,
                "user_id": s.user_id,
                "email": u.email,
                "full_name": u.full_name,
                "jti": s.jti,
                "ip_address": s.ip_address,
                "user_agent": s.user_agent,
                "expires_at": s.expires_at,
                "created_at": s.created_at,
                "current": s.jti == claims.get("jti"),
            }
            for s, u in rows
        ]
    )


@router.get("/users/sessions/export")
async def platform_users_sessions_export(
    claims: dict = Depends(require_platform_permission("platform_users", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 149 S1 — platform staff sessions CSV (no refresh-token secrets / no jti)."""
    text = await platform_staff_export_svc.export_platform_sessions_csv(
        db, current_jti=claims.get("jti")
    )
    return Response(
        content=text,
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="platform_staff_sessions_export.csv"'
        },
    )


@router.delete("/users/sessions/{session_id}")
async def platform_revoke_staff_session(
    session_id: str,
    request: Request,
    claims: dict = Depends(require_platform_permission("platform_users", "write")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 88 S1 — revoke a platform staff AuthSession."""
    if claims.get("role") != PLATFORM_SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Only platform_super_admin can revoke staff sessions")
    session = (
        await db.execute(
            select(m.AuthSession).where(
                m.AuthSession.id == session_id,
                m.AuthSession.tenant_id == PLATFORM_TENANT_ID,
            )
        )
    ).scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.revoked_at is None:
        session.revoked_at = datetime.utcnow()
    ip, ua = _client_meta(request)
    await audit.record_event(
        db,
        tenant_id=PLATFORM_TENANT_ID,
        user_id=claims.get("sub"),
        action="platform.user.session_revoke",
        entity="auth_session",
        entity_id=session.id,
        details={"target_user_id": session.user_id, "jti": session.jti},
        ip_address=ip,
        user_agent=ua,
        module="platform_users",
    )
    await db.commit()
    return env({"id": session.id, "revoked": True}, message="session revoked")


@router.post("/users")
async def platform_create_user(
    payload: PlatformUserCreate,
    request: Request,
    claims: dict = Depends(require_platform_permission("platform_users", "write")),
    db: AsyncSession = Depends(get_db),
):
    """Create platform staff; omit password to invite via set-password email (Stage 88 S1)."""
    if claims.get("role") != PLATFORM_SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Only platform_super_admin can create platform users")
    role = (payload.role or "").strip()
    if role not in PLATFORM_ROLES:
        raise HTTPException(
            status_code=400,
            detail=f"role must be one of: {sorted(PLATFORM_ROLES)}",
        )
    invite_by_email = not (payload.password and str(payload.password).strip())
    if invite_by_email:
        password = secrets.token_urlsafe(18) + "Aa1!"
    else:
        password = str(payload.password)
    validate_password_strength(password)
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
        password_hash=hash_password(password),
        role=role,
        permissions=permissions_for_role(role),
        email_verified=True,
        is_active=True,
        totp_enabled=False,
    )
    db.add(user)
    await db.flush()
    reset_token: str | None = None
    if invite_by_email:
        raw, token_hash, expires = issue_one_time_token()
        db.add(
            m.AuthToken(
                tenant_id=PLATFORM_TENANT_ID,
                user_id=user.id,
                purpose="password_reset",
                token_hash=token_hash,
                expires_at=expires,
            )
        )
        reset_token = raw
    ip, ua = _client_meta(request)
    await audit.record_event(
        db,
        tenant_id=PLATFORM_TENANT_ID,
        user_id=claims.get("sub"),
        action="platform.user.create",
        entity="user",
        entity_id=user.id,
        details={
            "email": user.email,
            "role": user.role,
            "invite_by_email": invite_by_email,
        },
        ip_address=ip,
        user_agent=ua,
        module="platform_users",
    )
    await db.commit()
    data: dict[str, Any] = {**serialize_user(user), "invite_by_email": invite_by_email}
    if invite_by_email and reset_token:
        from app import emailer

        email_result = await emailer.send_password_reset_email(to=user.email, token=reset_token)
        await platform_svc.record_platform_email_delivery(
            db,
            actor_user_id=claims.get("sub"),
            purpose="password_reset",
            recipient=user.email,
            related_action="platform.user.create",
            email_result=email_result,
            extra={"invite_by_email": True, "user_id": user.id},
            ip_address=ip,
            user_agent=ua,
        )
        await db.commit()
        data["email_delivery"] = {
            "sent": email_result.sent,
            "mode": email_result.mode,
            "error": email_result.error,
            "fabricated_success": False,
        }
        if settings.DEBUG or settings.APP_ENV.lower() != "production":
            data["reset_token"] = reset_token
        invite_msg = (
            "Invite email sent"
            if email_result.sent
            else (
                f"Invite email not sent (mode: {email_result.mode or 'n/a'}"
                f"{f'; error: {email_result.error}' if email_result.error else ''})"
            )
        )
        return env(data, message=invite_msg)
    return env(
        data,
        message="platform user invited" if invite_by_email else "platform user created",
    )


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


@router.post("/users/{user_id}/password-reset-email")
async def platform_password_reset_email(
    user_id: str,
    request: Request,
    claims: dict = Depends(require_platform_permission("platform_users", "write")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 86 E1 — House admin-initiated email password reset for platform staff."""
    await platform_svc.ensure_platform_tenant(db)
    user = await db.get(m.User, user_id)
    if not user or user.tenant_id != PLATFORM_TENANT_ID:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Cannot email reset for inactive user")
    raw, token_hash, expires = issue_one_time_token()
    db.add(
        m.AuthToken(
            tenant_id=PLATFORM_TENANT_ID,
            user_id=user.id,
            purpose="password_reset",
            token_hash=token_hash,
            expires_at=expires,
        )
    )
    ip, ua = _client_meta(request)
    await audit.record_event(
        db,
        tenant_id=PLATFORM_TENANT_ID,
        user_id=claims.get("sub"),
        action="platform.user.password_reset_email",
        entity="user",
        entity_id=user.id,
        details={"email": user.email, "initiated_by": claims.get("sub")},
        ip_address=ip,
        user_agent=ua,
        module="platform_users",
    )
    await db.commit()
    from app import emailer

    email_result = await emailer.send_password_reset_email(to=user.email, token=raw)
    await platform_svc.record_platform_email_delivery(
        db,
        actor_user_id=claims.get("sub"),
        purpose="password_reset",
        recipient=user.email,
        related_action="platform.user.password_reset_email",
        email_result=email_result,
        extra={"user_id": user.id},
        ip_address=ip,
        user_agent=ua,
    )
    await db.commit()
    data: dict[str, Any] = {
        "user_id": user.id,
        "email": user.email,
        "email_delivery": {
            "sent": email_result.sent,
            "mode": email_result.mode,
            "error": email_result.error,
        },
    }
    if settings.DEBUG or settings.APP_ENV.lower() != "production":
        data["reset_token"] = raw
    return env(data, "Password reset email issued")


@router.get("/health")
async def platform_health(
    claims: dict = Depends(require_platform_permission("platform_health", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Deep health + Stage 90 O1 operator support contacts from platform settings.

    Stage 92 K1: protected CORS allowlist detail (not exposed on public /health).
    """
    report, _status = await health_svc.assemble_health(deep=True)
    await platform_svc.ensure_platform_tenant(db)
    platform_tenant = await db.get(m.Tenant, PLATFORM_TENANT_ID)
    report["operator_contacts"] = {
        "support_email": getattr(platform_tenant, "email", None) if platform_tenant else None,
        "support_phone": getattr(platform_tenant, "phone", None) if platform_tenant else None,
        "company_name": getattr(platform_tenant, "company_name", None) if platform_tenant else None,
    }
    report["security"] = _platform_security_detail()
    report["house_runtime"] = _house_runtime(platform_tenant)
    report["runtime_identity"] = _runtime_identity()
    return env(report)


@router.get("/health/export")
async def platform_health_export(
    claims: dict = Depends(require_platform_permission("platform_health", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 151 H1 — platform health checks CSV (operator posture; not go-live Complete)."""
    report, _status = await health_svc.assemble_health(deep=True)
    await platform_svc.ensure_platform_tenant(db)
    platform_tenant = await db.get(m.Tenant, PLATFORM_TENANT_ID)
    operator_contacts = {
        "support_email": getattr(platform_tenant, "email", None) if platform_tenant else None,
        "support_phone": getattr(platform_tenant, "phone", None) if platform_tenant else None,
        "company_name": getattr(platform_tenant, "company_name", None) if platform_tenant else None,
    }
    security = _platform_security_detail()
    house_runtime = _house_runtime(platform_tenant)
    runtime_identity = _runtime_identity()
    report["operator_contacts"] = operator_contacts
    report["security"] = security
    report["house_runtime"] = house_runtime
    report["runtime_identity"] = runtime_identity
    report["generated_at"] = datetime.utcnow().isoformat() + "Z"
    text = platform_ops_export_svc.export_platform_health_csv(
        health_payload=report,
        operator_contacts=operator_contacts,
        security=security,
        house_runtime=house_runtime,
        runtime_identity=runtime_identity,
    )
    return Response(
        content=text,
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="platform_health_export.csv"'
        },
    )


async def _platform_audit_list_payload(
    db: AsyncSession,
    *,
    limit: int,
    offset: int,
    module: str | None,
    action: str | None,
    delivery_only: bool,
    from_date: str | None,
    to_date: str | None,
    default_recent_days: int | None = None,
) -> dict[str, Any]:
    """Shared Audit/Activity list (Stage 91 I1 date-range investigation)."""
    action_filter = (action or "").strip() or None
    module_filter = (module or "").strip() or None
    if delivery_only:
        action_filter = "platform.email.delivery"
        module_filter = module_filter or "platform_email"
    parsed_from = reports_svc.parse_date(from_date)
    parsed_to = reports_svc.parse_date(to_date, end_of_day=True)
    default_applied = False
    if parsed_from is None and default_recent_days is not None:
        parsed_from = datetime.utcnow() - timedelta(days=int(default_recent_days))
        default_applied = True
    rows = await audit.query_logs(
        db,
        tenant_id=PLATFORM_TENANT_ID,
        module=module_filter,
        action=action_filter,
        from_date=parsed_from,
        to_date=parsed_to,
        limit=min(limit + offset, 1000),
    )
    sliced = rows[offset : offset + limit]
    items = [audit.serialize_audit(r) for r in sliced]
    return {
        "items": items,
        "total": len(rows),
        "limit": limit,
        "offset": offset,
        "filters": {
            "module": module_filter,
            "action": action_filter,
            "delivery_only": delivery_only,
            "from_date": from_date,
            "to_date": to_date,
            "default_recent_days": default_recent_days if default_applied else None,
            "effective_from": parsed_from.isoformat() + "Z" if parsed_from else None,
            "effective_to": parsed_to.isoformat() + "Z" if parsed_to else None,
        },
    }


@router.get("/audit")
async def platform_audit(
    claims: dict = Depends(require_platform_permission("platform_audit", "read")),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    module: str | None = Query(None),
    action: str | None = Query(None),
    delivery_only: bool = Query(False),
    from_date: str | None = Query(None),
    to_date: str | None = Query(None),
):
    """Stage 86 A1 — platform audit with optional module/action filters.

    Stage 90 E1: ``delivery_only`` filters to ``platform.email.delivery`` events.
    Stage 91 I1: ``from_date`` / ``to_date`` investigation window.
    """
    return env(
        await _platform_audit_list_payload(
            db,
            limit=limit,
            offset=offset,
            module=module,
            action=action,
            delivery_only=delivery_only,
            from_date=from_date,
            to_date=to_date,
        )
    )


@router.get("/activity")
async def platform_activity_alias(
    claims: dict = Depends(require_platform_permission("platform_audit", "read")),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    module: str | None = Query(None),
    action: str | None = Query(None),
    delivery_only: bool = Query(False),
    from_date: str | None = Query(None),
    to_date: str | None = Query(None),
):
    """Stage 86 A1 — Activity alias for Platform Audit (parity with tenant /activity).

    Stage 91 I1: defaults to a recent 7-day window when ``from_date`` is omitted.
    """
    data = await _platform_audit_list_payload(
        db,
        limit=limit,
        offset=offset,
        module=module,
        action=action,
        delivery_only=delivery_only,
        from_date=from_date,
        to_date=to_date,
        default_recent_days=7,
    )
    data["alias_of"] = "/platform/audit"
    return env(data)


@router.get("/audit/export")
async def platform_audit_export(
    claims: dict = Depends(require_platform_permission("platform_audit", "read")),
    db: AsyncSession = Depends(get_db),
    module: str | None = Query(None),
    action: str | None = Query(None),
    from_date: str | None = Query(None),
    to_date: str | None = Query(None),
    delivery_only: bool = Query(False),
    format: str = Query("csv"),
):
    """Stage 87 X1 — export platform-tenant audit logs (csv/pdf).

    Stage 92 B1: ``delivery_only`` matches list-filter semantics.
    """
    action_filter = (action or "").strip() or None
    module_filter = (module or "").strip() or None
    if delivery_only:
        action_filter = "platform.email.delivery"
        module_filter = module_filter or "platform_email"
    rows = await audit.query_logs(
        db,
        tenant_id=PLATFORM_TENANT_ID,
        module=module_filter,
        action=action_filter,
        from_date=reports_svc.parse_date(from_date),
        to_date=reports_svc.parse_date(to_date, end_of_day=True),
        limit=1000,
    )
    chronological = list(reversed(rows))
    fmt = (format or "csv").strip().lower()
    if fmt == "pdf":
        pdf_bytes = audit.to_pdf(chronological)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=platform-audit-logs.pdf"},
        )
    if fmt != "csv":
        raise HTTPException(status_code=400, detail="format must be csv or pdf")
    csv_text = audit.to_csv(chronological)
    return PlainTextResponse(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=platform-audit-logs.csv"},
    )


@router.get("/audit/verify")
async def platform_audit_verify(
    claims: dict = Depends(require_platform_permission("platform_audit", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 87 X1 — verify integrity chain for platform-tenant audit logs."""
    return env(await audit.verify_chain(db, PLATFORM_TENANT_ID))


@router.get("/evidence")
async def platform_operator_evidence(
    claims: dict = Depends(require_platform_permission("platform_health", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 91 P1 — operator evidence pack (packaging honesty only).

    Not §§1–3 verified, §7 signed, or live go-live Complete.
    """
    report, _status = await health_svc.assemble_health(deep=True)
    await platform_svc.ensure_platform_tenant(db)
    platform_tenant = await db.get(m.Tenant, PLATFORM_TENANT_ID)
    report["security"] = _platform_security_detail()
    report["runtime_identity"] = _runtime_identity()
    identity = _runtime_identity()
    return env(
        {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "packaging_only": True,
            "note": (
                "Operator evidence pack for Ribdigi House — packaging honesty only; "
                "not sections 1–3 verified, section 7 signed, or go-live Complete."
            ),
            "house": {
                "tenant_id": PLATFORM_TENANT_ID,
                "company_name": getattr(platform_tenant, "company_name", None)
                if platform_tenant
                else None,
                "support_email": getattr(platform_tenant, "email", None)
                if platform_tenant
                else None,
                **_house_runtime(platform_tenant),
            },
            "house_runtime": _house_runtime(platform_tenant),
            "runtime_identity": identity,
            "health": report,
            "security": _platform_security_detail(),
            "honesty_flags": {
                "mrr_fabricated_claimed": False,
                "billing_complete_claimed": False,
                "subscriptions_live_claimed": False,
                "user_store_membership_claimed": False,
                "hard_delete_claimed": False,
                "sections_1_3_verified": False,
                "section_7_signed": False,
                "go_live_claimed": False,
                "attestation_claimed": False,
            },
        }
    )


@router.get("/evidence/export")
async def platform_operator_evidence_export(
    claims: dict = Depends(require_platform_permission("platform_health", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 151 E1 — operator evidence CSV (packaging honesty only; not go-live Complete)."""
    report, _status = await health_svc.assemble_health(deep=True)
    await platform_svc.ensure_platform_tenant(db)
    platform_tenant = await db.get(m.Tenant, PLATFORM_TENANT_ID)
    report["security"] = _platform_security_detail()
    report["runtime_identity"] = _runtime_identity()
    identity = _runtime_identity()
    evidence = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "packaging_only": True,
        "note": (
            "Operator evidence pack for Ribdigi House — packaging honesty only; "
            "not sections 1–3 verified, section 7 signed, or go-live Complete."
        ),
        "house": {
            "tenant_id": PLATFORM_TENANT_ID,
            "company_name": getattr(platform_tenant, "company_name", None)
            if platform_tenant
            else None,
            "support_email": getattr(platform_tenant, "email", None)
            if platform_tenant
            else None,
            **_house_runtime(platform_tenant),
        },
        "house_runtime": _house_runtime(platform_tenant),
        "runtime_identity": identity,
        "health": report,
        "security": _platform_security_detail(),
        "honesty_flags": {
            "mrr_fabricated_claimed": False,
            "billing_complete_claimed": False,
            "subscriptions_live_claimed": False,
            "user_store_membership_claimed": False,
            "hard_delete_claimed": False,
            "sections_1_3_verified": False,
            "section_7_signed": False,
            "go_live_claimed": False,
            "attestation_claimed": False,
        },
    }
    text = platform_ops_export_svc.export_platform_evidence_csv(evidence=evidence)
    return Response(
        content=text,
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="platform_evidence_export.csv"'
        },
    )
