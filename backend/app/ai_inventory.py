"""Rule-based AI inventory predictions (BR-21.3 / BR-21.4).

Uses tenant sales velocity (invoices + POS) — no LLM / Prophet.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import ai as ai_svc
from app import models as m
from app import reports as reports_svc
from app.config import settings

POSTED_STATUSES = ("posted", "sent", "partial", "paid", "overdue")


def lookback_days() -> int:
    return max(7, int(getattr(settings, "AI_INVENTORY_LOOKBACK_DAYS", 28) or 28))


def default_lead_days() -> int:
    return max(0, int(getattr(settings, "AI_INVENTORY_DEFAULT_LEAD_DAYS", 7) or 7))


def cover_days() -> int:
    return max(1, int(getattr(settings, "AI_INVENTORY_COVER_DAYS", 14) or 14))


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def confidence_score(*, sold_qty: float, lookback: int, sale_days_present: int) -> float:
    """Heuristic 0–1: more sale activity + coverage of lookback → higher confidence."""
    if sold_qty <= 0:
        return 0.25  # low-confidence "no velocity" observation
    coverage = sale_days_present / max(1, lookback)
    volume = _clamp(math.log10(sold_qty + 1) / 3.0)  # ~1000 units → 1.0
    return round(_clamp(0.35 + 0.45 * coverage + 0.2 * volume), 3)


def seasonality_hint(*, recent_velocity: float, prior_velocity: float) -> dict[str, Any]:
    """Simple two-window ratio (not full seasonal model)."""
    if prior_velocity <= 1e-9 and recent_velocity <= 1e-9:
        return {"detected": False, "ratio": None, "label": "insufficient_history"}
    if prior_velocity <= 1e-9:
        return {"detected": True, "ratio": None, "label": "emerging_demand"}
    ratio = recent_velocity / prior_velocity
    if ratio >= 1.35:
        label = "rising"
    elif ratio <= 0.65:
        label = "falling"
    else:
        label = "stable"
    return {"detected": label != "stable", "ratio": round(ratio, 3), "label": label}


async def _sales_qty_by_product(
    db: AsyncSession,
    tenant_id: str,
    *,
    from_date: datetime,
    to_date: datetime | None = None,
) -> dict[str, float]:
    report = await reports_svc.sales_by_product(
        db, tenant_id, from_date=from_date, to_date=to_date
    )
    return {
        str(p["product_id"]): float(p.get("quantity") or 0)
        for p in (report.get("products") or [])
    }


async def _sale_day_counts(
    db: AsyncSession,
    tenant_id: str,
    *,
    from_date: datetime,
) -> dict[str, int]:
    """Distinct calendar days with posted invoice lines per product (approx activity)."""
    rows = (
        await db.execute(
            select(m.SalesInvoiceItem.product_id, m.SalesInvoice.posted_at)
            .join(m.SalesInvoice, m.SalesInvoice.id == m.SalesInvoiceItem.sales_invoice_id)
            .where(
                m.SalesInvoiceItem.tenant_id == tenant_id,
                m.SalesInvoice.tenant_id == tenant_id,
                m.SalesInvoice.status.in_(list(POSTED_STATUSES)),
                m.SalesInvoice.posted_at.is_not(None),
                m.SalesInvoice.posted_at >= from_date,
            )
        )
    ).all()
    days: dict[str, set[str]] = {}
    for pid, posted_at in rows:
        if not pid or not posted_at:
            continue
        days.setdefault(str(pid), set()).add(posted_at.date().isoformat())
    # POS days
    for tx in (
        await db.execute(
            select(m.Transaction).where(
                m.Transaction.tenant_id == tenant_id,
                m.Transaction.tx_type == "pos_sale",
                m.Transaction.created_at >= from_date,
            )
        )
    ).scalars().all():
        day = tx.created_at.date().isoformat() if tx.created_at else None
        if not day:
            continue
        for line in (tx.payload or {}).get("items") or []:
            pid = line.get("product_id")
            if pid:
                days.setdefault(str(pid), set()).add(day)
    return {k: len(v) for k, v in days.items()}


def _recommended_qty(
    *,
    stock: float,
    velocity: float,
    lead: float,
    cover: float,
    reorder_level: float,
    reorder_qty: float,
) -> float:
    target = velocity * (lead + cover)
    gap = max(0.0, target - stock)
    # Prefer configured reorder_qty when product is already at/below reorder
    if stock <= reorder_level and reorder_qty > 0:
        return round(max(reorder_qty, gap), 3)
    if gap <= 0:
        return 0.0
    return round(max(1.0, gap) if velocity > 0 else 0.0, 3)


async def build_product_forecasts(
    db: AsyncSession,
    *,
    tenant_id: str,
) -> list[dict[str, Any]]:
    now = datetime.utcnow()
    lb = lookback_days()
    half = max(7, lb // 2)
    from_all = now - timedelta(days=lb)
    from_recent = now - timedelta(days=half)
    from_prior = now - timedelta(days=lb)
    to_prior = from_recent

    sold_all = await _sales_qty_by_product(db, tenant_id, from_date=from_all)
    sold_recent = await _sales_qty_by_product(db, tenant_id, from_date=from_recent)
    sold_prior = await _sales_qty_by_product(
        db, tenant_id, from_date=from_prior, to_date=to_prior
    )
    day_counts = await _sale_day_counts(db, tenant_id, from_date=from_all)

    products = (
        await db.execute(
            select(m.Product).where(
                m.Product.tenant_id == tenant_id,
                m.Product.is_active == True,  # noqa: E712
            )
        )
    ).scalars().all()

    # Warehouse reorder_qty map (max across warehouses as product hint)
    wh_rows = (
        await db.execute(
            select(m.WarehouseStock.product_id, m.WarehouseStock.reorder_qty).where(
                m.WarehouseStock.tenant_id == tenant_id
            )
        )
    ).all()
    reorder_qty_map: dict[str, float] = {}
    for pid, rq in wh_rows:
        reorder_qty_map[str(pid)] = max(float(rq or 0), reorder_qty_map.get(str(pid), 0.0))

    lead = float(default_lead_days())
    cover = float(cover_days())
    out: list[dict[str, Any]] = []
    for p in products:
        pid = p.id
        stock = float(p.stock_qty or 0)
        sold = float(sold_all.get(pid, 0))
        velocity = sold / float(lb) if lb else 0.0
        recent_v = float(sold_recent.get(pid, 0)) / float(half)
        prior_v = float(sold_prior.get(pid, 0)) / float(max(1, lb - half))
        days_to = (stock / velocity) if velocity > 1e-9 else None
        rq = float(reorder_qty_map.get(pid, 0))
        rec = _recommended_qty(
            stock=stock,
            velocity=velocity,
            lead=lead,
            cover=cover,
            reorder_level=float(p.reorder_level or 0),
            reorder_qty=rq,
        )
        conf = confidence_score(
            sold_qty=sold, lookback=lb, sale_days_present=int(day_counts.get(pid, 0))
        )
        season = seasonality_hint(recent_velocity=recent_v, prior_velocity=prior_v)
        out.append(
            {
                "product_id": pid,
                "sku": p.sku,
                "name": p.name,
                "stock_qty": stock,
                "reorder_level": float(p.reorder_level or 0),
                "reorder_qty": rq,
                "lookback_days": lb,
                "sold_qty_lookback": round(sold, 3),
                "velocity_per_day": round(velocity, 6),
                "days_to_stockout": round(days_to, 2) if days_to is not None else None,
                "forecast_demand_7": round(velocity * 7, 3),
                "forecast_demand_30": round(velocity * 30, 3),
                "forecast_demand_90": round(velocity * 90, 3),
                "recommended_order_qty": rec,
                "lead_time_days": lead,
                "cover_days": cover,
                "confidence": conf,
                "seasonality": season,
                "dead_stock": False,  # filled below
            }
        )

    sold_90 = await _sales_qty_by_product(
        db, tenant_id, from_date=now - timedelta(days=90)
    )
    for row in out:
        pid = row["product_id"]
        row["dead_stock"] = (
            row["velocity_per_day"] <= 1e-9
            and row["stock_qty"] > 0
            and float(sold_90.get(pid, 0)) <= 0
        )
    return out


async def inventory_predictions(
    db: AsyncSession,
    *,
    tenant_id: str,
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    rows = await build_product_forecasts(db, tenant_id=tenant_id)
    dead = [r for r in rows if r["dead_stock"]]
    rising = [r for r in rows if (r.get("seasonality") or {}).get("label") == "rising"]
    await ai_svc.record_query(
        db,
        tenant_id=tenant_id,
        user_id=actor_user_id,
        endpoint="inventory_predictions",
        status="ok",
        details={"products": len(rows), "dead_stock": len(dead), "method": "velocity_rules"},
    )
    await db.commit()
    return {
        "method": "rule_based_velocity",
        "lookback_days": lookback_days(),
        "lead_time_days": default_lead_days(),
        "cover_days": cover_days(),
        "products": rows,
        "dead_stock": dead,
        "seasonality_rising": rising[:50],
        "summary": {
            "product_count": len(rows),
            "dead_stock_count": len(dead),
            "rising_count": len(rising),
        },
    }


async def low_stock_prediction(
    db: AsyncSession,
    *,
    tenant_id: str,
    days_ahead: int = 14,
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    days_ahead = max(1, min(int(days_ahead or 14), 90))
    rows = await build_product_forecasts(db, tenant_id=tenant_id)
    at_risk: list[dict[str, Any]] = []
    for r in rows:
        dts = r.get("days_to_stockout")
        already_low = float(r["stock_qty"]) <= float(r["reorder_level"] or 0)
        predictive = dts is not None and dts <= days_ahead and r["velocity_per_day"] > 0
        if not (already_low or predictive):
            continue
        item = dict(r)
        item["at_risk"] = True
        item["risk_reason"] = (
            "below_reorder"
            if already_low and not predictive
            else ("predicted_stockout" if predictive and not already_low else "both")
        )
        item["suggested_order_qty"] = r["recommended_order_qty"]
        at_risk.append(item)

    at_risk.sort(
        key=lambda x: (
            x["days_to_stockout"] if x["days_to_stockout"] is not None else 9999,
            -x["confidence"],
        )
    )
    await ai_svc.record_query(
        db,
        tenant_id=tenant_id,
        user_id=actor_user_id,
        endpoint="low_stock_prediction",
        status="ok",
        details={
            "days_ahead": days_ahead,
            "at_risk": len(at_risk),
            "method": "velocity_rules",
        },
    )
    await db.commit()
    return {
        "method": "rule_based_velocity",
        "days_ahead": days_ahead,
        "lookback_days": lookback_days(),
        "lead_time_days": default_lead_days(),
        "cover_days": cover_days(),
        "at_risk": at_risk,
        "count": len(at_risk),
    }
