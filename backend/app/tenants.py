"""Tenant lifecycle: profile, suspend, activate, trial/grace, isolation helpers."""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.config import settings
from app.document_numbering import (
    normalize_document_numbering,
    preview_document_numbering,
    merge_document_numbering,
    numbering_source_for_serialize,
)
from app.platform_const import PLATFORM_TENANT_ID

VALID_STATUSES = frozenset({"trial", "active", "grace", "suspended"})
VALID_PLAN_CODES = frozenset({"trial", "starter", "growth", "enterprise"})
VALID_INDUSTRIES = frozenset(
    {"retail", "pharmacy", "restaurant", "bakery", "wholesale", "manufacturing", "mart"}
)
TRIAL_REMINDER_DAYS = (7, 3, 1)

# Stage 89 C1 — commercial metadata catalog only (no prices / checkout / fabricated MRR).
PLAN_CATALOG: dict[str, dict] = {
    "trial": {
        "code": "trial",
        "label": "Trial",
        "blurb": "Evaluation window for new customer tenants.",
        "soft_limits": {"stores": 1, "users": 5},
    },
    "starter": {
        "code": "starter",
        "label": "Starter",
        "blurb": "Single-location retail operations metadata tier.",
        "soft_limits": {"stores": 2, "users": 15},
    },
    "growth": {
        "code": "growth",
        "label": "Growth",
        "blurb": "Multi-store growth metadata tier.",
        "soft_limits": {"stores": 10, "users": 50},
    },
    "enterprise": {
        "code": "enterprise",
        "label": "Enterprise",
        "blurb": "Large-org metadata tier (limits negotiated offline).",
        "soft_limits": {"stores": None, "users": None},
    },
}


def plan_catalog_items() -> list[dict]:
    return [dict(PLAN_CATALOG[code]) for code in sorted(VALID_PLAN_CODES)]


def industry_catalog_items() -> list[dict]:
    """Stage 93 M1 — canonical industry catalog for House roster filters/provisioning."""
    return [{"code": code, "label": code.replace("_", " ").title()} for code in sorted(VALID_INDUSTRIES)]


def assert_mutable_customer_tenant(tenant: m.Tenant) -> None:
    """Refuse lifecycle mutations against the reserved Ribdigi House tenant (ADR-137)."""
    if tenant.id == PLATFORM_TENANT_ID or (tenant.slug or "") == PLATFORM_TENANT_ID:
        raise HTTPException(
            status_code=400,
            detail="Cannot suspend or alter lifecycle of the Ribdigi House platform tenant",
        )


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


def serialize_tenant(tenant: m.Tenant, *, company: m.Company | None = None) -> dict:
    numbering_raw = numbering_source_for_serialize(tenant, company)
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
        "plan_code": getattr(tenant, "plan_code", None) or "trial",
        "billing_deferred": True,
        "billing_provider": None,
        "plan_codes": sorted(VALID_PLAN_CODES),
        "legal_name": getattr(tenant, "legal_name", None),
        "registration_number": getattr(tenant, "registration_number", None),
        "phone": tenant.phone,
        "email": tenant.email,
        "website": tenant.website,
        "address": tenant.address,
        "billing_address": getattr(tenant, "billing_address", None),
        "shipping_address": getattr(tenant, "shipping_address", None),
        "warehouse_address": getattr(tenant, "warehouse_address", None),
        "contact_person_name": getattr(tenant, "contact_person_name", None),
        "contact_person_email": getattr(tenant, "contact_person_email", None),
        "contact_person_phone": getattr(tenant, "contact_person_phone", None),
        "inactivity_timeout_minutes": int(getattr(tenant, "inactivity_timeout_minutes", None) or 30),
        "date_format": getattr(tenant, "date_format", None) or "DD/MM/YYYY",
        "number_format": getattr(tenant, "number_format", None) or "1,234.56",
        "time_format": getattr(tenant, "time_format", None) or "24h",
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
        "document_numbering": normalize_document_numbering(numbering_raw),
        "document_numbering_preview": preview_document_numbering(numbering_raw),
        "document_numbering_scope": "company" if company is not None else "tenant",
        "document_numbering_company_id": company.id if company is not None else None,
        "invoice_print_template": getattr(tenant, "invoice_print_template", None) or "a4",
        "receipt_print_template": getattr(tenant, "receipt_print_template", None) or "thermal_80",
        "document_header": getattr(tenant, "document_header", None),
        "document_footer": getattr(tenant, "document_footer", None),
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
    assert_mutable_customer_tenant(tenant)
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
    if tenant.id == PLATFORM_TENANT_ID:
        return tenant
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
    assert_mutable_customer_tenant(tenant)
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


