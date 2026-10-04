"""User ↔ Store membership for store-scoped access control.

Company == Tenant in this MVP. Memberships limit which Stores a non-admin user
may open for POS / store pickers. Privileged roles always see all stores.
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m

STORE_ACCESS_DENIED = "STORE_ACCESS_DENIED"

# Roles that may operate across all tenant stores without membership rows.
PRIVILEGED_STORE_ROLES = frozenset(
    {
        "company_admin",
        "super_admin",
        "platform_owner",
        "platform_admin",
        "platform_support",
        "platform_finance",
    }
)


def role_bypasses_store_membership(role: str | None) -> bool:
    return (role or "").strip().lower() in PRIVILEGED_STORE_ROLES


async def list_memberships(
    db: AsyncSession, *, tenant_id: str, user_id: str, active_only: bool = True
) -> list[m.UserStoreMembership]:
    stmt = select(m.UserStoreMembership).where(
        m.UserStoreMembership.tenant_id == tenant_id,
        m.UserStoreMembership.user_id == user_id,
    )
    if active_only:
        stmt = stmt.where(m.UserStoreMembership.is_active.is_(True))
    rows = (await db.execute(stmt.order_by(m.UserStoreMembership.created_at.asc()))).scalars().all()
    return list(rows)


async def assigned_store_ids(
    db: AsyncSession, *, tenant_id: str, user_id: str
) -> list[str] | None:
    """
    Return store ids the user may access, or None = all active stores (privileged
    or grandfather: no memberships configured).
    """
    user = (
        await db.execute(
            select(m.User).where(m.User.id == user_id, m.User.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if role_bypasses_store_membership(user.role):
        return None
    rows = await list_memberships(db, tenant_id=tenant_id, user_id=user_id, active_only=True)
    if not rows:
        return None
    return [r.store_id for r in rows]


async def assert_store_access(
    db: AsyncSession, *, tenant_id: str, user_id: str, store_id: str | None
) -> None:
    """Deny if store_id is set and user is not allowed that store."""
    if not store_id:
        return
    allowed = await assigned_store_ids(db, tenant_id=tenant_id, user_id=user_id)
    if allowed is None:
        return
    if store_id not in allowed:
        raise HTTPException(
            status_code=403,
            detail={
                "code": STORE_ACCESS_DENIED,
                "message": "You are not assigned to this store",
                "store_id": store_id,
            },
        )


async def filter_stores_for_user(
    db: AsyncSession, *, tenant_id: str, user_id: str, stores: list[m.Store]
) -> list[m.Store]:
    allowed = await assigned_store_ids(db, tenant_id=tenant_id, user_id=user_id)
    if allowed is None:
        return stores
    allowed_set = set(allowed)
    return [s for s in stores if s.id in allowed_set]


async def replace_memberships(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    store_ids: list[str],
    actor_user_id: str | None,
) -> list[m.UserStoreMembership]:
    """Replace active memberships with the given store id list (empty = clear → all stores)."""
    user = (
        await db.execute(
            select(m.User).where(m.User.id == user_id, m.User.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    clean_ids: list[str] = []
    seen: set[str] = set()
    for raw in store_ids:
        sid = str(raw or "").strip()
        if not sid or sid in seen:
            continue
        store = (
            await db.execute(
                select(m.Store).where(m.Store.id == sid, m.Store.tenant_id == tenant_id)
            )
        ).scalar_one_or_none()
        if not store:
            raise HTTPException(status_code=404, detail=f"Store not found: {sid}")
        seen.add(sid)
        clean_ids.append(sid)

    existing = await list_memberships(db, tenant_id=tenant_id, user_id=user_id, active_only=False)
    by_store = {r.store_id: r for r in existing}
    keep = set(clean_ids)
    for row in existing:
        if row.store_id not in keep:
            row.is_active = False
    out: list[m.UserStoreMembership] = []
    for sid in clean_ids:
        row = by_store.get(sid)
        if row:
            row.is_active = True
            out.append(row)
        else:
            row = m.UserStoreMembership(
                tenant_id=tenant_id,
                user_id=user_id,
                store_id=sid,
                is_active=True,
                created_by=actor_user_id,
            )
            db.add(row)
            out.append(row)
    await db.flush()
    return out


def serialize_membership(row: m.UserStoreMembership) -> dict[str, Any]:
    return {
        "id": row.id,
        "user_id": row.user_id,
        "store_id": row.store_id,
        "is_active": bool(row.is_active),
        "created_by": row.created_by,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
