"""Deterministic AI sales analysis (Phase 4 / BR-21.5).

Sales trend forecasting, RFM customer segmentation, product affinity,
and peak hour/day patterns — no external ML required.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta
from itertools import combinations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.reports import apply_company_filter

POSTED_INVOICE_STATUSES = frozenset({"posted", "sent", "partial", "paid", "overdue"})
WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def _parse_bound(value: datetime | str | None, *, end: bool = False) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            dt = datetime.strptime(text[:19], fmt)
            if end and fmt == "%Y-%m-%d":
                return dt.replace(hour=23, minute=59, second=59)
            return dt
        except ValueError:
            continue
    raise ValueError(f"Invalid date: {value}")


def _rfm_segment(r_score: int, f_score: int, m_score: int) -> str:
    total = r_score + f_score + m_score
    if r_score >= 4 and f_score >= 4 and m_score >= 4:
        return "champion"
    if r_score >= 4 and f_score >= 3:
        return "loyal"
    if r_score >= 4 and f_score <= 2:
        return "new"
    if r_score <= 2 and (f_score >= 3 or m_score >= 3):
        return "at_risk"
    if r_score <= 2 and f_score <= 2:
        return "hibernating"
    if total >= 9:
        return "potential_loyalist"
    return "needs_attention"


def _score_by_rank(values: list[float], *, higher_better: bool) -> dict[float, int]:
    """Map raw value → 1–5 score (5 best). Ties share the same score."""
    if not values:
        return {}
    unique = sorted(set(values), reverse=higher_better)
    n = len(unique)
    out: dict[float, int] = {}
    for i, v in enumerate(unique):
        # top quintile-ish
        if n == 1:
            out[v] = 3
        else:
            out[v] = max(1, min(5, 5 - int(i * 5 / n)))
    return out


async def analyze_sales(
    db: AsyncSession,
    tenant_id: str,
    *,
    from_date: datetime | str | None = None,
    to_date: datetime | str | None = None,
    lookback_days: int = 90,
    company_id: str | None = None,
) -> dict:
    now = datetime.utcnow()
    lookback_days = max(14, min(int(lookback_days), 365))
    try:
        start = _parse_bound(from_date) or (now - timedelta(days=lookback_days))
        end = _parse_bound(to_date, end=True) or now
    except ValueError as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if end < start:
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail="to_date must be on or after from_date")

    inv_stmt = select(m.SalesInvoice).where(
        m.SalesInvoice.tenant_id == tenant_id,
        m.SalesInvoice.status.in_(list(POSTED_INVOICE_STATUSES)),
        m.SalesInvoice.created_at >= start,
        m.SalesInvoice.created_at <= end,
    )
    inv_stmt = apply_company_filter(inv_stmt, m.SalesInvoice.company_id, company_id)
    invoices = (await db.execute(inv_stmt)).scalars().all()

    inv_ids = [i.id for i in invoices]
    items: list[m.SalesInvoiceItem] = []
    if inv_ids:
        item_stmt = select(m.SalesInvoiceItem).where(
            m.SalesInvoiceItem.tenant_id == tenant_id,
            m.SalesInvoiceItem.sales_invoice_id.in_(inv_ids),
        )
        item_stmt = apply_company_filter(
            item_stmt, m.SalesInvoiceItem.company_id, company_id
        )
        items = (await db.execute(item_stmt)).scalars().all()

    product_ids = {it.product_id for it in items}
    products = {}
    if product_ids:
        prod_stmt = select(m.Product).where(
            m.Product.tenant_id == tenant_id,
            m.Product.id.in_(list(product_ids)),
        )
        prod_stmt = apply_company_filter(prod_stmt, m.Product.company_id, company_id)
        products = {
            p.id: p for p in (await db.execute(prod_stmt)).scalars().all()
        }

    customer_ids = {i.customer_id for i in invoices if i.customer_id}
    parties = {}
    if customer_ids:
        party_stmt = select(m.Party).where(
            m.Party.tenant_id == tenant_id,
            m.Party.id.in_(list(customer_ids)),
        )
        party_stmt = apply_company_filter(party_stmt, m.Party.company_id, company_id)
        parties = {
            p.id: p for p in (await db.execute(party_stmt)).scalars().all()
        }

    # --- Daily trend + forecast ---
    daily: dict[str, float] = defaultdict(float)
    hour_counts: Counter = Counter()
    weekday_counts: Counter = Counter()
    weekday_revenue: dict[int, float] = defaultdict(float)
    hour_revenue: dict[int, float] = defaultdict(float)

    for inv in invoices:
        when = inv.posted_at or inv.created_at or now
        amt = float(inv.total_amount or 0)
        daily[when.date().isoformat()] += amt
        hour_counts[when.hour] += 1
        weekday_counts[when.weekday()] += 1
        hour_revenue[when.hour] += amt
        weekday_revenue[when.weekday()] += amt

    # Fill missing days with 0 for slope stability
    day_list: list[tuple[str, float]] = []
    cursor = start.date()
    end_d = end.date()
    while cursor <= end_d:
        key = cursor.isoformat()
        day_list.append((key, round(daily.get(key, 0.0), 2)))
        cursor += timedelta(days=1)

    n = len(day_list)
    total_sales = round(sum(v for _, v in day_list), 2)
    avg_daily = round(total_sales / n, 2) if n else 0.0

    # Simple linear trend on daily totals
    slope = 0.0
    if n >= 2:
        xs = list(range(n))
        ys = [v for _, v in day_list]
        x_mean = sum(xs) / n
        y_mean = sum(ys) / n
        num = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
        den = sum((x - x_mean) ** 2 for x in xs) or 1.0
        slope = num / den

    last_y = day_list[-1][1] if day_list else 0.0
    trend_direction = "up" if slope > 0.5 else "down" if slope < -0.5 else "flat"
    forecast = {}
    for horizon in (7, 14, 30):
        # Project from last day with linear drift, floor at 0
        projected = []
        for i in range(1, horizon + 1):
            projected.append(max(0.0, last_y + slope * i))
        forecast[str(horizon)] = round(sum(projected), 2)

    # --- RFM ---
    by_customer: dict[str, dict] = {}
    for inv in invoices:
        cid = inv.customer_id
        if not cid:
            continue
        when = inv.posted_at or inv.created_at or now
        row = by_customer.setdefault(
            cid, {"count": 0, "monetary": 0.0, "last": when, "first": when}
        )
        row["count"] += 1
        row["monetary"] += float(inv.total_amount or 0)
        if when > row["last"]:
            row["last"] = when
        if when < row["first"]:
            row["first"] = when

    recency_vals = [(now - row["last"]).days for row in by_customer.values()]
    freq_vals = [float(row["count"]) for row in by_customer.values()]
    mon_vals = [float(row["monetary"]) for row in by_customer.values()]
    r_map = _score_by_rank(recency_vals, higher_better=False)
    f_map = _score_by_rank(freq_vals, higher_better=True)
    m_map = _score_by_rank(mon_vals, higher_better=True)

    rfm: list[dict] = []
    segment_counts: Counter = Counter()
    for cid, row in by_customer.items():
        recency_days = (now - row["last"]).days
        r_score = r_map.get(recency_days, 3)
        f_score = f_map.get(float(row["count"]), 3)
        m_score = m_map.get(float(row["monetary"]), 3)
        segment = _rfm_segment(r_score, f_score, m_score)
        segment_counts[segment] += 1
        party = parties.get(cid)
        rfm.append(
            {
                "customer_id": cid,
                "customer_name": party.name if party else cid,
                "recency_days": recency_days,
                "frequency": row["count"],
                "monetary": round(row["monetary"], 2),
                "r_score": r_score,
                "f_score": f_score,
                "m_score": m_score,
                "segment": segment,
                "last_purchase_at": row["last"],
            }
        )
    rfm.sort(key=lambda x: (-(x["r_score"] + x["f_score"] + x["m_score"]), -x["monetary"]))

    # --- Product affinity (market basket) ---
    items_by_inv: dict[str, set[str]] = defaultdict(set)
    for it in items:
        if it.product_id:
            items_by_inv[it.sales_invoice_id].add(it.product_id)

    pair_counts: Counter = Counter()
    baskets = 0
    for pids in items_by_inv.values():
        if len(pids) < 2:
            continue
        baskets += 1
        for a, b in combinations(sorted(pids), 2):
            pair_counts[(a, b)] += 1

    affinity = []
    for (a, b), cnt in pair_counts.most_common(20):
        pa, pb = products.get(a), products.get(b)
        support = round(cnt / baskets, 3) if baskets else 0.0
        affinity.append(
            {
                "product_a_id": a,
                "product_a_name": pa.name if pa else a,
                "product_a_sku": pa.sku if pa else None,
                "product_b_id": b,
                "product_b_name": pb.name if pb else b,
                "product_b_sku": pb.sku if pb else None,
                "co_occurrence_count": cnt,
                "support": support,
            }
        )

    # --- Peak hour / day ---
    peak_hour = hour_counts.most_common(1)[0][0] if hour_counts else None
    peak_weekday = weekday_counts.most_common(1)[0][0] if weekday_counts else None
    by_hour = [
        {
            "hour": h,
            "invoice_count": hour_counts.get(h, 0),
            "revenue": round(hour_revenue.get(h, 0.0), 2),
        }
        for h in range(24)
        if hour_counts.get(h, 0) > 0
    ]
    by_weekday = [
        {
            "weekday": d,
            "label": WEEKDAYS[d],
            "invoice_count": weekday_counts.get(d, 0),
            "revenue": round(weekday_revenue.get(d, 0.0), 2),
        }
        for d in range(7)
        if weekday_counts.get(d, 0) > 0
    ]
    by_hour.sort(key=lambda x: -x["invoice_count"])
    by_weekday.sort(key=lambda x: -x["invoice_count"])

    return {
        "generated_at": now,
        "from_date": start,
        "to_date": end,
        "method": "rules_v1",
        "summary": {
            "invoice_count": len(invoices),
            "total_sales": total_sales,
            "avg_daily_sales": avg_daily,
            "customer_count": len(by_customer),
            "trend_direction": trend_direction,
            "daily_slope": round(slope, 4),
        },
        "trend": {
            "daily": [{"date": d, "total": v} for d, v in day_list if v > 0 or n <= 60],
            "forecast_totals": forecast,
            "direction": trend_direction,
            "daily_slope": round(slope, 4),
            "note": "Linear projection from daily posted invoice totals (not Prophet).",
        },
        "rfm": {
            "customers": rfm[:100],
            "segment_counts": dict(segment_counts),
            "count": len(rfm),
        },
        "product_affinity": {
            "pairs": affinity,
            "baskets_with_2plus_lines": baskets,
        },
        "peaks": {
            "peak_hour": peak_hour,
            "peak_weekday": peak_weekday,
            "peak_weekday_label": WEEKDAYS[peak_weekday] if peak_weekday is not None else None,
            "by_hour": by_hour[:12],
            "by_weekday": by_weekday,
        },
    }
