"""Time-bounded RBAC elevation / break-glass grants (MVP Complete for this slice).

Reuses the ``expires_at`` deny-after-expiry pattern from store memberships.
Does **not** claim overall RBAC Complete, Offline, 7-day VERIFIED, go-live, or
paid billing Completes. Store-scoped RBAC Complete is claimed on the membership
honesty surface (flag default OFF); elevation keeps the same flag in sync.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from copy import deepcopy

from fastapi import HTTPException
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.rbac import (
    RECORD_SCOPE_KEY,
    assert_permissions_within_grantor,
    ensure_permission_dependencies,
    expand_permission_aliases,
    is_wildcard_admin,
)

# Honesty — elevation/break-glass MVP Complete for this engine slice.
ELEVATION_BREAK_GLASS_CLAIMED = True
# Keep in sync with store_memberships.STORE_SCOPED_RBAC_COMPLETE_CLAIMED.
STORE_SCOPED_RBAC_COMPLETE_CLAIMED = True

MIN_REASON_LEN = 5
MAX_REASON_LEN = 500
# Break-glass ceiling — grants longer than this are rejected.
MAX_ELEVATION_HOURS = 24


def honesty_payload() -> dict:
    return {
        "elevation_break_glass_claimed": ELEVATION_BREAK_GLASS_CLAIMED,
        "store_scoped_rbac_complete_claimed": STORE_SCOPED_RBAC_COMPLETE_CLAIMED,
        "max_elevation_hours": MAX_ELEVATION_HOURS,
        "complete_means": (
            "time_bounded_elevated_grant_with_required_reason_audit_and_auto_expiry; "
            "not_overall_rbac_complete"
        ),
    }


def elevation_not_expired_clause(now: datetime | None = None):
    """SQLAlchemy: expires_at still in the future (required on every grant)."""
    as_of = now or datetime.utcnow()
    return m.RbacElevation.expires_at > as_of


def is_elevation_effective(row: m.RbacElevation, *, now: datetime | None = None) -> bool:
    if row.revoked_at is not None:
        return False
    as_of = now or datetime.utcnow()
    return row.expires_at is not None and row.expires_at > as_of


def merge_permission_maps(base: dict | None, extra: dict | None) -> dict:
    """Union module→actions maps; wildcard admin in either wins."""
    left = expand_permission_aliases(base or {})
    right = expand_permission_aliases(extra or {})
    if is_wildcard_admin(left) or is_wildcard_admin(right):
        return {"*": ["*"]}
    out: dict[str, list[str]] = deepcopy(left)
    for module, actions in right.items():
        if module == RECORD_SCOPE_KEY:
            continue
        bucket = out.setdefault(module, [])
        for act in actions or []:
            if act and act not in bucket:
                bucket.append(act)
    # Preserve record scope from base when present.
    if isinstance(base, dict) and RECORD_SCOPE_KEY in base:
        out[RECORD_SCOPE_KEY] = base[RECORD_SCOPE_KEY]
    return out


def serialize_elevation(row: m.RbacElevation, *, subject: m.User | None = None) -> dict:
    now = datetime.utcnow()
    effective = is_elevation_effective(row, now=now)
    return {
        "id": row.id,
        "tenant_id": row.tenant_id,
        "user_id": row.user_id,
        "permissions": row.permissions or {},
        "reason": row.reason,
        "expires_at": row.expires_at.isoformat() if row.expires_at else None,
        "granted_by": row.granted_by,
        "revoked_at": row.revoked_at.isoformat() if row.revoked_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "is_expired": bool(row.expires_at is not None and row.expires_at <= now),
        "is_effective": effective,
        "subject_email": subject.email if subject else None,
        "subject_role": subject.role if subject else None,
        **honesty_payload(),
    }


def _parse_expires_at(raw) -> datetime | None:
    """ISO-8601 expires_at (same pattern as store membership temp access)."""
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


def parse_required_expires_at(raw) -> datetime:
    """Parse required future expires_at within MAX_ELEVATION_HOURS."""
    if raw is None or raw == "":
        raise HTTPException(status_code=400, detail="expires_at is required for elevation")
    exp = _parse_expires_at(raw)
    if exp is None:
        raise HTTPException(status_code=400, detail="expires_at is required for elevation")
    now = datetime.utcnow()
    if exp <= now:
        raise HTTPException(status_code=400, detail="expires_at must be in the future")
    ceiling = now + timedelta(hours=MAX_ELEVATION_HOURS)
    if exp > ceiling:
        raise HTTPException(
            status_code=400,
            detail=f"expires_at must be within {MAX_ELEVATION_HOURS} hours",
        )
    return exp


def parse_required_reason(raw) -> str:
    text = str(raw or "").strip()
    if len(text) < MIN_REASON_LEN:
        raise HTTPException(
            status_code=400,
            detail=f"reason is required (min {MIN_REASON_LEN} characters)",
        )
    if len(text) > MAX_REASON_LEN:
        raise HTTPException(
            status_code=400,
            detail=f"reason must be at most {MAX_REASON_LEN} characters",
        )
    return text


async def list_user_elevations(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    effective_only: bool = False,
) -> list[m.RbacElevation]:
    stmt = (
        select(m.RbacElevation)
        .where(
            m.RbacElevation.tenant_id == tenant_id,
            m.RbacElevation.user_id == user_id,
        )
        .order_by(m.RbacElevation.created_at.desc())
    )
    if effective_only:
        stmt = stmt.where(
            m.RbacElevation.revoked_at.is_(None),
            elevation_not_expired_clause(),
        )
    return list((await db.execute(stmt)).scalars().all())


async def active_elevation_permissions(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
) -> dict:
    """Merged permissions from all effective elevations (empty if none)."""
    rows = await list_user_elevations(
        db, tenant_id=tenant_id, user_id=user_id, effective_only=True
    )
    merged: dict = {}
    for row in rows:
        merged = merge_permission_maps(merged, row.permissions or {})
    return merged


async def overlay_active_elevations(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    base: dict | None,
) -> dict:
    """Merge effective elevation grants onto a base permission map."""
    elevated = await active_elevation_permissions(
        db, tenant_id=tenant_id, user_id=user_id
    )
    if not elevated:
        return dict(base or {})
    return merge_permission_maps(base, elevated)


async def grant_elevation(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    permissions: dict,
    reason: str,
    expires_at: datetime,
    granted_by: str,
    grantor_permissions: dict | None,
) -> m.RbacElevation:
    if user_id == granted_by:
        raise HTTPException(
            status_code=400,
            detail="Cannot elevate your own permissions (break-glass requires a second actor)",
        )
    user = (
        await db.execute(
            select(m.User).where(m.User.id == user_id, m.User.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        perms = ensure_permission_dependencies(
            permissions,
            allow_wildcard=False,
            allow_platform_modules=False,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not perms:
        raise HTTPException(status_code=400, detail="permissions must grant at least one action")
    if is_wildcard_admin(perms):
        raise HTTPException(status_code=400, detail="Elevation cannot grant wildcard admin")

    try:
        assert_permissions_within_grantor(perms, grantor_permissions)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    now = datetime.utcnow()
    row = m.RbacElevation(
        tenant_id=tenant_id,
        user_id=user_id,
        permissions=perms,
        reason=reason,
        expires_at=expires_at,
        granted_by=granted_by,
        revoked_at=None,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    await db.flush()
    return row


async def revoke_elevation(
    db: AsyncSession,
    *,
    tenant_id: str,
    elevation_id: str,
    actor_id: str,
) -> m.RbacElevation:
    row = (
        await db.execute(
            select(m.RbacElevation).where(
                m.RbacElevation.id == elevation_id,
                m.RbacElevation.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Elevation not found")
    if row.revoked_at is not None:
        return row
    now = datetime.utcnow()
    row.revoked_at = now
    row.updated_at = now
    # actor recorded via audit; keep column lean
    _ = actor_id
    await db.flush()
    return row


def effective_filter_clause(now: datetime | None = None):
    """revoked_at IS NULL AND expires_at > now."""
    return and_(
        m.RbacElevation.revoked_at.is_(None),
        elevation_not_expired_clause(now),
    )
