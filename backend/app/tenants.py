"""Tenant lifecycle: profile, suspend, activate, trial/grace, isolation helpers."""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app import packages as packages_svc
from app.config import settings

VALID_STATUSES = frozenset({"trial", "active", "grace", "suspended"})
VALID_INDUSTRIES = frozenset(
    {"retail", "pharmacy", "restaurant", "bakery", "wholesale", "manufacturing", "mart"}
)
VALID_DATE_FORMATS = frozenset({"DD/MM/YYYY", "MM/DD/YYYY", "YYYY-MM-DD"})
VALID_DECIMAL_SEPARATORS = frozenset({".", ","})
VALID_THOUSAND_SEPARATORS = frozenset({",", ".", " ", ""})
VALID_TIME_FORMATS = frozenset({"12h", "24h"})
TRIAL_REMINDER_DAYS = (7, 3, 1)


def coerce_industry_value(value: object) -> object:
    """Pydantic BeforeValidator: strip/lowercase; blank stays blank for Literal 422."""
    if value is None:
        return value
    if not isinstance(value, str):
        return value
    return value.strip().lower()


def coerce_tax_filing_period_value(value: object) -> object:
    """Pydantic BeforeValidator: strip/lowercase; blank stays blank for Literal 422."""
    if value is None:
        return value
    if not isinstance(value, str):
        return value
    return value.strip().lower()


def coerce_date_format_value(value: object) -> object:
    """Pydantic BeforeValidator: strip only (patterns are case-sensitive)."""
    if value is None:
        return value
    if not isinstance(value, str):
        return value
    return value.strip()


def coerce_decimal_separator_value(value: object) -> object:
    """Pydantic BeforeValidator: allow '.'|',' without stripping meaningful chars."""
    if value is None:
        return value
    if not isinstance(value, str):
        return value
    if value in {".", ","}:
        return value
    return value.strip()


def coerce_thousand_separator_value(value: object) -> object:
    """Pydantic BeforeValidator: map none→''; keep space; blank stays '' (valid none)."""
    if value is None:
        return value
    if not isinstance(value, str):
        return value
    if value in {",", ".", " ", ""}:
        return value
    stripped = value.strip()
    if stripped.lower() == "none":
        return ""
    return stripped


def coerce_time_format_value(value: object) -> object:
    """Pydantic BeforeValidator: strip/lowercase; blank stays blank for Literal 422."""
    if value is None:
        return value
    if not isinstance(value, str):
        return value
    return value.strip().lower()


def normalize_industry(industry: str | None, *, required: bool = True) -> str | None:
    """Normalize industry to a BR-1.2 / VALID_INDUSTRIES value (lowercase).

    Defense in depth: TenantCreate / TenantProfileUpdate schema Literals already
    reject blank/unknown (after coerce) with 422.
    """
    if industry is None:
        if required:
            raise HTTPException(
                status_code=400,
                detail=f"industry must be one of: {sorted(VALID_INDUSTRIES)}",
            )
        return None
    ind = industry.strip().lower()
    if not ind:
        if required:
            raise HTTPException(
                status_code=400,
                detail=f"industry must be one of: {sorted(VALID_INDUSTRIES)}",
            )
        return None
    if ind not in VALID_INDUSTRIES:
        raise HTTPException(
            status_code=400,
            detail=f"industry must be one of: {sorted(VALID_INDUSTRIES)}",
        )
    return ind


