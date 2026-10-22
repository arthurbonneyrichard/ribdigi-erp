"""Tenant-defined custom roles (BR-3.2)."""

from __future__ import annotations

import json
import re
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import func, inspect, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.honesty import require_honest_narrative
from app.rbac import (
    RECORD_SCOPE_KEY,
    ROLE_LABELS,
    VALID_ROLES,
    is_platform_role,
    is_wildcard_permission_map,
    list_customer_system_roles_for_industry,
    normalize_record_scope,
    permissions_for_role,
    record_scope_for_role,
    system_role_visible_for_industry,
)

ROLE_KEY_RE = re.compile(r"^[a-z][a-z0-9_]{1,48}$")
ROLE_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)
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
        "hotel",
        "fmcg",
        "hospital",
        "restaurant",
        "reports",
        "notifications",
        "users",
        "audit",
        "ai",
        "security",
        "backup",
        "company",
        "printers",
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


def assignable_clone_permissions(raw: dict | None, industry: str | None) -> dict[str, list[str]]:
    """Copy only tenant-assignable actions; drop wildcards and other-industry modules."""
    from app.packages import industry_allows_module

    out: dict[str, list[str]] = {}
    if not isinstance(raw, dict) or is_wildcard_permission_map(raw):
        return out
    for module, actions in raw.items():
        mod = str(module or "").strip()
        if mod in {RECORD_SCOPE_KEY, "*"} or mod not in ASSIGNABLE_MODULES:
            continue
        if not industry_allows_module(industry, mod):
            continue
        if not isinstance(actions, list):
            continue
        cleaned: list[str] = []
        for a in actions:
            act = str(a or "").strip()
            if act in {"read", "write", "approve"} and act not in cleaned:
                cleaned.append(act)
        if cleaned:
            out[mod] = cleaned
    return out


def normalize_permissions(raw: dict | None, *, industry: str | None = None) -> dict:
    # Schema CustomRoleCreate/Update.permissions rejects blank/unknown/bad actions
    # → 422; keep allow-list defense-in-depth (same codes as schema).
    from app.packages import industry_allows_module

    if not isinstance(raw, dict) or not raw:
        raise HTTPException(status_code=422, detail="permissions must be a non-empty object")
    if raw.get("*") == ["*"] or "*" in (raw.get("*") or []):
        raise HTTPException(status_code=422, detail="Custom roles cannot grant wildcard *:*")
    out: dict[str, list[str]] = {}
    for module, actions in raw.items():
        mod = str(module or "").strip()
        if mod == RECORD_SCOPE_KEY:
            continue
        if mod not in ASSIGNABLE_MODULES:
            raise HTTPException(status_code=422, detail=f"Unknown or disallowed module '{mod}'")
        if not industry_allows_module(industry, mod):
            raise HTTPException(
                status_code=422,
                detail=f"Module '{mod}' is not available for this industry",
            )
        if not isinstance(actions, list) or not actions:
            raise HTTPException(status_code=422, detail=f"Module '{mod}' actions must be a non-empty list")
        cleaned: list[str] = []
        for a in actions:
            act = str(a or "").strip()
            if act not in ALLOWED_ACTIONS:
                raise HTTPException(status_code=422, detail=f"Invalid action '{act}' for module '{mod}'")
            if act not in cleaned:
                cleaned.append(act)
        out[mod] = cleaned
    if not out:
        raise HTTPException(status_code=422, detail="permissions must include at least one module")
    return out


async def tenant_industry(db: AsyncSession, tenant_id: str) -> str | None:
    tenant = await db.get(m.Tenant, tenant_id)
    return getattr(tenant, "industry", None) if tenant else None


def serialize_system_role_for_tenant(role: str, industry: str | None) -> dict:
    raw = permissions_for_role(role)
    perms = assignable_clone_permissions(raw, industry)
    wildcard = is_wildcard_permission_map(raw)
    return {
        "role": role,
        "label": ROLE_LABELS.get(role, role),
        "permissions": perms,
        "record_scope": record_scope_for_role(role),
        "system": True,
        "cloneable": bool(perms) and not wildcard,
        "clone_group": "system_template",
    }


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
        "cloneable": bool(row.is_active),
        "clone_group": "tenant_role",
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


