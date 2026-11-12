"""Bakery counter sales rung while the internet was down.

Same rules as the restaurant till (restaurant_offline): each sale carries its own key
(`offline_ref`) and books once; prices come from today's catalogue, never the device;
what the cashier charged is kept beside it so a difference shows. Bakery has one till
shift per company, so a sale that arrives while no till is open waits on the device
(status "waiting") until someone opens the till, instead of being refused.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit as audit_svc
from app import bakery as bakery_svc
from app import models as m
from app import tax as tax_svc
from app.honesty import money_json

OFFLINE_MAX_AGE = timedelta(hours=72)
CLOCK_SLACK = timedelta(minutes=10)
OFFLINE_METHODS = frozenset({"cash", "card", "mobile_money"})
MAX_SALES_PER_SYNC = 100


def _naive(value: datetime) -> datetime:
    return value.replace(tzinfo=None) if value.tzinfo is not None else value


def _error_text(exc: HTTPException) -> str:
    detail = exc.detail
    if isinstance(detail, dict):
        return str(detail.get("message") or detail.get("code") or "Refused")
    return str(detail)


async def _booked(db: AsyncSession, tenant_id: str, ref: str) -> m.BakerySale | None:
    return (
        await db.execute(
            select(m.BakerySale).where(m.BakerySale.tenant_id == tenant_id, m.BakerySale.offline_ref == ref)
        )
    ).scalar_one_or_none()


def _result(ref: str, status: str, *, sale: m.BakerySale | None = None, **extra) -> dict:
    body = {"offline_ref": ref, "status": status}
    if sale is not None:
        body.update({"sale_id": sale.id, "order_number": sale.sale_number, "booked_total": money_json(sale.total)})
    body.update(extra)
    return body


async def _book_one(db: AsyncSession, tenant_id: str, sale, *, user_id: str | None, device_id: str | None) -> dict:
    ref = sale.offline_ref
    existing = await _booked(db, tenant_id, ref)
    if existing is not None:
        return _result(ref, "already_booked", sale=existing)
    rung_at = _naive(sale.created_at)
    now = datetime.utcnow()
    if rung_at > now + CLOCK_SLACK:
        return _result(ref, "refused", reason="The sale is dated in the future. Check the till's clock.")
    if rung_at < now - OFFLINE_MAX_AGE:
        return _result(ref, "refused", reason="The sale is more than 72 hours old. A manager must enter it by hand.")
    if sale.payment_method not in OFFLINE_METHODS:
        return _result(ref, "refused", reason="That payment needs a live connection and cannot be taken offline.")
    if await bakery_svc.current_shift(db, tenant_id) is None:
        return _result(ref, "waiting", reason="Open the till to book the sales kept on this device.")
    try:
        async with db.begin_nested():
            row = await bakery_svc.create_sale(db, tenant_id, sale, user_id=user_id)
            row.offline_ref = ref
            row.created_at = rung_at
            await db.flush()
    except HTTPException as exc:
        return _result(ref, "refused", reason=_error_text(exc))
    charged = Decimal(str(sale.charged_total)) if sale.charged_total is not None else None
    booked = Decimal(str(row.total or 0))
    difference = money_json(booked - charged) if charged is not None else 0.0
    await audit_svc.record_event(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        module="bakery",
        action="bakery_offline_sale_booked",
        entity="bakery_sale",
        entity_id=row.id,
        details={
            "offline_ref": ref,
            "rung_at": rung_at.isoformat(),
            "device_id": device_id,
            "charged_total": money_json(charged) if charged is not None else None,
            "booked_total": money_json(booked),
            "difference": difference,
        },
    )
    return _result(
        ref,
        "booked",
        sale=row,
        charged_total=money_json(charged) if charged is not None else None,
        difference=difference,
    )


async def sync_sales(db: AsyncSession, tenant_id: str, sales: list, *, user_id: str | None, device_id: str | None) -> dict:
    if len(sales) > MAX_SALES_PER_SYNC:
        raise HTTPException(status_code=422, detail=f"Send at most {MAX_SALES_PER_SYNC} sales at a time")
    seen: set[str] = set()
    results: list[dict] = []
    for sale in sales:
        if sale.offline_ref in seen:
            results.append(_result(sale.offline_ref, "duplicate_in_batch"))
            continue
        seen.add(sale.offline_ref)
        results.append(await _book_one(db, tenant_id, sale, user_id=user_id, device_id=device_id))
    counts: dict[str, int] = {}
    for row in results:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    return {"results": results, "counts": counts}


async def price_sheet(db: AsyncSession, tenant_id: str) -> dict:
    """Each item's price and tax rule, so an offline bill totals like the server's."""
    items: dict[str, dict] = {}
    products = (
        await db.execute(select(m.Product).where(m.Product.tenant_id == tenant_id, m.Product.is_active.is_(True)))
    ).scalars()
    for product in products:
        spec = await tax_svc.resolve_product_tax(db, tenant_id, product)
        items[product.id] = {
            "price": money_json(product.selling_price or 0),
            "tax_percent": money_json(spec.rate_pct or 0),
            "inclusive": (spec.pricing_mode or "exclusive") == "inclusive",
        }
    return {"items": items}
