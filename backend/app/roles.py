"""Tenant custom role CRUD and resolution."""

from __future__ import annotations

import re
from copy import deepcopy
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.rbac import (
    RECORD_SCOPE_KEY,
    ROLE_LABELS,
    SYSTEM_MODULES,
    VALID_ROLES,
    assert_permissions_within_grantor,
    dangerous_permission_warnings,
    ensure_permission_dependencies,
    FALLBACK_ADMIN_ROLES,
    list_system_role_catalog,
    normalize_permissions_map,
    normalize_record_scope,
    permissions_for_role,
    PROTECTED_OWNER_ROLES,
    record_scope_for_role,
    validate_permission_dependencies,
)
from app.platform_const import PLATFORM_ROLES, is_platform_tenant_id

SLUG_RE = re.compile(r"^[a-z][a-z0-9_]{1,48}$")
RESERVED_SLUGS = frozenset(VALID_ROLES) | frozenset({"admin", "root", "system", "owner"})


def validate_role_slug(slug: str) -> str:
    value = (slug or "").strip().lower()
    if not SLUG_RE.fullmatch(value):
        raise HTTPException(
            status_code=400,
            detail="Role slug must be 2–49 chars: start with a letter, then lowercase letters, digits, or underscore",
        )
    if value in RESERVED_SLUGS:
        raise HTTPException(status_code=400, detail=f"Role slug '{value}' is reserved for a system role")
    return value


