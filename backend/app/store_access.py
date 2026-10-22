"""User ↔ Store membership for store-scoped access control.

Reuses `user_store_memberships` + User.branch_id (ADR-005 Complete is not claimed).
Company == Tenant in this MVP. When active memberships exist, access is only those
stores (same tenant). Empty membership still grandfathers all tenant stores for
legacy users. Privileged roles always see every store in the tenant so a sole
store cannot silently lock a company admin out.
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m

STORE_ACCESS_DENIED = "STORE_ACCESS_DENIED"
STORE_BRANCH_MISMATCH = "STORE_BRANCH_MISMATCH"
STORE_SELECTION_REQUIRED = "STORE_SELECTION_REQUIRED"

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


async def memberships_by_user_ids(
    db: AsyncSession, *, tenant_id: str, user_ids: list[str]
) -> dict[str, list[str]]:
    """Active store ids per user. Missing users map to []. Does not invent access."""
    out: dict[str, list[str]] = {uid: [] for uid in user_ids}
    ids = [uid for uid in user_ids if uid]
    if not ids:
        return out
    rows = (
        await db.execute(
            select(m.UserStoreMembership).where(
                m.UserStoreMembership.tenant_id == tenant_id,
                m.UserStoreMembership.user_id.in_(ids),
                m.UserStoreMembership.is_active.is_(True),
            )
        )
    ).scalars().all()
    for row in rows:
        out.setdefault(row.user_id, []).append(row.store_id)
    return out


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


def _is_unscoped_actor(user_id: str | None) -> bool:
    """Jobs (`system`) and API keys are tenant-wide; they have no membership rows."""
    uid = (user_id or "").strip()
    return (not uid) or uid == "system" or uid.startswith("apikey:")


def merge_store_ids(store_id: str | None, store_ids: list[str] | None) -> list[str]:
    """Dedupe store_id + store_ids. Order preserved. Empty strings skipped."""
    out: list[str] = []
    seen: set[str] = set()
    for raw in list(store_ids or []) + ([store_id] if store_id else []):
        sid = str(raw or "").strip()
        if not sid or sid in seen:
            continue
        seen.add(sid)
        out.append(sid)
    return out


async def sole_active_store_id(db: AsyncSession, tenant_id: str) -> str | None:
    """The tenant's only active store, else None. Tenant-scoped; no extra tables."""
    rows = (
        await db.execute(
            select(m.Store.id).where(
                m.Store.tenant_id == tenant_id,
                m.Store.is_active.is_(True),
            )
        )
    ).scalars().all()
    if len(rows) == 1:
        return rows[0]
    return None


async def assign_stores_on_create(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    role: str | None,
    store_id: str | None,
    store_ids: list[str] | None,
    actor_user_id: str | None,
) -> list[str]:
    """Apply create-time store memberships.

    Explicit ids win. If none were sent and the tenant has exactly one active
    store, assign that store (single-store: no extra setup). Privileged roles
    skip auto-assign so empty membership keeps all tenant stores (no lockout).
    """
    requested = merge_store_ids(store_id, store_ids)
    if not requested and not role_bypasses_store_membership(role):
        sole = await sole_active_store_id(db, tenant_id)
        if sole:
            requested = [sole]
    if not requested:
        return []
    rows = await replace_memberships(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        store_ids=requested,
        actor_user_id=actor_user_id,
    )
    return [r.store_id for r in rows]


async def assigned_store_ids(
    db: AsyncSession, *, tenant_id: str, user_id: str
) -> list[str] | None:
    """
    Return store ids the user may access, or None = all active stores in this
    tenant (privileged or grandfather: no memberships configured).

    Empty membership list = grandfather all stores in *this tenant* (legacy).
    When any active membership exists, access is limited to those store ids.
    """
    if _is_unscoped_actor(user_id):
        return None
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
    """Deny if store_id is set and user is not allowed that store.

    Client IDs are never trusted alone: the store must belong to this tenant
    even for privileged / grandfathered actors.
    """
    if not store_id:
        return
    await get_tenant_store(db, tenant_id, store_id)
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