def _validate_separators(decimal_sep: str, thousand_sep: str) -> None:
    if thousand_sep and thousand_sep == decimal_sep:
        raise HTTPException(
            status_code=400,
            detail="thousand_separator must differ from decimal_separator",
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


def serialize_tenant(tenant: m.Tenant) -> dict:
    now = datetime.utcnow()
    days_left = None
    if tenant.status == "trial":
        days_left = calendar_days_until(tenant.trial_ends_at, now=now)
    elif tenant.status == "grace":
        days_left = calendar_days_until(tenant.grace_ends_at, now=now)
    usage = packages_svc.usage_snapshot(tenant, now=now)
    # Prefer subscription remaining when a paid/assigned term exists
    if usage.get("days_remaining") is not None and tenant.status in {"active", "trial"}:
        if getattr(tenant, "subscription_ends_at", None) is not None:
            days_left = usage["days_remaining"]
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
        "legal_name": getattr(tenant, "legal_name", None),
        "registration_number": getattr(tenant, "registration_number", None),
        "contact_person": getattr(tenant, "contact_person", None),
        "billing_address": getattr(tenant, "billing_address", None),
        "shipping_address": getattr(tenant, "shipping_address", None),
        "timezone": tenant.timezone or "Africa/Accra",
        "fiscal_year_start": tenant.fiscal_year_start or "01-01",
        "date_format": getattr(tenant, "date_format", None) or "DD/MM/YYYY",
        "decimal_separator": getattr(tenant, "decimal_separator", None) or ".",
        "thousand_separator": getattr(tenant, "thousand_separator", None)
        if getattr(tenant, "thousand_separator", None) is not None
        else ",",
        "time_format": getattr(tenant, "time_format", None) or "24h",
        "inactivity_timeout_minutes": int(
            getattr(tenant, "inactivity_timeout_minutes", None) or 30
        ),
        "expense_approval_threshold": float(tenant.expense_approval_threshold or 0),
        "expense_l2_threshold": float(getattr(tenant, "expense_l2_threshold", None) or 1000),
        "expense_approval_matrix": getattr(tenant, "expense_approval_matrix", None),
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
        "suspended_at": tenant.suspended_at,
        "suspended_reason": tenant.suspended_reason,
        "package_code": getattr(tenant, "package_code", None) or "trial",
        "max_stores_override": getattr(tenant, "max_stores_override", None),
        "store_limit": getattr(tenant, "store_limit", None),
        "subscription": usage,
        "enabled_modules": usage["enabled_modules"],
        "created_at": tenant.created_at,
    }


async def serialize_tenant_with_store_usage(db: AsyncSession, tenant: m.Tenant) -> dict:
    """Tenant serialize + live store usage counts (for /usage and entitlement UIs)."""
    from app import store_entitlements as store_ent_svc

    data = serialize_tenant(tenant)
    store_usage = await store_ent_svc.get_store_usage(db, tenant)
    data["store_usage"] = store_usage
    sub = dict(data.get("subscription") or {})
    sub.update(
        {
            "stores_active": store_usage["stores_active"],
            "stores_total": store_usage["stores_total"],
            "stores_remaining": store_usage["stores_remaining"],
            "effective_store_limit": store_usage["effective_store_limit"],
            "over_entitlement": store_usage["over_entitlement"],
            "unlimited_stores": store_usage["unlimited"],
        }
    )
    data["subscription"] = sub
    return data


async def set_max_stores_override(
    db: AsyncSession,
    tenant: m.Tenant,
    max_stores_override: int | None,
) -> m.Tenant:
    from app import store_entitlements as store_ent_svc

    tenant.max_stores_override = store_ent_svc.validate_max_stores_override(max_stores_override)
    # If company allocation now exceeds new entitlement, clamp is enforced at effective_*;
    # leave store_limit as-is so admins can see intent; effective uses min().
    await db.flush()
    return tenant


async def set_store_limit(
    db: AsyncSession,
    tenant: m.Tenant,
    store_limit: int | None,
) -> m.Tenant:
    from app import store_entitlements as store_ent_svc

    entitlement = store_ent_svc.subscription_store_entitlement(tenant)
    tenant.store_limit = store_ent_svc.validate_store_limit_value(
        store_limit, entitlement=entitlement
    )
    await db.flush()
    return tenant


async def assign_subscription(
    db: AsyncSession,
    tenant: m.Tenant,
    *,
    package_code: str,
    term_value: int,
    term_unit: str = "months",
    start_at: datetime | None = None,
    activate: bool = True,
    enabled_modules: list[str] | None = None,
    max_stores_override: int | None = None,
    apply_max_stores_override: bool = False,
    clear_max_stores_override: bool = False,
) -> m.Tenant:
    code = (package_code or "").strip().lower()
    # Defense in depth: TenantSubscriptionAssign.package_code Literal rejects
    # blank/unknown with 422 before this runs.
    if code not in packages_svc.VALID_PACKAGE_CODES:
        raise HTTPException(
            status_code=422,
            detail=f"package_code must be one of: {', '.join(sorted(packages_svc.VALID_PACKAGE_CODES))}",
        )
    unit = (term_unit or "months").strip().lower()
    # Defense in depth: TenantSubscriptionAssign.term_unit Literal rejects
    # blank/unknown with 422 before this runs. Empty used to coerce to months.
    if unit not in packages_svc.VALID_TERM_UNITS:
        raise HTTPException(status_code=422, detail="term_unit must be months or years")
    value = int(term_value)
    if value < 1 or value > 120:
        raise HTTPException(status_code=422, detail="term_value must be between 1 and 120")

    now = datetime.utcnow()
    starts = start_at or now
    months = packages_svc.term_to_months(value, unit)
    ends = packages_svc.add_calendar_months(starts, months)

    tenant.package_code = code
    tenant.subscription_term_unit = unit
    tenant.subscription_term_value = value
    tenant.subscription_starts_at = starts
    tenant.subscription_ends_at = ends
    tenant.package_assigned_at = now

    if clear_max_stores_override:
        await set_max_stores_override(db, tenant, None)
    elif apply_max_stores_override:
        await set_max_stores_override(db, tenant, max_stores_override)

    if enabled_modules is not None:
        await set_enabled_modules(db, tenant, enabled_modules, commit=False)
    else:
        # Clear custom override so package defaults apply
        tenant.enabled_modules = None

    if activate and tenant.status in {"trial", "grace", "suspended", "active"}:
        if tenant.status == "suspended":
            tenant.suspended_at = None
            tenant.suspended_reason = None
        tenant.status = "active"
        # Align trial end with subscription when converting from trial
        tenant.trial_ends_at = ends
        tenant.grace_ends_at = None

    await db.flush()
    return tenant