def serialize_custom_role(row: m.CustomRole) -> dict:
    perms = dict(row.permissions or {})
    perms.pop(RECORD_SCOPE_KEY, None)
    return {
        "role": row.slug,
        "slug": row.slug,
        "label": row.label,
        "org_chart_label": row.label,
        "description": row.description,
        "permissions": perms,
        "record_scope": row.record_scope or "own",
        "system": False,
        "is_active": bool(row.is_active),
        "id": row.id,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


async def list_custom_roles(
    db: AsyncSession,
    tenant_id: str,
    *,
    active_only: bool = False,
    is_active: bool | None = None,
) -> list[m.CustomRole]:
    """Stage 124 R1 — is_active for honest inactive-only custom role lists."""
    stmt = select(m.CustomRole).where(m.CustomRole.tenant_id == tenant_id)
    if is_active is not None:
        stmt = stmt.where(m.CustomRole.is_active.is_(bool(is_active)))
    elif active_only:
        stmt = stmt.where(m.CustomRole.is_active == True)  # noqa: E712
    stmt = stmt.order_by(m.CustomRole.label.asc())
    return list((await db.execute(stmt)).scalars().all())


async def get_custom_role(db: AsyncSession, tenant_id: str, slug: str) -> m.CustomRole:
    row = (
        await db.execute(
            select(m.CustomRole).where(
                m.CustomRole.tenant_id == tenant_id,
                m.CustomRole.slug == slug.strip().lower(),
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Role not found")
    return row


async def list_role_catalog(
    db: AsyncSession,
    tenant_id: str,
    *,
    active_only: bool = True,
    is_active: bool | None = None,
) -> list[dict]:
    """Stage 124 R1 — catalog with optional inactive custom roles."""
    if is_active is False:
        # Inactive-only honesty: custom roles only (system roles have no inactive state).
        rows = [
            serialize_custom_role(c)
            for c in await list_custom_roles(db, tenant_id, is_active=False)
        ]
        rows.sort(key=lambda r: (r.get("label") or r.get("role") or ""))
        return rows

    rows = list_system_role_catalog()
    if not is_platform_tenant_id(tenant_id):
        rows = [r for r in rows if r.get("role") not in PLATFORM_ROLES]
    customs = await list_custom_roles(
        db,
        tenant_id,
        active_only=active_only if is_active is None else False,
        is_active=is_active,
    )
    for custom in customs:
        rows.append(serialize_custom_role(custom))
    rows.sort(key=lambda r: (0 if r.get("system") else 1, r.get("label") or r.get("role") or ""))
    return rows


async def resolve_role_permissions(db: AsyncSession, tenant_id: str, role: str) -> dict:
    """Return module permission map for a system or custom role (no record_scope key)."""
    role = (role or "").strip()
    if role in VALID_ROLES:
        return permissions_for_role(role)
    custom = (
        await db.execute(
            select(m.CustomRole).where(
                m.CustomRole.tenant_id == tenant_id,
                m.CustomRole.slug == role,
                m.CustomRole.is_active == True,  # noqa: E712
            )
        )
    ).scalar_one_or_none()
    if not custom:
        raise HTTPException(status_code=400, detail=f"Unknown role '{role}'")
    perms = normalize_permissions_map(custom.permissions or {})
    perms.pop(RECORD_SCOPE_KEY, None)
    return perms


async def resolve_role_record_scope(db: AsyncSession, tenant_id: str, role: str) -> str:
    if role in VALID_ROLES:
        return record_scope_for_role(role)
    custom = await get_custom_role(db, tenant_id, role)
    return normalize_record_scope(custom.record_scope, default="own")


async def assert_assignable_role(
    db: AsyncSession,
    tenant_id: str,
    role: str,
    *,
    actor_role: str | None = None,
) -> str:
    role = (role or "").strip()
    if not role:
        raise HTTPException(status_code=400, detail="role is required")
    if role in PLATFORM_ROLES and not is_platform_tenant_id(tenant_id):
        raise HTTPException(
            status_code=400,
            detail="Platform roles can only be assigned on the Ribdigi House platform tenant",
        )
    if role == "super_admin" and actor_role != "super_admin":
        raise HTTPException(status_code=403, detail="Only super_admin can assign super_admin")
    if role in VALID_ROLES:
        return role
    custom = (
        await db.execute(
            select(m.CustomRole).where(
                m.CustomRole.tenant_id == tenant_id,
                m.CustomRole.slug == role,
                m.CustomRole.is_active == True,  # noqa: E712
            )
        )
    ).scalar_one_or_none()
    if not custom:
        raise HTTPException(status_code=400, detail=f"Unknown role '{role}'")
    return custom.slug


async def permissions_for_assignment(db: AsyncSession, tenant_id: str, role: str) -> dict:
    """Full permissions dict to store on user (includes default record_scope)."""
    if role in VALID_ROLES:
        perms = permissions_for_role(role)
        perms[RECORD_SCOPE_KEY] = record_scope_for_role(role)
        return perms
    custom = await get_custom_role(db, tenant_id, role)
    if not custom.is_active:
        raise HTTPException(status_code=400, detail=f"Role '{role}' is inactive")
    perms = normalize_permissions_map(custom.permissions or {})
    perms[RECORD_SCOPE_KEY] = normalize_record_scope(custom.record_scope, default="own")
    return perms


async def known_role_slugs(db: AsyncSession, tenant_id: str) -> set[str]:
    customs = await list_custom_roles(db, tenant_id, active_only=True)
    base = set(VALID_ROLES)
    if not is_platform_tenant_id(tenant_id):
        base -= set(PLATFORM_ROLES)
    return base | {c.slug for c in customs}


def _copy_base_permissions(base_role: str | None) -> dict:
    if not base_role:
        return permissions_for_role("cashier")
    base = base_role.strip()
    if base not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"base_role must be a system role; got '{base}'")
    if base in {"super_admin", "company_admin"} | set(PLATFORM_ROLES):
        raise HTTPException(
            status_code=400,
            detail="Cannot copy wildcard admin roles into a custom role; pick a narrower base",
        )
    return permissions_for_role(base)


async def assert_owner_lockout_safe(
    db: AsyncSession,
    *,
    tenant_id: str,
    target: m.User,
    deactivating: bool = False,
    new_role: str | None = None,
) -> None:
    """Prevent deactivating/demoting the last protected owner/admin for a tenant.

    - Last active ``super_admin`` or ``tenant_owner`` cannot be deactivated or demoted.
    - If no protected owners remain active, last active ``company_admin`` is protected.
    """
    if not deactivating and new_role is None:
        return
    old_role = (target.role or "").strip()
    demoting = new_role is not None and new_role.strip() != old_role
    if not deactivating and not demoting:
        return
    if not target.is_active and deactivating:
        return

    async def _active_count(roles: set[str], *, exclude_id: str | None = None) -> int:
        stmt = select(func.count()).select_from(m.User).where(
            m.User.tenant_id == tenant_id,
            m.User.is_active == True,  # noqa: E712
            m.User.role.in_(list(roles)),
        )
        if exclude_id:
            stmt = stmt.where(m.User.id != exclude_id)
        return int((await db.execute(stmt)).scalar_one() or 0)

    if old_role in PROTECTED_OWNER_ROLES:
        others = await _active_count({old_role}, exclude_id=target.id)
        if others == 0:
            action = "deactivate" if deactivating else "demote"
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Cannot {action} the last active '{old_role}' for this tenant "
                    "(owner lockout protection)"
                ),
            )
        return

    if old_role in FALLBACK_ADMIN_ROLES:
        owners = await _active_count(set(PROTECTED_OWNER_ROLES))
        if owners == 0:
            others = await _active_count(set(FALLBACK_ADMIN_ROLES), exclude_id=target.id)
            if others == 0:
                action = "deactivate" if deactivating else "demote"
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Cannot {action} the last active '{old_role}' for this tenant "
                        "(owner lockout protection)"
                    ),
                )


def role_payload_with_hardening(row: m.CustomRole) -> dict:
    """Serialize custom role and attach dependency / dangerous-permission warnings."""
    data = serialize_custom_role(row)
    perms = data.get("permissions") or {}
    data["permission_dependency_notes"] = validate_permission_dependencies(perms)
    data["dangerous_permission_warnings"] = dangerous_permission_warnings(perms)
    return data


