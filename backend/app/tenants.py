"""Tenant lifecycle: profile, suspend, activate, trial/grace, isolation helpers."""

from __future__ import annotations

import re
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app import packages as packages_svc
from app import schema_compat
from app.config import settings
from app.honesty import money_json, optional_honest_narrative, require_honest_narrative

_SAFE_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

VALID_STATUSES = frozenset({"trial", "active", "grace", "suspended"})
# Platform owner workspace — never suspend/delete (lockout recovery).
PROTECTED_TENANT_SLUGS = frozenset({"platform", "ribdigi-platform"})
VALID_INDUSTRIES = frozenset({"retail", "hotel", "restaurant"})
INDUSTRY_LABELS = {
    "retail": "Retail",
    "mart": "Mart",
    "hotel": "Hotel",
    "fmcg": "FMCG",
    "pharmacy": "Pharmacy",
    "restaurant": "Restaurant",
    "bakery": "Bakery",
    "wholesale": "Wholesale",
    "retail_wholesale": "Retail + Wholesale",
    "distribution": "Distribution",
    "general_trading": "General Trading",
    "manufacturing": "Manufacturing",
    "hospital": "Hospital",
}
# Customer industries a new or edited company can choose. Platform software is not in this list.
PROVISION_INDUSTRIES: tuple[str, ...] = ("retail", "hotel", "restaurant")
# Kept so older callers still import the name. Nothing is blocked.
RETIRED_PROVISION_INDUSTRIES: frozenset[str] = frozenset()
VALID_DATE_FORMATS = frozenset({"DD/MM/YYYY", "MM/DD/YYYY", "YYYY-MM-DD"})
VALID_DECIMAL_SEPARATORS = frozenset({".", ","})
VALID_THOUSAND_SEPARATORS = frozenset({",", ".", " ", ""})
VALID_TIME_FORMATS = frozenset({"12h", "24h"})
TRIAL_REMINDER_DAYS = (7, 3, 1)


def coerce_industry_value(value: object) -> object:
    """Pydantic BeforeValidator: strip/lowercase + safe aliases; blank stays blank for Literal 422."""
    if value is None:
        return value
    if not isinstance(value, str):
        return value
    raw = value.strip().lower()
    if not raw:
        return raw
    canon = packages_svc.canonicalize_industry(raw)
    return canon if canon else raw


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
    canon = packages_svc.canonicalize_industry(industry)
    if canon:
        return canon
    if required:
        raise HTTPException(
            status_code=400,
            detail=f"industry must be one of: {sorted(VALID_INDUSTRIES)}",
        )
    return None


def assert_industry_selectable(industry: str, *, previous: str | None = None) -> None:
    """New companies choose retail, hotel, or restaurant.

    RETIRED_PROVISION_INDUSTRIES is empty. A code added there later is rejected
    on create and on a change away from a company that already stores it.
    """
    if industry not in RETIRED_PROVISION_INDUSTRIES:
        return
    prev = (previous or "").strip().lower()
    if prev == industry:
        return
    raise HTTPException(
        status_code=400,
        detail=(
            "That business type is not available when creating or changing a company. "
            "A company that already uses it keeps its records."
        ),
    )


def industry_label(value: str | None) -> str:
    key = (value or "").strip().lower()
    if key in INDUSTRY_LABELS:
        return INDUSTRY_LABELS[key]
    if key:
        return key.replace("_", " ").title()
    return "Unknown"


def require_tenant_slug(value: str | None) -> str:
    """OpenAPI TenantSlugValue → 422; service defense-in-depth → 400."""
    from app.schemas import validate_tenant_slug_value

    try:
        return validate_tenant_slug_value((value or "").strip().lower())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def require_company_name(value: str | None) -> str:
    """OpenAPI CompanyNameValue → 422; service defense-in-depth → 400."""
    return require_honest_narrative(
        value, label="company name", min_length=2, max_length=200
    )


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


