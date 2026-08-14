"""Deterministic AI purchases analysis (Stage 25 P1).

Spend trends, supplier concentration, PO fill / open backlog, and purchase-invoice
overdue signals over live PO / GRN / PI actuals — no external ML.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.reports import apply_company_filter

ACTIVE_PO_STATUSES = frozenset(
    {"draft", "sent", "partially_received", "received"}
)
OPEN_PO_STATUSES = frozenset({"draft", "sent", "partially_received"})
POSTED_PI_STATUSES = frozenset({"unpaid", "partial", "paid", "overdue"})
OPEN_PI_STATUSES = frozenset({"unpaid", "partial", "overdue", "draft"})


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


async def analyze_purchases(
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

    po_stmt = select(m.PurchaseOrder).where(
        m.PurchaseOrder.tenant_id == tenant_id,
        m.PurchaseOrder.created_at >= start,
        m.PurchaseOrder.created_at <= end,
    )
    po_stmt = apply_company_filter(po_stmt, m.PurchaseOrder.company_id, company_id)
    orders = (await db.execute(po_stmt)).scalars().all()

    grn_stmt = select(m.GoodsReceipt).where(
        m.GoodsReceipt.tenant_id == tenant_id,
        m.GoodsReceipt.created_at >= start,
        m.GoodsReceipt.created_at <= end,
    )
    grn_stmt = apply_company_filter(grn_stmt, m.GoodsReceipt.company_id, company_id)
    grns = (await db.execute(grn_stmt)).scalars().all()

    pi_stmt = select(m.PurchaseInvoice).where(
        m.PurchaseInvoice.tenant_id == tenant_id,
        m.PurchaseInvoice.invoice_date >= start,
        m.PurchaseInvoice.invoice_date <= end,
    )
    pi_stmt = apply_company_filter(pi_stmt, m.PurchaseInvoice.company_id, company_id)
    invoices = (await db.execute(pi_stmt)).scalars().all()

    po_ids = [o.id for o in orders]
    po_items: list[m.PurchaseOrderItem] = []
    if po_ids:
        po_items = (
            await db.execute(
                select(m.PurchaseOrderItem).where(
                    m.PurchaseOrderItem.tenant_id == tenant_id,
                    m.PurchaseOrderItem.purchase_order_id.in_(po_ids),
                )
            )
        ).scalars().all()

    supplier_ids = {
        *(o.supplier_id for o in orders if o.supplier_id),
        *(g.supplier_id for g in grns if g.supplier_id),
        *(i.supplier_id for i in invoices if i.supplier_id),
    }
    parties = {}
    if supplier_ids:
        party_stmt = select(m.Party).where(
            m.Party.tenant_id == tenant_id,
            m.Party.id.in_(list(supplier_ids)),
        )
        party_stmt = apply_company_filter(party_stmt, m.Party.company_id, company_id)
        parties = {
            p.id: p for p in (await db.execute(party_stmt)).scalars().all()
        }

    # --- Spend trend from posted / open purchase invoices ---
    spend_invoices = [i for i in invoices if i.status in POSTED_PI_STATUSES or i.status == "draft"]
    posted_for_spend = [i for i in invoices if i.status in POSTED_PI_STATUSES]
    daily: dict[str, float] = defaultdict(float)
    for inv in posted_for_spend:
        when = inv.invoice_date or inv.created_at or now
        daily[when.date().isoformat()] += float(inv.total_amount or 0)

    day_list: list[tuple[str, float]] = []
    cursor = start.date()
    end_d = end.date()
    while cursor <= end_d:
        key = cursor.isoformat()
        day_list.append((key, round(daily.get(key, 0.0), 2)))
        cursor += timedelta(days=1)

    n = len(day_list)
    total_spend = round(sum(v for _, v in day_list), 2)
    avg_daily = round(total_spend / n, 2) if n else 0.0
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
    forecast: dict[str, float] = {}
    for horizon in (7, 14, 30):
        projected = [max(0.0, last_y + slope * i) for i in range(1, horizon + 1)]
        forecast[str(horizon)] = round(sum(projected), 2)

    # --- Supplier concentration ---
    by_supplier: dict[str, dict] = {}
    for inv in posted_for_spend:
        sid = inv.supplier_id
        if not sid:
            continue
        row = by_supplier.setdefault(
            sid, {"invoice_count": 0, "spend": 0.0, "last": inv.invoice_date or now}
        )
        row["invoice_count"] += 1
        row["spend"] += float(inv.total_amount or 0)
        when = inv.invoice_date or inv.created_at or now
        if when > row["last"]:
            row["last"] = when

    for o in orders:
        if o.status == "cancelled" or not o.supplier_id:
            continue
        row = by_supplier.setdefault(
            o.supplier_id,
            {"invoice_count": 0, "spend": 0.0, "last": o.created_at or now, "po_count": 0},
        )
        row["po_count"] = int(row.get("po_count") or 0) + 1

    suppliers: list[dict] = []
    for sid, row in by_supplier.items():
        party = parties.get(sid)
        spend = round(float(row["spend"]), 2)
        share = round(spend / total_spend, 3) if total_spend > 0 else 0.0
        suppliers.append(
            {
                "supplier_id": sid,
                "supplier_name": party.name if party else sid,
                "invoice_count": row["invoice_count"],
                "po_count": int(row.get("po_count") or 0),
                "spend": spend,
                "spend_share": share,
                "last_invoice_at": row["last"],
            }
        )
    suppliers.sort(key=lambda x: (-x["spend"], -x["invoice_count"]))
    top_share = suppliers[0]["spend_share"] if suppliers else 0.0

    # --- PO fill / open backlog ---
    items_by_po: dict[str, list[m.PurchaseOrderItem]] = defaultdict(list)
    for it in po_items:
        items_by_po[it.purchase_order_id].append(it)

    status_counts: Counter = Counter(o.status for o in orders)
    open_pos = [o for o in orders if o.status in OPEN_PO_STATUSES]
    open_po_value = round(
        sum(float(o.total_amount or 0) for o in open_pos if o.status != "draft"), 2
    )
    draft_pos = [o for o in orders if o.status == "draft"]
    partial_pos = [o for o in orders if o.status == "partially_received"]

    fill_rows: list[dict] = []
    for o in orders:
        if o.status == "cancelled":
            continue
        items = items_by_po.get(o.id) or []
        ordered = sum(float(it.quantity or 0) for it in items)
        received = sum(float(it.received_qty or 0) for it in items)
        fill_pct = round((received / ordered) * 100, 1) if ordered > 0 else None
        if fill_pct is None and o.status not in ("sent", "partially_received", "received"):
            continue
        fill_rows.append(
            {
                "purchase_order_id": o.id,
                "po_number": o.po_number,
                "status": o.status,
                "supplier_id": o.supplier_id,
                "supplier_name": parties.get(o.supplier_id).name
                if o.supplier_id and parties.get(o.supplier_id)
                else None,
                "ordered_qty": round(ordered, 3),
                "received_qty": round(received, 3),
                "fill_pct": fill_pct,
                "total_amount": float(o.total_amount or 0),
            }
        )
    fill_rows.sort(key=lambda x: (x["fill_pct"] is None, x["fill_pct"] if x["fill_pct"] is not None else 999))

    # --- Purchase invoice aging / open AP ---
    open_pis = [i for i in invoices if i.status in OPEN_PI_STATUSES]
    overdue_pis = []
    for inv in invoices:
        due = inv.due_date
        balance = float(inv.total_amount or 0) - float(inv.paid_amount or 0)
        is_overdue = inv.status == "overdue" or (
            due is not None
            and due < now
            and balance > 0.001
            and inv.status in {"unpaid", "partial", "overdue"}
        )
        if is_overdue:
            overdue_pis.append(
                {
                    "purchase_invoice_id": inv.id,
                    "invoice_number": inv.invoice_number,
                    "supplier_id": inv.supplier_id,
                    "supplier_name": parties.get(inv.supplier_id).name
                    if inv.supplier_id and parties.get(inv.supplier_id)
                    else None,
                    "status": inv.status,
                    "due_date": due,
                    "balance": round(balance, 2),
                    "total_amount": float(inv.total_amount or 0),
                }
            )
    overdue_pis.sort(key=lambda x: x["due_date"] or now)

    # --- Suggestions ---
    suggestions: list[dict] = []
    if top_share >= 0.6 and total_spend > 0:
        top = suppliers[0]
        suggestions.append(
            {
                "kind": "supplier_concentration",
                "severity": "high" if top_share >= 0.8 else "medium",
                "summary": (
                    f"{top['supplier_name']} accounts for {top_share:.0%} of purchase spend "
                    f"({top['spend']:.2f})."
                ),
                "action": "Diversify sourcing or negotiate volume terms with the dominant supplier.",
            }
        )
    if len(draft_pos) >= 3:
        draft_value = round(sum(float(o.total_amount or 0) for o in draft_pos), 2)
        suggestions.append(
            {
                "kind": "draft_po_backlog",
                "severity": "medium",
                "summary": f"{len(draft_pos)} draft PO(s) totaling {draft_value:.2f} are unsent.",
                "action": "Review and send or cancel stale drafts so open commitments stay accurate.",
            }
        )
    if partial_pos:
        suggestions.append(
            {
                "kind": "partial_receive_backlog",
                "severity": "medium",
                "summary": (
                    f"{len(partial_pos)} PO(s) are partially received — chase remaining lines or close short."
                ),
                "action": "Follow up with suppliers on outstanding quantities.",
            }
        )
    if overdue_pis:
        overdue_balance = round(sum(float(r["balance"]) for r in overdue_pis), 2)
        suggestions.append(
            {
                "kind": "overdue_bills",
                "severity": "high",
                "summary": (
                    f"{len(overdue_pis)} purchase invoice(s) are overdue "
                    f"(open balance {overdue_balance:.2f})."
                ),
                "action": "Schedule supplier payments or confirm disputes before late fees.",
            }
        )
    week_ago = end - timedelta(days=7)
    two_weeks = end - timedelta(days=14)
    this_week = sum(
        float(i.total_amount or 0)
        for i in posted_for_spend
        if i.invoice_date and week_ago <= i.invoice_date <= end
    )
    prev_week = sum(
        float(i.total_amount or 0)
        for i in posted_for_spend
        if i.invoice_date and two_weeks <= i.invoice_date < week_ago
    )
    wow_pct = None
    if prev_week > 0:
        wow_pct = round(((this_week - prev_week) / prev_week) * 100, 1)
        if wow_pct >= 40:
            suggestions.insert(
                0,
                {
                    "kind": "week_over_week_spend_spike",
                    "severity": "high",
                    "summary": (
                        f"Purchase spend up {wow_pct}% week-over-week "
                        f"({round(this_week, 2)} vs {round(prev_week, 2)})."
                    ),
                    "action": "Confirm large receipts/invoices were intentional before cash outflow.",
                },
            )

    active_orders = [o for o in orders if o.status in ACTIVE_PO_STATUSES]
    return {
        "generated_at": now,
        "from_date": start,
        "to_date": end,
        "method": "rules_v1",
        "summary": {
            "purchase_order_count": len(orders),
            "active_po_count": len(active_orders),
            "open_po_count": len(open_pos),
            "open_po_value": open_po_value,
            "grn_count": len(grns),
            "purchase_invoice_count": len(invoices),
            "posted_invoice_count": len(posted_for_spend),
            "total_spend": total_spend,
            "avg_daily_spend": avg_daily,
            "supplier_count": len(by_supplier),
            "overdue_invoice_count": len(overdue_pis),
            "trend_direction": trend_direction,
            "daily_slope": round(slope, 4),
            "wow_change_pct": wow_pct,
            "top_supplier_spend_share": top_share,
        },
        "trend": {
            "daily": [{"date": d, "total": v} for d, v in day_list if v > 0 or n <= 60],
            "forecast_totals": forecast,
            "direction": trend_direction,
            "daily_slope": round(slope, 4),
            "note": "Linear projection from daily posted purchase-invoice totals (not Prophet).",
        },
        "suppliers": {
            "rows": suppliers[:50],
            "count": len(suppliers),
            "top_spend_share": top_share,
        },
        "purchase_orders": {
            "status_counts": dict(status_counts),
            "open_value": open_po_value,
            "fill": fill_rows[:50],
            "draft_count": len(draft_pos),
            "partial_count": len(partial_pos),
        },
        "goods_receipts": {
            "count": len(grns),
            "by_status": dict(Counter(g.status for g in grns)),
        },
        "purchase_invoices": {
            "open_count": len(open_pis),
            "overdue": overdue_pis[:50],
            "overdue_count": len(overdue_pis),
            "analyzed_count": len(spend_invoices),
        },
        "suggestions": suggestions,
    }