async def create_custom_role(
    db: AsyncSession,
    *,
    tenant_id: str,
    slug: str,
    label: str,
    description: str | None = None,
    base_role: str | None = "cashier",
    permissions: dict | None = None,
    record_scope: str = "own",
    grantor_permissions: dict | None = None,
) -> m.CustomRole:
    slug = validate_role_slug(slug)
    label_clean = (label or "").strip()
    if len(label_clean) < 2:
        raise HTTPException(status_code=400, detail="label must be at least 2 characters")
    try:
        scope = normalize_record_scope(record_scope, default="own")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    exists = (
        await db.execute(
            select(m.CustomRole).where(m.CustomRole.tenant_id == tenant_id, m.CustomRole.slug == slug)
        )
    ).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="A custom role with this slug already exists")

    allow_platform = is_platform_tenant_id(tenant_id)
    if permissions is not None:
        try:
            perms = ensure_permission_dependencies(
                permissions,
                allow_wildcard=False,
                allow_platform_modules=allow_platform,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    else:
        try:
            perms = ensure_permission_dependencies(
                _copy_base_permissions(base_role),
                allow_wildcard=False,
                allow_platform_modules=allow_platform,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    if grantor_permissions is not None:
        try:
            assert_permissions_within_grantor(perms, grantor_permissions)
        except ValueError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc

    row = m.CustomRole(
        tenant_id=tenant_id,
        slug=slug,
        label=label_clean,
        description=(description or "").strip() or None,
        permissions=perms,
        record_scope=scope,
        is_active=True,
    )
    db.add(row)
    await db.flush()
    return row


async def update_custom_role(
    db: AsyncSession,
    *,
    tenant_id: str,
    slug: str,
    label: str | None = None,
    description: str | None = None,
    permissions: dict | None = None,
    record_scope: str | None = None,
    is_active: bool | None = None,
    grantor_permissions: dict | None = None,
) -> m.CustomRole:
    row = await get_custom_role(db, tenant_id, slug)
    if label is not None:
        label_clean = label.strip()
        if len(label_clean) < 2:
            raise HTTPException(status_code=400, detail="label must be at least 2 characters")
        row.label = label_clean
    if description is not None:
        row.description = description.strip() or None
    if record_scope is not None:
        try:
            row.record_scope = normalize_record_scope(record_scope, default="own")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    if permissions is not None:
        try:
            perms = ensure_permission_dependencies(
                permissions,
                allow_wildcard=False,
                allow_platform_modules=is_platform_tenant_id(tenant_id),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if grantor_permissions is not None:
            try:
                assert_permissions_within_grantor(perms, grantor_permissions)
            except ValueError as exc:
                raise HTTPException(status_code=403, detail=str(exc)) from exc
        row.permissions = perms
    if is_active is not None:
        row.is_active = bool(is_active)
    row.updated_at = datetime.utcnow()
    await db.flush()

    # Keep assigned users' permission snapshots in sync with the role definition.
    assigned = (
        await db.execute(
            select(m.User).where(m.User.tenant_id == tenant_id, m.User.role == row.slug)
        )
    ).scalars().all()
    assigned_ids: list[str] = []
    for user in assigned:
        prev_scope = None
        if isinstance(user.permissions, dict) and RECORD_SCOPE_KEY in user.permissions:
            prev_scope = user.permissions.get(RECORD_SCOPE_KEY)
        perms = deepcopy(row.permissions or {})
        perms.pop(RECORD_SCOPE_KEY, None)
        perms[RECORD_SCOPE_KEY] = (
            prev_scope if prev_scope is not None else (row.record_scope or "own")
        )
        user.permissions = perms
        assigned_ids.append(user.id)
    await db.flush()
    if assigned_ids:
        from app.cache import app_cache

        await app_cache.invalidate_users_permissions(tenant_id, assigned_ids)
    return row


async def delete_custom_role(db: AsyncSession, *, tenant_id: str, slug: str) -> None:
    row = await get_custom_role(db, tenant_id, slug)
    count = (
        await db.execute(
            select(func.count())
            .select_from(m.User)
            .where(m.User.tenant_id == tenant_id, m.User.role == row.slug)
        )
    ).scalar_one()
    if int(count or 0) > 0:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete role '{row.slug}' while {count} user(s) are assigned; reassign them first",
        )
    await db.delete(row)
    await db.flush()


def role_detail_payload(role: str, *, custom: m.CustomRole | None = None) -> dict:
    if custom is not None:
        return serialize_custom_role(custom)
    if role not in VALID_ROLES:
        raise HTTPException(status_code=404, detail="Role not found")
    return {
        "role": role,
        "label": ROLE_LABELS.get(role, role),
        "permissions": permissions_for_role(role),
        "record_scope": record_scope_for_role(role),
        "system": True,
    }


# Re-export for callers that need module list for UI
__all__ = [
    "SYSTEM_MODULES",
    "assert_assignable_role",
    "assert_owner_lockout_safe",
    "create_custom_role",
    "delete_custom_role",
    "get_custom_role",
    "known_role_slugs",
    "list_custom_roles",
    "list_role_catalog",
    "permissions_for_assignment",
    "resolve_role_permissions",
    "resolve_role_record_scope",
    "role_detail_payload",
    "role_payload_with_hardening",
    "serialize_custom_role",
    "update_custom_role",
    "validate_role_slug",
]