async def extend_trial(
    db: AsyncSession,
    tenant: m.Tenant,
    *,
    days: int,
    now: datetime | None = None,
) -> m.Tenant:
    """House ops: extend or reopen trial window (metadata lifecycle — not paid billing)."""
    assert_mutable_customer_tenant(tenant)
    days = int(days)
    if days < 1 or days > 365:
        raise HTTPException(status_code=400, detail="extend_trial_days must be between 1 and 365")
    now = now or datetime.utcnow()
    base = tenant.trial_ends_at or now
    if base < now:
        base = now
    tenant.trial_ends_at = base + timedelta(days=days)
    # Returning to trial from grace/suspended is an operator lifecycle action (not checkout).
    if tenant.status in {"grace", "suspended", "trial"}:
        tenant.status = "trial"
        tenant.suspended_at = None
        tenant.suspended_reason = None
        tenant.grace_ends_at = None
    elif tenant.status == "active":
        # Keep active; only push trial_ends_at for roster visibility / future grace.
        pass
    else:
        raise HTTPException(status_code=400, detail=f"Cannot extend trial from status {tenant.status}")
    await db.flush()
    return tenant


async def ensure_trial_state(db: AsyncSession, tenant: m.Tenant) -> m.Tenant:
    """Apply overdue trial→grace or grace→suspend transitions (idempotent)."""
    if tenant.id == PLATFORM_TENANT_ID:
        # Platform tenant must remain operable for Ribdigi House staff (ADR-137).
        if tenant.status != "active":
            tenant.status = "active"
            tenant.suspended_at = None
            tenant.suspended_reason = None
            tenant.grace_ends_at = None
            await db.flush()
        return tenant
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
    document_numbering_company: m.Company | None = None,
    invoice_print_template: str | None = None,
    receipt_print_template: str | None = None,
    document_header: str | None = None,
    document_footer: str | None = None,
    plan_code: str | None = None,
    legal_name: str | None = None,
    registration_number: str | None = None,
    billing_address: str | None = None,
    shipping_address: str | None = None,
    warehouse_address: str | None = None,
    contact_person_name: str | None = None,
    contact_person_email: str | None = None,
    contact_person_phone: str | None = None,
    inactivity_timeout_minutes: int | None = None,
    date_format: str | None = None,
    number_format: str | None = None,
    time_format: str | None = None,
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
        if document_numbering_company is not None:
            # Seed from tenant if company series empty so merges preserve counters.
            existing = getattr(document_numbering_company, "document_numbering", None)
            if not existing:
                existing = getattr(tenant, "document_numbering", None)
            document_numbering_company.document_numbering = merge_document_numbering(
                existing, document_numbering
            )
        else:
            tenant.document_numbering = merge_document_numbering(
                getattr(tenant, "document_numbering", None), document_numbering
            )
    if invoice_print_template is not None:
        from app.sales import INVOICE_PRINT_TEMPLATES

        tpl = invoice_print_template.strip().lower()
        if tpl not in INVOICE_PRINT_TEMPLATES:
            raise HTTPException(
                status_code=400,
                detail=f"invoice_print_template must be one of: {sorted(INVOICE_PRINT_TEMPLATES)}",
            )
        tenant.invoice_print_template = tpl
    if receipt_print_template is not None:
        from app.receipts import RECEIPT_PRINT_TEMPLATES

        rtpl = receipt_print_template.strip().lower()
        if rtpl not in RECEIPT_PRINT_TEMPLATES:
            raise HTTPException(
                status_code=400,
                detail=f"receipt_print_template must be one of: {sorted(RECEIPT_PRINT_TEMPLATES)}",
            )
        tenant.receipt_print_template = rtpl
    if document_header is not None:
        header = document_header.strip()
        if len(header) > 500:
            raise HTTPException(status_code=400, detail="document_header must be at most 500 characters")
        tenant.document_header = header or None
    if document_footer is not None:
        footer = document_footer.strip()
        if len(footer) > 500:
            raise HTTPException(status_code=400, detail="document_footer must be at most 500 characters")
        tenant.document_footer = footer or None
    if plan_code is not None:
        plan = plan_code.strip().lower()
        if plan not in VALID_PLAN_CODES:
            raise HTTPException(
                status_code=400,
                detail=f"plan_code must be one of: {sorted(VALID_PLAN_CODES)}",
            )
        tenant.plan_code = plan
    if legal_name is not None:
        tenant.legal_name = legal_name.strip() or None
    if registration_number is not None:
        tenant.registration_number = registration_number.strip() or None
    if billing_address is not None:
        tenant.billing_address = billing_address.strip() or None
    if shipping_address is not None:
        tenant.shipping_address = shipping_address.strip() or None
    if warehouse_address is not None:
        tenant.warehouse_address = warehouse_address.strip() or None
    if contact_person_name is not None:
        tenant.contact_person_name = contact_person_name.strip() or None
    if contact_person_email is not None:
        tenant.contact_person_email = contact_person_email.strip() or None
    if contact_person_phone is not None:
        tenant.contact_person_phone = contact_person_phone.strip() or None
    if inactivity_timeout_minutes is not None:
        minutes = int(inactivity_timeout_minutes)
        if minutes < 5 or minutes > 480:
            raise HTTPException(
                status_code=400,
                detail="inactivity_timeout_minutes must be between 5 and 480",
            )
        tenant.inactivity_timeout_minutes = minutes
    if date_format is not None:
        fmt = date_format.strip().upper()
        if fmt not in {"DD/MM/YYYY", "MM/DD/YYYY", "YYYY-MM-DD"}:
            raise HTTPException(
                status_code=400,
                detail="date_format must be one of: DD/MM/YYYY, MM/DD/YYYY, YYYY-MM-DD",
            )
        tenant.date_format = fmt
    if number_format is not None:
        nfmt = number_format.strip()
        if nfmt not in {"1,234.56", "1.234,56", "1 234.56"}:
            raise HTTPException(
                status_code=400,
                detail="number_format must be one of: 1,234.56, 1.234,56, 1 234.56",
            )
        tenant.number_format = nfmt
    if time_format is not None:
        tfmt = time_format.strip().lower()
        if tfmt not in {"24h", "12h"}:
            raise HTTPException(status_code=400, detail="time_format must be 24h or 12h")
        tenant.time_format = tfmt
    await db.flush()
    return tenant


