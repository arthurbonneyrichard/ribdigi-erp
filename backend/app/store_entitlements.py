"""Subscription-based Store entitlement helpers (ADR-490 / multi-store).

Hierarchy of truth (reuse existing Tenant.max_* columns; no parallel billing ORM):

  PLAN_CATALOG.soft_limits.stores  →  Tenant.max_stores (when no override)
       ↓
  Tenant.max_stores_override OR Tenant.max_stores   (= effective tenant entitlement)
       ↓
  Company.store_limit   (Tenant Admin allocation; never exceeds remaining entitlement)
       ↓
  Active Store rows (is_active=True)

Unlimited convention: integer ``-1`` (matches enterprise soft_limits ``None`` mapped to -1).
Downgrades never delete Stores; creation/reactivation is blocked while over entitlement.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app import tenants as tenants_svc

UNLIMITED = -1

# Per-process lock: SQLite ignores SELECT FOR UPDATE across concurrent async sessions.
_creation_locks: dict[str, asyncio.Lock] = {}
_creation_locks_guard = asyncio.Lock()


async def _lock_for(tenant_id: str, company_id: str) -> asyncio.Lock:
    key = f"{tenant_id}:{company_id}"
    async with _creation_locks_guard:
        lock = _creation_locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            _creation_locks[key] = lock
        return lock


@asynccontextmanager
async def store_capacity_lock(tenant_id: str, company_id: str) -> AsyncIterator[None]:
    """Serialize store create/activate for one company inside a single process.

    Combined with SELECT FOR UPDATE for multi-worker Postgres safety.
    """
    lock = await _lock_for(tenant_id, company_id)
    async with lock:
        yield


def is_unlimited(limit: int | None) -> bool:
    return limit is not None and int(limit) < 0


def plan_default_max_stores(plan_code: str | None) -> int:
    """Map PLAN_CATALOG soft_limits.stores → integer (None → unlimited)."""
    code = (plan_code or "trial").strip().lower()
    item = tenants_svc.PLAN_CATALOG.get(code) or tenants_svc.PLAN_CATALOG["trial"]
    soft = (item.get("soft_limits") or {}).get("stores")
    if soft is None:
        return UNLIMITED
    return max(0, int(soft))


def effective_tenant_store_limit(tenant: m.Tenant) -> int:
    """Platform override wins; otherwise Tenant.max_stores (plan-synced base)."""
    override = getattr(tenant, "max_stores_override", None)
    if override is not None:
        return int(override)
    return int(getattr(tenant, "max_stores", 5) or 0)


async def count_active_stores(
    db: AsyncSession,
    *,
    tenant_id: str,
    company_id: str | None = None,
) -> int:
    q = (
        select(func.count())
        .select_from(m.Store)
        .where(m.Store.tenant_id == tenant_id, m.Store.is_active.is_(True))
    )
    if company_id:
        q = q.where(m.Store.company_id == company_id)
    return int((await db.execute(q)).scalar_one() or 0)


async def sum_company_store_allocations(
    db: AsyncSession, *, tenant_id: str, exclude_company_id: str | None = None
) -> int:
    """Sum finite company.store_limit values (unlimited company allocations are ignored here)."""
    rows = (
        await db.execute(
            select(m.Company.id, m.Company.store_limit).where(
                m.Company.tenant_id == tenant_id,
                m.Company.is_active.is_(True),
            )
        )
    ).all()
    total = 0
    for cid, lim in rows:
        if exclude_company_id and cid == exclude_company_id:
            continue
        if lim is None:
            continue
        if is_unlimited(int(lim)):
            continue
        total += max(0, int(lim))
    return total


def company_store_limit_value(company: m.Company) -> int | None:
    """Explicit allocation, or None for legacy (share remaining tenant entitlement)."""
    lim = getattr(company, "store_limit", None)
    if lim is None:
        return None
    return int(lim)


async def effective_company_store_limit(
    db: AsyncSession, *, tenant: m.Tenant, company: m.Company
) -> int:
    """Resolved company cap used by create/activate checks."""
    explicit = company_store_limit_value(company)
    if explicit is not None:
        return explicit
    tenant_limit = effective_tenant_store_limit(tenant)
    if is_unlimited(tenant_limit):
        return UNLIMITED
    tenant_used = await count_active_stores(db, tenant_id=tenant.id)
    company_used = await count_active_stores(
        db, tenant_id=tenant.id, company_id=company.id
    )
    remaining = max(0, tenant_limit - tenant_used)
    return company_used + remaining


async def get_tenant_store_entitlement(db: AsyncSession, tenant: m.Tenant) -> dict:
    limit = effective_tenant_store_limit(tenant)
    used = await count_active_stores(db, tenant_id=tenant.id)
    allocated = await sum_company_store_allocations(db, tenant_id=tenant.id)
    unlimited = is_unlimited(limit)
    remaining = None if unlimited else max(0, limit - used)
    unallocated = None if unlimited else max(0, limit - allocated)
    over_entitlement = (not unlimited) and used > limit
    over_allocated = (not unlimited) and allocated > limit
    return {
        "max_stores": limit,
        "max_stores_unlimited": unlimited,
        "max_stores_override": getattr(tenant, "max_stores_override", None),
        "plan_code": getattr(tenant, "plan_code", None) or "trial",
        "plan_default_max_stores": plan_default_max_stores(getattr(tenant, "plan_code", None)),
        "used": used,
        "allocated_to_companies": allocated,
        "remaining": remaining,
        "unallocated": unallocated,
        "over_entitlement": over_entitlement,
        "over_allocated": over_allocated,
        "billing_deferred": True,
    }


async def get_company_store_entitlement(
    db: AsyncSession, *, tenant: m.Tenant, company: m.Company
) -> dict:
    tenant_ent = await get_tenant_store_entitlement(db, tenant)
    explicit = company_store_limit_value(company)
    company_limit = await effective_company_store_limit(db, tenant=tenant, company=company)
    used = await count_active_stores(db, tenant_id=tenant.id, company_id=company.id)
    company_unlimited = is_unlimited(company_limit)
    remaining = None if company_unlimited else max(0, company_limit - used)
    return {
        "company_id": company.id,
        "company_name": company.name,
        "store_limit": company_limit,
        "store_limit_explicit": explicit,
        "store_limit_legacy_unallocated": explicit is None,
        "store_limit_unlimited": company_unlimited,
        "used": used,
        "remaining": remaining,
        "tenant": {
            "max_stores": tenant_ent["max_stores"],
            "used": tenant_ent["used"],
            "remaining": tenant_ent["remaining"],
            "over_entitlement": tenant_ent["over_entitlement"],
            "over_allocated": tenant_ent["over_allocated"],
            "unallocated": tenant_ent["unallocated"],
        },
        "can_create_store": await can_create_store(db, tenant=tenant, company=company),
    }


async def can_create_store(
    db: AsyncSession, *, tenant: m.Tenant, company: m.Company
) -> bool:
    try:
        await assert_can_create_store(db, tenant=tenant, company=company, lock=False)
        return True
    except HTTPException:
        return False


async def assert_can_create_store(
    db: AsyncSession,
    *,
    tenant: m.Tenant,
    company: m.Company,
    lock: bool = True,
) -> None:
    """Reject when company or tenant active-store entitlement is exhausted.

    When ``lock`` is True, locks the Tenant and Company rows (SELECT FOR UPDATE)
    so concurrent creates cannot both pass the count check.
    """
    if company.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="Company not found")

    if lock:
        await db.execute(select(m.Tenant).where(m.Tenant.id == tenant.id).with_for_update())
        await db.execute(select(m.Company).where(m.Company.id == company.id).with_for_update())
        # Refresh after lock
        tenant = await db.get(m.Tenant, tenant.id) or tenant
        company = await db.get(m.Company, company.id) or company

    tenant_limit = effective_tenant_store_limit(tenant)
    tenant_used = await count_active_stores(db, tenant_id=tenant.id)
    company_limit = await effective_company_store_limit(db, tenant=tenant, company=company)
    company_used = await count_active_stores(
        db, tenant_id=tenant.id, company_id=company.id
    )

    if not is_unlimited(tenant_limit) and tenant_used >= tenant_limit:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "STORE_LIMIT_REACHED",
                "scope": "tenant",
                "message": (
                    f"Store limit reached. Your tenant currently uses {tenant_used} of "
                    f"{tenant_limit} allowed stores. Upgrade your subscription or contact "
                    "RIBDIGI HOUSE / your Tenant Administrator."
                ),
                "max_stores": tenant_limit,
                "current_stores": tenant_used,
                "company_id": company.id,
            },
        )

    if not is_unlimited(company_limit) and company_used >= company_limit:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "STORE_LIMIT_REACHED",
                "scope": "company",
                "message": (
                    f"Store limit reached. Your company currently uses {company_used} of "
                    f"{company_limit} allowed stores. Upgrade your subscription or contact "
                    "your Tenant Administrator."
                ),
                "max_stores": company_limit,
                "current_stores": company_used,
                "company_id": company.id,
                "tenant_max_stores": tenant_limit if not is_unlimited(tenant_limit) else None,
                "tenant_current_stores": tenant_used,
            },
        )


async def assert_can_activate_store(
    db: AsyncSession, *, tenant: m.Tenant, company: m.Company, store: m.Store
) -> None:
    """Reactivating an inactive store consumes entitlement like a create."""
    if store.is_active:
        return
    await assert_can_create_store(db, tenant=tenant, company=company, lock=True)


async def assert_store_counts_not_exceeded(
    db: AsyncSession, *, tenant: m.Tenant, company: m.Company
) -> None:
    """Post-write guard: active counts must not exceed limits (strict ``>``).

    Call after flush of a new/reactivated Store so a raced insert cannot commit.
    """
    if company.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="Company not found")

    tenant_limit = effective_tenant_store_limit(tenant)
    tenant_used = await count_active_stores(db, tenant_id=tenant.id)
    company_limit = await effective_company_store_limit(db, tenant=tenant, company=company)
    company_used = await count_active_stores(
        db, tenant_id=tenant.id, company_id=company.id
    )

    if not is_unlimited(tenant_limit) and tenant_used > tenant_limit:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "STORE_LIMIT_REACHED",
                "scope": "tenant",
                "message": (
                    f"Store limit reached. Your tenant currently uses {tenant_used} of "
                    f"{tenant_limit} allowed stores. Upgrade your subscription or contact "
                    "RIBDIGI HOUSE / your Tenant Administrator."
                ),
                "max_stores": tenant_limit,
                "current_stores": tenant_used,
                "company_id": company.id,
            },
        )

    if not is_unlimited(company_limit) and company_used > company_limit:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "STORE_LIMIT_REACHED",
                "scope": "company",
                "message": (
                    f"Store limit reached. Your company currently uses {company_used} of "
                    f"{company_limit} allowed stores. Upgrade your subscription or contact "
                    "your Tenant Administrator."
                ),
                "max_stores": company_limit,
                "current_stores": company_used,
                "company_id": company.id,
                "tenant_max_stores": tenant_limit if not is_unlimited(tenant_limit) else None,
                "tenant_current_stores": tenant_used,
            },
        )


async def set_company_store_limit(
    db: AsyncSession,
    *,
    tenant: m.Tenant,
    company: m.Company,
    store_limit: int,
) -> m.Company:
    """Tenant Admin allocation. Must not exceed remaining unallocated entitlement."""
    if company.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="Company not found")

    await db.execute(select(m.Tenant).where(m.Tenant.id == tenant.id).with_for_update())
    await db.execute(select(m.Company).where(m.Company.id == company.id).with_for_update())
    tenant = await db.get(m.Tenant, tenant.id) or tenant
    company = await db.get(m.Company, company.id) or company

    if store_limit < UNLIMITED:
        raise HTTPException(status_code=400, detail="store_limit must be >= -1")

    used = await count_active_stores(db, tenant_id=tenant.id, company_id=company.id)
    if not is_unlimited(store_limit) and store_limit < used:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "STORE_ALLOCATION_BELOW_USAGE",
                "message": (
                    f"Cannot set allocation to {store_limit}: company already has "
                    f"{used} active store(s). Deactivate stores first or choose a "
                    "higher allocation."
                ),
                "store_limit": store_limit,
                "current_stores": used,
            },
        )

    tenant_limit = effective_tenant_store_limit(tenant)
    if not is_unlimited(tenant_limit) and not is_unlimited(store_limit):
        others = await sum_company_store_allocations(
            db, tenant_id=tenant.id, exclude_company_id=company.id
        )
        if others + store_limit > tenant_limit:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "STORE_ALLOCATION_EXCEEDS_TENANT",
                    "message": (
                        f"Allocation {store_limit} would exceed tenant entitlement "
                        f"({tenant_limit}). Other companies already use {others} of the "
                        f"allowance; at most {max(0, tenant_limit - others)} remain."
                    ),
                    "requested": store_limit,
                    "tenant_max_stores": tenant_limit,
                    "allocated_elsewhere": others,
                    "unallocated": max(0, tenant_limit - others),
                },
            )

    if is_unlimited(store_limit) and not is_unlimited(tenant_limit):
        raise HTTPException(
            status_code=400,
            detail={
                "code": "STORE_ALLOCATION_UNLIMITED_DENIED",
                "message": (
                    "Cannot assign unlimited company store allocation while the tenant "
                    "entitlement is finite."
                ),
            },
        )

    company.store_limit = int(store_limit)
    await db.flush()
    return company


async def assign_initial_company_store_limit(
    db: AsyncSession,
    *,
    tenant: m.Tenant,
    company: m.Company,
    requested_limit: int | None,
) -> m.Company:
    """Lock + validate a new company's allocation.

    Explicit ``store_limit`` is rejected when it exceeds remaining entitlement.
    Default (None) assigns 1 slot when unallocated capacity exists, otherwise 0.
    """
    await db.execute(select(m.Tenant).where(m.Tenant.id == tenant.id).with_for_update())
    tenant = await db.get(m.Tenant, tenant.id) or tenant
    if requested_limit is not None:
        return await set_company_store_limit(
            db, tenant=tenant, company=company, store_limit=int(requested_limit)
        )
    tenant_limit = effective_tenant_store_limit(tenant)
    if is_unlimited(tenant_limit):
        default_limit = 1
    else:
        others = await sum_company_store_allocations(
            db, tenant_id=tenant.id, exclude_company_id=company.id
        )
        remaining = max(0, tenant_limit - others)
        default_limit = 1 if remaining >= 1 else 0
    return await set_company_store_limit(
        db, tenant=tenant, company=company, store_limit=default_limit
    )


def apply_plan_store_defaults(tenant: m.Tenant, plan_code: str) -> dict:
    """When override is unset, sync Tenant.max_stores from PLAN_CATALOG soft_limits."""
    before = int(getattr(tenant, "max_stores", 5) or 0)
    if getattr(tenant, "max_stores_override", None) is not None:
        return {
            "synced": False,
            "reason": "override_set",
            "max_stores": before,
            "max_stores_override": tenant.max_stores_override,
        }
    new_limit = plan_default_max_stores(plan_code)
    tenant.max_stores = new_limit
    return {
        "synced": True,
        "from": before,
        "to": new_limit,
        "max_stores_override": None,
    }


async def store_usage_by_company(db: AsyncSession, *, tenant_id: str) -> list[dict]:
    companies = (
        await db.execute(
            select(m.Company)
            .where(m.Company.tenant_id == tenant_id)
            .order_by(m.Company.name)
        )
    ).scalars().all()
    tenant = await db.get(m.Tenant, tenant_id)
    out = []
    for co in companies:
        used = await count_active_stores(db, tenant_id=tenant_id, company_id=co.id)
        explicit = company_store_limit_value(co)
        lim = (
            await effective_company_store_limit(db, tenant=tenant, company=co)
            if tenant
            else (explicit or 0)
        )
        unlimited = is_unlimited(lim)
        out.append(
            {
                "company_id": co.id,
                "company_name": co.name,
                "company_code": co.code,
                "is_active": bool(co.is_active),
                "store_limit": lim if explicit is not None else lim,
                "store_limit_explicit": explicit,
                "store_limit_legacy_unallocated": explicit is None,
                "store_limit_unlimited": unlimited,
                "used": used,
                "remaining": None if unlimited else max(0, lim - used),
            }
        )
    return out
