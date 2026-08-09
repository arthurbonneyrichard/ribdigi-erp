"""Deterministic AI inventory predictions (sales velocity / stockout risk).

Phase 4 / BR-21.4 — no external LLM required; uses posted sales invoice history.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m

POSTED_INVOICE_STATUSES = frozenset({"posted", "sent", "partial", "paid", "overdue"})
DEFAULT_LOOKBACK_DAYS = 30
DEFAULT_HORIZON_DAYS = 14
DEFAULT_LEAD_TIME_DAYS = 7
DEFAULT_SAFETY_DAYS = 7


def _confidence(*, lookback_days: int, days_with_sales: int, units_sold: float) -> float:
    """0–1 score from sample coverage and volume."""
    if units_sold <= 0:
        return 0.0
    coverage = min(1.0, days_with_sales / max(7, min(lookback_days, 14)))
    volume = min(1.0, units_sold / 10.0)
    return round(min(1.0, 0.55 * coverage + 0.45 * volume), 3)


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
    mid = now - timedelta(days=7)
    prior_start = now - timedelta(days=14)

    products = (
        await db.execute(
            select(m.Product).where(
                m.Product.tenant_id == tenant_id,
                m.Product.is_active == True,  # noqa: E712
            )
        )
    ).scalars().all()
    by_id = {p.id: p for p in products}

    rows = (
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

    sold_total: dict[str, float] = defaultdict(float)
    sold_recent: dict[str, float] = defaultdict(float)
    sold_prior: dict[str, float] = defaultdict(float)
    days_seen: dict[str, set] = defaultdict(set)

    for item, inv in rows:
        pid = item.product_id
        if pid not in by_id:
            continue
        qty = float(item.quantity or 0)
        if qty <= 0:
            continue
        when = inv.posted_at or inv.created_at or now
        sold_total[pid] += qty
        days_seen[pid].add(when.date().isoformat())
        if when >= mid:
            sold_recent[pid] += qty
        elif when >= prior_start:
            sold_prior[pid] += qty

    predictions: list[dict] = []
    for product in products:
        stock = float(product.stock_qty or 0)
        reserved = float(getattr(product, "reserved_qty", 0) or 0)
        available = max(0.0, stock - reserved)
        units = round(sold_total.get(product.id, 0.0), 3)
        velocity = round(units / lookback_days, 4) if lookback_days else 0.0

        recent_v = sold_recent.get(product.id, 0.0) / 7.0
        prior_v = sold_prior.get(product.id, 0.0) / 7.0
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

        cover_days = lead_time_days + DEFAULT_SAFETY_DAYS
        target = adjusted_velocity * cover_days if adjusted_velocity > 0 else 0.0
        reorder_floor = float(product.reorder_level or 0)
        suggested = max(0.0, round(max(target, reorder_floor) - available, 3))
        if at_risk and suggested <= 0 and adjusted_velocity > 0:
            suggested = round(max(adjusted_velocity * lead_time_days, 1.0), 3)

        row = {
            "product_id": product.id,
            "sku": product.sku,
            "name": product.name,
            "stock_qty": stock,
            "reserved_qty": reserved,
            "available_qty": available,
            "reorder_level": reorder_floor,
            "units_sold_lookback": units,
            "lookback_days": lookback_days,
            "velocity_per_day": velocity,
            "seasonality_factor": seasonality_factor,
            "adjusted_velocity_per_day": adjusted_velocity,
            "days_to_stockout": days_to_stockout,
            "horizon_days": horizon_days,
            "lead_time_days": lead_time_days,
            "confidence": confidence,
            "status": status,
            "at_risk": at_risk,
            "suggested_order_qty": suggested,
            "within_prediction_window": bool(
                days_to_stockout is not None and 0 <= days_to_stockout <= horizon_days
            ),
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
