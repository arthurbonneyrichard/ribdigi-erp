"""FMCG demand forecast: how much will sell, when stock runs out and what to order.

Everything here is an estimate built from the company's own delivered FMCG orders. It is never
shown as sales. The method is plain on purpose, so a manager can check it by hand:

* daily demand = average of the last ``history`` days (zero days count), blended 60/40 with the
  last 28 days when there is at least 56 days of history, so a recent change shows up;
* safety stock = z x standard deviation of daily demand x square root of the lead time;
* reorder point = daily demand x lead time + safety stock;
* suggested order = daily demand x (lead time + horizon) + safety stock - stock - already on order.

A backtest compares what the method would have said 28 days ago with what really sold, so the
screen can say how far to trust it. Products with fewer than 3 selling days get no forecast.
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import date, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit as audit_svc
from app import models as m
from app.honesty import money_json

POLICY_KEY = "fmcg_forecast_policy"
DEFAULT_POLICY = {"lead_time_days": 7, "service_level": 95, "overstock_days": 120}
Z = {90: 1.28, 95: 1.65, 97: 1.88, 99: 2.33}
MIN_SELLING_DAYS = 3
RECENT = 28


async def get_policy(db: AsyncSession, tenant_id: str) -> dict:
    tenant = (await db.execute(select(m.Tenant).where(m.Tenant.id == tenant_id))).scalar_one()
    raw = (tenant.document_numbering or {}).get(POLICY_KEY) or {}
    out = dict(DEFAULT_POLICY)
    for key in out:
        try:
            out[key] = int(raw.get(key, out[key]))
        except (TypeError, ValueError):
            pass
    if out["service_level"] not in Z:
        out["service_level"] = DEFAULT_POLICY["service_level"]
    return out


async def set_policy(db: AsyncSession, tenant_id: str, *, lead_time_days: int, service_level: int, overstock_days: int, user_id) -> dict:
    if not 1 <= lead_time_days <= 120:
        raise HTTPException(status_code=422, detail="Lead time is 1 to 120 days")
    if service_level not in Z:
        raise HTTPException(status_code=422, detail=f"Service level must be one of: {', '.join(map(str, Z))}")
    if not 30 <= overstock_days <= 720:
        raise HTTPException(status_code=422, detail="Overstock threshold is 30 to 720 days of cover")
    tenant = (await db.execute(select(m.Tenant).where(m.Tenant.id == tenant_id).with_for_update())).scalar_one()
    data = dict(tenant.document_numbering or {})
    data[POLICY_KEY] = {"lead_time_days": lead_time_days, "service_level": service_level, "overstock_days": overstock_days}
    tenant.document_numbering = data
    await audit_svc.record_event(
        db, tenant_id=tenant_id, user_id=user_id, module="fmcg", action="fmcg_forecast_policy_saved",
        entity="tenant", entity_id=tenant_id, details=data[POLICY_KEY],
    )
    await db.flush()
    return await get_policy(db, tenant_id)


def _stats(series: list[float]) -> tuple[float, float]:
    n = len(series)
    mean = sum(series) / n
    var = sum((x - mean) ** 2 for x in series) / n
    return mean, math.sqrt(var)


def _daily_forecast(series: list[float]) -> float:
    avg, _ = _stats(series)
    if len(series) >= 56:
        recent = sum(series[-RECENT:]) / RECENT
        return 0.6 * recent + 0.4 * avg
    return avg


def _confidence(series: list[float]) -> str:
    selling = sum(1 for x in series if x > 0)
    if selling >= 40 and len(series) >= 60:
        return "high"
    if selling >= 15:
        return "medium"
    return "low"


async def forecast(db: AsyncSession, *, tenant_id: str, history_days: int = 90, horizon_days: int = 30) -> dict:
    if not 28 <= history_days <= 365:
        raise HTTPException(status_code=422, detail="History is 28 to 365 days")
    if not 7 <= horizon_days <= 180:
        raise HTTPException(status_code=422, detail="Horizon is 7 to 180 days")
    policy = await get_policy(db, tenant_id)
    today = date.today()
    start = today - timedelta(days=history_days)
    begin = datetime.combine(start, datetime.min.time())
    end = datetime.combine(today, datetime.min.time())  # today is still in progress, so it is left out

    rows = (
        await db.execute(
            select(
                m.FmcgOrderLine.product_id, m.FmcgOrder.delivered_at, m.FmcgOrder.route_id,
                m.FmcgOrderLine.quantity, m.FmcgOrderLine.returned_qty, m.FmcgOrderLine.scheme_id,
            )
            .join(m.FmcgOrder, m.FmcgOrder.id == m.FmcgOrderLine.order_id)
            .where(
                m.FmcgOrderLine.tenant_id == tenant_id, m.FmcgOrder.status == "delivered",
                m.FmcgOrder.delivered_at >= begin, m.FmcgOrder.delivered_at < end,
            )
        )
    ).all()
    daily: dict[str, list[float]] = defaultdict(lambda: [0.0] * history_days)
    promo: dict[str, float] = defaultdict(float)
    sold: dict[str, float] = defaultdict(float)
    by_route: dict[str | None, float] = defaultdict(float)
    for product_id, delivered_at, route_id, qty, returned, scheme_id in rows:
        net = max(float(qty or 0) - float(returned or 0), 0.0)
        idx = (delivered_at.date() - start).days
        if 0 <= idx < history_days:
            daily[product_id][idx] += net
            sold[product_id] += net
            if scheme_id:
                promo[product_id] += net
            by_route[route_id] += net

    products = (
        await db.execute(select(m.Product).where(m.Product.tenant_id == tenant_id, m.Product.is_active.is_(True)).limit(2000))
    ).scalars().all()
    on_order = dict(
        (
            await db.execute(
                select(m.PurchaseOrderItem.product_id, func.coalesce(func.sum(m.PurchaseOrderItem.quantity - m.PurchaseOrderItem.received_qty), 0))
                .join(m.PurchaseOrder, m.PurchaseOrder.id == m.PurchaseOrderItem.purchase_order_id)
                .where(m.PurchaseOrderItem.tenant_id == tenant_id, m.PurchaseOrder.status.in_(("sent", "partially_received")))
                .group_by(m.PurchaseOrderItem.product_id)
            )
        ).all()
    )
    categories = {c.id: c.name for c in (await db.execute(select(m.ProductCategory).where(m.ProductCategory.tenant_id == tenant_id))).scalars().all()}
    routes = {r.id: r.name for r in (await db.execute(select(m.FmcgRoute).where(m.FmcgRoute.tenant_id == tenant_id))).scalars().all()}

    lead, z = policy["lead_time_days"], Z[policy["service_level"]]
    items, by_category = [], defaultdict(float)
    err_abs = err_actual = 0.0
    counts = {"stockout_risk": 0, "overstock": 0, "dead": 0, "no_forecast": 0}
    for p in products:
        series = daily.get(p.id)
        stock = float(p.stock_qty or 0)
        if series is None:
            if stock > 0:
                counts["dead"] += 1
                items.append({"product_id": p.id, "product": p.name, "stock": money_json(stock), "status": "dead",
                              "note": f"No sales in the last {history_days} days"})
            continue
        selling = sum(1 for x in series if x > 0)
        if selling < MIN_SELLING_DAYS:
            counts["no_forecast"] += 1
            items.append({"product_id": p.id, "product": p.name, "stock": money_json(stock), "status": "no_forecast",
                          "selling_days": selling, "note": "Not enough sales history to forecast"})
            continue
        avg, sd = _stats(series)
        per_day = _daily_forecast(series)
        safety = z * sd * math.sqrt(lead)
        reorder_point = per_day * lead + safety
        ordered = float(on_order.get(p.id, 0) or 0)
        need = per_day * (lead + horizon_days) + safety - stock - ordered
        cover = stock / per_day if per_day > 0 else None
        if stock <= reorder_point and per_day > 0:
            status = "stockout_risk"
        elif cover is not None and cover > policy["overstock_days"]:
            status = "overstock"
        else:
            status = "ok"
        if status in counts:
            counts[status] += 1
        if p.category_id:
            by_category[categories.get(p.category_id, "Other")] += per_day * horizon_days
        else:
            by_category["No category"] += per_day * horizon_days
        if history_days >= 56:
            train, actual = series[:-RECENT], sum(series[-RECENT:])
            predicted = (sum(train) / len(train)) * RECENT
            err_abs += abs(predicted - actual)
            err_actual += actual
        items.append(
            {
                "product_id": p.id, "product": p.name, "stock": money_json(stock), "on_order": money_json(ordered),
                "sold_in_history": money_json(round(sold[p.id], 3)), "selling_days": selling,
                "daily_forecast": round(per_day, 3), "trend_pct": round(100 * (sum(series[-RECENT:]) / RECENT - avg) / avg, 1) if avg > 0 else None,
                "forecast_horizon_qty": round(per_day * horizon_days, 1), "days_of_cover": round(cover, 1) if cover is not None else None,
                "stockout_date": (today + timedelta(days=int(cover))).isoformat() if cover is not None and cover < horizon_days + lead else None,
                "safety_stock": round(safety, 1), "reorder_point": round(reorder_point, 1),
                "suggested_order": max(0, math.ceil(need)) if status != "overstock" else 0,
                "promo_share_pct": round(100 * promo[p.id] / sold[p.id], 1) if sold[p.id] > 0 else 0.0,
                "confidence": _confidence(series), "status": status,
            }
        )
    order = {"stockout_risk": 0, "ok": 1, "overstock": 2, "dead": 3, "no_forecast": 4}
    items.sort(key=lambda i: (order[i["status"]], i.get("days_of_cover") if i.get("days_of_cover") is not None else 1e9))
    total_hist = sum(by_route.values()) or 0
    return {
        "meta": {
            "kind": "estimate", "history_from": start.isoformat(), "history_to": (today - timedelta(days=1)).isoformat(),
            "history_days": history_days, "horizon_days": horizon_days, "lead_time_days": lead,
            "service_level": policy["service_level"], "generated_at": datetime.utcnow().isoformat(timespec="seconds"),
            "note": "Estimates from delivered FMCG orders. They are not sales and can be wrong, especially on new products and promotions.",
        },
        "accuracy": {
            "method": "Backtest: last 28 days predicted from the days before them",
            "error_pct": round(100 * err_abs / err_actual, 1) if err_actual > 0 else None,
        },
        "counts": counts,
        "products": items,
        "by_category": [{"category": k, "forecast_qty": round(v, 1)} for k, v in sorted(by_category.items(), key=lambda t: -t[1])],
        "by_route": [
            {"route": routes.get(k, "No route"), "history_qty": round(v, 1),
             "forecast_qty": round(v / history_days * horizon_days, 1), "share_pct": round(100 * v / total_hist, 1) if total_hist else 0.0}
            for k, v in sorted(by_route.items(), key=lambda t: -t[1])
        ],
    }
