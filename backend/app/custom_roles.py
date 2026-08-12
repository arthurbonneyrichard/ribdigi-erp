"""Tenant-defined custom roles (BR-3.2)."""

from __future__ import annotations

import re
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.rbac import (
    RECORD_SCOPE_KEY,
    VALID_ROLES,
    list_role_catalog,
    normalize_record_scope,
    permissions_for_role,
    record_scope_for_role,
)

ROLE_KEY_RE = re.compile(r"^[a-z][a-z0-9_]{1,48}$")
ALLOWED_ACTIONS = frozenset({"read", "write", "approve", "*"})
# Modules that may appear in a custom role map (exclude platform owner modules).
ASSIGNABLE_MODULES = frozenset(
    {
        "dashboard",
        "inventory",
        "sales",
        "pos",
        "purchasing",
        "suppliers",
        "customers",
        "expenses",
        "accounting",
        "credit",
        "tax",
        "stores",
        "reports",
        "notifications",
        "users",
        "audit",
        "ai",
        "security",
        "backup",
        "company",
    }
)


def validate_role_key(key: str) -> str:
    cleaned = (key or "").strip().lower()
    if not ROLE_KEY_RE.match(cleaned):
        raise HTTPException(
            status_code=400,
            detail="Role key must be lowercase letters/numbers/underscore, start with a letter (2–49 chars)",
        )
    if cleaned in VALID_ROLES:
        raise HTTPException(status_code=400, detail="Role key collides with a system role")
    if cleaned.startswith("super_"):
        raise HTTPException(status_code=400, detail="Role key reserved")
    return cleaned


def normalize_permissions(raw: dict | None) -> dict:
    if not isinstance(raw, dict) or not raw:
        raise HTTPException(status_code=400, detail="permissions must be a non-empty object")
    if raw.get("*") == ["*"] or "*" in (raw.get("*") or []):
        raise HTTPException(status_code=400, detail="Custom roles cannot grant wildcard *:*")
    out: dict[str, list[str]] = {}
    for module, actions in raw.items():
        mod = str(module or "").strip()
        if mod == RECORD_SCOPE_KEY:
            continue
        if mod not in ASSIGNABLE_MODULES:
            raise HTTPException(status_code=400, detail=f"Unknown or disallowed module '{mod}'")
        if not isinstance(actions, list) or not actions:
            raise HTTPException(status_code=400, detail=f"Module '{mod}' actions must be a non-empty list")
        cleaned: list[str] = []
        for a in actions:
            act = str(a or "").strip()
            if act not in ALLOWED_ACTIONS:
                raise HTTPException(status_code=400, detail=f"Invalid action '{act}' for module '{mod}'")
            if act not in cleaned:
                cleaned.append(act)
        out[mod] = cleaned
    if not out:
        raise HTTPException(status_code=400, detail="permissions must include at least one module")
    return out


def permissions_payload(permissions: dict, record_scope: str) -> dict:
    payload = {k: list(v) for k, v in permissions.items() if k != RECORD_SCOPE_KEY}
    payload[RECORD_SCOPE_KEY] = [record_scope]
    return payload


