"""Rule-based AI Sales Analysis (BR-21.5) — no LLM."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta
from itertools import combinations
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import ai as ai_svc
from app import models as m
from app import reports as reports_svc
from app.ai_inventory import seasonality_hint

POSTED = ("posted", "sent", "partial", "paid", "overdue")


def _parse_range(
    from_date: str | datetime | None,
    to_date: str | datetime | None,
) -> tuple[datetime, datetime]:
    now = datetime.utcnow()
    start = reports_svc.parse_date(from_date) or (now - timedelta(days=90))
    end = reports_svc.parse_date(to_date, end_of_day=True) or now
    if end < start:
        start, end = end.replace(hour=0, minute=0, second=0, microsecond=0), start
    return start, end


def _rfm_segment(r: int, f: int, m: int) -> str:
    score = r + f + m
    if r >= 4 and f >= 4 and m >= 4:
        return "champions"
    if r >= 4 and f >= 3:
        return "loyal"
    if r >= 4 and f <= 2:
        return "promising"
    if r <= 2 and f >= 3 and m >= 3:
        return "at_risk"
    if r <= 2 and f <= 2:
        return "hibernating"
    if score >= 10:
        return "potential_loyalists"
    return "needs_attention"


def _score_map(metrics: dict[str, float], *, higher_is_better: bool = True) -> dict[str, int]:
    if not metrics:
        return {}
    items = sorted(metrics.items(), key=lambda x: x[1], reverse=higher_is_better)
    n = len(items)
    out: dict[str, int] = {}
    for i, (key, _) in enumerate(items):
        # top quintile = 5
        rank = i / max(1, n - 1) if n > 1 else 0.0
        if higher_is_better:
            score = 5 - int(rank * 4.999)
        else:
            score = 1 + int(rank * 4.999)
        out[key] = max(1, min(5, score))
    return out


async def _invoice_baskets(
    db: AsyncSession, tenant_id: str, *, start: datetime, end: datetime
) -> list[dict[str, Any]]:
    rows = (
        await db.execute(
            select(m.SalesInvoice, m.SalesInvoiceItem)
            .join(m.SalesInvoiceItem, m.SalesInvoiceItem.sales_invoice_id == m.SalesInvoice.id)
            .where(
                m.SalesInvoice.tenant_id == tenant_id,
                m.SalesInvoice.status.in_(list(POSTED)),
                m.SalesInvoice.posted_at.is_not(None),
                m.SalesInvoice.posted_at >= start,
                m.SalesInvoice.posted_at <= end,
            )
        )
    ).all()
    baskets: dict[str, dict[str, Any]] = {}
    for inv, item in rows:
        b = baskets.setdefault(
            inv.id,
            {
                "id": inv.id,
                "customer_id": inv.customer_id,
                "posted_at": inv.posted_at,
                "total": float(inv.total_amount or 0),
                "product_ids": set(),
            },
        )
        if item.product_id:
            b["product_ids"].add(item.product_id)
    return list(baskets.values())


async def _pos_events(
    db: AsyncSession, tenant_id: str, *, start: datetime, end: datetime
) -> list[dict[str, Any]]:
    txs = (
        await db.execute(
            select(m.Transaction).where(
                m.Transaction.tenant_id == tenant_id,
                m.Transaction.tx_type == "pos_sale",
                m.Transaction.created_at >= start,
                m.Transaction.created_at <= end,
            )
        )
    ).scalars().all()
    out: list[dict[str, Any]] = []
    for tx in txs:
        pids = {
            line.get("product_id")
            for line in (tx.payload or {}).get("items") or []
            if line.get("product_id")
        }
        out.append(
            {
                "id": tx.id,
                "created_at": tx.created_at,
                "total": float(tx.total or 0),
                "product_ids": pids,
            }
        )
    return out


async def sales_analysis(
    db: AsyncSession,
    *,
    tenant_id: str,
    from_date: str | datetime | None = None,
    to_date: str | datetime | None = None,
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    start, end = _parse_range(from_date, to_date)
    baskets = await _invoice_baskets(db, tenant_id, start=start, end=end)
    pos = await _pos_events(db, tenant_id, start=start, end=end)

    # --- Trend: monthly totals + heuristic next month ---
    months: dict[str, float] = defaultdict(float)
    for b in baskets:
        if b["posted_at"]:
            key = b["posted_at"].strftime("%Y-%m")
            months[key] += float(b["total"])
    for p in pos:
        if p["created_at"]:
            key = p["created_at"].strftime("%Y-%m")
            months[key] += float(p["total"])
    series = [{"month": k, "total": round(v, 2)} for k, v in sorted(months.items())]
    if len(series) >= 2:
        recent = series[-1]["total"]
        prior = series[-2]["total"]
        season = seasonality_hint(
            recent_velocity=recent / 30.0, prior_velocity=prior / 30.0
        )
        ratio = season.get("ratio") or (1.0 if prior <= 0 else recent / max(prior, 1e-9))
        if season.get("label") == "emerging_demand":
            ratio = 1.15
        forecast_next = round(recent * float(ratio), 2)
    elif len(series) == 1:
        season = {"detected": False, "ratio": 1.0, "label": "stable"}
        forecast_next = series[0]["total"]
    else:
        season = {"detected": False, "ratio": None, "label": "insufficient_history"}
        forecast_next = 0.0

    # --- RFM ---
    now = end
    cust: dict[str, dict[str, Any]] = {}
    for b in baskets:
        cid = b.get("customer_id")
        if not cid:
            continue
        row = cust.setdefault(
            cid, {"customer_id": cid, "frequency": 0, "monetary": 0.0, "last": None}
        )
        row["frequency"] += 1
        row["monetary"] += float(b["total"])
        if b["posted_at"] and (row["last"] is None or b["posted_at"] > row["last"]):
            row["last"] = b["posted_at"]
    recency_days = {
        cid: (now - (row["last"] or start)).days for cid, row in cust.items()
    }
    freq = {cid: float(row["frequency"]) for cid, row in cust.items()}
    mon = {cid: float(row["monetary"]) for cid, row in cust.items()}
    r_scores = _score_map(recency_days, higher_is_better=False)
    f_scores = _score_map(freq, higher_is_better=True)
    m_scores = _score_map(mon, higher_is_better=True)
    parties = {}
    if cust:
        for p in (
            await db.execute(
                select(m.Party).where(
                    m.Party.tenant_id == tenant_id, m.Party.id.in_(list(cust.keys()))
                )
            )
        ).scalars().all():
            parties[p.id] = p.name
    rfm_rows = []
    for cid, row in cust.items():
        rs, fs, ms = r_scores.get(cid, 1), f_scores.get(cid, 1), m_scores.get(cid, 1)
        rfm_rows.append(
            {
                "customer_id": cid,
                "customer_name": parties.get(cid),
                "recency_days": recency_days.get(cid),
                "frequency": row["frequency"],
                "monetary": round(row["monetary"], 2),
                "r": rs,
                "f": fs,
                "m": ms,
                "segment": _rfm_segment(rs, fs, ms),
            }
        )
    rfm_rows.sort(key=lambda x: (-(x["r"] + x["f"] + x["m"]), -x["monetary"]))
    segment_counts = Counter(r["segment"] for r in rfm_rows)

    # --- Affinity ---
    pair_counts: Counter[tuple[str, str]] = Counter()
    for b in baskets + [
        {"product_ids": p["product_ids"]} for p in pos
    ]:
        ids = sorted(b["product_ids"])
        for a, c in combinations(ids, 2):
            pair_counts[(a, c)] += 1
    top_pairs = pair_counts.most_common(15)
    product_ids = {pid for pair, _ in top_pairs for pid in pair}
    names = {}
    if product_ids:
        for p in (
            await db.execute(
                select(m.Product).where(
                    m.Product.tenant_id == tenant_id, m.Product.id.in_(list(product_ids))
                )
            )
        ).scalars().all():
            names[p.id] = {"sku": p.sku, "name": p.name}
    affinity = [
        {
            "product_a": {"id": a, **names.get(a, {})},
            "product_b": {"id": b, **names.get(b, {})},
            "together_count": cnt,
        }
        for (a, b), cnt in top_pairs
        if cnt >= 1
    ]

    # --- Peak hour / day ---
    hour_counts: Counter[int] = Counter()
    dow_counts: Counter[int] = Counter()
    for b in baskets:
        if b["posted_at"]:
            hour_counts[b["posted_at"].hour] += 1
            dow_counts[b["posted_at"].weekday()] += 1
    for p in pos:
        if p["created_at"]:
            hour_counts[p["created_at"].hour] += 1
            dow_counts[p["created_at"].weekday()] += 1
    dow_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    peak_hours = [
        {"hour": h, "count": c} for h, c in hour_counts.most_common(5)
    ]
    peak_days = [
        {"weekday": dow_names[d], "weekday_index": d, "count": c}
        for d, c in dow_counts.most_common(7)
    ]

    await ai_svc.record_query(
        db,
        tenant_id=tenant_id,
        user_id=actor_user_id,
        endpoint="sales_analysis",
        status="ok",
        details={
            "baskets": len(baskets),
            "pos": len(pos),
            "customers": len(rfm_rows),
            "method": "rule_based",
        },
    )
    await db.commit()
    return {
        "method": "rule_based",
        "from_date": start.isoformat(),
        "to_date": end.isoformat(),
        "trend": {
            "monthly_series": series,
            "seasonality": season,
            "forecast_next_month": forecast_next,
        },
        "rfm": {
            "customers": rfm_rows[:100],
            "segment_counts": dict(segment_counts),
            "customer_count": len(rfm_rows),
        },
        "affinity": affinity,
        "peaks": {"hours": peak_hours, "days": peak_days},
    }