async def set_enabled_modules(
    db: AsyncSession,
    tenant: m.Tenant,
    modules: list[str],
    *,
    commit: bool = True,
) -> m.Tenant:
    cleaned: list[str] = []
    seen: set[str] = set()
    # Defense in depth: TenantModulesUpdate / TenantSubscriptionAssign.enabled_modules
    # Literals reject blank/unknown/platform with 422 before this runs.
    for raw in modules or []:
        mod = str(raw).strip().lower()
        if not mod or mod in seen:
            continue
        if mod == "platform":
            continue
        if mod not in packages_svc.PACKAGEABLE_MODULES:
            raise HTTPException(status_code=422, detail=f"Unknown module: {mod}")
        seen.add(mod)
        cleaned.append(mod)
    for m_on in packages_svc.ALWAYS_ON_MODULES:
        if m_on not in seen:
            cleaned.append(m_on)
            seen.add(m_on)
    tenant.enabled_modules = cleaned
    await db.flush()
    if commit:
        await db.commit()
    return tenant


async def clear_module_override(db: AsyncSession, tenant: m.Tenant) -> m.Tenant:
    tenant.enabled_modules = None
    await db.flush()
    return tenant


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
    suspended_by: str | None = None,
) -> m.Tenant:
    if tenant.status == "suspended":
        raise HTTPException(status_code=400, detail="Tenant is already suspended")
    tenant.status = "suspended"
    tenant.suspended_at = datetime.utcnow()
    tenant.suspended_reason = (reason or "").strip() or None
    tenant.grace_ends_at = None
    await revoke_all_sessions(db, tenant.id)
    await db.flush()
    from app import webhooks as webhooks_svc

    await webhooks_svc.emit_event(
        db,
        tenant_id=tenant.id,
        event="tenant.suspended",
        data={
            "tenant_id": tenant.id,
            "slug": tenant.slug,
            "reason": tenant.suspended_reason,
            "suspended_at": tenant.suspended_at.isoformat() if tenant.suspended_at else None,
            "suspended_by": suspended_by,
        },
    )
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
    legal_name: str | None = None,
    registration_number: str | None = None,
    contact_person: str | None = None,
    billing_address: str | None = None,
    shipping_address: str | None = None,
    timezone: str | None = None,
    fiscal_year_start: str | None = None,
    tax_jurisdiction: str | None = None,
    tax_registration_number: str | None = None,
    tax_filing_period: str | None = None,
    date_format: str | None = None,
    decimal_separator: str | None = None,
    thousand_separator: str | None = None,
    time_format: str | None = None,
    inactivity_timeout_minutes: int | None = None,
) -> m.Tenant:
    if company_name is not None:
        name = company_name.strip()
        if len(name) < 2:
            raise HTTPException(status_code=400, detail="company_name is required")
        tenant.company_name = name
    if industry is not None:
        tenant.industry = normalize_industry(industry)
    if currency is not None:
        # Defense in depth: TenantProfileUpdate CurrencyCodeValue → 422 on blank/non-ISO.
        from app.fx import normalize_currency

        tenant.currency = normalize_currency(currency)
    if phone is not None:
        tenant.phone = phone.strip() or None
    if email is not None:
        tenant.email = email.strip() or None
    if website is not None:
        tenant.website = website.strip() or None
    if address is not None:
        tenant.address = address.strip() or None
    if legal_name is not None:
        ln = legal_name.strip()
        if ln and len(ln) < 2:
            raise HTTPException(status_code=400, detail="legal_name must be at least 2 characters")
        if len(ln) > 200:
            raise HTTPException(status_code=400, detail="legal_name must be at most 200 characters")
        tenant.legal_name = ln or None
    if registration_number is not None:
        reg = registration_number.strip()
        if len(reg) > 80:
            raise HTTPException(status_code=400, detail="registration_number must be at most 80 characters")
        tenant.registration_number = reg or None
    if contact_person is not None:
        cp = contact_person.strip()
        if len(cp) > 150:
            raise HTTPException(status_code=400, detail="contact_person must be at most 150 characters")
        tenant.contact_person = cp or None
    if billing_address is not None:
        tenant.billing_address = billing_address.strip() or None
    if shipping_address is not None:
        tenant.shipping_address = shipping_address.strip() or None
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
        # Defense in depth: TenantProfileUpdate TaxFilingJurisdictionValue → 422 on blank/unknown.
        from app.tax_filings import SUPPORTED

        juris = tax_jurisdiction.strip().upper()
        if juris not in SUPPORTED:
            raise HTTPException(
                status_code=400,
                detail=f"tax_jurisdiction must be one of: {sorted(SUPPORTED)}",
            )
        tenant.tax_jurisdiction = juris
    if tax_registration_number is not None:
        tin = tax_registration_number.strip()
        tenant.tax_registration_number = tin or None
    if tax_filing_period is not None:
        # Defense in depth: TenantProfileUpdate Literal rejects blank/unknown with 422.
        period = tax_filing_period.strip().lower()
        if period not in {"monthly", "quarterly"}:
            raise HTTPException(status_code=400, detail="tax_filing_period must be monthly or quarterly")
        tenant.tax_filing_period = period

    # Apply formatting fields, then validate the resulting combination.
    if date_format is not None:
        # Defense in depth: schema DateFormatValue Literal → 422 on blank/unknown.
        df = date_format.strip()
        if df not in VALID_DATE_FORMATS:
            raise HTTPException(
                status_code=400,
                detail=f"date_format must be one of: {sorted(VALID_DATE_FORMATS)}",
            )
        tenant.date_format = df
    if decimal_separator is not None:
        ds = decimal_separator if decimal_separator in {".", ","} else decimal_separator.strip()
        if ds not in VALID_DECIMAL_SEPARATORS:
            raise HTTPException(status_code=400, detail="decimal_separator must be '.' or ','")
        tenant.decimal_separator = ds
    if thousand_separator is not None:
        # Allow empty string for "none"; treat literal "none" as empty.
        ts = "" if thousand_separator.strip().lower() == "none" else thousand_separator
        if ts not in VALID_THOUSAND_SEPARATORS:
            raise HTTPException(
                status_code=400,
                detail="thousand_separator must be ',', '.', space, or none",
            )
        tenant.thousand_separator = ts
    if time_format is not None:
        tf = time_format.strip().lower()
        if tf not in VALID_TIME_FORMATS:
            raise HTTPException(status_code=400, detail="time_format must be 12h or 24h")
        tenant.time_format = tf
    if inactivity_timeout_minutes is not None:
        minutes = int(inactivity_timeout_minutes)
        if minutes < 5 or minutes > 480:
            raise HTTPException(
                status_code=400,
                detail="inactivity_timeout_minutes must be between 5 and 480",
            )
        tenant.inactivity_timeout_minutes = minutes
    _validate_separators(
        getattr(tenant, "decimal_separator", None) or ".",
        getattr(tenant, "thousand_separator", None)
        if getattr(tenant, "thousand_separator", None) is not None
        else ",",
    )

    await db.flush()
    return tenant


async def list_tenants(db: AsyncSession, *, status: str | None = None, limit: int = 100) -> list[m.Tenant]:
    q = select(m.Tenant).order_by(m.Tenant.created_at.desc()).limit(min(max(limit, 1), 500))
    # Schema TenantStatusFilterValue rejects blank/invalid → 422; keep allow-list
    # defense-in-depth (no silent empty equality filter / blank→all).
    if status is not None:
        key = (status or "").strip().lower()
        if not key:
            status = None
        elif key not in VALID_STATUSES:
            raise HTTPException(status_code=422, detail="Invalid status filter")
        else:
            status = key
    if status:
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