def serialize_custom_role(row: m.CustomRole) -> dict:
    perms = dict(row.permissions or {})
    perms.pop(RECORD_SCOPE_KEY, None)
    return {
        "role": row.key,
        "label": row.label,
        "permissions": perms,
        "record_scope": row.record_scope or "own",
        "base_role": row.base_role,
        "system": False,
        "is_active": bool(row.is_active),
        "id": row.id,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


async def get_custom_role(
    db: AsyncSession, tenant_id: str, key: str, *, active_only: bool = True
) -> m.CustomRole | None:
    stmt = select(m.CustomRole).where(
        m.CustomRole.tenant_id == tenant_id,
        m.CustomRole.key == key,
    )
    if active_only:
        stmt = stmt.where(m.CustomRole.is_active == True)  # noqa: E712
    return (await db.execute(stmt)).scalar_one_or_none()


async def list_custom_roles(
    db: AsyncSession, tenant_id: str, *, include_inactive: bool = False
) -> list[m.CustomRole]:
    stmt = select(m.CustomRole).where(m.CustomRole.tenant_id == tenant_id)
    if not include_inactive:
        stmt = stmt.where(m.CustomRole.is_active == True)  # noqa: E712
    stmt = stmt.order_by(m.CustomRole.label.asc())
    return list((await db.execute(stmt)).scalars().all())


async def catalog_for_tenant(
    db: AsyncSession, tenant_id: str, *, include_inactive: bool = False
) -> list[dict]:
    rows = list_role_catalog()
    for custom in await list_custom_roles(db, tenant_id, include_inactive=include_inactive):
        rows.append(serialize_custom_role(custom))
    return rows


async def resolve_role_assignment(
    db: AsyncSession, tenant_id: str, role: str
) -> tuple[str, dict]:
    """Return (role_key, permissions payload including record_scope) for user assignment."""
    role_key = (role or "").strip()
    if not role_key:
        raise HTTPException(status_code=400, detail="Role is required")
    if role_key in VALID_ROLES:
        perms = permissions_for_role(role_key)
        scope = record_scope_for_role(role_key)
        return role_key, permissions_payload(perms, scope)

    custom = await get_custom_role(db, tenant_id, role_key, active_only=True)
    if not custom:
        raise HTTPException(status_code=400, detail=f"Unknown role '{role_key}'")
    perms = dict(custom.permissions or {})
    perms.pop(RECORD_SCOPE_KEY, None)
    scope = normalize_record_scope(custom.record_scope or "own")
    return custom.key, permissions_payload(perms, scope)


async def create_custom_role(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    key: str,
    label: str,
    permissions: dict | None = None,
    base_role: str | None = None,
    record_scope: str | None = None,
) -> m.CustomRole:
    role_key = validate_role_key(key)
    label_s = (label or "").strip()
    if not label_s:
        raise HTTPException(status_code=400, detail="label is required")

    base = (base_role or "").strip() or None
    if base and base not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"Unknown base_role '{base}'")
    if base == "super_admin":
        raise HTTPException(status_code=400, detail="Cannot clone super_admin")

    if permissions is None:
        if not base:
            raise HTTPException(status_code=400, detail="permissions or base_role is required")
        perms = permissions_for_role(base)
        perms.pop(RECORD_SCOPE_KEY, None)
    else:
        perms = normalize_permissions(permissions)

    scope = normalize_record_scope(
        record_scope if record_scope is not None else (record_scope_for_role(base) if base else "own")
    )

    exists = await get_custom_role(db, tenant_id, role_key, active_only=False)
    if exists:
        raise HTTPException(status_code=409, detail="Custom role key already exists")

    row = m.CustomRole(
        tenant_id=tenant_id,
        key=role_key,
        label=label_s[:120],
        base_role=base,
        permissions=perms,
        record_scope=scope,
        is_active=True,
        created_by=user_id,
    )
    db.add(row)
    await db.flush()
    return row


async def update_custom_role(
    db: AsyncSession,
    *,
    tenant_id: str,
    key: str,
    label: str | None = None,
    permissions: dict | None = None,
    record_scope: str | None = None,
    is_active: bool | None = None,
    sync_users: bool = True,
) -> m.CustomRole:
    row = await get_custom_role(db, tenant_id, key, active_only=False)
    if not row:
        raise HTTPException(status_code=404, detail="Custom role not found")

    if label is not None:
        label_s = label.strip()
        if not label_s:
            raise HTTPException(status_code=400, detail="label is required")
        row.label = label_s[:120]
    if permissions is not None:
        row.permissions = normalize_permissions(permissions)
    if record_scope is not None:
        row.record_scope = normalize_record_scope(record_scope)
    if is_active is not None:
        row.is_active = bool(is_active)
    row.updated_at = datetime.utcnow()
    await db.flush()

    if sync_users and row.is_active:
        payload = permissions_payload(dict(row.permissions or {}), row.record_scope or "own")
        users = (
            await db.execute(
                select(m.User).where(m.User.tenant_id == tenant_id, m.User.role == row.key)
            )
        ).scalars().all()
        for user in users:
            user.permissions = payload
    await db.flush()
    return row


async def delete_custom_role(db: AsyncSession, *, tenant_id: str, key: str) -> None:
    row = await get_custom_role(db, tenant_id, key, active_only=False)
    if not row:
        raise HTTPException(status_code=404, detail="Custom role not found")
    count = (
        await db.execute(
            select(func.count()).select_from(m.User).where(
                m.User.tenant_id == tenant_id,
                m.User.role == row.key,
            )
        )
    ).scalar_one()
    if int(count or 0) > 0:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete role '{row.key}' while {count} user(s) are assigned",
        )
    await db.delete(row)
    await db.flush()
