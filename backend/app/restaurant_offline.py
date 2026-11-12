"""Restaurant till sales rung while the internet was down.

The till keeps each sale on the device with its own key (`offline_ref`). When the
connection returns it sends them here. Each key books once: a retry, a second tab
or a double tap returns the order already booked instead of charging the books twice.

A queued sale is booked like a paid till order (stock out, sale journal, the
cashier's shift) at today's menu prices. What the cashier charged is kept beside it,
so a price that changed while offline shows as a difference instead of being hidden.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit as audit_svc
from app import models as m
from app import restaurant as restaurant_svc
from app.honesty import money_json

# A sale older than this is refused: the device was offline too long to trust its clock and drawer.
OFFLINE_MAX_AGE = timedelta(hours=72)
# A sale stamped later than now (device clock ahead) is refused past this slack.
CLOCK_SLACK = timedelta(minutes=10)
# Card and mobile money run on their own terminal and still work without the ERP.
# A wallet / house balance needs a live check, so it is not taken offline.
OFFLINE_METHODS = frozenset({"cash", "card", "mobile_money"})
MAX_SALES_PER_SYNC = 100


def _now() -> datetime:
    return datetime.utcnow()


def _naive(value: datetime) -> datetime:
    return value.replace(tzinfo=None) if value.tzinfo is not None else value


async def _booked(db: AsyncSession, tenant_id: str, ref: str) -> m.RestaurantOrder | None:
    return (
        await db.execute(
            select(m.RestaurantOrder).where(
                m.RestaurantOrder.tenant_id == tenant_id,
                m.RestaurantOrder.offline_ref == ref,
            )
        )
    ).scalar_one_or_none()


def _result(ref: str, status: str, *, order: m.RestaurantOrder | None = None, **extra) -> dict:
    body = {"offline_ref": ref, "status": status}
    if order is not None:
        body.update(
            {
                "order_id": order.id,
                "order_number": order.order_number,
                "booked_total": money_json(order.total_amount),
            }
        )
    body.update(extra)
    return body


def _error_text(exc: HTTPException) -> str:
    detail = exc.detail
    if isinstance(detail, dict):
        return str(detail.get("message") or detail.get("code") or "Refused")
    return str(detail)


async def _book_one(
    db: AsyncSession, tenant_id: str, sale, *, user_id: str | None, device_id: str | None
) -> dict:
    ref = sale.offline_ref
    existing = await _booked(db, tenant_id, ref)
    if existing is not None:
        return _result(ref, "already_booked", order=existing)

    rung_at = _naive(sale.created_at)
    now = _now()
    if rung_at > now + CLOCK_SLACK:
        return _result(ref, "refused", reason="The sale is dated in the future. Check the till's clock.")
    if rung_at < now - OFFLINE_MAX_AGE:
        return _result(
            ref,
            "refused",
            reason="The sale is more than 72 hours old. A manager must enter it by hand.",
        )
    if sale.payment_method not in OFFLINE_METHODS:
        return _result(ref, "refused", reason="That payment needs a live connection and cannot be taken offline.")

    try:
        async with db.begin_nested():
            order = await restaurant_svc.create_order(db, tenant_id, sale, user_id=user_id)
            order.offline_ref = ref
            order.created_at = rung_at
            await db.flush()
            order = await restaurant_svc.complete_order(
                db, tenant_id, order.id, user_id=user_id, device_id=device_id
            )
            shift_id = await _shift_for_sale(db, tenant_id, sale.shift_id, user_id)
            if shift_id:
                order.till_shift_id = shift_id
            order.completed_at = rung_at
            await db.flush()
    except HTTPException as exc:
        return _result(ref, "refused", reason=_error_text(exc))

    charged = Decimal(str(sale.charged_total)) if sale.charged_total is not None else None
    booked = Decimal(str(order.total_amount or 0))
    difference = money_json(booked - charged) if charged is not None else 0.0
    await audit_svc.record_event(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        module="restaurant",
        action="restaurant_offline_sale_booked",
        entity="restaurant_order",
        entity_id=order.id,
        details={
            "offline_ref": ref,
            "rung_at": rung_at.isoformat(),
            "device_id": device_id,
            "charged_total": money_json(charged) if charged is not None else None,
            "booked_total": money_json(booked),
            "difference": difference,
            "shift_id": order.till_shift_id,
        },
    )
    return _result(
        ref,
        "booked",
        order=order,
        charged_total=money_json(charged) if charged is not None else None,
        difference=difference,
        no_shift=order.till_shift_id is None,
    )


async def _shift_for_sale(
    db: AsyncSession, tenant_id: str, shift_id: str | None, user_id: str | None
) -> str | None:
    """The open shift the cash went into. Never a closed drawer: its count is final."""
    if shift_id:
        shift = await db.get(m.RestaurantTillShift, shift_id)
        if shift is not None and shift.tenant_id == tenant_id and shift.status == "open":
            return shift.id
    from app import restaurant_till as till_svc

    shift = await till_svc.open_shift_for_user(db, tenant_id, user_id)
    return shift.id if shift is not None else None


async def sync_sales(
    db: AsyncSession, tenant_id: str, sales: list, *, user_id: str | None, device_id: str | None
) -> dict:
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
    """What the till needs to total a bill with no connection: each dish's added tax
    rate, the service charge and the tax on it. Mirrors restaurant._bill_amounts;
    any rounding gap shows as a difference when the sale syncs."""
    from app import packages as packages_svc
    from app import tax as tax_svc

    tenant = await db.get(m.Tenant, tenant_id)
    if tenant is None or packages_svc.canonicalize_industry(getattr(tenant, "industry", None)) != "restaurant":
        return {"service_percent": 0.0, "service_tax_percent": 0.0, "items": {}}
    items: dict[str, dict] = {}
    products = (
        await db.execute(
            select(m.Product).where(m.Product.tenant_id == tenant_id, m.Product.is_active.is_(True))
        )
    ).scalars()
    for product in products:
        spec = await tax_svc.resolve_product_tax(db, tenant_id, product)
        added = 0.0
        if (spec.pricing_mode or "exclusive") == "exclusive" and not spec.is_reverse_charge:
            _net, tax, _gross = spec.compute_amounts(100.0)
            added = money_json(tax)
        items[product.id] = {"price": money_json(product.selling_price or 0), "added_tax_percent": added}
    service = await restaurant_svc.service_percent(db, tenant_id)
    service_tax = 0.0
    if service > 0:
        default = await tax_svc.get_default_tax_rate(db, tenant_id)
        if (
            default is not None
            and default.is_active
            and (default.pricing_mode or "exclusive") == "exclusive"
            and not default.is_reverse_charge
        ):
            service_tax = money_json(default.rate or 0)
    return {"service_percent": money_json(service), "service_tax_percent": service_tax, "items": items}
