"""Deterministic AI inventory intelligence (sales velocity).

Phase 4:
- BR-21.4 low-stock / stockout prediction
- BR-21.3 demand forecast (7/30/90d), optimal reorder, seasonality, dead stock

No external LLM or Prophet required for the commercial MVP slice.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m

POSTED_INVOICE_STATUSES = frozenset({"posted", "sent", "partial", "paid", "overdue"})
DEFAULT_LOOKBACK_DAYS = 30
DEFAULT_HORIZON_DAYS = 14
DEFAULT_LEAD_TIME_DAYS = 7
DEFAULT_SAFETY_DAYS = 7
DEFAULT_DEAD_STOCK_DAYS = 90
FORECAST_HORIZONS = (7, 30, 90)


def _confidence(*, lookback_days: int, days_with_sales: int, units_sold: float) -> float:
    """0–1 score from sample coverage and volume."""
    if units_sold <= 0:
        return 0.0
    coverage = min(1.0, days_with_sales / max(7, min(lookback_days, 14)))
    volume = min(1.0, units_sold / 10.0)
    return round(min(1.0, 0.55 * coverage + 0.45 * volume), 3)


def _seasonality_label(factor: float, *, has_signal: bool) -> str:
    if not has_signal:
        return "unknown"
    if factor >= 1.2:
        return "increasing"
    if factor <= 0.8:
        return "decreasing"
    return "stable"


async def _load_active_products(db: AsyncSession, tenant_id: str) -> list[m.Product]:
    return (
        await db.execute(
            select(m.Product).where(
                m.Product.tenant_id == tenant_id,
                m.Product.is_active == True,  # noqa: E712
            )
        )
    ).scalars().all()


async def _sales_rows_since(
    db: AsyncSession,
    tenant_id: str,
    *,
    window_start: datetime,
):
    return (
        await db.execute(
            select(m.SalesInvoiceItem, m.SalesInvoice)
            .join(m.SalesInvoice, m.SalesInvoice.id == m.SalesInvoiceItem.sales_invoice_id)
            .where(
                m.SalesInvoiceItem.tenant_id == tenant_id,
                m.SalesInvoice.tenant_id == tenant_id,
                m.SalesInvoice.status.in_(list(POSTED_INVOICE_STATUSES)),
                m.SalesInvoice.created_at >= window_start,
            )
        )
    ).all()


def _aggregate_sales(
    rows,
    *,
    product_ids: set[str],
    now: datetime,
    lookback_days: int,  # noqa: ARG001 — reserved for callers / future window clamps
) -> tuple[dict[str, float], dict[str, float], dict[str, float], dict[str, set], dict[str, datetime]]:
    mid = now - timedelta(days=7)
    prior_start = now - timedelta(days=14)
    sold_total: dict[str, float] = defaultdict(float)
    sold_recent: dict[str, float] = defaultdict(float)
    sold_prior: dict[str, float] = defaultdict(float)
    days_seen: dict[str, set] = defaultdict(set)
    last_sale: dict[str, datetime] = {}

    for item, inv in rows:
        pid = item.product_id
        if pid not in product_ids:
            continue
        qty = float(item.quantity or 0)
        if qty <= 0:
            continue
        when = inv.posted_at or inv.created_at or now
        sold_total[pid] += qty
        days_seen[pid].add(when.date().isoformat())
        prev = last_sale.get(pid)
        if prev is None or when > prev:
            last_sale[pid] = when
        # Seasonality windows always use last 14 days, independent of lookback clamp
        if when >= mid:
            sold_recent[pid] += qty
        elif when >= prior_start:
            sold_prior[pid] += qty
    return sold_total, sold_recent, sold_prior, days_seen, last_sale


def _velocity_fields(
    product: m.Product,
    *,
    sold_total: dict[str, float],
    sold_recent: dict[str, float],
    sold_prior: dict[str, float],
    days_seen: dict[str, set],
    lookback_days: int,
) -> dict:
    stock = float(product.stock_qty or 0)
    reserved = float(getattr(product, "reserved_qty", 0) or 0)
    available = max(0.0, stock - reserved)
    units = round(sold_total.get(product.id, 0.0), 3)
    velocity = round(units / lookback_days, 4) if lookback_days else 0.0

    recent_v = sold_recent.get(product.id, 0.0) / 7.0
    prior_v = sold_prior.get(product.id, 0.0) / 7.0
    has_signal = recent_v > 0 or prior_v > 0
    if prior_v > 0 and recent_v > 0:
        seasonality_factor = round(min(2.5, max(0.4, recent_v / prior_v)), 3)
    elif recent_v > 0 and prior_v == 0:
        seasonality_factor = 1.25
    else:
        seasonality_factor = 1.0

    adjusted_velocity = round(velocity * seasonality_factor, 4)
    days_with_sales = len(days_seen.get(product.id, set()))
    confidence = _confidence(
        lookback_days=lookback_days,
        days_with_sales=days_with_sales,
        units_sold=units,
    )
    return {
        "stock_qty": stock,
        "reserved_qty": reserved,
        "available_qty": available,
        "units_sold_lookback": units,
        "velocity_per_day": velocity,
        "seasonality_factor": seasonality_factor,
        "seasonality": _seasonality_label(seasonality_factor, has_signal=has_signal and units > 0),
        "adjusted_velocity_per_day": adjusted_velocity,
        "days_with_sales": days_with_sales,
        "confidence": confidence,
    }


def _optimal_reorder_qty(
    *,
    available: float,
    adjusted_velocity: float,
    reorder_level: float,
    lead_time_days: int,
) -> float:
    cover_days = lead_time_days + DEFAULT_SAFETY_DAYS
    target = adjusted_velocity * cover_days if adjusted_velocity > 0 else 0.0
    suggested = max(0.0, round(max(target, reorder_level) - available, 3))
    if suggested <= 0 and adjusted_velocity > 0 and available < reorder_level:
        suggested = round(max(adjusted_velocity * lead_time_days, 1.0), 3)
    return suggested


async def predict_low_stock(
    db: AsyncSession,
    tenant_id: str,
    *,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    horizon_days: int = DEFAULT_HORIZON_DAYS,
    lead_time_days: int = DEFAULT_LEAD_TIME_DAYS,
    at_risk_only: bool = False,
) -> dict:
    """Predict stockouts from average daily sales velocity + short-window seasonality."""
    lookback_days = max(7, min(int(lookback_days), 90))
    horizon_days = max(1, min(int(horizon_days), 60))
    lead_time_days = max(0, min(int(lead_time_days), 60))

    now = datetime.utcnow()
    window_start = now - timedelta(days=lookback_days)
    products = await _load_active_products(db, tenant_id)
    by_id = {p.id: p for p in products}
    rows = await _sales_rows_since(db, tenant_id, window_start=window_start)
    sold_total, sold_recent, sold_prior, days_seen, _last = _aggregate_sales(
        rows, product_ids=set(by_id), now=now, lookback_days=lookback_days
    )

    predictions: list[dict] = []
    for product in products:
        v = _velocity_fields(
            product,
            sold_total=sold_total,
            sold_recent=sold_recent,
            sold_prior=sold_prior,
            days_seen=days_seen,
            lookback_days=lookback_days,
        )
        available = v["available_qty"]
        adjusted_velocity = v["adjusted_velocity_per_day"]
        units = v["units_sold_lookback"]
        reorder_floor = float(product.reorder_level or 0)

        if adjusted_velocity <= 0:
            days_to_stockout = None
            status = "insufficient_data" if units <= 0 else "stable"
            at_risk = False
        else:
            days_to_stockout = round(available / adjusted_velocity, 1)
            at_risk = days_to_stockout <= float(horizon_days)
            if available <= 0:
                status = "stockout"
                at_risk = True
                days_to_stockout = 0.0
            elif at_risk:
                status = "at_risk"
            else:
                status = "ok"

        suggested = _optimal_reorder_qty(
            available=available,
            adjusted_velocity=adjusted_velocity,
            reorder_level=reorder_floor,
            lead_time_days=lead_time_days,
        )
        if at_risk and suggested <= 0 and adjusted_velocity > 0:
            suggested = round(max(adjusted_velocity * lead_time_days, 1.0), 3)

        row = {
            "product_id": product.id,
            "sku": product.sku,
            "name": product.name,
            "reorder_level": reorder_floor,
            "lookback_days": lookback_days,
            "days_to_stockout": days_to_stockout,
            "horizon_days": horizon_days,
            "lead_time_days": lead_time_days,
            "status": status,
            "at_risk": at_risk,
            "suggested_order_qty": suggested,
            "within_prediction_window": bool(
                days_to_stockout is not None and 0 <= days_to_stockout <= horizon_days
            ),
            **{k: v[k] for k in (
                "stock_qty",
                "reserved_qty",
                "available_qty",
                "units_sold_lookback",
                "velocity_per_day",
                "seasonality_factor",
                "adjusted_velocity_per_day",
                "confidence",
            )},
        }
        if at_risk_only and not at_risk:
            continue
        predictions.append(row)

    predictions.sort(
        key=lambda r: (
            0 if r["at_risk"] else 1,
            r["days_to_stockout"] if r["days_to_stockout"] is not None else 9999,
            -r["confidence"],
        )
    )
    at_risk_count = sum(1 for r in predictions if r["at_risk"])
    return {
        "generated_at": now,
        "lookback_days": lookback_days,
        "horizon_days": horizon_days,
        "lead_time_days": lead_time_days,
        "method": "sales_velocity_v1",
        "at_risk_count": at_risk_count,
        "predictions": predictions,
    }


async def forecast_demand(
    db: AsyncSession,
    tenant_id: str,
    *,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    lead_time_days: int = DEFAULT_LEAD_TIME_DAYS,
    product_id: str | None = None,
) -> dict:
    """BR-21.3 — demand forecast for 7/30/90 days with reorder + seasonality."""
    lookback_days = max(14, min(int(lookback_days), 180))
    lead_time_days = max(0, min(int(lead_time_days), 60))
    now = datetime.utcnow()
    # Need enough history for seasonality (14d) and velocity
    window_start = now - timedelta(days=max(lookback_days, 90))
    products = await _load_active_products(db, tenant_id)
    if product_id:
        products = [p for p in products if p.id == product_id]
    by_id = {p.id: p for p in products}
    rows = await _sales_rows_since(db, tenant_id, window_start=window_start)
    sold_total, sold_recent, sold_prior, days_seen, last_sale = _aggregate_sales(
        rows, product_ids=set(by_id), now=now, lookback_days=lookback_days
    )

    # Re-aggregate sold_total strictly for lookback window used in velocity
    lookback_start = now - timedelta(days=lookback_days)
    sold_lookback: dict[str, float] = defaultdict(float)
    days_lookback: dict[str, set] = defaultdict(set)
    for item, inv in rows:
        pid = item.product_id
        if pid not in by_id:
            continue
        when = inv.posted_at or inv.created_at or now
        if when < lookback_start:
            continue
        qty = float(item.quantity or 0)
        if qty <= 0:
            continue
        sold_lookback[pid] += qty
        days_lookback[pid].add(when.date().isoformat())

    forecasts: list[dict] = []
    for product in products:
        v = _velocity_fields(
            product,
            sold_total=sold_lookback,
            sold_recent=sold_recent,
            sold_prior=sold_prior,
            days_seen=days_lookback,
            lookback_days=lookback_days,
        )
        adj = v["adjusted_velocity_per_day"]
        reorder_floor = float(product.reorder_level or 0)
        optimal = _optimal_reorder_qty(
            available=v["available_qty"],
            adjusted_velocity=adj,
            reorder_level=reorder_floor,
            lead_time_days=lead_time_days,
        )
        horizon_map = {
            str(h): round(adj * h, 3) if adj > 0 else 0.0 for h in FORECAST_HORIZONS
        }
        last = last_sale.get(product.id)
        forecasts.append(
            {
                "product_id": product.id,
                "sku": product.sku,
                "name": product.name,
                "stock_qty": v["stock_qty"],
                "available_qty": v["available_qty"],
                "reorder_level": reorder_floor,
                "units_sold_lookback": v["units_sold_lookback"],
                "lookback_days": lookback_days,
                "velocity_per_day": v["velocity_per_day"],
                "seasonality_factor": v["seasonality_factor"],
                "seasonality": v["seasonality"],
                "adjusted_velocity_per_day": adj,
                "forecast_units": horizon_map,
                "forecast_7d": horizon_map["7"],
                "forecast_30d": horizon_map["30"],
                "forecast_90d": horizon_map["90"],
                "optimal_reorder_qty": optimal,
                "confidence": v["confidence"],
                "last_sale_at": last,
                "status": "ok" if adj > 0 else "insufficient_data",
            }
        )

    forecasts.sort(key=lambda r: (-r["forecast_30d"], -r["confidence"], r["name"]))
    return {
        "generated_at": now,
        "lookback_days": lookback_days,
        "lead_time_days": lead_time_days,
        "horizons_days": list(FORECAST_HORIZONS),
        "method": "sales_velocity_v1",
        "count": len(forecasts),
        "forecasts": forecasts,
    }


async def identify_dead_stock(
    db: AsyncSession,
    tenant_id: str,
    *,
    lookback_days: int = DEFAULT_DEAD_STOCK_DAYS,
    min_stock: float = 0.0,
) -> dict:
    """BR-21.3 — products with on-hand stock and no posted sales in the lookback window."""
    lookback_days = max(30, min(int(lookback_days), 365))
    min_stock = max(0.0, float(min_stock))
    now = datetime.utcnow()
    window_start = now - timedelta(days=lookback_days)

    products = await _load_active_products(db, tenant_id)
    by_id = {p.id: p for p in products}
    # Wider window to find last sale even beyond lookback
    history_start = now - timedelta(days=max(lookback_days, 365))
    rows = await _sales_rows_since(db, tenant_id, window_start=history_start)
    _t, _r, _p, _d, last_sale = _aggregate_sales(
        rows, product_ids=set(by_id), now=now, lookback_days=lookback_days
    )

    items: list[dict] = []
    for product in products:
        stock = float(product.stock_qty or 0)
        if stock <= min_stock:
            continue
        last = last_sale.get(product.id)
        if last is not None and last >= window_start:
            continue
        days_without = None
        if last is not None:
            days_without = max(0, (now - last).days)
        else:
            days_without = lookback_days
        cost = float(product.cost_price or 0)
        items.append(
            {
                "product_id": product.id,
                "sku": product.sku,
                "name": product.name,
                "stock_qty": stock,
                "cost_price": cost,
                "estimated_carrying_cost": round(stock * cost, 2),
                "last_sale_at": last,
                "days_without_sale": days_without,
                "lookback_days": lookback_days,
            }
        )

    items.sort(
        key=lambda r: (
            -(r["days_without_sale"] or 0),
            -r["estimated_carrying_cost"],
            r["name"],
        )
    )
    return {
        "generated_at": now,
        "lookback_days": lookback_days,
        "method": "sales_velocity_v1",
        "count": len(items),
        "items": items,
        "total_carrying_cost": round(sum(i["estimated_carrying_cost"] for i in items), 2),
    }


async def notify_predicted_stockouts(
    db: AsyncSession,
    tenant_id: str,
    *,
    horizon_days: int = DEFAULT_HORIZON_DAYS,
) -> dict:
    """Create low_stock notifications for products predicted to stock out within horizon."""
    from app.notifications import create_notification

    result = await predict_low_stock(
        db, tenant_id, horizon_days=horizon_days, at_risk_only=True
    )
    created = 0
    for pred in result["predictions"]:
        if not pred.get("within_prediction_window"):
            continue
        if pred.get("confidence", 0) < 0.25:
            continue
        days = pred.get("days_to_stockout")
        existing = (
            await db.execute(
                select(m.Notification).where(
                    m.Notification.tenant_id == tenant_id,
                    m.Notification.category == "low_stock",
                    m.Notification.entity_id == pred["product_id"],
                    m.Notification.status == "unread",
                    m.Notification.title == "Predicted Stockout",
                )
            )
        ).scalar_one_or_none()
        if existing:
            continue
        await create_notification(
            db,
            tenant_id=tenant_id,
            category="low_stock",
            title="Predicted Stockout",
            message=(
                f"{pred['name']} ({pred['sku']}) may stock out in ~{days} day(s) "
                f"(confidence {pred['confidence']:.0%}). "
                f"Suggested order qty: {pred['suggested_order_qty']}."
            ),
            entity_type="product",
            entity_id=pred["product_id"],
        )
        created += 1
    await db.flush()
    return {"at_risk_count": result["at_risk_count"], "notifications_created": created}
