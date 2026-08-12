"""Platform (software-owner) staff users on the platform home tenant."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.rbac import (
    PLATFORM_ROLES,
    can_assign_platform_role,
    is_platform_role,
    permissions_for_role,
    serialize_user,
)
from app.security import hash_password, validate_password_strength

# Safe fallback when revoking software-owner dashboard access.
DEFAULT_APP_ROLE = "company_admin"


async def list_platform_staff(db: AsyncSession, *, tenant_id: str) -> list[m.User]:
    rows = (
        await db.execute(
            select(m.User)
            .where(m.User.tenant_id == tenant_id)
            .order_by(m.User.full_name.asc())
        )
    ).scalars().all()
    return [u for u in rows if is_platform_role(u.role)]


async def list_app_users(db: AsyncSession, *, tenant_id: str) -> list[m.User]:
    """Non-platform users on the platform workspace (candidates for dashboard access)."""
    rows = (
        await db.execute(
            select(m.User)
            .where(m.User.tenant_id == tenant_id)
            .order_by(m.User.full_name.asc())
        )
    ).scalars().all()
    return [u for u in rows if not is_platform_role(u.role)]


async def _get_workspace_user(db: AsyncSession, tenant_id: str, user_id: str) -> m.User:
    user = (
        await db.execute(
            select(m.User).where(m.User.id == user_id, m.User.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found on this workspace")
    return user


async def grant_dashboard_access(
    db: AsyncSession,
    *,
    tenant_id: str,
    actor_id: str,
    actor_role: str,
    user_id: str,
    role: str = "platform_support",
) -> m.User:
    """Promote an existing app user so they can open the software-owner dashboard."""
    role_key = (role or "platform_support").strip().lower()
    if not is_platform_role(role_key):
        raise HTTPException(
            status_code=422,
            detail=f"role must be one of: {', '.join(sorted(PLATFORM_ROLES))}",
        )
    if role_key == "super_admin" and actor_role != "super_admin":
        raise HTTPException(status_code=403, detail="Only super_admin can assign super_admin")
    if not can_assign_platform_role(actor_role, role_key):
        raise HTTPException(
            status_code=403,
            detail=f"You cannot assign platform role '{role_key}'",
        )
    user = await _get_workspace_user(db, tenant_id, user_id)
    if user.id == actor_id and user.role != role_key:
        raise HTTPException(status_code=400, detail="Cannot change your own role via grant")
    if not user.is_active:
        raise HTTPException(status_code=409, detail="Activate the user before granting access")
    user.role = role_key
    user.permissions = permissions_for_role(role_key)
    await db.flush()
    return user


async def revoke_dashboard_access(
    db: AsyncSession,
    *,
    tenant_id: str,
    actor_id: str,
    actor_role: str,
    user_id: str,
    fallback_role: str = DEFAULT_APP_ROLE,
) -> m.User:
    """Remove software-owner dashboard access; user remains an app user on the workspace."""
    user = await _get_workspace_user(db, tenant_id, user_id)
    if not is_platform_role(user.role):
        raise HTTPException(status_code=400, detail="User does not have platform dashboard access")
    if user.id == actor_id:
        raise HTTPException(status_code=400, detail="Cannot revoke your own dashboard access")
    if not can_assign_platform_role(actor_role, user.role):
        raise HTTPException(
            status_code=403,
            detail="You cannot revoke access for this staff role",
        )
    fallback = (fallback_role or DEFAULT_APP_ROLE).strip().lower()
    if is_platform_role(fallback) or fallback == "super_admin":
        raise HTTPException(status_code=422, detail="fallback_role must be a non-platform app role")
    from app import custom_roles as custom_roles_svc

    role_key, role_perms = await custom_roles_svc.resolve_role_assignment(
        db, tenant_id, fallback
    )
    if is_platform_role(role_key):
        raise HTTPException(status_code=422, detail="fallback_role must be a non-platform app role")
    user.role = role_key
    user.permissions = role_perms
    await db.flush()
    return user


async def create_platform_staff(
    db: AsyncSession,
    *,
    tenant_id: str,
    actor_role: str,
    email: str,
    full_name: str,
    password: str,
    role: str,
    phone: str | None = None,
) -> m.User:
    role_key = (role or "").strip().lower()
    if not is_platform_role(role_key):
        raise HTTPException(
            status_code=422,
            detail=f"role must be one of: {', '.join(sorted(PLATFORM_ROLES))}",
        )
    if not can_assign_platform_role(actor_role, role_key):
        raise HTTPException(
            status_code=403,
            detail=f"You cannot assign platform role '{role_key}'",
        )
    validate_password_strength(password)
    existing = (
        await db.execute(
            select(m.User).where(m.User.tenant_id == tenant_id, m.User.email == email.lower())
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="User email already exists on this workspace")

    user = m.User(
        tenant_id=tenant_id,
        email=email.lower().strip(),
        full_name=full_name.strip(),
        password_hash=hash_password(password),
        role=role_key,
        phone=phone,
        email_verified=True,
        permissions=permissions_for_role(role_key),
        is_active=True,
    )
    db.add(user)
    await db.flush()
    return user


async def update_platform_staff(
    db: AsyncSession,
    *,
    tenant_id: str,
    actor_id: str,
    actor_role: str,
    user_id: str,
    full_name: str | None = None,
    role: str | None = None,
    phone: str | None = None,
    is_active: bool | None = None,
) -> m.User:
    user = (
        await db.execute(
            select(m.User).where(m.User.id == user_id, m.User.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if not user or not is_platform_role(user.role):
        raise HTTPException(status_code=404, detail="Platform staff user not found")
    if user.id == actor_id and role is not None and role != user.role:
        raise HTTPException(status_code=400, detail="Cannot change your own role")
    if user.id == actor_id and is_active is False:
        raise HTTPException(status_code=400, detail="Cannot deactivate yourself")

    if role is not None:
        role_key = role.strip().lower()
        if not is_platform_role(role_key):
            raise HTTPException(status_code=422, detail="Invalid platform role")
        if not can_assign_platform_role(actor_role, role_key):
            raise HTTPException(status_code=403, detail=f"You cannot assign role '{role_key}'")
        user.role = role_key
        user.permissions = permissions_for_role(role_key)
    if full_name is not None:
        name = full_name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="full_name cannot be empty")
        user.full_name = name
    if phone is not None:
        user.phone = phone.strip() or None
    if is_active is not None:
        user.is_active = bool(is_active)
    await db.flush()
    return user


def serialize_staff(user: m.User) -> dict:
    return serialize_user(user)