VALID_DATE_FORMATS = frozenset({"DD/MM/YYYY", "MM/DD/YYYY", "YYYY-MM-DD"})
VALID_TIME_FORMATS = frozenset({"24h", "12h"})
VALID_NUMBER_FORMATS = frozenset({"1,234.56", "1.234,56", "1 234.56"})


async def update_smtp_settings(
    db: AsyncSession,
    tenant: m.Tenant,
    *,
    smtp_enabled: bool | None = None,
    smtp_host: str | None = None,
    smtp_port: int | None = None,
    smtp_username: str | None = None,
    smtp_password: str | None = None,
    clear_password: bool = False,
    smtp_from_email: str | None = None,
    smtp_from_name: str | None = None,
    smtp_use_tls: bool | None = None,
    smtp_use_ssl: bool | None = None,
) -> m.Tenant:
    if smtp_enabled is not None:
        tenant.smtp_enabled = bool(smtp_enabled)
    if smtp_host is not None:
        tenant.smtp_host = smtp_host.strip() or None
    if smtp_port is not None:
        port = int(smtp_port)
        if port < 1 or port > 65535:
            raise HTTPException(status_code=400, detail="smtp_port must be 1–65535")
        tenant.smtp_port = port
    if smtp_username is not None:
        tenant.smtp_username = smtp_username.strip() or None
    if clear_password:
        tenant.smtp_password_enc = None
    elif smtp_password is not None:
        from app.totp import encrypt_secret

        pwd = smtp_password.strip()
        tenant.smtp_password_enc = encrypt_secret(pwd) if pwd else None
    if smtp_from_email is not None:
        tenant.smtp_from_email = smtp_from_email.strip() or None
    if smtp_from_name is not None:
        tenant.smtp_from_name = smtp_from_name.strip() or None
    if smtp_use_tls is not None:
        tenant.smtp_use_tls = bool(smtp_use_tls)
    if smtp_use_ssl is not None:
        tenant.smtp_use_ssl = bool(smtp_use_ssl)
    if tenant.smtp_enabled and not ((tenant.smtp_host or "").strip() and (tenant.smtp_from_email or "").strip()):
        raise HTTPException(
            status_code=400,
            detail="smtp_host and smtp_from_email are required when smtp_enabled is true",
        )
    await db.flush()
    return tenant


async def list_tenants(db: AsyncSession, *, status: str | None = None, limit: int = 100) -> list[m.Tenant]:
    q = (
        select(m.Tenant)
        .where(m.Tenant.id != PLATFORM_TENANT_ID)
        .order_by(m.Tenant.created_at.desc())
        .limit(min(max(limit, 1), 500))
    )
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
