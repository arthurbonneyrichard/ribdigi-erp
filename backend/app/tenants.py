"""Tenant lifecycle: profile, suspend, activate, trial/grace, isolation helpers."""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.config import settings
from app.document_numbering import normalize_document_numbering, preview_document_numbering, merge_document_numbering

VALID_STATUSES = frozenset({"trial", "active", "grace", "suspended"})
VALID_INDUSTRIES = frozenset(
    {"retail", "pharmacy", "restaurant", "bakery", "wholesale", "manufacturing", "mart"}
)
TRIAL_REMINDER_DAYS = (7, 3, 1)


def default_trial_ends_at(from_dt: datetime | None = None) -> datetime:
    base = from_dt or datetime.utcnow()
    days = max(1, int(settings.TRIAL_DAYS))
    return base + timedelta(days=days)


def calendar_days_until(when: datetime | None, *, now: datetime | None = None) -> int | None:
    if when is None:
        return None
    now = now or datetime.utcnow()
    return (when.date() - now.date()).days


def is_read_only(tenant: m.Tenant) -> bool:
    return tenant.status == "grace"


def serialize_tenant(tenant: m.Tenant) -> dict:
    now = datetime.utcnow()
    days_left = None
    if tenant.status == "trial":
        days_left = calendar_days_until(tenant.trial_ends_at, now=now)
    elif tenant.status == "grace":
        days_left = calendar_days_until(tenant.grace_ends_at, now=now)
    return {
        "id": tenant.id,
        "slug": tenant.slug,
        "company_name": tenant.company_name,
        "industry": tenant.industry,
        "currency": tenant.currency,
        "tax_jurisdiction": getattr(tenant, "tax_jurisdiction", None) or "GH",
        "tax_registration_number": getattr(tenant, "tax_registration_number", None),
        "tax_filing_period": getattr(tenant, "tax_filing_period", None) or "monthly",
        "status": tenant.status,
        "phone": tenant.phone,
        "email": tenant.email,
        "website": tenant.website,
        "address": tenant.address,
        "timezone": tenant.timezone or "Africa/Accra",
        "fiscal_year_start": tenant.fiscal_year_start or "01-01",
        "expense_approval_threshold": float(tenant.expense_approval_threshold or 0),
        "expense_l2_threshold": float(getattr(tenant, "expense_l2_threshold", None) or 1000),
        "expense_approval_matrix": getattr(tenant, "expense_approval_matrix", None),
        "purchase_request_approval_matrix": getattr(
            tenant, "purchase_request_approval_matrix", None
        ),
        "early_pay_discount_pct": float(getattr(tenant, "early_pay_discount_pct", None) or 0),
        "early_pay_discount_days": int(getattr(tenant, "early_pay_discount_days", None) or 0),
        "fefo_strict_warehouse": bool(getattr(tenant, "fefo_strict_warehouse", False)),
        "trial_ends_at": tenant.trial_ends_at,
        "grace_ends_at": tenant.grace_ends_at,
        "days_remaining": days_left,
        "read_only": is_read_only(tenant),
        "trial_days": int(settings.TRIAL_DAYS),
        "grace_days": int(settings.TRIAL_GRACE_DAYS),
        "logo_url": tenant.logo_url,
        "has_logo": bool(tenant.logo_url),
        "document_numbering": normalize_document_numbering(
            getattr(tenant, "document_numbering", None)
        ),
        "document_numbering_preview": preview_document_numbering(
            getattr(tenant, "document_numbering", None)
        ),
        "suspended_at": tenant.suspended_at,
        "suspended_reason": tenant.suspended_reason,
        "created_at": tenant.created_at,
    }


async def get_tenant(db: AsyncSession, tenant_id: str) -> m.Tenant:
    tenant = await db.get(m.Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


async def resolve_tenant(db: AsyncSession, tenant_ref: str) -> m.Tenant:
    tenant = (
        await db.execute(
            select(m.Tenant).where((m.Tenant.id == tenant_ref) | (m.Tenant.slug == tenant_ref))
        )
    ).scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


def assert_tenant_active_for_login(tenant: m.Tenant) -> None:
    if tenant.status == "suspended":
        raise HTTPException(status_code=403, detail="Tenant is suspended")


def assert_writable(claims: dict) -> None:
    if claims.get("read_only"):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "TENANT_READ_ONLY",
                "message": "Trial expired; account is read-only during the grace period. Activate to restore write access.",
            },
        )