def _fiscal_year_label(tenant: m.Tenant) -> str:
    from app.accounting import fiscal_year_display_label

    return fiscal_year_display_label(getattr(tenant, "fiscal_year_start", None) or "01-01")


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
        "industry_label": industry_label(getattr(tenant, "industry", None)),
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
        "fiscal_year_label": _fiscal_year_label(tenant),
        "date_format": getattr(tenant, "date_format", None) or "DD/MM/YYYY",
        "decimal_separator": getattr(tenant, "decimal_separator", None) or ".",
        "thousand_separator": getattr(tenant, "thousand_separator", None)
        if getattr(tenant, "thousand_separator", None) is not None
        else ",",
        "time_format": getattr(tenant, "time_format", None) or "24h",
        "inactivity_timeout_minutes": int(
            getattr(tenant, "inactivity_timeout_minutes", None) or 30
        ),
        "offline_auth_hours": int(getattr(tenant, "offline_auth_hours", None) or 168),
        "expense_approval_threshold": money_json(tenant.expense_approval_threshold),
        "expense_l2_threshold": money_json(
            getattr(tenant, "expense_l2_threshold", None), default=1000.0
        ),
        "expense_approval_matrix": getattr(tenant, "expense_approval_matrix", None),
        "early_pay_discount_pct": money_json(
            getattr(tenant, "early_pay_discount_pct", None)
        ),
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
        "max_stores": usage.get("subscription_store_entitlement"),
        "multi_store": usage.get("subscription_store_entitlement") is None
        or int(usage.get("subscription_store_entitlement") or 0) > 1,
        "subscription": usage,
        "enabled_modules": usage["enabled_modules"],
        "created_at": tenant.created_at,
    }


async def tenant_admin_email(db: AsyncSession, tenant_id: str) -> str | None:
    """Earliest company_admin email for that tenant (create-account login)."""
    email = (
        await db.execute(
            select(m.User.email)
            .where(m.User.tenant_id == tenant_id, m.User.role == "company_admin")
            .order_by(m.User.created_at.asc())
            .limit(1)
        )
    ).scalar_one_or_none()
    return str(email) if email else None


