"""Commercial packages and per-tenant feature entitlements (software-owner controlled)."""

from __future__ import annotations

import calendar
from datetime import datetime
from typing import Any

# Always available so tenants can log in, see home, and get security alerts.
ALWAYS_ON_MODULES: frozenset[str] = frozenset({"dashboard", "notifications", "security"})

# Modules a package may grant (excludes platform — software-owner only).
PACKAGEABLE_MODULES: tuple[str, ...] = (
    "dashboard",
    "company",
    "inventory",
    "sales",
    "pos",
    "purchasing",
    "expenses",
    "accounting",
    "credit",
    "tax",
    "stores",
    "reports",
    "notifications",
    "audit",
    "backup",
    "ai",
    "users",
    "security",
    "customers",
    "suppliers",
)

_STARTER = (
    "dashboard",
    "company",
    "inventory",
    "sales",
    "pos",
    "accounting",
    "expenses",
    "notifications",
    "security",
    "users",
    "customers",
    "suppliers",
)

_PROFESSIONAL = _STARTER + (
    "purchasing",
    "credit",
    "tax",
    "stores",
    "reports",
    "audit",
    "backup",
    "ai",
)

_ENTERPRISE = tuple(m for m in PACKAGEABLE_MODULES)

# max_stores / max_companies: int or None (None = unlimited). Company == Tenant in this product,
# so max_companies is informational (always 1 company profile per tenant).
PACKAGES: dict[str, dict[str, Any]] = {
    "trial": {
        "code": "trial",
        "name": "Trial",
        "description": "Time-limited evaluation (Professional feature set)",
        "modules": list(_PROFESSIONAL),
        "max_companies": 1,
        "max_stores": 1,
    },
    "starter": {
        "code": "starter",
        "name": "Starter",
        "description": "Single-store core: inventory, sales, POS, expenses, basic accounting",
        "modules": list(_STARTER),
        "max_companies": 1,
        "max_stores": 1,
    },
    "professional": {
        "code": "professional",
        "name": "Professional",
        "description": "Multi-store + purchasing, credit, tax, reports, AI",
        "modules": list(_PROFESSIONAL),
        "max_companies": 1,
        "max_stores": 10,
    },
    "enterprise": {
        "code": "enterprise",
        "name": "Enterprise",
        "description": "All tenant modules",
        "modules": list(_ENTERPRISE),
        "max_companies": 1,
        "max_stores": None,
    },
}

VALID_PACKAGE_CODES = frozenset(PACKAGES.keys())
VALID_TERM_UNITS = frozenset({"months", "years"})


def list_packages() -> list[dict[str, Any]]:
    return [
        {
            **dict(p),
            "max_stores": p.get("max_stores"),
            "max_companies": p.get("max_companies"),
        }
        for p in PACKAGES.values()
    ]


def package_modules(package_code: str | None) -> list[str]:
    code = (package_code or "trial").strip().lower()
    pkg = PACKAGES.get(code) or PACKAGES["trial"]
    return list(pkg["modules"])


def add_calendar_months(dt: datetime, months: int) -> datetime:
    """Add whole months preserving time-of-day; clamp day to month length."""
    if months == 0:
        return dt
    total = dt.month - 1 + months
    year = dt.year + total // 12
    month = total % 12 + 1
    day = min(dt.day, calendar.monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)


def months_between(start: datetime, end: datetime) -> int:
    """Whole calendar months from start to end (floor). Negative if end < start."""
    months = (end.year - start.year) * 12 + (end.month - start.month)
    if end.day < start.day:
        months -= 1
    return months


def term_to_months(term_value: int, term_unit: str) -> int:
    unit = (term_unit or "months").lower()
    if unit == "years":
        return int(term_value) * 12
    return int(term_value)


def resolve_enabled_modules(tenant) -> list[str]:
    """Effective module allowlist for a tenant (custom override or package default)."""
    custom = getattr(tenant, "enabled_modules", None)
    if isinstance(custom, list) and custom:
        mods = [str(m).strip().lower() for m in custom if str(m).strip()]
        # Always merge always-on
        for m in ALWAYS_ON_MODULES:
            if m not in mods:
                mods.append(m)
        return mods
    return package_modules(getattr(tenant, "package_code", None))


def module_allowed(tenant, module: str) -> bool:
    mod = (module or "").strip().lower()
    if not mod or mod == "platform":
        return True  # platform gated by role elsewhere
    if mod in ALWAYS_ON_MODULES:
        return True
    return mod in resolve_enabled_modules(tenant)


def usage_snapshot(tenant, *, now: datetime | None = None) -> dict[str, Any]:
    """Months/years assigned, used, and remaining until renewal."""
    now = now or datetime.utcnow()
    starts = getattr(tenant, "subscription_starts_at", None)
    ends = getattr(tenant, "subscription_ends_at", None)
    term_value = getattr(tenant, "subscription_term_value", None)
    term_unit = getattr(tenant, "subscription_term_unit", None) or "months"
    package_code = getattr(tenant, "package_code", None) or "trial"

    # Fall back to trial window when paid term not assigned yet
    if starts is None and getattr(tenant, "created_at", None):
        starts = tenant.created_at
    if ends is None and getattr(tenant, "trial_ends_at", None):
        ends = tenant.trial_ends_at

    months_assigned = None
    if term_value is not None:
        months_assigned = term_to_months(int(term_value), str(term_unit))
    elif starts and ends:
        months_assigned = max(0, months_between(starts, ends))

    months_used = 0
    months_remaining = None
    days_remaining = None
    years_assigned = None
    years_used = None
    years_remaining = None

    if starts:
        months_used = max(0, months_between(starts, now))
    if ends:
        days_remaining = (ends.date() - now.date()).days
        months_remaining = max(0, months_between(now, ends))
        if days_remaining < 0:
            months_remaining = 0

    if months_assigned is not None:
        years_assigned = round(months_assigned / 12, 2)
    if months_used is not None:
        years_used = round(months_used / 12, 2)
    if months_remaining is not None:
        years_remaining = round(months_remaining / 12, 2)

    enabled = resolve_enabled_modules(tenant)
    from app import store_entitlements as store_ent_svc

    pkg = PACKAGES.get(package_code) or PACKAGES["trial"]
    return {
        "package_code": package_code,
        "package_name": pkg["name"],
        "term_value": term_value,
        "term_unit": term_unit if term_value is not None else None,
        "months_assigned": months_assigned,
        "years_assigned": years_assigned,
        "months_used": months_used,
        "years_used": years_used,
        "months_remaining": months_remaining,
        "years_remaining": years_remaining,
        "days_remaining": days_remaining,
        "subscription_starts_at": starts,
        "subscription_ends_at": ends,
        "package_assigned_at": getattr(tenant, "package_assigned_at", None),
        "renewal_due": ends,
        "enabled_modules": enabled,
        "modules_customized": bool(
            isinstance(getattr(tenant, "enabled_modules", None), list)
            and getattr(tenant, "enabled_modules", None)
        ),
        # Store quotas (counts filled async via attach_store_usage / serialize paths)
        "package_max_stores": store_ent_svc.package_max_stores(package_code),
        "package_max_companies": store_ent_svc.package_max_companies(package_code),
        "max_stores_override": getattr(tenant, "max_stores_override", None),
        "store_limit": getattr(tenant, "store_limit", None),
        "subscription_store_entitlement": store_ent_svc.subscription_store_entitlement(tenant),
        "effective_store_limit": store_ent_svc.effective_store_limit(tenant),
    }