async def revoke_all_sessions(db: AsyncSession, tenant_id: str) -> int:
    rows = (
        await db.execute(
            select(m.AuthSession).where(
                m.AuthSession.tenant_id == tenant_id,
                m.AuthSession.revoked_at.is_(None),
            )
        )
    ).scalars().all()
    now = datetime.utcnow()
    for session in rows:
        session.revoked_at = now
    await db.flush()
    return len(rows)


async def suspend_tenant(
    db: AsyncSession,
    tenant: m.Tenant,
    *,
    reason: str | None = None,
) -> m.Tenant:
    if tenant.status == "suspended":
        raise HTTPException(status_code=400, detail="Tenant is already suspended")
    tenant.status = "suspended"
    tenant.suspended_at = datetime.utcnow()
    tenant.suspended_reason = (reason or "").strip() or None
    tenant.grace_ends_at = None
    await revoke_all_sessions(db, tenant.id)
    await db.flush()
    return tenant


async def enter_grace(db: AsyncSession, tenant: m.Tenant, *, now: datetime | None = None) -> m.Tenant:
    now = now or datetime.utcnow()
    if tenant.status == "grace":
        return tenant
    if tenant.status not in {"trial"}:
        raise HTTPException(status_code=400, detail=f"Cannot enter grace from status {tenant.status}")
    grace_days = max(1, int(settings.TRIAL_GRACE_DAYS))
    tenant.status = "grace"
    tenant.grace_ends_at = now + timedelta(days=grace_days)
    notices = dict(tenant.trial_notices or {})
    notices["grace_entered"] = now.isoformat()
    tenant.trial_notices = notices
    await db.flush()
    return tenant


async def activate_tenant(db: AsyncSession, tenant: m.Tenant) -> m.Tenant:
    if tenant.status == "active":
        raise HTTPException(status_code=400, detail="Tenant is already active")
    if tenant.status not in {"suspended", "trial", "grace"}:
        raise HTTPException(status_code=400, detail=f"Cannot activate from status {tenant.status}")
    tenant.status = "active"
    tenant.suspended_at = None
    tenant.suspended_reason = None
    tenant.grace_ends_at = None
    await db.flush()
    return tenant


async def ensure_trial_state(db: AsyncSession, tenant: m.Tenant) -> m.Tenant:
    """Apply overdue trial→grace or grace→suspend transitions (idempotent)."""
    now = datetime.utcnow()
    if tenant.status == "trial" and tenant.trial_ends_at and tenant.trial_ends_at <= now:
        await enter_grace(db, tenant, now=now)
    if tenant.status == "grace" and tenant.grace_ends_at and tenant.grace_ends_at <= now:
        await suspend_tenant(db, tenant, reason="Trial grace period ended")
    return tenant


async def notify_trial_event(
    db: AsyncSession,
    tenant: m.Tenant,
    *,
    title: str,
    message: str,
) -> None:
    from app import notifications as notifications_svc

    await notifications_svc.create_notification(
        db,
        tenant_id=tenant.id,
        category="billing",
        title=title,
        message=message,
        entity_type="tenant",
        entity_id=tenant.id,
    )


async def process_trial_lifecycle(db: AsyncSession) -> dict:
    """Scan all tenants: reminders, enter grace, end grace → suspend."""
    now = datetime.utcnow()
    reminded = 0
    entered_grace = 0
    suspended = 0

    tenants = (await db.execute(select(m.Tenant))).scalars().all()
    for tenant in tenants:
        if tenant.status == "trial":
            if tenant.trial_ends_at and tenant.trial_ends_at <= now:
                await enter_grace(db, tenant, now=now)
                entered_grace += 1
                await notify_trial_event(
                    db,
                    tenant,
                    title="Trial ended — grace period started",
                    message=(
                        f"Your trial for {tenant.company_name} has ended. "
                        f"The account is read-only until "
                        f"{tenant.grace_ends_at.isoformat() if tenant.grace_ends_at else 'grace ends'}. "
                        "Activate to restore full access."
                    ),
                )
                continue

            days_left = calendar_days_until(tenant.trial_ends_at, now=now)
            if days_left is None or days_left not in TRIAL_REMINDER_DAYS:
                continue
            key = str(days_left)
            notices = dict(tenant.trial_notices or {})
            if notices.get(key):
                continue
            await notify_trial_event(
                db,
                tenant,
                title=f"Trial ends in {days_left} day{'s' if days_left != 1 else ''}",
                message=(
                    f"Your RIBDIGI trial for {tenant.company_name} ends on "
                    f"{tenant.trial_ends_at.isoformat() if tenant.trial_ends_at else 'soon'}. "
                    "Activate your company to keep write access after the trial."
                ),
            )
            notices[key] = now.isoformat()
            tenant.trial_notices = notices
            reminded += 1
            await db.flush()

        elif tenant.status == "grace":
            if tenant.grace_ends_at and tenant.grace_ends_at <= now:
                await suspend_tenant(db, tenant, reason="Trial grace period ended")
                suspended += 1

    return {
        "reminded": reminded,
        "entered_grace": entered_grace,
        "suspended": suspended,
        "scanned": len(tenants),
    }