async def assert_warehouse_access(
    db: AsyncSession, *, tenant_id: str, user_id: str, warehouse_id: str | None
) -> None:
    """Deny if warehouse is linked to a store the user may not access."""
    if not warehouse_id:
        return
    wh = (
        await db.execute(
            select(m.Warehouse).where(
                m.Warehouse.id == warehouse_id,
                m.Warehouse.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not wh:
        raise HTTPException(status_code=404, detail="Warehouse not found")
    await assert_store_access(
        db, tenant_id=tenant_id, user_id=user_id, store_id=wh.store_id
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

    required_branch = getattr(user, "branch_id", None)
    clean_ids: list[str] = []
    seen: set[str] = set()
    for raw in store_ids:
        sid = str(raw or "").strip()
        if not sid or sid in seen:
            continue
        store = await get_tenant_store(db, tenant_id, sid)
        assert_store_matches_branch(store, required_branch)
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


async def get_tenant_store(db: AsyncSession, tenant_id: str, store_id: str) -> m.Store:
    store = (
        await db.execute(
            select(m.Store).where(m.Store.id == store_id, m.Store.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if not store:
        raise HTTPException(status_code=404, detail=f"Store not found: {store_id}")
    return store


def assert_store_matches_branch(store: m.Store, branch_id: str | None) -> None:
    """When a branch is selected, the store must belong to that branch (same tenant)."""
    if not branch_id:
        return
    if store.branch_id != branch_id:
        raise HTTPException(
            status_code=400,
            detail={
                "code": STORE_BRANCH_MISMATCH,
                "message": "Store must belong to the selected branch",
                "store_id": store.id,
                "branch_id": branch_id,
            },
        )


async def prune_memberships_for_branch(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    branch_id: str | None,
    actor_user_id: str | None,
) -> list[m.UserStoreMembership] | None:
    """Drop stores that are not in ``branch_id``.

    If none remain, leave existing memberships unchanged so empty assignment
    cannot silently grandfather (broaden) access.
    """
    if not branch_id:
        return None
    rows = await list_memberships(db, tenant_id=tenant_id, user_id=user_id, active_only=True)
    if not rows:
        return None
    keep: list[str] = []
    for row in rows:
        store = (
            await db.execute(
                select(m.Store).where(
                    m.Store.id == row.store_id, m.Store.tenant_id == tenant_id
                )
            )
        ).scalar_one_or_none()
        if store and store.branch_id == branch_id:
            keep.append(row.store_id)
    if not keep:
        return None
    if set(keep) == {r.store_id for r in rows}:
        return rows
    return await replace_memberships(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        store_ids=keep,
        actor_user_id=actor_user_id,
    )


async def require_location_warehouse(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    warehouse_id: str | None,
) -> None:
    """Store-assigned users must mutate stock through a warehouse they can access."""
    allowed = await assigned_store_ids(db, tenant_id=tenant_id, user_id=user_id)
    if allowed is not None and not warehouse_id:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "WAREHOUSE_REQUIRED",
                "message": "warehouse_id is required for your store assignment",
            },
        )
    if warehouse_id:
        await assert_warehouse_access(
            db, tenant_id=tenant_id, user_id=user_id, warehouse_id=warehouse_id
        )


def with_store_fields(payload: dict[str, Any], store_ids: list[str] | None) -> dict[str, Any]:
    ids = list(store_ids or [])
    payload["store_ids"] = ids
    payload["store_id"] = ids[0] if ids else None
    return payload


async def bind_location_scope(
    db: AsyncSession, *, tenant_id: str, user_id: str, claims: dict[str, Any]
) -> dict[str, Any]:
    """Attach session location scope from membership — never from client IDs.

    Location assignment does not grant extra RBAC; it only constrains stores.
    ``store_ids`` is None when the actor may use every tenant store.
    """
    allowed = await assigned_store_ids(db, tenant_id=tenant_id, user_id=user_id)
    claims["store_ids"] = list(allowed) if allowed is not None else None
    claims["store_scope"] = "all" if allowed is None else "assigned"
    return claims


async def resolve_requested_store_id(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    client_store_id: str | None,
    require_store: bool = False,
) -> str | None:
    """Authorize a client store_id against session assignment.

    Client IDs are never trusted alone. A single assigned store is used when the
    client omits store_id. Multiple assignments require an explicit pick.
    """
    sid = str(client_store_id or "").strip() or None
    allowed = await assigned_store_ids(db, tenant_id=tenant_id, user_id=user_id)
    if sid:
        await assert_store_access(
            db, tenant_id=tenant_id, user_id=user_id, store_id=sid
        )
        return sid
    if allowed is None:
        if require_store:
            raise HTTPException(status_code=400, detail="store_id is required")
        return None
    if len(allowed) == 1:
        return allowed[0]
    raise HTTPException(
        status_code=400,
        detail={
            "code": STORE_SELECTION_REQUIRED,
            "message": "Select an assigned store",
            "store_ids": allowed,
        },
    )


async def report_store_kwargs(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    store_id: str | None,
) -> dict[str, Any]:
    """Session-derived store filter for reports/search/export.

    Assigned users without a store pick are limited to their stores (IN filter).
    A client store_id is accepted only after membership + tenant checks.
    """
    sid = str(store_id or "").strip() or None
    await assert_store_access(db, tenant_id=tenant_id, user_id=user_id, store_id=sid)
    allowed = await assigned_store_ids(db, tenant_id=tenant_id, user_id=user_id)
    if sid:
        return {"store_id": sid, "store_ids": None}
    if allowed is None:
        return {"store_id": None, "store_ids": None}
    return {"store_id": None, "store_ids": list(allowed)}