async def get_custom_role_ref(
    db: AsyncSession, tenant_id: str, ref: str, *, active_only: bool = True
) -> m.CustomRole | None:
    """Tenant-scoped lookup by custom role key or UUID. Other tenants never match."""
    cleaned = (ref or "").strip().lower()
    if ROLE_UUID_RE.fullmatch(cleaned):
        stmt = select(m.CustomRole).where(
            m.CustomRole.tenant_id == tenant_id,
            m.CustomRole.id == cleaned,
        )
        if active_only:
            stmt = stmt.where(m.CustomRole.is_active == True)  # noqa: E712
        return (await db.execute(stmt)).scalar_one_or_none()
    return await get_custom_role(db, tenant_id, cleaned, active_only=active_only)


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
    industry = await tenant_industry(db, tenant_id)
    rows = [
        serialize_system_role_for_tenant(role, industry)
        for role in list_customer_system_roles_for_industry(industry)
    ]
    for custom in await list_custom_roles(db, tenant_id, include_inactive=include_inactive):
        rows.append(serialize_custom_role(custom))
    return rows


async def resolve_role_assignment(
    db: AsyncSession, tenant_id: str, role: str
) -> tuple[str, dict]:
    """Return (role_key, permissions payload including record_scope) for user assignment."""
    # Schema RoleKeyValue rejects blank/malformed → 422; keep shape + unknown defense-in-depth.
    role_key = (role or "").strip().lower()
    if not role_key:
        raise HTTPException(status_code=400, detail="Role is required")
    if not ROLE_KEY_RE.match(role_key):
        raise HTTPException(
            status_code=400,
            detail="Role key must be lowercase letters/numbers/underscore, start with a letter (2–49 chars)",
        )
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
    label_s = require_honest_narrative(label, label="custom role label", max_length=120)

    base = (base_role or "").strip() or None
    industry = await tenant_industry(db, tenant_id)
    cloned_scope = None
    if base:
        if is_platform_role(base):
            raise HTTPException(status_code=422, detail="Cannot clone platform roles")
        if base in VALID_ROLES:
            if not system_role_visible_for_industry(base, industry):
                raise HTTPException(status_code=404, detail="Role not found")
            cloned = assignable_clone_permissions(permissions_for_role(base), industry)
            cloned_scope = record_scope_for_role(base)
        else:
            source = await get_custom_role(db, tenant_id, base, active_only=True)
            if not source:
                raise HTTPException(status_code=404, detail="Role not found")
            cloned = assignable_clone_permissions(dict(source.permissions or {}), industry)
            cloned_scope = source.record_scope or "own"
        if permissions is None and not cloned:
            raise HTTPException(
                status_code=400,
                detail="Clone source has no assignable permissions for this industry",
            )
    else:
        cloned = None

    if permissions is None:
        if not cloned:
            raise HTTPException(status_code=400, detail="permissions or a compatible clone source is required")
        perms = cloned
    else:
        perms = normalize_permissions(permissions, industry=industry)

    scope = normalize_record_scope(
        record_scope if record_scope is not None else (cloned_scope or "own")
    )

    exists = await get_custom_role(db, tenant_id, role_key, active_only=False)
    if exists:
        raise HTTPException(status_code=409, detail="Custom role key already exists")

    now = datetime.utcnow()
    row = m.CustomRole(
        id=m.uid(),
        tenant_id=tenant_id,
        key=role_key,
        label=label_s[:120],
        base_role=base,
        permissions=perms,
        record_scope=scope,
        is_active=True,
        created_by=user_id,
        created_at=now,
        updated_at=now,
    )

    def _has_slug(sync_session) -> bool:
        cols = inspect(sync_session.connection()).get_columns("custom_roles")
        return any(c["name"] == "slug" for c in cols)

    # Some databases still require custom_roles.slug (unique with tenant).
    # The app identity is `key`; copy it into slug when that column exists.
    if await db.run_sync(_has_slug):
        await db.execute(
            text(
                "INSERT INTO custom_roles "
                "(id, tenant_id, slug, key, label, base_role, permissions, "
                "record_scope, is_active, created_by, created_at, updated_at) "
                "VALUES (:id, :tenant_id, :slug, :key, :label, :base_role, "
                "CAST(:permissions AS json), :record_scope, :is_active, "
                ":created_by, :created_at, :updated_at)"
            ),
            {
                "id": row.id,
                "tenant_id": tenant_id,
                "slug": role_key,
                "key": role_key,
                "label": row.label,
                "base_role": base,
                "permissions": json.dumps(perms),
                "record_scope": scope,
                "is_active": True,
                "created_by": user_id,
                "created_at": now,
                "updated_at": now,
            },
        )
        await db.flush()
        saved = await get_custom_role(db, tenant_id, role_key, active_only=False)
        if not saved:
            raise HTTPException(status_code=400, detail="Custom role was not saved")
        return saved

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
        row.label = require_honest_narrative(
            label, label="custom role label", max_length=120
        )
    if permissions is not None:
        industry = await tenant_industry(db, tenant_id)
        row.permissions = normalize_permissions(permissions, industry=industry)
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
