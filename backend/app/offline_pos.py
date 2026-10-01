"""Offline POS policy + sync preflight on the existing /pos/sales path.

This is not a second sync stack. Queued sales flush to POST /pos/sales with
``client_request_id`` idempotency. Server catalog/stock remain authoritative.
Payment information is recorded as tender details only — funds are never held.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.config import settings
from app.honesty import money_json

OFFLINE_AUTH_EXPIRED = "OFFLINE_AUTH_EXPIRED"
PRICE_CONFLICT = "PRICE_CONFLICT"
STOCK_CONFLICT = "STOCK_CONFLICT"

# Default 168 hours = 7 days, aligned with REFRESH_TOKEN_EXPIRE_DAYS. Not a client hardcode.
DEFAULT_OFFLINE_AUTH_HOURS = int(settings.OFFLINE_AUTH_HOURS_DEFAULT or 168)


def clamp_offline_auth_hours(hours: int | None) -> int:
    lo = int(settings.OFFLINE_AUTH_HOURS_MIN or 1)
    hi = int(settings.OFFLINE_AUTH_HOURS_MAX or 168)
    raw = DEFAULT_OFFLINE_AUTH_HOURS if hours is None else int(hours)
    return max(lo, min(hi, raw))


def tenant_offline_auth_hours(tenant: m.Tenant | None) -> int:
    return clamp_offline_auth_hours(getattr(tenant, "offline_auth_hours", None) if tenant else None)


def policy_payload(tenant: m.Tenant | None) -> dict[str, Any]:
    hours = tenant_offline_auth_hours(tenant)
    return {
        "offline_auth_hours": hours,
        "offline_auth_hours_default": DEFAULT_OFFLINE_AUTH_HOURS,
        "offline_auth_hours_min": int(settings.OFFLINE_AUTH_HOURS_MIN or 1),
        "offline_auth_hours_max": int(settings.OFFLINE_AUTH_HOURS_MAX or 168),
        "max_sync_retries": int(settings.OFFLINE_SYNC_MAX_RETRIES or 8),
        "aligned_with_refresh_token_days": int(settings.REFRESH_TOKEN_EXPIRE_DAYS or 7),
        "offline_complete_claimed": False,
        "workflows": {
            "pos_catalog_prices": True,
            "pos_create_sale": True,
            "pos_payment_details": True,
            "pos_queue_sync": True,
            "stale_stock_warning": True,
        },
        "not_offline": ["inventory", "reports", "hotel", "purchasing", "accounting"],
        "limitations": [
            "Offline Complete is MISSING — this is a POS-only queue on /pos/sales, not a full offline ERP.",
            "Offline selling requires a prior online sign-in on this device with a valid offline envelope.",
            "First-time login while offline is not supported.",
            "Only cash tenders can be completed offline; card/wallet/credit require an online confirmation.",
            "Cached catalog stock is non-authoritative; conflicts stay visible and are never dropped silently.",
            "Inventory, reports, and hotel are not available offline.",
            "Server catalog price and on-hand stock are the source of truth after sync.",
            "Access/refresh tokens must not be stored in localStorage; they are not used for offline authorization.",
        ],
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
    if offline_created_at is None:
        return False
    now = now or datetime.utcnow()
    return offline_created_at + timedelta(hours=hours) < now


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


async def preflight_offline_sale(
    db: AsyncSession,
    *,
    tenant: m.Tenant,
    tenant_id: str,
    user_id: str,
    store_id: str | None,
    items: list[dict],
    customer_id: str | None,
    offline_created_at: datetime | None,
    device_id: str | None,
    client_request_id: str | None,
) -> None:
    """Revalidate catalog prices and stock. Never silently apply a stale price or drop the sale."""
    hours = tenant_offline_auth_hours(tenant)
    if offline_window_expired(offline_created_at=offline_created_at, hours=hours):
        await record_sync_event(
            db,
            tenant_id=tenant_id,
            user_id=user_id,
            device_id=device_id,
            client_request_id=client_request_id,
            sale_id=None,
            store_id=store_id,
            offline_created_at=offline_created_at,
            result="expired",
            conflict_code=OFFLINE_AUTH_EXPIRED,
            details={"offline_auth_hours": hours},
        )
        raise HTTPException(
            status_code=403,
            detail={
                "code": OFFLINE_AUTH_EXPIRED,
                "message": "Offline authorization expired — reconnect to revalidate before syncing this sale",
                "offline_auth_hours": hours,
            },
        )

    from app.catalog import resolve_sale_line

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
        await record_sync_event(
            db,
            tenant_id=tenant_id,
            user_id=user_id,
            device_id=device_id,
            client_request_id=client_request_id,
            sale_id=None,
            store_id=store_id,
            offline_created_at=offline_created_at,
            result="conflict",
            conflict_code=PRICE_CONFLICT,
            details={"lines": price_conflicts},
        )
        raise HTTPException(
            status_code=409,
            detail={
                "code": PRICE_CONFLICT,
                "message": "Offline price differs from server catalog — resolve the conflict; sale was not dropped",
                "lines": price_conflicts,
            },
        )

    stock_conflicts: list[dict[str, Any]] = []
    if product_ids:
        from sqlalchemy import select

        if store_id:
            from app.inventory import store_warehouse_on_hand

            on_hand = await store_warehouse_on_hand(db, tenant_id, store_id, product_ids)
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
        for pid, qty in qty_by_product.items():
            available = money_json(on_hand.get(pid, 0))
            if qty > available + 0.009:
                stock_conflicts.append(
                    {
                        "product_id": pid,
                        "requested_qty": qty,
                        "server_on_hand": available,
                    }
                )
        if stock_conflicts:
            await record_sync_event(
                db,
                tenant_id=tenant_id,
                user_id=user_id,
                device_id=device_id,
                client_request_id=client_request_id,
                sale_id=None,
                store_id=store_id,
                offline_created_at=offline_created_at,
                result="conflict",
                conflict_code=STOCK_CONFLICT,
                details={"lines": stock_conflicts},
            )
            raise HTTPException(
                status_code=409,
                detail={
                    "code": STOCK_CONFLICT,
                    "message": "Server stock cannot fulfill this offline sale — resolve the conflict; sale was not dropped",
                    "lines": stock_conflicts,
                    "stock_authoritative": True,
                },
            )
