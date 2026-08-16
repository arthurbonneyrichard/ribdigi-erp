"""Subscription-based store (location) entitlements.

Hierarchy in this codebase (Company == Tenant):
  RIBDIGI HOUSE → Package max_stores → Tenant override → Tenant store_limit → Stores

NULL / None means unlimited. Limits count *active* stores for create/activate.
Downgrades never delete stores; they only block new creates / activations while over.
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app import packages as packages_svc

STORE_LIMIT_REACHED = "STORE_LIMIT_REACHED"


def package_max_stores(package_code: str | None) -> int | None:
    """Catalog max_stores for a package code; None = unlimited."""
    code = (package_code or "trial").strip().lower()
    pkg = packages_svc.PACKAGES.get(code) or packages_svc.PACKAGES["trial"]
    raw = pkg.get("max_stores")
    if raw is None:
        return None
    return int(raw)


def package_max_companies(package_code: str | None) -> int | None:
    """Catalog max_companies (informational; this product is one company per tenant)."""
    code = (package_code or "trial").strip().lower()
    pkg = packages_svc.PACKAGES.get(code) or packages_svc.PACKAGES["trial"]
    raw = pkg.get("max_companies")
    if raw is None:
        return None
    return int(raw)


def subscription_store_entitlement(tenant: m.Tenant) -> int | None:
    """
    Platform-effective store entitlement for the tenant.
    max_stores_override (when set) wins over package catalog; None = unlimited.
    """
    override = getattr(tenant, "max_stores_override", None)
    if override is not None:
        return int(override)
    return package_max_stores(getattr(tenant, "package_code", None))


def effective_store_limit(tenant: m.Tenant) -> int | None:
    """
    Limit that create/activate must respect.
    Tenant store_limit (company allocation) cannot raise above subscription entitlement;
    when both set, effective = min(allocation, entitlement).
    """
    entitlement = subscription_store_entitlement(tenant)
    allocation = getattr(tenant, "store_limit", None)
    if allocation is not None:
        allocation = int(allocation)
    if entitlement is None and allocation is None:
        return None
    if entitlement is None:
        return allocation
    if allocation is None:
        return entitlement
    return min(allocation, entitlement)


async def count_active_stores(db: AsyncSession, tenant_id: str) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(m.Store)
        .where(m.Store.tenant_id == tenant_id, m.Store.is_active.is_(True))
    )
    return int(result.scalar_one() or 0)


async def count_all_stores(db: AsyncSession, tenant_id: str) -> int:
    result = await db.execute(
        select(func.count()).select_from(m.Store).where(m.Store.tenant_id == tenant_id)
    )
    return int(result.scalar_one() or 0)


async def get_store_usage(db: AsyncSession, tenant: m.Tenant) -> dict[str, Any]:
    """Usage + entitlement snapshot for APIs / UI."""
    active = await count_active_stores(db, tenant.id)
    total = await count_all_stores(db, tenant.id)
    entitlement = subscription_store_entitlement(tenant)
    allocation = getattr(tenant, "store_limit", None)
    if allocation is not None:
        allocation = int(allocation)
    effective = effective_store_limit(tenant)
    remaining = None if effective is None else max(0, effective - active)
    over = bool(effective is not None and active > effective)
    return {
        "stores_active": active,
        "stores_total": total,
        "stores_inactive": max(0, total - active),
        "package_max_stores": package_max_stores(getattr(tenant, "package_code", None)),
        "package_max_companies": package_max_companies(getattr(tenant, "package_code", None)),
        "max_stores_override": getattr(tenant, "max_stores_override", None),
        "subscription_store_entitlement": entitlement,
        "store_limit": allocation,
        "effective_store_limit": effective,
        "stores_remaining": remaining,
        "over_entitlement": over,
        "unlimited": effective is None,
    }


def store_limit_reached_detail(*, used: int, limit: int) -> dict[str, Any]:
    return {
        "code": STORE_LIMIT_REACHED,
        "message": (
            f"Store limit reached. Your company currently uses {used} of {limit} allowed stores. "
            "Upgrade your subscription or contact your Tenant Administrator."
        ),
        "stores_used": used,
        "stores_limit": limit,
    }


async def assert_can_create_store(db: AsyncSession, tenant: m.Tenant) -> dict[str, Any]:
    """Raise 403 STORE_LIMIT_REACHED when active stores already at/above effective limit."""
    usage = await get_store_usage(db, tenant)
    limit = usage["effective_store_limit"]
    used = usage["stores_active"]
    if limit is not None and used >= limit:
        raise HTTPException(status_code=403, detail=store_limit_reached_detail(used=used, limit=limit))
    return usage


async def assert_can_activate_store(db: AsyncSession, tenant: m.Tenant, store: m.Store) -> dict[str, Any]:
    """
    When reactivating an inactive store, require headroom under the effective limit.
    Already-active stores are allowed (no-op activate).
    """
    if bool(store.is_active):
        return await get_store_usage(db, tenant)
    usage = await get_store_usage(db, tenant)
    limit = usage["effective_store_limit"]
    used = usage["stores_active"]
    if limit is not None and used >= limit:
        raise HTTPException(
            status_code=403,
            detail={
                **store_limit_reached_detail(used=used, limit=limit),
                "message": (
                    f"Cannot activate store. Your company currently uses {used} of {limit} allowed "
                    "active stores. Deactivate another store, raise the allocation, or upgrade."
                ),
            },
        )
    return usage


async def lock_tenant_for_store_quota(db: AsyncSession, tenant_id: str) -> m.Tenant:
    """Row-lock tenant so concurrent store creates cannot both pass the limit check."""
    tenant = (
        await db.execute(select(m.Tenant).where(m.Tenant.id == tenant_id).with_for_update())
    ).scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


def validate_store_limit_value(value: int | None, *, entitlement: int | None) -> int | None:
    """Normalize tenant store_limit; must be >= 0; cannot exceed subscription entitlement when finite."""
    if value is None:
        return None
    limit = int(value)
    if limit < 0:
        raise HTTPException(status_code=422, detail="store_limit must be >= 0 or null (use full entitlement)")
    if entitlement is not None and limit > entitlement:
        raise HTTPException(
            status_code=422,
            detail=(
                f"store_limit ({limit}) cannot exceed subscription store entitlement ({entitlement})"
            ),
        )
    return limit


def validate_max_stores_override(value: int | None) -> int | None:
    if value is None:
        return None
    override = int(value)
    if override < 0:
        raise HTTPException(status_code=422, detail="max_stores_override must be >= 0 or null (unlimited/package)")
    return override