async def serialize_tenant_with_store_usage(db: AsyncSession, tenant: m.Tenant) -> dict:
    """Tenant serialize + live store usage counts (for /usage and entitlement UIs)."""
    from app import store_entitlements as store_ent_svc

    data = serialize_tenant(tenant)
    store_usage = await store_ent_svc.get_store_usage(db, tenant)
    data["store_usage"] = store_usage
    data["admin_email"] = await tenant_admin_email(db, tenant.id)
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
    industry = packages_svc.canonicalize_industry(getattr(tenant, "industry", None))
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
        if not packages_svc.industry_allows_module(industry, mod):
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Module '{mod}' is not available for business type '{industry}'. "
                    f"Change the tenant industry before enabling this module."
                ),
            )
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
    try:
        tenant = await db.get(m.Tenant, tenant_id)
        if tenant:
            return tenant
    except SQLAlchemyError:
        await db.rollback()
    tenant = await schema_compat.get_mapped(db, m.Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


async def resolve_tenant(db: AsyncSession, tenant_ref: str) -> m.Tenant:
    try:
        tenant = (
            await db.execute(
                select(m.Tenant).where((m.Tenant.id == tenant_ref) | (m.Tenant.slug == tenant_ref))
            )
        ).scalar_one_or_none()
        if tenant:
            return tenant
    except SQLAlchemyError:
        await db.rollback()
    rows = await schema_compat.fetch_live_dicts(
        db, "tenants", "id = :ref OR slug = :ref", {"ref": tenant_ref}
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return await schema_compat.attach_mapped(db, m.Tenant, rows[0])


def assert_tenant_active_for_login(tenant: m.Tenant) -> None:
    if tenant.status == "suspended":
        # Platform workspace must remain sign-in capable so owners can recover.
        slug = (tenant.slug or "").strip().lower()
        tid = (tenant.id or "").strip().lower()
        if slug in PROTECTED_TENANT_SLUGS or tid in PROTECTED_TENANT_SLUGS:
            return
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
    slug = (tenant.slug or "").strip().lower()
    if slug in PROTECTED_TENANT_SLUGS or (tenant.id or "") in PROTECTED_TENANT_SLUGS:
        raise HTTPException(
            status_code=400,
            detail="The platform owner workspace cannot be suspended",
        )
    reason_s = require_honest_narrative(reason, label="suspend reason")
    tenant.status = "suspended"
    tenant.suspended_at = datetime.utcnow()
    tenant.suspended_reason = reason_s
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


def _tenant_scoped_tables():
    """ORM tables that carry tenant_id (deleted before the tenant row)."""
    tables = []
    for name in dir(m):
        obj = getattr(m, name)
        if not isinstance(obj, type) or not hasattr(obj, "__table__"):
            continue
        cols = {c.name for c in obj.__table__.columns}
        if "tenant_id" in cols:
            tables.append(obj.__table__)
    return tables


def _quote_ident(name: str) -> str:
    if not _SAFE_IDENT.match(name or ""):
        raise ValueError(f"unsafe SQL identifier: {name!r}")
    return f'"{name}"'


async def _db_tenant_scoped_table_names(db: AsyncSession) -> list[str]:
    """Live tables with a tenant_id column (ORM + any legacy/reflected tables)."""

    def _names(sync_conn) -> list[str]:
        from sqlalchemy import inspect as sa_inspect

        insp = sa_inspect(sync_conn)
        names: list[str] = []
        for tname in insp.get_table_names():
            if not _SAFE_IDENT.match(tname):
                continue
            cols = {c["name"] for c in insp.get_columns(tname)}
            if "tenant_id" in cols:
                names.append(tname)
        return sorted(names)

    conn = await db.connection()
    return await conn.run_sync(_names)


async def _db_nullable_fk_columns(db: AsyncSession, table_name: str) -> list[str]:
    """Nullable FK column names on a live table (excluding tenant_id)."""

    def _cols(sync_conn) -> list[str]:
        from sqlalchemy import inspect as sa_inspect

        insp = sa_inspect(sync_conn)
        col_meta = {c["name"]: c for c in insp.get_columns(table_name)}
        out: list[str] = []
        for fk in insp.get_foreign_keys(table_name):
            for col in fk.get("constrained_columns") or ():
                if col == "tenant_id" or not _SAFE_IDENT.match(col):
                    continue
                if col_meta.get(col, {}).get("nullable", True):
                    out.append(col)
        seen: set[str] = set()
        unique: list[str] = []
        for col in out:
            if col not in seen:
                seen.add(col)
                unique.append(col)
        return unique

    conn = await db.connection()
    return await conn.run_sync(_cols)


async def _null_tenant_nullable_fks(db: AsyncSession, tenant_id: str) -> None:
    """Null every nullable FK on tenant-scoped rows so cyclic graphs can be deleted.

    Uses live DB metadata (not only ORM) so Postgres leftover/legacy tables and
    FKs are cleared. ``sort_tables`` drops ordering edges for cycles such as
    ``users`` ↔ ``branches`` ↔ ``departments``; clearing nullable FKs first
    leaves a DAG of required FKs that multipass deletes can remove.
    """
    from sqlalchemy import text

    table_names = await _db_tenant_scoped_table_names(db)
    if not table_names:
        table_names = [t.name for t in _tenant_scoped_tables()]

    for tname in table_names:
        fk_cols = await _db_nullable_fk_columns(db, tname)
        if not fk_cols:
            orm = next((t for t in _tenant_scoped_tables() if t.name == tname), None)
            if orm is not None:
                fk_cols = [
                    col.name
                    for col in orm.columns
                    if col.name != "tenant_id"
                    and col.nullable
                    and col.foreign_keys
                    and _SAFE_IDENT.match(col.name)
                ]
        if not fk_cols:
            continue
        assignments = ", ".join(f"{_quote_ident(c)}=NULL" for c in fk_cols)
        sql = (
            f"UPDATE {_quote_ident(tname)} SET {assignments} "
            f"WHERE {_quote_ident('tenant_id')} = :tid"
        )
        await db.execute(text(sql), {"tid": tenant_id})


async def purge_tenant_records(db: AsyncSession, tenant: m.Tenant) -> None:
    """Delete every row scoped to this tenant, then the tenant row.

    Nullable FKs are cleared first (live DB metadata). Deletes then run in
    dependency order with savepoint retries so a temporary parent/child
    ordering miss on Postgres cannot abort the whole purge. Tables that exist
    only in the database (legacy) are included when they have ``tenant_id``.
    The platform deletion log has no ``tenant_id`` and is left in place.
    A failure raises 409 and the caller rolls back.
    """
    import logging
    import warnings

    from sqlalchemy import delete, text
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.schema import sort_tables

    log = logging.getLogger("ribdigi.tenants")
    orm_tables = _tenant_scoped_tables()
    orm_by_name = {t.name: t for t in orm_tables}
    live_names = await _db_tenant_scoped_table_names(db)
    if not live_names:
        live_names = list(orm_by_name.keys())

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            ordered_orm = list(reversed(sort_tables(orm_tables)))
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Unable to order tenant tables for delete: {exc}",
        ) from exc

    ordered_names: list[str] = [t.name for t in ordered_orm]
    for name in live_names:
        if name not in ordered_names:
            # Unknown/legacy tables first so dependents of ORM parents clear early.
            ordered_names.insert(0, name)

    try:
        await _null_tenant_nullable_fks(db, tenant.id)
        await db.flush()

        remaining = {name: name for name in ordered_names}
        for _pass in range(len(ordered_names) + 8):
            if not remaining:
                break
            progressed = False
            for name in list(remaining):
                try:
                    async with db.begin_nested():
                        table = orm_by_name.get(name)
                        if table is not None:
                            result = await db.execute(
                                delete(table).where(table.c.tenant_id == tenant.id)
                            )
                        else:
                            result = await db.execute(
                                text(
                                    f"DELETE FROM {_quote_ident(name)} "
                                    f"WHERE {_quote_ident('tenant_id')} = :tid"
                                ),
                                {"tid": tenant.id},
                            )
                    remaining.pop(name, None)
                    progressed = True
                    if result.rowcount:
                        log.debug(
                            "purge tenant %s deleted %s rows from %s",
                            tenant.id,
                            result.rowcount,
                            name,
                        )
                except IntegrityError:
                    continue
            if not progressed:
                break

        leftovers: list[str] = []
        for name in live_names:
            count = (
                await db.execute(
                    text(
                        f"SELECT COUNT(*) FROM {_quote_ident(name)} "
                        f"WHERE {_quote_ident('tenant_id')} = :tid"
                    ),
                    {"tid": tenant.id},
                )
            ).scalar_one()
            if int(count or 0) > 0:
                leftovers.append(f"{name}:{count}")
        if leftovers:
            raise RuntimeError(
                "tenant purge left rows after multipass delete: " + ", ".join(leftovers[:12])
            )

        await db.delete(tenant)
        await db.flush()
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("tenant purge failed for %s", getattr(tenant, "id", None))
        cause = str(exc).strip()
        detail = (
            "Cannot delete this tenant because some records could not be removed. "
            "Suspend the tenant instead, or contact support."
        )
        if cause.startswith("tenant purge left rows"):
            detail = f"{detail} ({cause})"
        raise HTTPException(status_code=409, detail=detail) from exc


def _remove_tenant_files(tenant_id: str) -> str | None:
    """Drop this tenant's uploads and on-disk logical backups. None when both succeed."""
    from app.backup import backup_root
    from app.storage import delete_tenant_media
    import shutil

    errors = []
    try:
        delete_tenant_media(tenant_id)
    except Exception:
        errors.append("files_remaining")
    try:
        tid = (tenant_id or "").strip()
        if tid and all(part not in tid for part in ("/", "\\", "..")):
            root = backup_root().resolve()
            path = (root / tid).resolve()
            path.relative_to(root)
            if path.is_dir():
                shutil.rmtree(path)
    except Exception:
        errors.append("backups_remaining")
    return errors[0] if errors else None


async def _notify_deletion_result(db: AsyncSession, deleted_tenant_id: str, status: str) -> None:
    """Tell platform owners on their own workspace. Identifier and status only."""
    from app import notifications as notifications_svc
    from app.rbac import PLATFORM_OWNER_ROLES

    owners = (
        await db.execute(
            select(m.User).where(
                m.User.role.in_(tuple(PLATFORM_OWNER_ROLES)),
                m.User.is_active == True,  # noqa: E712
            )
        )
    ).scalars().all()
    title = "Tenant deletion completed" if status == "completed" else "Tenant deletion failed"
    message = f"Tenant {deleted_tenant_id} deletion {status}."
    for owner in owners:
        if owner.tenant_id == deleted_tenant_id:
            continue
        await notifications_svc.create_notification(
            db,
            tenant_id=owner.tenant_id,
            user_id=owner.id,
            category="platform",
            title=title,
            message=message,
            entity_type="tenant_deletion",
            entity_id=deleted_tenant_id,
        )


async def delete_tenant(
    db: AsyncSession,
    tenant: m.Tenant,
    *,
    actor_role: str,
    actor_tenant_id: str,
    confirm_slug: str,
) -> dict:
    """Permanently remove a company tenant and all of its scoped data."""
    from app.rbac import is_platform_tenant_delete_role

    if not is_platform_tenant_delete_role(actor_role):
        raise HTTPException(
            status_code=403,
            detail="Only the software owner can delete a tenant",
        )
    slug = (tenant.slug or "").strip().lower()
    if slug in PROTECTED_TENANT_SLUGS:
        raise HTTPException(
            status_code=400,
            detail="The platform owner workspace cannot be deleted",
        )
    if tenant.id == actor_tenant_id:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete your own workspace",
        )
    expected = (tenant.slug or "").strip().lower()
    provided = (confirm_slug or "").strip().lower()
    if not provided or provided != expected:
        raise HTTPException(
            status_code=400,
            detail=f'Type the tenant slug "{expected}" to confirm deletion',
        )

    snapshot = {
        "id": tenant.id,
        "slug": tenant.slug,
        "company_name": tenant.company_name,
        "status": tenant.status,
    }
    await purge_tenant_records(db, tenant)
    return snapshot