async def update_profile(
    db: AsyncSession,
    tenant: m.Tenant,
    *,
    company_name: str | None = None,
    industry: str | None = None,
    currency: str | None = None,
    phone: str | None = None,
    email: str | None = None,
    website: str | None = None,
    address: str | None = None,
    timezone: str | None = None,
    fiscal_year_start: str | None = None,
    tax_jurisdiction: str | None = None,
    tax_registration_number: str | None = None,
    tax_filing_period: str | None = None,
    document_numbering: dict | None = None,
) -> m.Tenant:
    if company_name is not None:
        name = company_name.strip()
        if len(name) < 2:
            raise HTTPException(status_code=400, detail="company_name is required")
        tenant.company_name = name
    if industry is not None:
        ind = industry.strip().lower()
        if ind not in VALID_INDUSTRIES:
            raise HTTPException(
                status_code=400,
                detail=f"industry must be one of: {sorted(VALID_INDUSTRIES)}",
            )
        tenant.industry = ind
    if currency is not None:
        cur = currency.strip().upper()
        if len(cur) < 3 or len(cur) > 10:
            raise HTTPException(status_code=400, detail="Invalid currency")
        tenant.currency = cur
    if phone is not None:
        tenant.phone = phone.strip() or None
    if email is not None:
        tenant.email = email.strip() or None
    if website is not None:
        tenant.website = website.strip() or None
    if address is not None:
        tenant.address = address.strip() or None
    if timezone is not None:
        tz = timezone.strip()
        if not tz:
            raise HTTPException(status_code=400, detail="timezone is required")
        tenant.timezone = tz
    if fiscal_year_start is not None:
        fys = fiscal_year_start.strip()
        if len(fys) != 5 or fys[2] != "-":
            raise HTTPException(status_code=400, detail="fiscal_year_start must be MM-DD")
        tenant.fiscal_year_start = fys
    if tax_jurisdiction is not None:
        juris = tax_jurisdiction.strip().upper()
        if len(juris) < 2 or len(juris) > 10:
            raise HTTPException(status_code=400, detail="Invalid tax_jurisdiction")
        tenant.tax_jurisdiction = juris
    if tax_registration_number is not None:
        tin = tax_registration_number.strip()
        tenant.tax_registration_number = tin or None
    if tax_filing_period is not None:
        period = tax_filing_period.strip().lower()
        if period not in {"monthly", "quarterly"}:
            raise HTTPException(status_code=400, detail="tax_filing_period must be monthly or quarterly")
        tenant.tax_filing_period = period
    if document_numbering is not None:
        tenant.document_numbering = merge_document_numbering(
            getattr(tenant, "document_numbering", None), document_numbering
        )
    await db.flush()
    return tenant


async def list_tenants(db: AsyncSession, *, status: str | None = None, limit: int = 100) -> list[m.Tenant]:
    q = select(m.Tenant).order_by(m.Tenant.created_at.desc()).limit(min(max(limit, 1), 500))
    if status:
        if status not in VALID_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid status filter")
        q = q.where(m.Tenant.status == status)
    return list((await db.execute(q)).scalars().all())


async def ensure_tenant_owns(
    db: AsyncSession,
    model: type,
    *,
    tenant_id: str,
    entity_id: str,
    not_found: str = "Resource not found",
):
    """Load a tenant-scoped row or raise 404 (never leak cross-tenant existence)."""
    row = await db.get(model, entity_id)
    if not row or getattr(row, "tenant_id", None) != tenant_id:
        raise HTTPException(status_code=404, detail=not_found)
    return row
