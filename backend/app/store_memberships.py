"""ADR-005 user↔store membership scaffold.

Assignment CRUD plus optional flag-gated scope expansion documented in
``docs/ADR_005_MEMBERSHIP_SCOPE_CUTOVER.md``. Default operational scope remains
``stores.manager_id`` (``STORE_MEMBERSHIP_SCOPE_ENABLED`` false). When the flag
is on, ``dashboard_scope.managed_store_ids`` unions membership store IDs for
store_manager only; cashiers stay ``None`` on that helper and use
``store_visibility_ids`` / ``cashier_membership_store_ids`` for POS + store-list
fail-closed. Optional ``expires_at`` excludes rows from scope once past (temp
access PARTIAL — elevation / break-glass MISSING). ADR-005 Complete via
automated soak; Complete ≠ prod default ON. Store-scoped RBAC Complete remains
MISSING.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.config import settings
from app.stores import get_store

# Honesty — ADR-005 Complete via automated soak (SEC-M2-style). Flag default
# OFF remains intentional ops cutover. Store-scoped RBAC Complete stays false.
ADR005_COMPLETE_CLAIMED = True
STORE_SCOPED_RBAC_COMPLETE_CLAIMED = False
SCOPE_WIRED_TO_MEMBERSHIP = True
# Temp membership expiry is enforced in scope; elevation/break-glass not claimed.
TEMP_MEMBERSHIP_EXPIRES_AT_CLAIMED = True
ELEVATION_BREAK_GLASS_CLAIMED = False


def honesty_payload() -> dict:
    """Stable honesty flags for API responses and tests."""
    flag_on = bool(getattr(settings, "STORE_MEMBERSHIP_SCOPE_ENABLED", False))
    return {
        "adr005_complete_claimed": ADR005_COMPLETE_CLAIMED,
        "store_scoped_rbac_complete_claimed": STORE_SCOPED_RBAC_COMPLETE_CLAIMED,
        "scope_wired_to_membership": SCOPE_WIRED_TO_MEMBERSHIP,
        "store_membership_scope_enabled": flag_on,
        "cashier_membership_fail_closed": flag_on,
        "temp_membership_expires_at_claimed": TEMP_MEMBERSHIP_EXPIRES_AT_CLAIMED,
        "elevation_break_glass_claimed": ELEVATION_BREAK_GLASS_CLAIMED,
        "scaffold_status": "complete",
        "operational_scope": (
            "stores.manager_id ∪ user_store_memberships (+ cashier membership fail-closed on POS/store lists; expires_at enforced)"
            if flag_on
            else "stores.manager_id (membership scope wired; enable STORE_MEMBERSHIP_SCOPE_ENABLED for union + cashier fail-closed; expires_at enforced when flag ON)"
        ),
        "complete_means": (
            "feature_complete_plus_automated_flag_on_soak; "
            "production_default_flag_remains_off_until_ops_cutover"
        ),
    }


def membership_not_expired_clause(now: datetime | None = None):
    """SQLAlchemy clause: expires_at is null or still in the future."""
    as_of = now or datetime.utcnow()
    return or_(
        m.UserStoreMembership.expires_at.is_(None),
        m.UserStoreMembership.expires_at > as_of,
    )


def is_membership_effective(row: m.UserStoreMembership, *, now: datetime | None = None) -> bool:
    """Active and not past expires_at (null expires_at = permanent)."""
    if not bool(row.is_active):
        return False
    exp = getattr(row, "expires_at", None)
    if exp is None:
        return True
    as_of = now or datetime.utcnow()
    return exp > as_of


def parse_expires_at(raw) -> datetime | None:
    """Parse optional ISO-8601 expires_at; None clears expiry."""
    if raw is None or raw == "":
        return None
    try:
        text = str(raw).strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is not None:
            dt = dt.replace(tzinfo=None)
        return dt
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="expires_at must be ISO-8601") from exc


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
        "expires_at": row.expires_at.isoformat() if row.expires_at else None,
        "is_expired": bool(
            row.expires_at is not None and row.expires_at <= datetime.utcnow()
        ),
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
    effective_only: bool = False,
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
    if effective_only:
        stmt = stmt.where(membership_not_expired_clause())
    rows = (await db.execute(stmt)).all()
    return [serialize_membership(mem, user=user, store=st) for mem, user, st in rows]


async def membership_store_ids(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    company_id: str | None = None,
) -> list[str]:
    """Active, non-expired membership store IDs (assignment + scope helper).

    ``managed_store_ids`` consults the same effective rows only when
    ``STORE_MEMBERSHIP_SCOPE_ENABLED`` is true (union with manager_id).
    """
    stmt = select(m.UserStoreMembership.store_id).where(
        m.UserStoreMembership.tenant_id == tenant_id,
        m.UserStoreMembership.user_id == user_id,
        m.UserStoreMembership.is_active.is_(True),
        membership_not_expired_clause(),
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
    expires_at: datetime | None = None,
    clear_expires_at: bool = False,
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
        if clear_expires_at:
            existing.expires_at = None
        elif expires_at is not None:
            existing.expires_at = expires_at
        await db.flush()
        return existing

    row = m.UserStoreMembership(
        tenant_id=tenant_id,
        company_id=store_company_id,
        user_id=user_id,
        store_id=store.id,
        is_active=True,
        expires_at=None if clear_expires_at else expires_at,
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
