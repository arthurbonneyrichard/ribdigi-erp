"""ADR-005 user↔store membership scaffold.

Assignment CRUD plus optional flag-gated scope expansion documented in
``docs/ADR_005_MEMBERSHIP_SCOPE_CUTOVER.md``. Default operational scope remains
``stores.manager_id`` (``STORE_MEMBERSHIP_SCOPE_ENABLED`` false). When the flag
is on, ``dashboard_scope.managed_store_ids`` unions membership store IDs for
store_manager only. ADR-005 Complete / store-scoped RBAC Complete remain MISSING.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.config import settings
from app.stores import get_store

# Honesty — never flip these to True from this scaffold module alone.
# scope_wired_to_membership stays False until production-default cutover + evidence
# (flag-gated wire ≠ Complete).
ADR005_COMPLETE_CLAIMED = False
STORE_SCOPED_RBAC_COMPLETE_CLAIMED = False
SCOPE_WIRED_TO_MEMBERSHIP = False


def honesty_payload() -> dict:
    """Stable non-claim flags for API responses and tests."""
    flag_on = bool(getattr(settings, "STORE_MEMBERSHIP_SCOPE_ENABLED", False))
    return {
        "adr005_complete_claimed": ADR005_COMPLETE_CLAIMED,
        "store_scoped_rbac_complete_claimed": STORE_SCOPED_RBAC_COMPLETE_CLAIMED,
        "scope_wired_to_membership": SCOPE_WIRED_TO_MEMBERSHIP,
        "store_membership_scope_enabled": flag_on,
        "scaffold_status": "partial",
        "operational_scope": (
            "stores.manager_id ∪ user_store_memberships"
            if flag_on
            else "stores.manager_id"
        ),
    }


def serialize_membership(
    row: m.UserStoreMembership,
    *,
    user: m.User | None = None,
    store: m.Store | None = None,
) -> dict:
    return {
        "id": row.id,
        "tenant_id": row.tenant_id,
        "company_id": row.company_id,
        "user_id": row.user_id,
        "store_id": row.store_id,
        "is_active": bool(row.is_active),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "user_email": user.email if user else None,
        "user_full_name": user.full_name if user else None,
        "user_role": user.role if user else None,
        "store_code": store.code if store else None,
        "store_name": store.name if store else None,
        **honesty_payload(),
    }


async def list_store_memberships(
    db: AsyncSession,
    *,
    tenant_id: str,
    store_id: str,
    company_id: str | None = None,
    active_only: bool = False,
) -> list[dict]:
    store = await get_store(db, tenant_id, store_id, company_id=company_id)
    stmt = (
        select(m.UserStoreMembership, m.User, m.Store)
        .join(m.User, m.User.id == m.UserStoreMembership.user_id)
        .join(m.Store, m.Store.id == m.UserStoreMembership.store_id)
        .where(
            m.UserStoreMembership.tenant_id == tenant_id,
            m.UserStoreMembership.store_id == store.id,
        )
        .order_by(m.User.email)
    )
    if company_id:
        stmt = stmt.where(m.UserStoreMembership.company_id == company_id)
    if active_only:
        stmt = stmt.where(m.UserStoreMembership.is_active.is_(True))
    rows = (await db.execute(stmt)).all()
    return [serialize_membership(mem, user=user, store=st) for mem, user, st in rows]


async def list_user_store_memberships(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    company_id: str | None = None,
    active_only: bool = True,
) -> list[dict]:
    stmt = (
        select(m.UserStoreMembership, m.User, m.Store)
        .join(m.User, m.User.id == m.UserStoreMembership.user_id)
        .join(m.Store, m.Store.id == m.UserStoreMembership.store_id)
        .where(
            m.UserStoreMembership.tenant_id == tenant_id,
            m.UserStoreMembership.user_id == user_id,
        )
        .order_by(m.Store.code)
    )
    if company_id:
        stmt = stmt.where(m.UserStoreMembership.company_id == company_id)
    if active_only:
        stmt = stmt.where(m.UserStoreMembership.is_active.is_(True))
    rows = (await db.execute(stmt)).all()
    return [serialize_membership(mem, user=user, store=st) for mem, user, st in rows]


async def membership_store_ids(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    company_id: str | None = None,
) -> list[str]:
    """Active membership store IDs (assignment helper).

    ``managed_store_ids`` consults the same active rows only when
    ``STORE_MEMBERSHIP_SCOPE_ENABLED`` is true (union with manager_id).
    """
    stmt = select(m.UserStoreMembership.store_id).where(
        m.UserStoreMembership.tenant_id == tenant_id,
        m.UserStoreMembership.user_id == user_id,
        m.UserStoreMembership.is_active.is_(True),
    )
    if company_id:
        stmt = stmt.where(m.UserStoreMembership.company_id == company_id)
    rows = (await db.execute(stmt)).scalars().all()
    return [str(sid) for sid in rows]


async def assign_store_membership(
    db: AsyncSession,
    *,
    tenant_id: str,
    store_id: str,
    user_id: str,
    company_id: str | None = None,
) -> m.UserStoreMembership:
    store = await get_store(db, tenant_id, store_id, company_id=company_id)
    store_company_id = getattr(store, "company_id", None)
    if not store_company_id:
        raise HTTPException(
            status_code=400,
            detail="Store has no company_id; cannot assign membership",
        )
    if company_id and store_company_id != company_id:
        raise HTTPException(status_code=404, detail="Store not found")

    user = (
        await db.execute(
            select(m.User).where(m.User.id == user_id, m.User.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    existing = (
        await db.execute(
            select(m.UserStoreMembership).where(
                m.UserStoreMembership.tenant_id == tenant_id,
                m.UserStoreMembership.user_id == user_id,
                m.UserStoreMembership.store_id == store.id,
            )
        )
    ).scalar_one_or_none()
    now = datetime.utcnow()
    if existing:
        existing.is_active = True
        existing.company_id = store_company_id
        existing.updated_at = now
        await db.flush()
        return existing

    row = m.UserStoreMembership(
        tenant_id=tenant_id,
        company_id=store_company_id,
        user_id=user_id,
        store_id=store.id,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    await db.flush()
    return row


async def revoke_store_membership(
    db: AsyncSession,
    *,
    tenant_id: str,
    store_id: str,
    user_id: str,
    company_id: str | None = None,
) -> m.UserStoreMembership:
    store = await get_store(db, tenant_id, store_id, company_id=company_id)
    row = (
        await db.execute(
            select(m.UserStoreMembership).where(
                m.UserStoreMembership.tenant_id == tenant_id,
                m.UserStoreMembership.user_id == user_id,
                m.UserStoreMembership.store_id == store.id,
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Store membership not found")
    row.is_active = False
    row.updated_at = datetime.utcnow()
    await db.flush()
    return row