async def delete_own_tenant(
    db: AsyncSession,
    tenant: m.Tenant,
    *,
    actor_role: str,
    actor_user_id: str,
    password: str,
    confirm_name: str,
    confirm: bool,
) -> dict:
    """Company admin permanently deletes the tenant on their own token.

    Sessions are revoked and that change is committed before the purge, so
    existing tokens stop working immediately. The purge is one transaction.
    If it fails, it rolls back and the admin can sign in and retry. The
    deletion row stays outside tenant data.
    """
    import asyncio

    from app.rbac import PLATFORM_OWNER_ROLES
    from app.security import verify_password

    if (actor_role or "") != "company_admin":
        raise HTTPException(
            status_code=403,
            detail="Only a company admin can delete this company",
        )
    slug = (tenant.slug or "").strip().lower()
    if slug in PROTECTED_TENANT_SLUGS or (tenant.id or "") in PROTECTED_TENANT_SLUGS:
        raise HTTPException(
            status_code=400,
            detail="The platform owner workspace cannot be deleted",
        )
    if confirm is not True:
        raise HTTPException(status_code=400, detail="Confirm deletion before continuing")
    expected_name = (tenant.company_name or "").strip()
    if (confirm_name or "").strip() != expected_name:
        raise HTTPException(
            status_code=400,
            detail="Type this company's exact name to confirm deletion",
        )
    user = await db.get(m.User, actor_user_id)
    if user is None or user.tenant_id != tenant.id or not user.is_active:
        raise HTTPException(status_code=403, detail="Only a company admin of this company can delete it")
    if not await asyncio.to_thread(verify_password, password, user.password_hash):
        raise HTTPException(status_code=401, detail="Password is incorrect")

    owners_here = (
        await db.execute(
            select(m.User.id).where(
                m.User.tenant_id == tenant.id,
                m.User.role.in_(tuple(PLATFORM_OWNER_ROLES)),
            )
        )
    ).first()
    if owners_here is not None:
        raise HTTPException(
            status_code=400,
            detail="This company hosts a platform owner account and cannot be deleted here",
        )

    deleted_id = tenant.id
    row = m.PlatformTenantDeletion(
        deleted_tenant_id=deleted_id,
        actor_user_id=actor_user_id,
        status="pending",
    )
    db.add(row)
    await db.flush()
    deletion_id = row.id
    await revoke_all_sessions(db, deleted_id)
    await db.commit()

    tenant = await db.get(m.Tenant, deleted_id)
    row = await db.get(m.PlatformTenantDeletion, deletion_id)
    if tenant is None:
        if row is not None:
            row.status = "completed"
            row.completed_at = datetime.utcnow()
            await db.commit()
        return {"deleted_tenant_id": deleted_id, "status": "completed"}
    try:
        await purge_tenant_records(db, tenant)
        if row is not None:
            row.status = "completed"
            row.completed_at = datetime.utcnow()
        await db.commit()
    except Exception:
        await db.rollback()
        failed = await db.get(m.PlatformTenantDeletion, deletion_id)
        if failed is not None:
            failed.status = "failed"
            failed.error_code = "purge_failed"
            failed.completed_at = datetime.utcnow()
            await db.commit()
        await _notify_deletion_result(db, deleted_id, "failed")
        await db.commit()
        raise HTTPException(
            status_code=409,
            detail=(
                "Deletion did not finish. Your existing sessions were signed out. "
                "Sign in and retry. Company data was not removed."
            ),
        )
    file_error = _remove_tenant_files(deleted_id)
    if file_error:
        saved = await db.get(m.PlatformTenantDeletion, deletion_id)
        if saved is not None:
            saved.error_code = file_error
            await db.commit()
    try:
        await _notify_deletion_result(db, deleted_id, "completed")
        await db.commit()
    except Exception:
        await db.rollback()
    return {"deleted_tenant_id": deleted_id, "status": "completed"}


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
                from app import saas_billing as billing_svc

                billing_outcome = await billing_svc.note_trial_ended(db, tenant)
                if billing_outcome == "paid" or tenant.status != "trial":
                    continue
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
    offline_auth_hours: int | None = None,
) -> m.Tenant:
    if company_name is not None:
        # OpenAPI CompanyNameValue → 422; service defense-in-depth → 400.
        tenant.company_name = require_honest_narrative(
            company_name, label="company name", min_length=2, max_length=200
        )
    if industry is not None:
        tenant.industry = normalize_industry(industry)
        # Prune custom module overrides that no longer match the business type.
        custom = getattr(tenant, "enabled_modules", None)
        if isinstance(custom, list) and custom:
            pruned = packages_svc.filter_modules_for_industry(custom, tenant.industry)
            for m_on in packages_svc.ALWAYS_ON_MODULES:
                if m_on not in pruned:
                    pruned.append(m_on)
            tenant.enabled_modules = pruned
        from app import printers as printers_svc

        await printers_svc.drop_inapplicable_printer_destinations(
            db, tenant_id=tenant.id, industry=tenant.industry
        )
    if currency is not None:
        # Defense in depth: TenantProfileUpdate CurrencyCodeValue → 422 on blank/non-ISO.
        from app.fx import normalize_currency

        tenant.currency = normalize_currency(currency)
    if phone is not None:
        # Defense in depth: TenantProfileUpdate E164PhoneValue → 422 on blank/invalid.
        from app.schemas import validate_e164_phone_value

        try:
            tenant.phone = validate_e164_phone_value(str(phone).strip())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    if email is not None:
        tenant.email = email.strip() or None
    if website is not None:
        # Defense in depth: TenantProfileUpdate WebhookUrlValue → 422 on blank/invalid.
        from app.schemas import validate_webhook_url_value

        try:
            tenant.website = validate_webhook_url_value(str(website).strip())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    if address is not None:
        # OpenAPI AddressValue → 422; service defense-in-depth → 400.
        tenant.address = optional_honest_narrative(
            address, label="company address", max_length=500
        )
    if legal_name is not None:
        # OpenAPI LegalNameValue → 422; service defense-in-depth → 400.
        tenant.legal_name = optional_honest_narrative(
            legal_name, label="legal name", min_length=2, max_length=200
        )
    if registration_number is not None:
        # OpenAPI RegistrationNumberValue → 422; service defense-in-depth → 400.
        tenant.registration_number = optional_honest_narrative(
            registration_number, label="registration number", max_length=80
        )
    if contact_person is not None:
        # OpenAPI ContactPersonValue → 422; service defense-in-depth → 400.
        tenant.contact_person = optional_honest_narrative(
            contact_person, label="contact person", max_length=150
        )
    if billing_address is not None:
        # OpenAPI AddressValue → 422; service defense-in-depth → 400.
        tenant.billing_address = optional_honest_narrative(
            billing_address, label="billing address", max_length=500
        )
    if shipping_address is not None:
        # OpenAPI AddressValue → 422; service defense-in-depth → 400.
        tenant.shipping_address = optional_honest_narrative(
            shipping_address, label="shipping address", max_length=500
        )
    if timezone is not None:
        # Defense in depth: TenantProfileUpdate TimezoneValue → 422 on blank/non-IANA.
        from zoneinfo import ZoneInfo

        tz = timezone.strip()
        if not tz:
            raise HTTPException(status_code=400, detail="timezone is required")
        try:
            ZoneInfo(tz)
        except Exception as exc:
            raise HTTPException(
                status_code=400,
                detail="timezone must be a valid IANA timezone",
            ) from exc
        tenant.timezone = tz
    if fiscal_year_start is not None:
        # Defense in depth: TenantProfileUpdate FiscalYearStartValue → 422 on blank/bad MM-DD.
        from app.accounting import parse_fiscal_mmdd

        fys = fiscal_year_start.strip()
        parse_fiscal_mmdd(fys)
        tenant.fiscal_year_start = fys
    if tax_jurisdiction is not None:
        # Defense in depth: TenantProfileUpdate TenantTaxJurisdictionValue → 422 on blank/unknown.
        from app.tax_filings import TAX_COUNTRY_CODES

        juris = tax_jurisdiction.strip().upper()
        if juris not in TAX_COUNTRY_CODES:
            raise HTTPException(
                status_code=400,
                detail="tax_jurisdiction must be a supported ISO country code",
            )
        tenant.tax_jurisdiction = juris
    if tax_registration_number is not None:
        # OpenAPI TaxRegistrationNumberValue → 422; service defense-in-depth → 400.
        tenant.tax_registration_number = optional_honest_narrative(
            tax_registration_number, label="tax registration number", max_length=40
        )
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
    if offline_auth_hours is not None:
        from app.offline_pos import clamp_offline_auth_hours
        from app.config import settings as app_settings

        hours = int(offline_auth_hours)
        lo = int(app_settings.OFFLINE_AUTH_HOURS_MIN or 1)
        hi = int(app_settings.OFFLINE_AUTH_HOURS_MAX or 168)
        if hours < lo or hours > hi:
            raise HTTPException(
                status_code=400,
                detail=f"offline_auth_hours must be between {lo} and {hi}",
            )
        tenant.offline_auth_hours = clamp_offline_auth_hours(hours)
    _validate_separators(
        getattr(tenant, "decimal_separator", None) or ".",
        getattr(tenant, "thousand_separator", None)
        if getattr(tenant, "thousand_separator", None) is not None
        else ",",
    )

    await db.flush()
    return tenant


