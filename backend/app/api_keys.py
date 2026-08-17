"""Tenant API key lifecycle for integration auth (BR-18.1)."""

from __future__ import annotations

import secrets
from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.rbac import ALLOWED_ACTIONS, SYSTEM_MODULES
from app.security import hash_token

KEY_PREFIX_TOKEN = "rdk_"
DEFAULT_PERMISSIONS: dict[str, list[str]] = {
    "inventory": ["read"],
    "sales": ["read"],
    "purchasing": ["read"],
    "customers": ["read"],
    "reports": ["read"],
}


def normalize_permissions(raw: dict | None) -> dict[str, list[str]]:
    # Schema ApiKeyCreate rejects unknown modules/actions → 422; keep allow-list
    # defense-in-depth (no silent drop of bad keys).
    source = raw if isinstance(raw, dict) and raw else DEFAULT_PERMISSIONS
    out: dict[str, list[str]] = {}
    for module, actions in source.items():
        mod = str(module).strip().lower()
        if mod not in SYSTEM_MODULES:
            raise HTTPException(status_code=422, detail=f"Invalid permission module: {module}")
        if not isinstance(actions, (list, tuple)) or not actions:
            raise HTTPException(status_code=422, detail=f"Invalid actions for module: {module}")
        cleaned: list[str] = []
        for action in actions:
            act = str(action).strip().lower()
            if act not in ALLOWED_ACTIONS:
                raise HTTPException(status_code=422, detail=f"Invalid action: {action}")
            if act not in cleaned:
                cleaned.append(act)
        out[mod] = cleaned
    if not out:
        raise HTTPException(status_code=422, detail="permissions must include at least one module")
    return out


def _is_expired(row: m.ApiKey, *, now: datetime | None = None) -> bool:
    if not row.expires_at:
        return False
    return row.expires_at <= (now or datetime.utcnow())


def serialize_key(row: m.ApiKey, *, include_secret: str | None = None) -> dict[str, Any]:
    data = {
        "id": row.id,
        "name": row.name,
        "key_prefix": row.key_prefix,
        "permissions": row.permissions or {},
        "created_by": row.created_by,
        "created_at": row.created_at,
        "last_used_at": row.last_used_at,
        "request_count": int(row.request_count or 0),
        "expires_at": row.expires_at,
        "revoked_at": row.revoked_at,
        "status": "revoked" if row.revoked_at else ("expired" if _is_expired(row) else "active"),
    }
    if include_secret:
        data["api_key"] = include_secret
        data["secret_shown_once"] = True
    return data


def generate_raw_key() -> tuple[str, str, str]:
    """Return (raw_key, prefix_for_display, hash)."""
    secret = secrets.token_urlsafe(32)
    raw = f"{KEY_PREFIX_TOKEN}{secret}"
    prefix = raw[:12]
    return raw, prefix, hash_token(raw)


async def list_keys(
    db: AsyncSession,
    tenant_id: str,
    *,
    status: str | None = None,
    active_only: bool = False,
) -> list[m.ApiKey]:
    rows = list(
        (
            await db.execute(
                select(m.ApiKey)
                .where(m.ApiKey.tenant_id == tenant_id)
                .order_by(m.ApiKey.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    if status is not None:
        # Schema ApiKeyStatusFilterValue rejects blank/invalid → 422; keep allow-list
        # defense-in-depth (no silent empty filter / blank→all).
        wanted = (status or "").strip().lower()
        if not wanted:
            pass
        elif wanted not in {"active", "revoked", "expired"}:
            raise HTTPException(
                status_code=422,
                detail="status must be active, revoked, or expired",
            )
        else:
            rows = [r for r in rows if serialize_key(r)["status"] == wanted]
    elif active_only:
        rows = [r for r in rows if serialize_key(r)["status"] == "active"]
    return rows


async def create_key(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str | None,
    name: str,
    permissions: dict | None = None,
    expires_at: datetime | None = None,
) -> tuple[m.ApiKey, str]:
    cleaned_name = (name or "").strip()
    # Schema ApiKeyCreate enforces name length → 422; keep defense-in-depth.
    if len(cleaned_name) < 2:
        raise HTTPException(status_code=422, detail="name must be at least 2 characters")
    if len(cleaned_name) > 120:
        raise HTTPException(status_code=422, detail="name must be at most 120 characters")
    perms = normalize_permissions(permissions)
    raw, prefix, key_hash = generate_raw_key()
    row = m.ApiKey(
        tenant_id=tenant_id,
        name=cleaned_name,
        key_prefix=prefix,
        key_hash=key_hash,
        permissions=perms,
        created_by=user_id,
        expires_at=expires_at,
        request_count=0,
    )
    db.add(row)
    await db.flush()
    return row, raw


async def get_key(db: AsyncSession, tenant_id: str, key_id: str) -> m.ApiKey:
    row = (
        await db.execute(
            select(m.ApiKey).where(m.ApiKey.id == key_id, m.ApiKey.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="API key not found")
    return row


async def revoke_key(db: AsyncSession, tenant_id: str, key_id: str) -> m.ApiKey:
    row = await get_key(db, tenant_id, key_id)
    if row.revoked_at is None:
        row.revoked_at = datetime.utcnow()
        await db.flush()
    return row


async def touch_usage(db: AsyncSession, row: m.ApiKey) -> None:
    """Persist last_used_at + request_count (read-only requests still need a commit)."""
    now = datetime.utcnow()
    row.last_used_at = now
    row.request_count = int(row.request_count or 0) + 1
    await db.commit()


async def usage_stats(db: AsyncSession, tenant_id: str, key_id: str) -> dict[str, Any]:
    """Lightweight usage summary (request_count + last_used_at) for admin UI."""
    row = await get_key(db, tenant_id, key_id)
    return {
        "id": row.id,
        "name": row.name,
        "key_prefix": row.key_prefix,
        "request_count": int(row.request_count or 0),
        "last_used_at": row.last_used_at.isoformat() if row.last_used_at else None,
        "revoked_at": row.revoked_at.isoformat() if row.revoked_at else None,
        "expires_at": row.expires_at.isoformat() if row.expires_at else None,
    }


async def authenticate_api_key(db: AsyncSession, raw_key: str) -> m.ApiKey:
    raw = (raw_key or "").strip()
    if not raw.startswith(KEY_PREFIX_TOKEN) or len(raw) < 20:
        raise HTTPException(status_code=401, detail="Invalid API key")
    digest = hash_token(raw)
    row = (
        await db.execute(select(m.ApiKey).where(m.ApiKey.key_hash == digest))
    ).scalar_one_or_none()
    if not row or row.revoked_at is not None:
        raise HTTPException(status_code=401, detail="Invalid API key")
    if _is_expired(row):
        raise HTTPException(status_code=401, detail="API key expired")
    await touch_usage(db, row)
    return row
