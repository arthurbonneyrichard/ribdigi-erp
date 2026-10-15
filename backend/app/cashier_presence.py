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
from app.honesty import money_json

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


async def list_cashier_presence(
    db: AsyncSession,
    tenant_id: str,
    *,
    now: datetime | None = None,
    store_ids: list[str] | None = None,
) -> list[dict]:
    """Active cashiers in this tenant, with selling status and offline duration.

    ``store_ids is None`` means the caller may see every store in the company
    (company admin, or a manager with no store membership yet). A list limits
    terminals and open shifts to those stores, so a store manager does not see
    another store's cashier email or shift totals.
    """
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
    allowed = set(store_ids) if store_ids is not None else None
    if allowed is not None:
        devices = [device for device in devices if device.store_id in allowed]
    by_user: dict[str, list[m.PosDevice]] = {user_id: [] for user_id in user_ids}
    for device in devices:
        if device.user_id in by_user:
            by_user[device.user_id].append(device)
    store_ids = {device.store_id for device in devices if device.store_id}
    stores: dict[str, m.Store] = {}
    if store_ids:
        store_rows = (
            await db.execute(
                select(m.Store).where(
                    m.Store.tenant_id == tenant_id,
                    m.Store.id.in_(tuple(store_ids)),
                )
            )
        ).scalars().all()
        stores = {store.id: store for store in store_rows}
    open_shifts = (
        await db.execute(
            select(m.PosSession).where(
                m.PosSession.tenant_id == tenant_id,
                m.PosSession.user_id.in_(user_ids),
                m.PosSession.status == "open",
            )
        )
    ).scalars().all()
    shift_by_user: dict[str, m.PosSession] = {}
    for shift in open_shifts:
        if allowed is not None and shift.store_id not in allowed:
            continue
        current = shift_by_user.get(shift.user_id)
        if current is None or (shift.opened_at or datetime.min) >= (current.opened_at or datetime.min):
            shift_by_user[shift.user_id] = shift
    rows: list[dict] = []
    for user in users:
        user_devices = by_user.get(user.id) or []
        shift = shift_by_user.get(user.id)
        if allowed is not None and not user_devices and shift is None:
            continue
        summary = summarize_devices(user_devices, moment)
        latest = None
        if user_devices:
            latest = max(user_devices, key=lambda row: row.last_seen_at or datetime.min)
        store = stores.get(latest.store_id) if latest and latest.store_id else None
        pending = sum(int(device.pending_queue_count or 0) for device in user_devices)
        rows.append(
            {
                "user_id": user.id,
                "full_name": user.full_name,
                "email": user.email,
                "role": user.role,
                "store_name": f"{store.code} — {store.name}" if store else None,
                "pending_queue_count": pending,
                "shift_number": shift.session_number if shift else None,
                "shift_status": "open" if shift else "none",
                "shift_sale_count": int(shift.sale_count or 0) if shift else None,
                "shift_sales": money_json(shift.total_sales) if shift else None,
                **summary,
            }
        )
    return rows
