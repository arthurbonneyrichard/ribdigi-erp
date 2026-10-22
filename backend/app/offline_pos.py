"""Offline POS: server-issued grants, per-device stock allocations, and sync preflight.

This is not a second sync stack. Queued sales flush to POST /pos/sales with
``client_request_id`` idempotency. Server catalog/stock remain authoritative.
Payment information is recorded as tender details only — funds are never held.

Authorization model
-------------------
* ``POST /pos/offline/authorize`` (online only) revalidates user, tenant,
  industry, permissions, store access, and device, then issues a device-bound
  :class:`OfflineGrant` with a configurable expiry and per-device stock slices.
* Expiry blocks *new* offline sales on the device. It never invalidates sales
  recorded inside the grant window, so an online-authenticated user can always
  sync the queue without a fresh grant.
* Conflicts (price, stock, allocation, credit, window) are recorded as
  :class:`OfflineSyncEvent` rows and resolved by an authorised user. Nothing is
  deleted and no amount is changed without an explicit, audited resolution.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.config import settings
from app.honesty import money_json

OFFLINE_AUTH_EXPIRED = "OFFLINE_AUTH_EXPIRED"
OFFLINE_GRANT_INVALID = "OFFLINE_GRANT_INVALID"
OFFLINE_SALE_OUTSIDE_GRANT = "OFFLINE_SALE_OUTSIDE_GRANT"
PRICE_CONFLICT = "PRICE_CONFLICT"
STOCK_CONFLICT = "STOCK_CONFLICT"
ALLOCATION_EXCEEDED = "ALLOCATION_EXCEEDED"
OFFLINE_TENDER_NOT_ALLOWED = "OFFLINE_TENDER_NOT_ALLOWED"
SESSION_CLOSED = "SESSION_CLOSED"
DEVICE_BLOCKED = "DEVICE_BLOCKED"
SALE_DISMISSED = "SALE_DISMISSED"
RESOLUTION_INVALID = "RESOLUTION_INVALID"

# Default 168 hours = 7 days, aligned with REFRESH_TOKEN_EXPIRE_DAYS. Not a client hardcode.
DEFAULT_OFFLINE_AUTH_HOURS = int(settings.OFFLINE_AUTH_HOURS_DEFAULT or 168)
# Device clocks drift; a sale stamped slightly outside the window is still inside it.
CLOCK_SKEW = timedelta(minutes=15)
DEFAULT_ALLOCATION_PCT = 50
MAX_ALLOCATION_PRODUCTS = 5000
OFFLINE_CATALOG_LIMIT = 5000
OFFLINE_CUSTOMER_LIMIT = 5000

# Tender details only. No provider is contacted; card/MoMo/bank need a reference
# the cashier copied from the customer's slip or SMS.
OFFLINE_TENDERS = frozenset({"cash", "mobile_money", "card", "bank_transfer", "credit"})
INACTIVE_TENANT_STATUSES = frozenset({"suspended", "cancelled", "canceled", "closed", "deleted"})

RESOLUTION_ACTIONS: dict[str, frozenset[str]] = {
    "approve_server_price": frozenset({PRICE_CONFLICT}),
    "approve_outside_window": frozenset({OFFLINE_SALE_OUTSIDE_GRANT, OFFLINE_AUTH_EXPIRED}),
    "approve_allocation_override": frozenset({ALLOCATION_EXCEEDED}),
    "approve_credit_override": frozenset({"CREDIT_LIMIT_EXCEEDED"}),
    "dismiss": frozenset(),
}

RECENT_CHANGES_NOTICE = (
    "Offline mode uses the permissions, prices, and stock this device received at its last "
    "online check. Recent account, permission, price, or stock changes may not be on this "
    "device yet; the server rechecks every sale when it syncs."
)


def _utcnow() -> datetime:
    return datetime.utcnow()


def _iso(dt: datetime | None) -> str | None:
    if not dt:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.isoformat() + "Z"


def clamp_offline_auth_hours(hours: int | None) -> int:
    lo = int(settings.OFFLINE_AUTH_HOURS_MIN or 1)
    hi = int(settings.OFFLINE_AUTH_HOURS_MAX or 168)
    raw = DEFAULT_OFFLINE_AUTH_HOURS if hours is None else int(hours)
    return max(lo, min(hi, raw))


def tenant_offline_auth_hours(tenant: m.Tenant | None) -> int:
    return clamp_offline_auth_hours(getattr(tenant, "offline_auth_hours", None) if tenant else None)


OFFLINE_COMPLETE_MISSING = (
    "Offline Complete remains missing because the browser device id is not strong device binding, "
    "a private window with no till-agent journal on this PC cannot recover those sales, saved sales upload "
    "only while the Point of Sale page is open and signed in, and a live site has not been tested."
)


def policy_payload(tenant: m.Tenant | None) -> dict[str, Any]:
    hours = tenant_offline_auth_hours(tenant)
    return {
        "offline_auth_hours": hours,
        "offline_auth_hours_default": DEFAULT_OFFLINE_AUTH_HOURS,
        "offline_auth_hours_min": int(settings.OFFLINE_AUTH_HOURS_MIN or 1),
        "offline_auth_hours_max": int(settings.OFFLINE_AUTH_HOURS_MAX or 168),
        "aligned_with_refresh_token_days": int(settings.REFRESH_TOKEN_EXPIRE_DAYS or 7),
        "offline_complete_claimed": False,
        "grant_issuer": "server",
        "grant_endpoint": "/pos/offline/authorize",
        "default_allocation_pct": DEFAULT_ALLOCATION_PCT,
        "offline_tenders": sorted(OFFLINE_TENDERS),
        "workflows": {
            "pos_catalog_prices": True,
            "pos_create_sale": True,
            "pos_payment_details": True,
            "pos_queue_sync": True,
            "pos_credit_sale_queued": True,
            "wholesale_quote_capture": True,
            "device_stock_allocations": True,
            "stale_stock_warning": True,
        },
        "not_offline": [
            "inventory",
            "purchasing",
            "accounting",
            "reports_authoritative",
            "hotel",
            "platform_admin",
            "user_management",
            "backup_restore",
            "shift_close",
        ],
        "limitations": [
            "Offline covers the POS counter only; inventory, purchasing, accounting, and platform "
            "administration stay online-only.",
            "Offline selling needs a server-issued, device-bound authorization obtained while online.",
            "First-time sign-in while offline is not supported.",
            "Card, Mobile Money, and bank tenders are recorded as details with a reference; no "
            "payment provider is contacted offline.",
            "Gift cards and loyalty points need a live balance and are online-only.",
            "Stock shown offline is this device's allocation; other devices' unsynced sales make "
            "store totals provisional until they sync.",
            "Server price, stock, permissions, and credit limits are rechecked at sync; conflicts "
            "go to a resolution queue and are never dropped.",
            "A missed server response stays pending and retries. Price, stock, and credit conflicts "
            "stay for a manager.",
            OFFLINE_COMPLETE_MISSING,
            RECENT_CHANGES_NOTICE,
        ],
        "recent_changes_notice": RECENT_CHANGES_NOTICE,
    }


def parse_offline_created_at(value: str | datetime | None) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        if not text:
            return None
        try:
            if text.endswith("Z"):
                text = text[:-1] + "+00:00"
            dt = datetime.fromisoformat(text)
        except ValueError:
            from app.reports import parse_date

            dt = parse_date(text)
            if dt is None:
                return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def offline_window_expired(
    *,
    offline_created_at: datetime | None,
    hours: int,
    now: datetime | None = None,
) -> bool:
    """True when a *device* authorization issued at ``offline_created_at`` has lapsed.

    Used for the device-side expiry display only. Sync validity is decided by the
    grant window (:func:`sale_inside_grant_window`), not by how long ago the sale was.
    """
    if offline_created_at is None:
        return False
    now = now or _utcnow()
    return offline_created_at + timedelta(hours=hours) < now


def grant_window_end(grant: m.OfflineGrant) -> datetime:
    end = grant.valid_until
    if grant.revoked_at is not None and grant.revoked_at < end:
        end = grant.revoked_at
    return end


def sale_inside_grant_window(grant: m.OfflineGrant, created_at: datetime | None) -> bool:
    if created_at is None:
        return False
    start = (grant.issued_at or grant.created_at) - CLOCK_SKEW
    return start <= created_at <= grant_window_end(grant) + CLOCK_SKEW


def grant_active(grant: m.OfflineGrant | None, now: datetime | None = None) -> bool:
    if grant is None:
        return False
    now = now or _utcnow()
    return grant.revoked_at is None and grant.valid_until > now


def _perms(claims: dict) -> dict | None:
    perms = claims.get("permissions")
    return perms if isinstance(perms, dict) else None


def claims_can(claims: dict, module: str, action: str) -> bool:
    from app.rbac import has_permission

    return has_permission(claims.get("role", "") or "", module, action, overrides=_perms(claims))


def allowed_actions_for(claims: dict) -> list[str]:
    actions = ["pos_sale", "discount", "receipt_provisional"]
    if claims_can(claims, "credit", "write"):
        actions.append("credit_sale")
    if claims_can(claims, "sales", "write"):
        actions.append("quote_capture")
    if claims_can(claims, "pos", "approve"):
        actions.append("allocation_override")
        actions.append("resolve_conflicts")
    return actions


# ── Allocations ────────────────────────────────────────────────────────────


def _outstanding_expr():
    return case(
        (
            m.OfflineStockAllocation.allocated_qty > m.OfflineStockAllocation.sold_qty,
            m.OfflineStockAllocation.allocated_qty - m.OfflineStockAllocation.sold_qty,
        ),
        else_=0,
    )


def _active_allocation_filters(tenant_id: str, now: datetime):
    return (
        m.OfflineStockAllocation.tenant_id == tenant_id,
        m.OfflineStockAllocation.released_at.is_(None),
        m.OfflineGrant.revoked_at.is_(None),
        m.OfflineGrant.valid_until > now,
    )


async def outstanding_by_product(
    db: AsyncSession,
    *,
    tenant_id: str,
    warehouse_id: str | None,
    product_ids: set[str] | None = None,
    exclude_device_id: str | None = None,
) -> dict[str, float]:
    """Unsold allocated qty on active grants, by product (other devices only when excluded).

    Only devices seen within OFFLINE_RESERVATION_STALE_HOURS count: a reservation left by a
    browser or phone that stopped checking in no longer blocks other tills.
    """
    now = _utcnow()
    seen_after = now - timedelta(hours=max(1, int(settings.OFFLINE_RESERVATION_STALE_HOURS or 4)))
    recent_devices = select(m.PosDevice.device_id).where(
        m.PosDevice.tenant_id == tenant_id,
        m.PosDevice.last_seen_at >= seen_after,
    )
    stmt = (
        select(m.OfflineStockAllocation.product_id, func.coalesce(func.sum(_outstanding_expr()), 0))
        .join(m.OfflineGrant, m.OfflineGrant.id == m.OfflineStockAllocation.grant_id)
        .where(*_active_allocation_filters(tenant_id, now))
        .where(m.OfflineStockAllocation.device_id.in_(recent_devices))
        .group_by(m.OfflineStockAllocation.product_id)
    )
    if warehouse_id:
        stmt = stmt.where(m.OfflineStockAllocation.warehouse_id == warehouse_id)
    else:
        stmt = stmt.where(m.OfflineStockAllocation.warehouse_id.is_(None))
    if product_ids is not None:
        if not product_ids:
            return {}
        stmt = stmt.where(m.OfflineStockAllocation.product_id.in_(list(product_ids)))
    if exclude_device_id:
        stmt = stmt.where(m.OfflineStockAllocation.device_id != exclude_device_id)
    rows = (await db.execute(stmt)).all()
    return {str(pid): money_json(qty or 0) for pid, qty in rows}


async def outstanding_allocated_qty(
    db: AsyncSession,
    *,
    tenant_id: str,
    warehouse_id: str | None,
    product_id: str,
    exclude_device_id: str | None = None,
) -> float:
    found = await outstanding_by_product(
        db,
        tenant_id=tenant_id,
        warehouse_id=warehouse_id,
        product_ids={product_id},
        exclude_device_id=exclude_device_id,
    )
    return money_json(found.get(product_id, 0))


def _slice(free: float, pct: int) -> float:
    if free <= 0:
        return 0.0
    if free >= 1:
        return float(max(1, math.floor(free * pct / 100.0)))
    return math.floor(free * pct / 100.0 * 1000) / 1000.0


async def _store_stock(
    db: AsyncSession, *, tenant_id: str, warehouse_id: str | None
) -> dict[str, float]:
    if warehouse_id:
        rows = (
            await db.execute(
                select(m.WarehouseStock.product_id, m.WarehouseStock.quantity)
                .join(m.Product, m.Product.id == m.WarehouseStock.product_id)
                .where(
                    m.WarehouseStock.tenant_id == tenant_id,
                    m.WarehouseStock.warehouse_id == warehouse_id,
                    m.WarehouseStock.quantity > 0,
                    m.Product.is_active == True,  # noqa: E712
                )
                .limit(MAX_ALLOCATION_PRODUCTS)
            )
        ).all()
    else:
        rows = (
            await db.execute(
                select(m.Product.id, m.Product.stock_qty)
                .where(
                    m.Product.tenant_id == tenant_id,
                    m.Product.is_active == True,  # noqa: E712
                    m.Product.stock_qty > 0,
                )
                .limit(MAX_ALLOCATION_PRODUCTS)
            )
        ).all()
    return {str(pid): money_json(qty or 0) for pid, qty in rows}


async def _reserved_by_product(
    db: AsyncSession, *, tenant_id: str, warehouse_id: str | None
) -> dict[str, float]:
    if not warehouse_id:
        return {}
    rows = (
        await db.execute(
            select(m.StockReservation.product_id, func.coalesce(func.sum(m.StockReservation.quantity), 0))
            .where(
                m.StockReservation.tenant_id == tenant_id,
                m.StockReservation.warehouse_id == warehouse_id,
                m.StockReservation.status == "active",
            )
            .group_by(m.StockReservation.product_id)
        )
    ).all()
    return {str(pid): money_json(qty or 0) for pid, qty in rows}


async def _store_warehouse_id(db: AsyncSession, tenant_id: str, store_id: str | None) -> str | None:
    if not store_id:
        return None
    from app import stores as stores_svc

    wh = await stores_svc.warehouse_for_store(db, tenant_id, store_id)
    return wh.id


async def _upsert_device(
    db: AsyncSession,
    *,
    tenant_id: str,
    device_id: str,
    user_id: str,
    store_id: str | None,
    label: str | None,
    app_version: str | None,
    pending_queue_count: int | None,
) -> m.PosDevice:
    now = _utcnow()
    row = (
        await db.execute(
            select(m.PosDevice).where(
                m.PosDevice.tenant_id == tenant_id,
                m.PosDevice.device_id == device_id,
            )
        )
    ).scalar_one_or_none()
    if row is not None and bool(getattr(row, "offline_blocked", False)):
        raise HTTPException(
            status_code=403,
            detail={
                "code": DEVICE_BLOCKED,
                "message": "This device is blocked from offline selling. Ask a manager to review it.",
            },
        )
    if row is None:
        row = m.PosDevice(
            tenant_id=tenant_id,
            device_id=device_id,
            label=label,
            store_id=store_id,
            user_id=user_id,
            app_version=app_version,
            pending_queue_count=int(pending_queue_count or 0),
            last_seen_at=now,
            created_at=now,
            updated_at=now,
        )
        db.add(row)
    else:
        if label is not None:
            row.label = label
        if store_id is not None:
            row.store_id = store_id
        row.user_id = user_id
        if app_version is not None:
            row.app_version = app_version
        if pending_queue_count is not None:
            row.pending_queue_count = int(pending_queue_count)
        row.last_seen_at = now
        row.updated_at = now
    await db.flush()
    return row


async def _revoke_device_grants(
    db: AsyncSession, *, tenant_id: str, device_id: str, reason: str
) -> int:
    now = _utcnow()
    grants = (
        await db.execute(
            select(m.OfflineGrant).where(
                m.OfflineGrant.tenant_id == tenant_id,
                m.OfflineGrant.device_id == device_id,
                m.OfflineGrant.revoked_at.is_(None),
            )
        )
    ).scalars().all()
    for grant in grants:
        grant.revoked_at = now
        grant.revoke_reason = reason
    if grants:
        allocs = (
            await db.execute(
                select(m.OfflineStockAllocation).where(
                    m.OfflineStockAllocation.tenant_id == tenant_id,
                    m.OfflineStockAllocation.grant_id.in_([g.id for g in grants]),
                    m.OfflineStockAllocation.released_at.is_(None),
                )
            )
        ).scalars().all()
        for alloc in allocs:
            alloc.released_at = now
            alloc.updated_at = now
    await db.flush()
    return len(grants)


async def issue_grant(
    db: AsyncSession,
    *,
    claims: dict,
    device_id: str,
    store_id: str | None,
    pending_items: dict[str, float] | None = None,
    allocation_pct: int | None = None,
    label: str | None = None,
    app_version: str | None = None,
    pending_queue_count: int | None = None,
) -> tuple[m.OfflineGrant, list[m.OfflineStockAllocation]]:
    """Revalidate the online user and issue a fresh device-bound grant + allocations."""
    from app import store_access as store_access_svc
    from app import stores as stores_svc
    from app import tenants as tenants_svc

    tenant_id = claims["tenant_id"]
    user_id = claims["sub"]
    tenant = await tenants_svc.get_tenant(db, tenant_id)
    if tenant is None or str(getattr(tenant, "status", "") or "").lower() in INACTIVE_TENANT_STATUSES:
        raise HTTPException(status_code=403, detail="Workspace is not active")
    user = await db.get(m.User, user_id)
    if user is None or user.tenant_id != tenant_id or not bool(user.is_active):
        raise HTTPException(status_code=403, detail="User is not active in this workspace")
    if not claims_can(claims, "pos", "write"):
        raise HTTPException(status_code=403, detail="Missing permission: pos:write")

    if store_id:
        store = await stores_svc.get_store(db, tenant_id, store_id)
        if not bool(getattr(store, "is_active", True)):
            raise HTTPException(status_code=409, detail="Store is not active")
        await store_access_svc.assert_store_access(
            db, tenant_id=tenant_id, user_id=user_id, store_id=store_id
        )

    await _upsert_device(
        db,
        tenant_id=tenant_id,
        device_id=device_id,
        user_id=user_id,
        store_id=store_id,
        label=label,
        app_version=app_version,
        pending_queue_count=pending_queue_count,
    )
    await _revoke_device_grants(db, tenant_id=tenant_id, device_id=device_id, reason="superseded")

    can_override = claims_can(claims, "pos", "approve")
    pct = DEFAULT_ALLOCATION_PCT if allocation_pct is None else max(1, min(100, int(allocation_pct)))
    if pct > DEFAULT_ALLOCATION_PCT and not can_override:
        pct = DEFAULT_ALLOCATION_PCT

    now = _utcnow()
    hours = tenant_offline_auth_hours(tenant)
    warehouse_id = await _store_warehouse_id(db, tenant_id, store_id)
    grant = m.OfflineGrant(
        tenant_id=tenant_id,
        user_id=user_id,
        device_id=device_id,
        store_id=store_id,
        warehouse_id=warehouse_id,
        industry=claims.get("industry") or getattr(tenant, "industry", None),
        allowed_actions=allowed_actions_for(claims),
        can_override_allocation=can_override,
        issued_at=now,
        valid_until=now + timedelta(hours=hours),
        created_at=now,
    )
    db.add(grant)
    await db.flush()

    on_hand = await _store_stock(db, tenant_id=tenant_id, warehouse_id=warehouse_id)
    reserved = await _reserved_by_product(db, tenant_id=tenant_id, warehouse_id=warehouse_id)
    others = await outstanding_by_product(
        db,
        tenant_id=tenant_id,
        warehouse_id=warehouse_id,
        product_ids=set(on_hand.keys()),
        exclude_device_id=device_id,
    )
    pending = {str(k): max(0.0, money_json(v or 0)) for k, v in (pending_items or {}).items()}
    allocations: list[m.OfflineStockAllocation] = []
    for pid, qty in on_hand.items():
        free = money_json(qty - reserved.get(pid, 0) - others.get(pid, 0) - pending.get(pid, 0))
        share = _slice(free, pct)
        if share <= 0:
            continue
        row = m.OfflineStockAllocation(
            tenant_id=tenant_id,
            grant_id=grant.id,
            device_id=device_id,
            store_id=store_id,
            warehouse_id=warehouse_id,
            product_id=pid,
            allocated_qty=share,
            sold_qty=0,
            created_at=now,
            updated_at=now,
        )
        db.add(row)
        allocations.append(row)
    await db.flush()
    return grant, allocations


def serialize_grant(grant: m.OfflineGrant, allocations: list[m.OfflineStockAllocation]) -> dict:
    hours = max(1, int(round((grant.valid_until - grant.issued_at).total_seconds() / 3600)))
    return {
        "grant_id": grant.id,
        "tenant_id": grant.tenant_id,
        "user_id": grant.user_id,
        "device_id": grant.device_id,
        "store_id": grant.store_id,
        "warehouse_id": grant.warehouse_id,
        "industry": grant.industry,
        "allowed_actions": list(grant.allowed_actions or []),
        "can_override_allocation": bool(grant.can_override_allocation),
        "issued_at": _iso(grant.issued_at),
        "valid_until": _iso(grant.valid_until),
        "revoked_at": _iso(grant.revoked_at),
        "offline_auth_hours": hours,
        "server_time": _iso(_utcnow()),
        "allocations": [
            {
                "product_id": a.product_id,
                "allocated_qty": money_json(a.allocated_qty or 0),
                "sold_qty": money_json(a.sold_qty or 0),
            }
            for a in allocations
        ],
        "recent_changes_notice": RECENT_CHANGES_NOTICE,
    }


async def latest_grant(
    db: AsyncSession, *, tenant_id: str, user_id: str, device_id: str
) -> m.OfflineGrant | None:
    return (
        await db.execute(
            select(m.OfflineGrant)
            .where(
                m.OfflineGrant.tenant_id == tenant_id,
                m.OfflineGrant.user_id == user_id,
                m.OfflineGrant.device_id == device_id,
            )
            .order_by(m.OfflineGrant.issued_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def grant_allocations(db: AsyncSession, grant: m.OfflineGrant) -> list[m.OfflineStockAllocation]:
    return list(
        (
            await db.execute(
                select(m.OfflineStockAllocation).where(
                    m.OfflineStockAllocation.tenant_id == grant.tenant_id,
                    m.OfflineStockAllocation.grant_id == grant.id,
                )
            )
        ).scalars().all()
    )


async def release_device(
    db: AsyncSession, *, tenant_id: str, device_id: str, reason: str
) -> int:
    return await _revoke_device_grants(db, tenant_id=tenant_id, device_id=device_id, reason=reason)


async def set_device_blocked(
    db: AsyncSession, *, tenant_id: str, device_id: str, blocked: bool
) -> m.PosDevice:
    row = (
        await db.execute(
            select(m.PosDevice).where(
                m.PosDevice.tenant_id == tenant_id,
                m.PosDevice.device_id == device_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Device not found")
    row.offline_blocked = bool(blocked)
    row.updated_at = _utcnow()
    if blocked:
        await _revoke_device_grants(db, tenant_id=tenant_id, device_id=device_id, reason="device_blocked")
    await db.flush()
    return row


async def consume_grant_allocation(
    db: AsyncSession,
    *,
    grant: m.OfflineGrant,
    qty_by_product: dict[str, float],
) -> None:
    rows = {a.product_id: a for a in await grant_allocations(db, grant)}
    now = _utcnow()
    for pid, qty in qty_by_product.items():
        row = rows.get(pid)
        if row is None:
            row = m.OfflineStockAllocation(
                tenant_id=grant.tenant_id,
                grant_id=grant.id,
                device_id=grant.device_id,
                store_id=grant.store_id,
                warehouse_id=grant.warehouse_id,
                product_id=pid,
                allocated_qty=0,
                sold_qty=0,
                created_at=now,
                updated_at=now,
            )
            db.add(row)
        row.sold_qty = money_json(money_json(row.sold_qty or 0) + money_json(qty))
        row.updated_at = now
    await db.flush()


async def consume_online_allocation(
    db: AsyncSession,
    *,
    tenant_id: str,
    device_id: str | None,
    qty_by_product: dict[str, float],
) -> dict[str, float] | None:
    """An online sale on a device with an active grant uses that device's slice first.

    Returns remaining allocation per product so the device can update its local copy.
    """
    if not device_id or not qty_by_product:
        return None
    now = _utcnow()
    grant = (
        await db.execute(
            select(m.OfflineGrant)
            .where(
                m.OfflineGrant.tenant_id == tenant_id,
                m.OfflineGrant.device_id == device_id,
                m.OfflineGrant.revoked_at.is_(None),
                m.OfflineGrant.valid_until > now,
            )
            .order_by(m.OfflineGrant.issued_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if grant is None:
        return None
    rows = {a.product_id: a for a in await grant_allocations(db, grant)}
    remaining: dict[str, float] = {}
    for pid, qty in qty_by_product.items():
        row = rows.get(pid)
        if row is None or row.released_at is not None:
            continue
        allocated = money_json(row.allocated_qty or 0)
        sold = money_json(row.sold_qty or 0)
        row.sold_qty = money_json(min(allocated, sold + money_json(qty)))
        row.updated_at = now
        remaining[pid] = money_json(max(0.0, allocated - money_json(row.sold_qty)))
    await db.flush()
    return remaining


# ── Sync validation ────────────────────────────────────────────────────────


async def validate_sale_grant(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    device_id: str | None,
    grant_id: str | None,
    offline_created_at: datetime | None,
    window_approved: bool = False,
) -> m.OfflineGrant | None:
    """Check the sale was recorded under a grant that belonged to this user and device.

    ``None`` grant id = legacy queue entry from before server grants; the user is
    online-authenticated with pos:write, so it may sync (recorded as legacy).
    """
    if not grant_id:
        return None
    grant = await db.get(m.OfflineGrant, grant_id)
    if (
        grant is None
        or grant.tenant_id != tenant_id
        or grant.user_id != user_id
        or (device_id and grant.device_id != device_id)
    ):
        raise HTTPException(
            status_code=403,
            detail={
                "code": OFFLINE_GRANT_INVALID,
                "message": "This sale was recorded under an authorization that does not belong to "
                "this user or device. It was kept; a manager must review it.",
            },
        )
    if window_approved:
        return grant
    if not sale_inside_grant_window(grant, offline_created_at):
        raise HTTPException(
            status_code=403,
            detail={
                "code": OFFLINE_SALE_OUTSIDE_GRANT,
                "message": "This sale is timestamped outside the device's offline authorization. "
                "It was kept; a manager must approve or dismiss it.",
                "grant_issued_at": _iso(grant.issued_at),
                "grant_valid_until": _iso(grant_window_end(grant)),
                "offline_created_at": _iso(offline_created_at),
            },
        )
    return grant


async def check_grant_allocation(
    db: AsyncSession,
    *,
    grant: m.OfflineGrant,
    qty_by_product: dict[str, float],
    override_requested: bool,
    override_approved: bool = False,
) -> None:
    rows = {a.product_id: a for a in await grant_allocations(db, grant)}
    over: list[dict[str, Any]] = []
    for pid, qty in qty_by_product.items():
        row = rows.get(pid)
        allocated = money_json(row.allocated_qty or 0) if row else 0.0
        sold = money_json(row.sold_qty or 0) if row else 0.0
        if qty > allocated - sold + 1e-9:
            over.append(
                {
                    "product_id": pid,
                    "requested_qty": money_json(qty),
                    "allocated_qty": allocated,
                    "already_sold_qty": sold,
                }
            )
    if not over:
        return
    if override_approved or (override_requested and bool(grant.can_override_allocation)):
        return
    raise HTTPException(
        status_code=409,
        detail={
            "code": ALLOCATION_EXCEEDED,
            "message": "This offline sale used more than the device's stock allocation. It was kept; "
            "a manager must approve or dismiss it.",
            "lines": over,
        },
    )


def assert_offline_tenders(payments: list[dict]) -> None:
    from app.pos import normalize_payment_method

    bad = sorted(
        {
            normalize_payment_method(p.get("payment_method"))
            for p in payments
            if normalize_payment_method(p.get("payment_method")) not in OFFLINE_TENDERS
        }
    )
    if bad:
        raise HTTPException(
            status_code=409,
            detail={
                "code": OFFLINE_TENDER_NOT_ALLOWED,
                "message": "These tenders need a live balance and cannot be taken offline: "
                + ", ".join(bad),
                "methods": bad,
            },
        )


async def resolve_sync_session(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    session_id: str | None,
) -> tuple[m.PosSession, str | None]:
    """Use the shift the sale was rung on; fall back to the cashier's open shift at the same store.

    Returns ``(session, original_session_id_if_moved)``.
    """
    from app import pos as pos_svc
    from app import store_access as store_access_svc

    original = None
    if session_id:
        original = await db.get(m.PosSession, session_id)
        if original is None or original.tenant_id != tenant_id:
            original = None
    if original is not None and original.user_id == user_id and original.status == "open":
        await store_access_svc.assert_store_access(
            db, tenant_id=tenant_id, user_id=user_id, store_id=original.store_id
        )
        return original, None
    current = await pos_svc.get_open_session_for_user(db, tenant_id, user_id)
    if current is not None and (original is None or current.store_id == original.store_id):
        await store_access_svc.assert_store_access(
            db, tenant_id=tenant_id, user_id=user_id, store_id=current.store_id
        )
        return current, (original.id if original is not None else None)
    raise HTTPException(
        status_code=409,
        detail={
            "code": SESSION_CLOSED,
            "message": "The shift this sale was rung on is closed. Open a shift at the same store, "
            "then sync again. The sale was kept.",
            "original_session_id": original.id if original is not None else session_id,
        },
    )


async def preflight_offline_sale(
    db: AsyncSession,
    *,
    tenant: m.Tenant | None,
    tenant_id: str,
    user_id: str,
    store_id: str | None,
    items: list[dict],
    customer_id: str | None,
    offline_created_at: datetime | None,
    device_id: str | None,
    client_request_id: str | None,
    accept_server_price: bool = False,
) -> None:
    """Revalidate catalog prices and stock. Never silently apply a stale price or drop the sale."""
    from app.catalog import resolve_sale_line

    _ = tenant, offline_created_at, client_request_id, user_id
    price_conflicts: list[dict[str, Any]] = []
    product_ids: set[str] = set()
    qty_by_product: dict[str, float] = {}
    for item in items:
        pid = str(item.get("product_id") or "")
        if pid:
            product_ids.add(pid)
            qty_by_product[pid] = money_json(qty_by_product.get(pid, 0)) + money_json(
                item.get("quantity") or 0
            )
        if accept_server_price:
            continue
        catalog_item = dict(item)
        catalog_item.pop("unit_price", None)
        _product, _variant, catalog_price = await resolve_sale_line(
            db, tenant_id, catalog_item, customer_id=customer_id
        )
        client_price = item.get("unit_price")
        if client_price is None:
            continue
        client_price = money_json(client_price)
        if abs(client_price - money_json(catalog_price)) > 0.009:
            price_conflicts.append(
                {
                    "product_id": pid,
                    "offline_unit_price": client_price,
                    "server_unit_price": money_json(catalog_price),
                }
            )

    if price_conflicts:
        raise HTTPException(
            status_code=409,
            detail={
                "code": PRICE_CONFLICT,
                "message": "Offline price differs from the server catalog. The sale was kept; "
                "a manager can approve the server price or dismiss it.",
                "lines": price_conflicts,
            },
        )

    if not product_ids:
        return
    warehouse_id = None
    if store_id:
        from app.inventory import store_warehouse_on_hand

        on_hand = await store_warehouse_on_hand(db, tenant_id, store_id, product_ids)
        wh = (
            await db.execute(
                select(m.Warehouse.id).where(
                    m.Warehouse.tenant_id == tenant_id,
                    m.Warehouse.store_id == store_id,
                )
            )
        ).scalar_one_or_none()
        warehouse_id = wh
    else:
        rows = (
            await db.execute(
                select(m.Product).where(
                    m.Product.tenant_id == tenant_id,
                    m.Product.id.in_(product_ids),
                )
            )
        ).scalars().all()
        on_hand = {p.id: money_json(p.stock_qty or 0) for p in rows}
    others = await outstanding_by_product(
        db,
        tenant_id=tenant_id,
        warehouse_id=warehouse_id,
        product_ids=product_ids,
        exclude_device_id=device_id,
    )
    stock_conflicts: list[dict[str, Any]] = []
    for pid, qty in qty_by_product.items():
        available = money_json(on_hand.get(pid, 0) - others.get(pid, 0))
        if qty > available + 0.009:
            stock_conflicts.append(
                {
                    "product_id": pid,
                    "requested_qty": qty,
                    "server_on_hand": money_json(on_hand.get(pid, 0)),
                    "allocated_to_other_devices": money_json(others.get(pid, 0)),
                }
            )
    if stock_conflicts:
        raise HTTPException(
            status_code=409,
            detail={
                "code": STOCK_CONFLICT,
                "message": "Server stock cannot fulfil this offline sale. The sale was kept; "
                "count or receive the stock, then retry.",
                "lines": stock_conflicts,
                "stock_authoritative": True,
            },
        )


def qty_by_product(items: list[dict]) -> dict[str, float]:
    out: dict[str, float] = {}
    for item in items:
        pid = str(item.get("product_id") or "")
        if not pid:
            continue
        out[pid] = money_json(out.get(pid, 0) + money_json(item.get("quantity") or 0))
    return out


# ── Sync events, conflicts, and resolutions ────────────────────────────────


async def record_sync_event(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str | None,
    device_id: str | None,
    client_request_id: str | None,
    sale_id: str | None,
    store_id: str | None,
    offline_created_at: datetime | None,
    result: str,
    conflict_code: str | None = None,
    details: dict[str, Any] | None = None,
) -> m.OfflineSyncEvent:
    row = m.OfflineSyncEvent(
        tenant_id=tenant_id,
        user_id=user_id,
        device_id=(device_id or None),
        client_request_id=client_request_id,
        sale_id=sale_id,
        store_id=store_id,
        offline_created_at=offline_created_at,
        result=result,
        conflict_code=conflict_code,
        details=details or {},
    )
    db.add(row)
    await db.flush()
    return row


def _exception_code(exc: HTTPException) -> str:
    detail = exc.detail
    if isinstance(detail, dict) and detail.get("code"):
        return str(detail["code"])[:80]
    if exc.status_code == 403:
        return "PERMISSION_DENIED"
    if exc.status_code == 404:
        return "NOT_FOUND"
    if exc.status_code == 422:
        return "INVALID_SALE"
    return f"HTTP_{exc.status_code}"


def _exception_message(exc: HTTPException) -> str:
    detail = exc.detail
    if isinstance(detail, dict):
        return str(detail.get("message") or detail.get("detail") or "Sync needs attention")[:500]
    return str(detail or "Sync needs attention")[:500]


async def record_sync_failure(
    db: AsyncSession,
    *,
    claims: dict,
    request: dict[str, Any],
    exc: HTTPException,
    store_id: str | None = None,
) -> m.OfflineSyncEvent:
    """Keep one open conflict per queued sale + code; the full request is preserved for review."""
    tenant_id = claims["tenant_id"]
    crid = (request.get("client_request_id") or "").strip() or None
    code = _exception_code(exc)
    detail_payload = exc.detail if isinstance(exc.detail, dict) else {"message": _exception_message(exc)}
    details = {
        "status": exc.status_code,
        "detail": detail_payload,
        "request": request,
        "grant_id": request.get("offline_grant_id"),
    }
    existing = None
    if crid:
        existing = (
            await db.execute(
                select(m.OfflineSyncEvent)
                .where(
                    m.OfflineSyncEvent.tenant_id == tenant_id,
                    m.OfflineSyncEvent.client_request_id == crid,
                    m.OfflineSyncEvent.conflict_code == code,
                    m.OfflineSyncEvent.resolution.is_(None),
                )
                .order_by(m.OfflineSyncEvent.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
    if existing is not None:
        merged = dict(existing.details or {})
        merged.update(details)
        merged["attempts"] = int(merged.get("attempts") or 1) + 1
        existing.details = merged
        from sqlalchemy.orm.attributes import flag_modified

        flag_modified(existing, "details")
        await db.flush()
        return existing
    details["attempts"] = 1
    return await record_sync_event(
        db,
        tenant_id=tenant_id,
        user_id=claims.get("sub"),
        device_id=request.get("device_id"),
        client_request_id=crid,
        sale_id=None,
        store_id=store_id,
        offline_created_at=parse_offline_created_at(request.get("offline_created_at")),
        result="conflict" if exc.status_code < 500 else "error",
        conflict_code=code,
        details=details,
    )


def exception_with_event(exc: HTTPException, event: m.OfflineSyncEvent) -> HTTPException:
    detail = dict(exc.detail) if isinstance(exc.detail, dict) else {"message": _exception_message(exc)}
    detail.setdefault("code", _exception_code(exc))
    detail["sync_event_id"] = event.id
    detail["needs_attention"] = exc.status_code < 500
    detail["kept"] = True
    return HTTPException(status_code=exc.status_code, detail=detail, headers=exc.headers)


async def close_events_for_synced_sale(
    db: AsyncSession, *, tenant_id: str, client_request_id: str | None, sale_id: str
) -> None:
    if not client_request_id:
        return
    rows = (
        await db.execute(
            select(m.OfflineSyncEvent).where(
                m.OfflineSyncEvent.tenant_id == tenant_id,
                m.OfflineSyncEvent.client_request_id == client_request_id,
                m.OfflineSyncEvent.result.in_(("conflict", "error", "expired")),
            )
        )
    ).scalars().all()
    now = _utcnow()
    for row in rows:
        row.sale_id = sale_id
        if row.resolution is None:
            row.resolution = "synced"
            row.resolved_at = now
    await db.flush()


async def load_resolution(
    db: AsyncSession,
    *,
    tenant_id: str,
    client_request_id: str | None,
    event_id: str | None,
) -> m.OfflineSyncEvent | None:
    """Approved resolution for this queued sale, if the device sent one."""
    if not event_id:
        dismissed = None
        if client_request_id:
            dismissed = (
                await db.execute(
                    select(m.OfflineSyncEvent.id).where(
                        m.OfflineSyncEvent.tenant_id == tenant_id,
                        m.OfflineSyncEvent.client_request_id == client_request_id,
                        m.OfflineSyncEvent.resolution == "dismiss",
                    )
                )
            ).first()
        if dismissed:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": SALE_DISMISSED,
                    "message": "A manager dismissed this offline sale. It stays on record and was not posted.",
                },
            )
        return None
    event = await db.get(m.OfflineSyncEvent, event_id)
    if (
        event is None
        or event.tenant_id != tenant_id
        or (client_request_id and event.client_request_id != client_request_id)
        or not event.resolution
        or event.resolution == "synced"
    ):
        raise HTTPException(
            status_code=409,
            detail={
                "code": RESOLUTION_INVALID,
                "message": "That resolution does not match this sale.",
            },
        )
    if event.resolution == "dismiss":
        raise HTTPException(
            status_code=409,
            detail={
                "code": SALE_DISMISSED,
                "message": "A manager dismissed this offline sale. It stays on record and was not posted.",
            },
        )
    return event


def serialize_event(row: m.OfflineSyncEvent) -> dict:
    details = dict(row.details or {})
    request = details.get("request") or {}
    detail = details.get("detail") or {}
    return {
        "id": row.id,
        "device_id": row.device_id,
        "user_id": row.user_id,
        "store_id": row.store_id,
        "client_request_id": row.client_request_id,
        "sale_id": row.sale_id,
        "result": row.result,
        "conflict_code": row.conflict_code,
        "message": detail.get("message") if isinstance(detail, dict) else None,
        "lines": detail.get("lines") if isinstance(detail, dict) else None,
        "status": details.get("status"),
        "attempts": details.get("attempts"),
        "offline_created_at": _iso(row.offline_created_at),
        "offline_total": request.get("total"),
        "local_receipt_number": request.get("local_receipt_number"),
        "resolution": row.resolution,
        "resolved_by": row.resolved_by,
        "resolved_at": _iso(row.resolved_at),
        "resolution_note": row.resolution_note,
        "allowed_resolutions": [
            action
            for action, codes in RESOLUTION_ACTIONS.items()
            if action == "dismiss" or (row.conflict_code or "") in codes
        ],
        "created_at": _iso(row.created_at),
    }


async def list_events(
    db: AsyncSession,
    *,
    claims: dict,
    device_id: str | None = None,
    open_only: bool = True,
    client_request_ids: list[str] | None = None,
    limit: int = 200,
) -> list[m.OfflineSyncEvent]:
    from app import store_access as store_access_svc

    stmt = select(m.OfflineSyncEvent).where(
        m.OfflineSyncEvent.tenant_id == claims["tenant_id"],
        m.OfflineSyncEvent.result.in_(("conflict", "error", "expired")),
    )
    if device_id:
        stmt = stmt.where(m.OfflineSyncEvent.device_id == device_id)
    if client_request_ids is not None:
        if not client_request_ids:
            return []
        stmt = stmt.where(m.OfflineSyncEvent.client_request_id.in_(client_request_ids[:500]))
    if open_only:
        stmt = stmt.where(
            (m.OfflineSyncEvent.resolution.is_(None))
            | (m.OfflineSyncEvent.resolution.notin_(("synced",)) & m.OfflineSyncEvent.sale_id.is_(None))
        )
    if not claims_can(claims, "pos", "approve"):
        stmt = stmt.where(m.OfflineSyncEvent.user_id == claims["sub"])
    allowed = await store_access_svc.assigned_store_ids(
        db, tenant_id=claims["tenant_id"], user_id=claims["sub"]
    )
    if allowed is not None:
        stmt = stmt.where(
            (m.OfflineSyncEvent.store_id.in_(allowed)) | (m.OfflineSyncEvent.store_id.is_(None))
        )
    stmt = stmt.order_by(m.OfflineSyncEvent.created_at.desc()).limit(max(1, min(limit, 500)))
    return list((await db.execute(stmt)).scalars().all())


async def resolve_event(
    db: AsyncSession,
    *,
    claims: dict,
    event_id: str,
    action: str,
    note: str,
) -> m.OfflineSyncEvent:
    from app import audit as audit_svc
    from app import store_access as store_access_svc

    if not claims_can(claims, "pos", "approve"):
        raise HTTPException(status_code=403, detail="Missing permission: pos:approve")
    if action not in RESOLUTION_ACTIONS:
        raise HTTPException(status_code=422, detail="Unknown resolution")
    note = (note or "").strip()
    if len(note) < 3:
        raise HTTPException(status_code=422, detail="Enter a short reason (at least 3 characters)")
    event = await db.get(m.OfflineSyncEvent, event_id)
    if event is None or event.tenant_id != claims["tenant_id"]:
        raise HTTPException(status_code=404, detail="Sync record not found")
    if event.store_id:
        await store_access_svc.assert_store_access(
            db, tenant_id=claims["tenant_id"], user_id=claims["sub"], store_id=event.store_id
        )
    if event.sale_id:
        raise HTTPException(status_code=409, detail="This sale already synced")
    allowed_codes = RESOLUTION_ACTIONS[action]
    if action != "dismiss" and (event.conflict_code or "") not in allowed_codes:
        raise HTTPException(status_code=409, detail="That resolution does not apply to this conflict")
    if action == "approve_credit_override" and not claims_can(claims, "credit", "approve"):
        raise HTTPException(status_code=403, detail="Missing permission: credit:approve")
    event.resolution = action
    event.resolved_by = claims["sub"]
    event.resolved_at = _utcnow()
    event.resolution_note = note[:1000]
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="pos",
        action="offline_conflict_resolved",
        entity="offline_sync_event",
        entity_id=event.id,
        details={
            "resolution": action,
            "note": note[:500],
            "conflict_code": event.conflict_code,
            "client_request_id": event.client_request_id,
            "device_id": event.device_id,
        },
    )
    await db.flush()
    return event


async def device_status(
    db: AsyncSession,
    *,
    claims: dict,
    device_id: str,
    client_request_ids: list[str] | None = None,
) -> dict[str, Any]:
    tenant_id = claims["tenant_id"]
    grant = await latest_grant(db, tenant_id=tenant_id, user_id=claims["sub"], device_id=device_id)
    allocations = await grant_allocations(db, grant) if grant else []
    device = (
        await db.execute(
            select(m.PosDevice).where(
                m.PosDevice.tenant_id == tenant_id,
                m.PosDevice.device_id == device_id,
            )
        )
    ).scalar_one_or_none()
    others_pending = 0
    store_id = (grant.store_id if grant else None) or (device.store_id if device else None)
    if store_id:
        others_pending = int(
            (
                await db.execute(
                    select(func.coalesce(func.sum(m.PosDevice.pending_queue_count), 0)).where(
                        m.PosDevice.tenant_id == tenant_id,
                        m.PosDevice.store_id == store_id,
                        m.PosDevice.device_id != device_id,
                    )
                )
            ).scalar()
            or 0
        )
    events = []
    if client_request_ids is not None:
        events = await list_events(
            db,
            claims=claims,
            client_request_ids=client_request_ids,
            open_only=False,
            limit=500,
        )
    return {
        "device_id": device_id,
        "device_blocked": bool(getattr(device, "offline_blocked", False)) if device else False,
        "grant": serialize_grant(grant, allocations) if grant else None,
        "grant_active": grant_active(grant),
        "other_devices_pending": others_pending,
        "provisional": others_pending > 0,
        "events": [serialize_event(e) for e in events],
        "server_time": _iso(_utcnow()),
        "recent_changes_notice": RECENT_CHANGES_NOTICE,
    }


async def store_pending_summary(
    db: AsyncSession, *, tenant_id: str, store_ids: list[str] | None
) -> dict[str, Any]:
    """Devices with unsynced offline sales → reports/stock are provisional."""
    stmt = select(
        func.count(m.PosDevice.id), func.coalesce(func.sum(m.PosDevice.pending_queue_count), 0)
    ).where(m.PosDevice.tenant_id == tenant_id, m.PosDevice.pending_queue_count > 0)
    if store_ids is not None:
        if not store_ids:
            return {"devices_pending": 0, "sales_pending": 0, "provisional": False}
        stmt = stmt.where(m.PosDevice.store_id.in_(store_ids))
    devices, sales = (await db.execute(stmt)).one()
    return {
        "devices_pending": int(devices or 0),
        "sales_pending": int(sales or 0),
        "provisional": int(sales or 0) > 0,
    }


# ── Offline catalogue for the device cache ─────────────────────────────────


async def offline_catalog(
    db: AsyncSession,
    *,
    claims: dict,
    store_id: str | None,
) -> dict[str, Any]:
    """Products, variants, barcodes, prices, tax, pharmacy lots, tiers, customers for one store."""
    from app import store_access as store_access_svc
    from app import stores as stores_svc
    from app.packages import canonicalize_industry
    from app.tax import resolve_products_tax_map

    tenant_id = claims["tenant_id"]
    if store_id:
        await stores_svc.get_store(db, tenant_id, store_id)
        await store_access_svc.assert_store_access(
            db, tenant_id=tenant_id, user_id=claims["sub"], store_id=store_id
        )
    industry = canonicalize_industry(claims.get("industry"))
    pharmacy = industry == "pharmacy"
    wholesale = industry in {"wholesale", "retail_wholesale"}

    products = list(
        (
            await db.execute(
                select(m.Product)
                .where(m.Product.tenant_id == tenant_id, m.Product.is_active == True)  # noqa: E712
                .order_by(m.Product.name)
                .limit(OFFLINE_CATALOG_LIMIT)
            )
        ).scalars().all()
    )
    by_id = {p.id: p for p in products}
    variants = list(
        (
            await db.execute(
                select(m.ProductVariant).where(
                    m.ProductVariant.tenant_id == tenant_id,
                    m.ProductVariant.is_active == True,  # noqa: E712
                    m.ProductVariant.product_id.in_(list(by_id.keys()) or [""]),
                )
            )
        ).scalars().all()
    )
    specs = await resolve_products_tax_map(db, tenant_id, products)
    warehouse_id = await _store_warehouse_id(db, tenant_id, store_id) if store_id else None
    if warehouse_id:
        stock_rows = (
            await db.execute(
                select(m.WarehouseStock.product_id, m.WarehouseStock.quantity).where(
                    m.WarehouseStock.tenant_id == tenant_id,
                    m.WarehouseStock.warehouse_id == warehouse_id,
                )
            )
        ).all()
        stock = {str(pid): money_json(q or 0) for pid, q in stock_rows}
    else:
        stock = {p.id: money_json(p.stock_qty or 0) for p in products}

    lots: dict[str, list[dict]] = {}
    if pharmacy and by_id:
        from app import pharmacy as pharmacy_svc

        now = _utcnow()
        batch_stmt = select(m.ProductBatch).where(
            m.ProductBatch.tenant_id == tenant_id,
            m.ProductBatch.product_id.in_(list(by_id.keys())),
            m.ProductBatch.quantity > 0,
        )
        if warehouse_id:
            batch_stmt = batch_stmt.where(
                (m.ProductBatch.warehouse_id == warehouse_id) | (m.ProductBatch.warehouse_id.is_(None))
            )
        batches = list((await db.execute(batch_stmt)).scalars().all())
        held = await pharmacy_svc.open_hold_batch_ids(db, tenant_id, [b.id for b in batches])
        for b in batches:
            if b.id in held:
                continue
            if b.expiry_date is not None and b.expiry_date < now:
                continue
            lots.setdefault(b.product_id, []).append(
                {
                    "expiry_date": b.expiry_date.date().isoformat() if b.expiry_date else None,
                    "quantity": money_json(b.quantity or 0),
                }
            )
        tracked = {b.product_id for b in batches}
    else:
        tracked = set()

    tiers: dict[str, list[dict]] = {}
    if wholesale and by_id:
        from app import schema_compat as schema_compat_svc

        if await schema_compat_svc.table_column_names(db, "product_price_tiers"):
            tier_rows = (
                await db.execute(
                    select(m.ProductPriceTier).where(
                        m.ProductPriceTier.tenant_id == tenant_id,
                        m.ProductPriceTier.product_id.in_(list(by_id.keys())),
                    )
                )
            ).scalars().all()
            for t in tier_rows:
                tiers.setdefault(t.product_id, []).append(
                    {
                        "min_qty": money_json(t.min_qty or 0),
                        "unit_price": money_json(t.unit_price or 0),
                        "customer_group_id": t.customer_group_id,
                    }
                )

    def tax_fields(product: m.Product | None) -> dict:
        spec = specs.get(product.id) if product is not None else None
        if spec is None:
            return {
                "tax_rate_pct": 0.0,
                "tax_pricing_mode": "exclusive",
                "tax_reverse_charge": False,
                "tax_components": None,
            }
        return {
            "tax_rate_pct": money_json(spec.rate_pct or 0),
            "tax_pricing_mode": spec.pricing_mode or "exclusive",
            "tax_reverse_charge": bool(spec.is_reverse_charge),
            "tax_components": list(spec.components) if spec.components else None,
        }

    def pharmacy_fields(product: m.Product) -> dict:
        if not pharmacy:
            return {}
        product_lots = sorted(lots.get(product.id, []), key=lambda r: r["expiry_date"] or "9999")
        batch_tracked = bool(getattr(product, "tracks_batches", False)) or product.id in tracked
        block = None
        if bool(getattr(product, "rx_only", False)):
            block = "Prescription-only items need an online prescription check."
        elif batch_tracked and not product_lots:
            block = "No sellable lot: stock is expired, recalled, or quarantined."
        return {
            "rx_only": bool(getattr(product, "rx_only", False)),
            "batch_tracked": batch_tracked,
            "saleable_lots": product_lots,
            "nearest_expiry_date": product_lots[0]["expiry_date"] if product_lots else None,
            "offline_block_reason": block,
        }

    rows: list[dict] = []
    for p in products:
        row = {
            "id": p.id,
            "product_id": p.id,
            "variant_id": None,
            "name": p.name,
            "sku": p.sku,
            "barcode": p.barcode,
            "category": (getattr(p, "category", None) or "").strip() or None,
            "category_id": getattr(p, "category_id", None),
            "selling_price": money_json(p.selling_price or 0),
            "stock_qty": money_json(stock.get(p.id, 0)),
            "kind": "product",
            "has_image": bool(p.image_url),
            "min_order_qty": money_json(getattr(p, "min_order_qty", 0) or 0),
            "price_tiers": tiers.get(p.id) or [],
        }
        row.update(tax_fields(p))
        row.update(pharmacy_fields(p))
        rows.append(row)
    for v in variants:
        parent = by_id.get(v.product_id)
        if parent is None:
            continue
        row = {
            "id": v.id,
            "product_id": v.product_id,
            "variant_id": v.id,
            "name": v.name,
            "sku": v.sku,
            "barcode": v.barcode,
            "category": (getattr(parent, "category", None) or "").strip() or None,
            "category_id": getattr(parent, "category_id", None),
            "selling_price": money_json(v.selling_price or 0),
            "stock_qty": money_json(stock.get(v.product_id, 0)),
            "kind": "variant",
            "has_image": False,
            "min_order_qty": money_json(getattr(parent, "min_order_qty", 0) or 0),
            "price_tiers": tiers.get(v.product_id) or [],
        }
        row.update(tax_fields(parent))
        row.update(pharmacy_fields(parent))
        rows.append(row)

    customers: list[dict] = []
    if claims_can(claims, "pos", "write"):
        party_rows = (
            await db.execute(
                select(m.Party)
                .where(
                    m.Party.tenant_id == tenant_id,
                    m.Party.kind == "customer",
                    m.Party.status == "active",
                )
                .order_by(m.Party.name)
                .limit(OFFLINE_CUSTOMER_LIMIT)
            )
        ).scalars().all()
        group_ids = {getattr(p, "customer_group_id", None) for p in party_rows} - {None}
        groups: dict[str, Any] = {}
        if group_ids and hasattr(m, "CustomerGroup"):
            for g in (
                await db.execute(
                    select(m.CustomerGroup).where(
                        m.CustomerGroup.tenant_id == tenant_id,
                        m.CustomerGroup.id.in_(list(group_ids)),
                    )
                )
            ).scalars().all():
                if bool(getattr(g, "is_active", True)):
                    groups[g.id] = g
        for party in party_rows:
            group = groups.get(getattr(party, "customer_group_id", None) or "")
            customers.append(
                {
                    "id": party.id,
                    "name": party.name,
                    "phone": party.phone,
                    "status": party.status,
                    "credit_limit": money_json(getattr(party, "credit_limit", 0) or 0),
                    "balance": money_json(party.balance or 0),
                    "payment_terms_days": getattr(party, "payment_terms_days", None),
                    "customer_group_id": getattr(party, "customer_group_id", None),
                    "customer_group": (
                        {
                            "id": group.id,
                            "name": group.name,
                            "discount_percent": money_json(group.discount_percent or 0),
                        }
                        if group is not None
                        else None
                    ),
                }
            )

    return {
        "store_id": store_id,
        "industry": industry,
        "generated_at": _iso(_utcnow()),
        "products": rows,
        "customers": customers,
        "truncated": len(products) >= OFFLINE_CATALOG_LIMIT,
        "pharmacy_rules": pharmacy,
        "wholesale_tiers": wholesale,
    }
