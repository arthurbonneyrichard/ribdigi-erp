"""FMCG command centre: one read-only view over sales, stock, money and operations.

Every figure is read from the company's own records at request time; nothing is stored or
estimated here (the demand forecast has its own screen). Sales are delivered orders before tax,
net of returns. "Value at risk" is stock at cost in batches that are expired, held or inside the
company's widest expiry warning.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import fmcg_batches as batches_svc
from app import fmcg_fleet as fleet_svc
from app import fmcg_orders as orders
from app import fmcg_quality as quality_svc
from app import models as m
from app.honesty import money_json


def _m(v) -> float:
    return money_json(round(float(v or 0), 2))


def _months_back(day: date, n: int) -> date:
    y, mth = day.year, day.month - n
    while mth <= 0:
        mth += 12
        y -= 1
    return date(y, mth, 1)


async def _sales_block(db, tenant_id: str, start: date, end: date) -> dict:
    n = await orders.period_numbers(db, tenant_id, start=start, end=end)
    return {
        "net_sales": n["net_sales"], "orders": n["delivered_orders"], "gross_profit": n["gross_profit"],
        "margin_pct": n["gross_margin_percent"], "collected": n["collected"], "returns": n["returns"],
        "scheme_discounts": n["scheme_discounts"],
    }


async def command_centre(db: AsyncSession, *, tenant_id: str) -> dict:
    today = date.today()
    month_start = today.replace(day=1)
    year_start = today.replace(month=1, day=1)

    sales = {
        "today": await _sales_block(db, tenant_id, today, today),
        "week": await _sales_block(db, tenant_id, today - timedelta(days=6), today),
        "month": await _sales_block(db, tenant_id, month_start, today),
        "year": await _sales_block(db, tenant_id, year_start, today),
    }

    # --- money
    owed = await orders.aging(db, tenant_id)
    late = _m(sum(r["total"] - r["current"] for r in owed["rows"]))
    payables = (
        await db.execute(
            select(func.coalesce(func.sum(m.Party.balance), 0)).where(
                m.Party.tenant_id == tenant_id, m.Party.kind == "supplier", m.Party.balance > 0
            )
        )
    ).scalar_one()
    purchases_month = (
        await db.execute(
            select(func.coalesce(func.sum(m.PurchaseInvoice.total_amount), 0)).where(
                m.PurchaseInvoice.tenant_id == tenant_id, m.PurchaseInvoice.status.notin_(("draft", "cancelled")),
                m.PurchaseInvoice.invoice_date >= datetime.combine(month_start, datetime.min.time()),
            )
        )
    ).scalar_one()
    credit_sales_month = (
        await db.execute(
            select(func.coalesce(func.sum(m.FmcgOrder.total), 0)).where(
                m.FmcgOrder.tenant_id == tenant_id, m.FmcgOrder.status == "delivered", m.FmcgOrder.terms == "credit",
                m.FmcgOrder.delivered_at >= datetime.combine(month_start, datetime.min.time()),
            )
        )
    ).scalar_one()
    stolen = (
        await db.execute(
            select(func.coalesce(func.sum(m.StockMovement.quantity), 0)).where(
                m.StockMovement.tenant_id == tenant_id, m.StockMovement.reference_type.in_(("fmcg_write_off", "fmcg_van_loss", "fmcg_van_close")),
                m.StockMovement.created_at >= datetime.combine(month_start, datetime.min.time()),
            )
        )
    ).scalar_one()

    # --- stock
    products = (await db.execute(select(m.Product).where(m.Product.tenant_id == tenant_id, m.Product.is_active.is_(True)))).scalars().all()
    valuation = sum(float(p.stock_qty or 0) * float(p.cost_price or 0) for p in products)
    low = sum(1 for p in products if float(p.reorder_level or 0) > 0 and 0 < float(p.stock_qty or 0) <= float(p.reorder_level))
    out_of_stock = sum(1 for p in products if float(p.stock_qty or 0) <= 0)
    batch_view = await batches_svc.list_batches(db, tenant_id=tenant_id)
    at_risk = sum(b["value_at_cost"] for b in batch_view["batches"] if b["state"] in ("expired", "held", "near"))
    since = datetime.combine(today - timedelta(days=90), datetime.min.time())
    sold_ids = {
        r[0] for r in (
            await db.execute(
                select(m.FmcgOrderLine.product_id)
                .join(m.FmcgOrder, m.FmcgOrder.id == m.FmcgOrderLine.order_id)
                .where(m.FmcgOrder.tenant_id == tenant_id, m.FmcgOrder.status == "delivered", m.FmcgOrder.delivered_at >= since)
                .distinct()
            )
        ).all()
    }
    dead = sorted(
        (p for p in products if float(p.stock_qty or 0) > 0 and p.id not in sold_ids),
        key=lambda p: -float(p.stock_qty or 0) * float(p.cost_price or 0),
    )

    # --- 30 day sales detail
    d30 = today - timedelta(days=29)
    begin = datetime.combine(d30, datetime.min.time())
    lines = (
        await db.execute(
            select(m.FmcgOrderLine, m.FmcgOrder, m.Product)
            .join(m.FmcgOrder, m.FmcgOrder.id == m.FmcgOrderLine.order_id)
            .join(m.Product, m.Product.id == m.FmcgOrderLine.product_id)
            .where(m.FmcgOrder.tenant_id == tenant_id, m.FmcgOrder.status == "delivered", m.FmcgOrder.delivered_at >= begin)
        )
    ).all()
    categories = {c.id: c.name for c in (await db.execute(select(m.ProductCategory).where(m.ProductCategory.tenant_id == tenant_id))).scalars().all()}
    party_names = {p.id: p.name for p in (await db.execute(select(m.Party).where(m.Party.tenant_id == tenant_id, m.Party.kind == "customer"))).scalars().all()}
    daily: dict[date, float] = defaultdict(float)
    by_cat: dict[str, float] = defaultdict(float)
    by_rep: dict[str, float] = defaultdict(float)
    by_product: dict[str, list] = defaultdict(lambda: [0.0, 0.0])
    by_customer: dict[str, float] = defaultdict(float)
    for line, order, product in lines:
        net = float(line.line_total or 0) - float(line.tax or 0)
        daily[order.delivered_at.date()] += net
        by_cat[categories.get(product.category_id, "No category")] += net
        by_rep[order.rep_name or "No rep"] += net
        by_product[product.name][0] += float(line.quantity or 0)
        by_product[product.name][1] += net
        by_customer[order.customer_id] += net
    daily_series = [{"date": (d30 + timedelta(days=i)).isoformat(), "value": _m(daily.get(d30 + timedelta(days=i), 0))} for i in range(30)]

    # --- 12 months sales vs purchases
    first = _months_back(today, 11)
    sales_rows = (
        await db.execute(
            select(m.FmcgOrder.delivered_at, m.FmcgOrder.total, m.FmcgOrder.tax).where(
                m.FmcgOrder.tenant_id == tenant_id, m.FmcgOrder.status == "delivered",
                m.FmcgOrder.delivered_at >= datetime.combine(first, datetime.min.time()),
            )
        )
    ).all()
    buy_rows = (
        await db.execute(
            select(m.PurchaseInvoice.invoice_date, m.PurchaseInvoice.total_amount).where(
                m.PurchaseInvoice.tenant_id == tenant_id, m.PurchaseInvoice.status.notin_(("draft", "cancelled")),
                m.PurchaseInvoice.invoice_date >= datetime.combine(first, datetime.min.time()),
            )
        )
    ).all()
    s_by, p_by = defaultdict(float), defaultdict(float)
    for when, total, tax in sales_rows:
        s_by[(when.year, when.month)] += float(total or 0) - float(tax or 0)
    for when, total in buy_rows:
        p_by[(when.year, when.month)] += float(total or 0)
    months = []
    for i in range(12):
        d = _months_back(today, 11 - i)
        months.append({"month": f"{d.year}-{d.month:02d}", "sales": _m(s_by.get((d.year, d.month), 0)), "purchases": _m(p_by.get((d.year, d.month), 0))})

    # --- operations

    async def one(stmt):
        return int((await db.execute(stmt)).scalar_one() or 0)

    to_load = await one(select(func.count()).select_from(m.FmcgOrder).where(m.FmcgOrder.tenant_id == tenant_id, m.FmcgOrder.status == "booked"))
    on_trucks = await one(select(func.count()).select_from(m.FmcgOrder).where(m.FmcgOrder.tenant_id == tenant_id, m.FmcgOrder.status == "loaded"))
    open_dispatches = await one(select(func.count()).select_from(m.FmcgDispatch).where(m.FmcgDispatch.tenant_id == tenant_id, m.FmcgDispatch.status == "open"))
    open_vans = await one(
        select(func.count(func.distinct(m.FmcgVanLoad.dispatch_id)))
        .join(m.FmcgDispatch, m.FmcgDispatch.id == m.FmcgVanLoad.dispatch_id)
        .where(m.FmcgVanLoad.tenant_id == tenant_id, m.FmcgDispatch.status == "open")
    )
    stale_dispatches = await one(select(func.count()).select_from(m.FmcgDispatch).where(
        m.FmcgDispatch.tenant_id == tenant_id, m.FmcgDispatch.status == "open", m.FmcgDispatch.dispatch_date < today))
    outlets = await one(select(func.count()).select_from(m.Party).where(m.Party.tenant_id == tenant_id, m.Party.kind == "customer", m.Party.status == "active"))
    reps = await one(select(func.count(func.distinct(m.FmcgTerritoryRep.user_id))).where(m.FmcgTerritoryRep.tenant_id == tenant_id))
    vehicles = await one(select(func.count()).select_from(m.FmcgVehicle).where(m.FmcgVehicle.tenant_id == tenant_id, m.FmcgVehicle.status == "active"))
    routes = await one(select(func.count()).select_from(m.FmcgRoute).where(m.FmcgRoute.tenant_id == tenant_id))
    open_recalls = await one(select(func.count()).select_from(m.FmcgRecall).where(m.FmcgRecall.tenant_id == tenant_id, m.FmcgRecall.status == "open"))
    open_complaints = await one(select(func.count()).select_from(m.FmcgComplaint).where(m.FmcgComplaint.tenant_id == tenant_id, m.FmcgComplaint.status.in_(("open", "investigating"))))
    pending_qc = await one(select(func.count()).select_from(m.FmcgQcInspection).where(m.FmcgQcInspection.tenant_id == tenant_id, m.FmcgQcInspection.status == "pending"))
    pending_promos = await one(select(func.count()).select_from(m.FmcgTradeScheme).where(m.FmcgTradeScheme.tenant_id == tenant_id, m.FmcgTradeScheme.status == "pending"))
    pending_po = await one(select(func.count()).select_from(m.PurchaseOrder).where(m.PurchaseOrder.tenant_id == tenant_id, m.PurchaseOrder.status.in_(("draft", "sent", "partially_received"))))
    no_pod = len(await quality_svc.missing_pod(db, tenant_id=tenant_id, days=7))
    fleet_alerts = await fleet_svc.attention(db, tenant_id=tenant_id)
    over_limit = sum(1 for o in await orders.list_outlets(db, tenant_id) if o["credit_limit"] > 0 and o["balance"] > o["credit_limit"])

    attention = []
    def add(level, text, href):
        attention.append({"level": level, "text": text, "href": href})
    if batch_view["counts"]["expired"]:
        add("warning", f"{batch_view['counts']['expired']} expired batches still in stock", "/fmcg?tab=batches")
    if open_recalls:
        add("warning", f"{open_recalls} open recalls", "/fmcg?tab=recalls")
    if fleet_alerts:
        add("warning", f"{len(fleet_alerts)} vehicle alerts (documents or service)", "/fmcg?tab=fleet")
    if stale_dispatches:
        add("warning", f"{stale_dispatches} dispatches from an earlier day are not settled", "/fmcg?tab=deliveries")
    if over_limit:
        add("warning", f"{over_limit} outlets over their credit limit", "/fmcg?tab=outlets")
    if pending_promos:
        add("info", f"{pending_promos} promotions waiting for approval", "/fmcg?tab=promotions")
    if no_pod:
        add("info", f"{no_pod} deliveries in the last 7 days have no proof", "/fmcg?tab=pod")
    if open_complaints:
        add("info", f"{open_complaints} open complaints", "/fmcg?tab=complaints")
    if pending_qc:
        add("info", f"{pending_qc} inspections waiting for a decision", "/fmcg?tab=quality")

    return {
        "as_of": datetime.utcnow().isoformat(timespec="seconds"),
        "note": "Sales are delivered orders before tax, net of returns. Stock value is at cost.",
        "sales": sales,
        "money": {
            "owed_by_outlets": owed["total"], "owed_late": late, "owed_to_suppliers": _m(payables),
            "purchases_this_month": _m(purchases_month), "credit_sales_this_month": _m(credit_sales_month),
            "aging": [{"bucket": k, "amount": _m(sum(r[k] for r in owed["rows"]))} for k in ("current", "d1_30", "d31_60", "d61_plus")],
        },
        "stock": {
            "products": len(products), "units": round(sum(float(p.stock_qty or 0) for p in products), 1), "valuation": _m(valuation),
            "low_stock": low, "out_of_stock": out_of_stock, "batches": batch_view["counts"], "value_at_risk": _m(at_risk),
            "dead_stock_products": len(dead), "units_lost_this_month": round(abs(float(stolen or 0)), 1),
            "dead_stock": [{"product": p.name, "units": float(p.stock_qty), "value": _m(float(p.stock_qty) * float(p.cost_price or 0))} for p in dead[:5]],
            "fast_movers": [{"product": k, "units": round(v[0], 1), "sales": _m(v[1])} for k, v in sorted(by_product.items(), key=lambda t: -t[1][0])[:5]],
        },
        "operations": {
            "orders_to_load": to_load, "orders_on_trucks": on_trucks, "open_dispatches": open_dispatches, "vans_out": open_vans,
            "stale_dispatches": stale_dispatches, "deliveries_without_proof_7d": no_pod, "open_recalls": open_recalls,
            "open_complaints": open_complaints, "inspections_pending": pending_qc, "promotions_pending": pending_promos,
            "purchase_orders_open": pending_po, "vehicle_alerts": len(fleet_alerts), "outlets": outlets, "reps": reps,
            "active_vehicles": vehicles, "routes": routes, "outlets_over_limit": over_limit,
        },
        "charts": {
            "daily_sales_30": daily_series, "monthly_12": months,
            "by_category_30": [{"name": k, "sales": _m(v)} for k, v in sorted(by_cat.items(), key=lambda t: -t[1])[:8]],
            "by_rep_30": [{"name": k, "sales": _m(v)} for k, v in sorted(by_rep.items(), key=lambda t: -t[1])[:8]],
            "top_customers_30": [{"name": party_names.get(k, "?"), "sales": _m(v)} for k, v in sorted(by_customer.items(), key=lambda t: -t[1])[:8]],
            "top_products_30": [{"name": k, "sales": _m(v[1])} for k, v in sorted(by_product.items(), key=lambda t: -t[1][1])[:8]],
            "by_route": (await orders.period_numbers(db, tenant_id, start=d30, end=today))["by_route"][:8],
        },
        "attention": attention,
    }
