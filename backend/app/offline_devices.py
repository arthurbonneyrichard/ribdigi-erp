"""Tenant offline/PWA device registration (Stage 163 V1). Soft-revoke only."""

from __future__ import annotations

import secrets
from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m

DEVICE_CODE_PREFIX = "ofd_"
ALLOWED_PLATFORMS = {"web", "android", "ios", "desktop", "other"}


def serialize_device(row: m.OfflineDevice) -> dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "device_code": row.device_code,
        "platform": row.platform,
        "user_agent": row.user_agent,
        "registered_by": row.registered_by,
        "last_seen_at": row.last_seen_at,
        "revoked_at": row.revoked_at,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "status": "revoked" if row.revoked_at else "active",
    }


def _normalize_platform(raw: str | None) -> str | None:
    if raw is None or str(raw).strip() == "":
        return None
    platform = str(raw).strip().lower()
    if platform not in ALLOWED_PLATFORMS:
        raise HTTPException(
            status_code=400,
            detail="platform must be one of: web, android, ios, desktop, other",
        )
    return platform


def generate_device_code() -> str:
    return f"{DEVICE_CODE_PREFIX}{secrets.token_urlsafe(16)}"


async def list_devices(
    db: AsyncSession,
    tenant_id: str,
    *,
    status: str | None = None,
    active_only: bool = False,
) -> list[m.OfflineDevice]:
    rows = list(
        (
            await db.execute(
                select(m.OfflineDevice)
                .where(m.OfflineDevice.tenant_id == tenant_id)
                .order_by(m.OfflineDevice.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    if status is not None:
        wanted = str(status).strip().lower()
        if wanted not in {"active", "revoked"}:
            raise HTTPException(status_code=400, detail="status must be active or revoked")
        rows = [r for r in rows if serialize_device(r)["status"] == wanted]
    elif active_only:
        rows = [r for r in rows if r.revoked_at is None]
    return rows


async def create_device(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str | None,
    name: str,
    platform: str | None = None,
    user_agent: str | None = None,
) -> m.OfflineDevice:
    cleaned_name = (name or "").strip()
    if len(cleaned_name) < 2:
        raise HTTPException(status_code=400, detail="name must be at least 2 characters")
    if len(cleaned_name) > 120:
        raise HTTPException(status_code=400, detail="name must be at most 120 characters")
    ua = (user_agent or "").strip() or None
    if ua and len(ua) > 500:
        ua = ua[:500]
    now = datetime.utcnow()
    row = m.OfflineDevice(
        tenant_id=tenant_id,
        name=cleaned_name,
        device_code=generate_device_code(),
        platform=_normalize_platform(platform),
        user_agent=ua,
        registered_by=user_id,
        last_seen_at=now,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    await db.flush()
    return row


async def get_device(db: AsyncSession, tenant_id: str, device_id: str) -> m.OfflineDevice:
    row = (
        await db.execute(
            select(m.OfflineDevice).where(
                m.OfflineDevice.id == device_id,
                m.OfflineDevice.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Offline device not found")
    return row


async def revoke_device(db: AsyncSession, tenant_id: str, device_id: str) -> m.OfflineDevice:
    row = await get_device(db, tenant_id, device_id)
    if row.revoked_at is None:
        now = datetime.utcnow()
        row.revoked_at = now
        row.updated_at = now
        await db.flush()
    return row


def sync_status_payload() -> dict[str, Any]:
    """Stage 163 S1 — honest deferred sync status (no fake offline sales)."""
    return {
        "sync_enabled": False,
        "queue_depth": 0,
        "pending_pushes": 0,
        "pending_pulls": 0,
        "last_sync_at": None,
        "conflict_count": 0,
        "message": (
            "Offline sync engine is deferred (Stage 164+). "
            "No fake offline sales or fabricated sync success."
        ),
    }
