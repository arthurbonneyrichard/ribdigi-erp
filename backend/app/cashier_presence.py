"""Cashier POS selling presence for company admins.

Online selling follows the cashier's browser (`navigator.onLine`) via the POS
heartbeat. If that last report cannot be sent, a quiet heartbeat older than
PRESENCE_STALE_SECONDS is treated as offline. Duration starts at `offline_since`
when the cashier reported offline, otherwise at the last heartbeat.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m

CASHIER_PRESENCE_ROLES = frozenset({"cashier", "hotel_cashier"})
# POS heartbeats about once a minute. Two missed beats means the browser
# stopped reaching the server (typical when selling goes offline).
PRESENCE_STALE_SECONDS = 150


def note_selling_state(row: m.PosDevice, *, selling_online: bool, now: datetime) -> None:
    """Record the cashier's selling pill on this terminal."""
    online = bool(selling_online)
    row.selling_online = online
    row.last_seen_at = now
    row.updated_at = now
    if online:
        row.offline_since = None
    elif row.offline_since is None:
        row.offline_since = now


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat() + "Z"


def _fresh_online(row: m.PosDevice, now: datetime) -> bool:
    if not row.last_seen_at:
        return False
    if row.selling_online is False:
        return False
    age = (now - row.last_seen_at).total_seconds()
    return age <= PRESENCE_STALE_SECONDS


def summarize_devices(devices: list[m.PosDevice], now: datetime) -> dict:
    """One cashier row from their terminals. Online if any terminal is fresh."""
    if not devices:
        return {
            "status": "no_signal",
            "offline_since": None,
            "offline_duration_seconds": None,
            "last_seen_at": None,
        }
    latest = max(devices, key=lambda row: row.last_seen_at or datetime.min)
    if any(_fresh_online(row, now) for row in devices):
        return {
            "status": "online",
            "offline_since": None,
            "offline_duration_seconds": None,
            "last_seen_at": _iso(latest.last_seen_at),
        }
    if latest.selling_online is False:
        since = latest.offline_since or latest.last_seen_at
    else:
        since = latest.last_seen_at
    seconds = 0
    if since is not None:
        seconds = max(0, int((now - since).total_seconds()))
    return {
        "status": "offline",
        "offline_since": _iso(since),
        "offline_duration_seconds": seconds,
        "last_seen_at": _iso(latest.last_seen_at),
    }


async def list_cashier_presence(db: AsyncSession, tenant_id: str, *, now: datetime | None = None) -> list[dict]:
    """Active cashiers in this tenant only, with selling status and offline duration."""
    moment = now or datetime.utcnow()
    users = (
        await db.execute(
            select(m.User)
            .where(
                m.User.tenant_id == tenant_id,
                m.User.role.in_(tuple(CASHIER_PRESENCE_ROLES)),
                m.User.is_active.is_(True),
            )
            .order_by(m.User.full_name.asc())
        )
    ).scalars().all()
    if not users:
        return []
    user_ids = [user.id for user in users]
    devices = (
        await db.execute(
            select(m.PosDevice).where(
                m.PosDevice.tenant_id == tenant_id,
                m.PosDevice.user_id.in_(user_ids),
            )
        )
    ).scalars().all()
    by_user: dict[str, list[m.PosDevice]] = {user_id: [] for user_id in user_ids}
    for device in devices:
        if device.user_id in by_user:
            by_user[device.user_id].append(device)
    rows: list[dict] = []
    for user in users:
        summary = summarize_devices(by_user.get(user.id) or [], moment)
        rows.append(
            {
                "user_id": user.id,
                "full_name": user.full_name,
                "role": user.role,
                **summary,
            }
        )
    return rows