async def request_admin_password_reset(
    db: AsyncSession,
    tenant: m.Tenant,
    *,
    actor_id: str,
    user_id: str | None = None,
    new_password: str | None = None,
) -> dict:
    """Reset that tenant's company administrator password for the software owner.

    When ``new_password`` is set, the password is changed immediately and sessions
    are revoked. When it is omitted, a single-use reset link is emailed instead.
    Does not return the current password, the new password, or the raw token.
    """
    import asyncio

    from app import emailer
    from app.security import hash_password, issue_one_time_token, validate_password_strength

    if user_id:
        user = await db.get(m.User, user_id)
        if not user or user.tenant_id != tenant.id:
            raise HTTPException(status_code=404, detail="Tenant administrator not found")
        if user.role != "company_admin":
            raise HTTPException(
                status_code=403,
                detail="Only that tenant's administrator can be reset from the platform console",
            )
    else:
        user = (
            await db.execute(
                select(m.User)
                .where(m.User.tenant_id == tenant.id, m.User.role == "company_admin")
                .order_by(m.User.created_at.asc())
            )
        ).scalars().first()
        if not user:
            raise HTTPException(status_code=404, detail="Tenant administrator not found")

    now = datetime.utcnow()
    sessions = (
        await db.execute(
            select(m.AuthSession).where(
                m.AuthSession.user_id == user.id,
                m.AuthSession.tenant_id == tenant.id,
                m.AuthSession.revoked_at.is_(None),
            )
        )
    ).scalars().all()
    for session in sessions:
        session.revoked_at = now

    password_set = False
    email_sent = False
    email_error = None
    typed = (new_password or "").strip()
    if typed:
        validate_password_strength(typed)
        user.password_hash = await asyncio.to_thread(hash_password, typed)
        user.failed_login_attempts = 0
        user.locked_until = None
        password_set = True
        await db.flush()
    else:
        raw, token_hash, expires = issue_one_time_token()
        db.add(
            m.AuthToken(
                tenant_id=tenant.id,
                user_id=user.id,
                purpose="password_reset",
                token_hash=token_hash,
                expires_at=expires,
            )
        )
        await db.flush()
        try:
            result = await emailer.send_password_reset_email(
                to=user.email, token=raw, tenant=tenant
            )
            email_sent = bool(result.sent)
            email_error = result.error
        except Exception:
            email_error = "send_failed"

    return {
        "tenant_id": tenant.id,
        "slug": tenant.slug,
        "user_id": user.id,
        "email": user.email,
        "initiated_by": actor_id,
        "initiated_at": now.isoformat() + "Z",
        "sessions_revoked": len(sessions),
        "password_set": password_set,
        "email_sent": email_sent,
        "email_error": email_error,
    }


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
