"""FMCG reporting centre: one catalogue of reports, each as a table that can be shown or exported as CSV.

Every report is a ``(columns, rows)`` table read live from the company's own records. Sales
figures are delivered orders before tax; cost uses each product's current cost price unless the
report says otherwise. CSV cells that start with = + - or @ are prefixed so a spreadsheet never
runs them as formulas. Reports are for managers and admins.
"""

from __future__ import annotations

import csv
import io
from collections import defaultdict
from datetime import date, datetime, time, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import fmcg_batches as batches_svc
from app import fmcg_fleet as fleet_svc
from app import fmcg_forecast as forecast_svc
from app import fmcg_orders as orders
from app import fmcg_promos as promos_svc
from app import fmcg_quality as quality_svc
from app import fmcg_van as van_svc
from app import models as m
from app.honesty import money_json

MAX_ROWS = 5000
MAX_DAYS = 366


def _m(v) -> float:
    return money_json(round(float(v or 0), 2))


def _col(key: str, label: str, kind: str = "text") -> dict:
    return {"key": key, "label": label, "kind": kind}


CATALOGUE = [
    {"id": "sales_by_product", "group": "Sales", "title": "Sales by product", "period": True, "filters": ["product_id", "category_id", "brand_id", "outlet_id", "route_id", "territory_id", "rep"]},
    {"id": "sales_by_category", "group": "Sales", "title": "Sales by category", "period": True, "filters": ["product_id", "category_id", "brand_id", "outlet_id", "route_id", "territory_id", "rep"]},
    {"id": "sales_by_outlet", "group": "Sales", "title": "Sales by outlet", "period": True, "filters": ["product_id", "category_id", "brand_id", "outlet_id", "route_id", "territory_id", "rep"]},
    {"id": "sales_by_rep", "group": "Sales", "title": "Sales by sales rep", "period": True, "filters": ["product_id", "category_id", "brand_id", "outlet_id", "route_id", "territory_id", "rep"]},
    {"id": "sales_by_route", "group": "Sales", "title": "Sales by route", "period": True, "filters": ["product_id", "category_id", "brand_id", "outlet_id", "route_id", "territory_id", "rep"]},
    {"id": "receivables_aging", "group": "Money", "title": "Who owes what, by age", "period": False, "filters": ["outlet_id", "route_id"]},
    {"id": "promotions", "group": "Sales", "title": "Promotions: budget, spend and use", "period": False, "filters": ["status"]},
    {"id": "stock_valuation", "group": "Stock", "title": "Stock valuation", "period": False, "filters": ["product_id", "category_id", "brand_id"]},
    {"id": "batch_expiry", "group": "Stock", "title": "Batches and expiry", "period": False, "filters": ["product_id", "category_id", "brand_id", "status"]},
    {"id": "forecast_orders", "group": "Stock", "title": "Demand forecast and suggested orders (estimates)", "period": False, "filters": ["product_id", "category_id", "status"]},
    {"id": "van_trips", "group": "Distribution", "title": "Van trips and variances", "period": False, "filters": ["vehicle_id"]},
    {"id": "fleet_costs", "group": "Distribution", "title": "Vehicle running costs", "period": True, "filters": ["vehicle_id"]},
    {"id": "missing_pod", "group": "Distribution", "title": "Deliveries without proof", "period": True, "filters": ["outlet_id", "route_id"]},
    {"id": "supplier_quality", "group": "Quality", "title": "Supplier quality", "period": False, "filters": ["supplier_id"]},
    {"id": "complaints", "group": "Quality", "title": "Complaints", "period": False, "filters": ["status", "outlet_id", "product_id"]},
    {"id": "recalls", "group": "Quality", "title": "Recalls", "period": False, "filters": ["status"]},
]


FILTER_KEYS = ("product_id", "category_id", "brand_id", "outlet_id", "route_id", "territory_id", "rep", "supplier_id", "vehicle_id", "status")


def _check_filters(report_id: str, f: dict) -> None:
    entry = next(c for c in CATALOGUE if c["id"] == report_id)
    bad = sorted(k for k in f if k not in entry["filters"])
    if bad:
        raise HTTPException(status_code=422, detail=f"These filters do not apply to this report: {', '.join(bad)}. It accepts: {', '.join(entry['filters']) or 'none'}")


async def _delivered_lines(db, tenant_id: str, start: date, end: date, f: dict | None = None):
    f = f or {}
    stmt = (
        select(m.FmcgOrderLine, m.FmcgOrder, m.Product)
        .join(m.FmcgOrder, m.FmcgOrder.id == m.FmcgOrderLine.order_id)
        .join(m.Product, m.Product.id == m.FmcgOrderLine.product_id)
        .where(
            m.FmcgOrder.tenant_id == tenant_id, m.FmcgOrder.status == "delivered",
            m.FmcgOrder.delivered_at >= datetime.combine(start, time.min), m.FmcgOrder.delivered_at <= datetime.combine(end, time.max),
        )
    )
    if f.get("product_id"):
        stmt = stmt.where(m.FmcgOrderLine.product_id == f["product_id"])
    if f.get("category_id"):
        stmt = stmt.where(m.Product.category_id == f["category_id"])
    if f.get("brand_id"):
        stmt = stmt.where(m.Product.brand_id == f["brand_id"])
    if f.get("outlet_id"):
        stmt = stmt.where(m.FmcgOrder.customer_id == f["outlet_id"])
    if f.get("route_id"):
        stmt = stmt.where(m.FmcgOrder.route_id == f["route_id"])
    if f.get("territory_id"):
        stmt = stmt.where(m.FmcgOrder.route_id.in_(select(m.FmcgTerritoryRoute.route_id).where(
            m.FmcgTerritoryRoute.tenant_id == tenant_id, m.FmcgTerritoryRoute.territory_id == f["territory_id"])))
    if f.get("rep"):
        stmt = stmt.where(func.lower(m.FmcgOrder.rep_name) == f["rep"].strip().lower())
    return (await db.execute(stmt)).all()


def _group(rows, key_fn, label):
    out: dict = defaultdict(lambda: {"qty": 0.0, "sales": 0.0, "discount": 0.0, "cost": 0.0, "orders": set()})
    for line, order, product in rows:
        g = out[key_fn(line, order, product)]
        g["qty"] += float(line.quantity or 0)
        g["sales"] += float(line.line_total or 0) - float(line.tax or 0)
        g["discount"] += float(line.discount or 0)
        g["cost"] += float(line.quantity or 0) * float(product.cost_price or 0)
        g["orders"].add(order.id)
    table = []
    for k, g in sorted(out.items(), key=lambda t: -t[1]["sales"]):
        profit = g["sales"] - g["cost"]
        table.append(
            {label: k, "orders": len(g["orders"]), "units": round(g["qty"], 3), "sales": _m(g["sales"]), "discount": _m(g["discount"]),
             "cost": _m(g["cost"]), "gross_profit": _m(profit), "margin_pct": round(100 * profit / g["sales"], 1) if g["sales"] > 0 else None}
        )
    return table


def _sales_cols(label: str, title: str) -> list[dict]:
    return [_col(label, title), _col("orders", "Orders", "number"), _col("units", "Units", "number"), _col("sales", "Sales", "money"),
            _col("discount", "Discount", "money"), _col("cost", "Cost", "money"), _col("gross_profit", "Gross profit", "money"),
            _col("margin_pct", "Margin %", "number")]


async def _build(db, tenant_id: str, rid: str, start: date, end: date, f: dict | None = None) -> tuple[list[dict], list[dict], str]:
    f = f or {}
    if rid in ("sales_by_product", "sales_by_category", "sales_by_outlet", "sales_by_rep", "sales_by_route"):
        rows = await _delivered_lines(db, tenant_id, start, end, f)
        if rid == "sales_by_product":
            return _sales_cols("name", "Product"), _group(rows, lambda l, o, p: p.name, "name"), "Cost uses current cost prices."
        if rid == "sales_by_category":
            cats = {c.id: c.name for c in (await db.execute(select(m.ProductCategory).where(m.ProductCategory.tenant_id == tenant_id))).scalars().all()}
            return _sales_cols("name", "Category"), _group(rows, lambda l, o, p: cats.get(p.category_id, "No category"), "name"), ""
        if rid == "sales_by_outlet":
            names = {p.id: p.name for p in (await db.execute(select(m.Party).where(m.Party.tenant_id == tenant_id))).scalars().all()}
            return _sales_cols("name", "Outlet"), _group(rows, lambda l, o, p: names.get(o.customer_id, "?"), "name"), ""
        if rid == "sales_by_rep":
            return _sales_cols("name", "Sales rep"), _group(rows, lambda l, o, p: o.rep_name or "No rep", "name"), ""
        routes = {r.id: r.name for r in (await db.execute(select(m.FmcgRoute).where(m.FmcgRoute.tenant_id == tenant_id))).scalars().all()}
        return _sales_cols("name", "Route"), _group(rows, lambda l, o, p: routes.get(o.route_id, "No route"), "name"), ""
    if rid == "receivables_aging":
        data = await orders.aging(db, tenant_id)
        names = {p.id: p.name for p in (await db.execute(select(m.Party).where(m.Party.tenant_id == tenant_id))).scalars().all()}
        keep = {r["customer_id"] for r in data["rows"]}
        if f.get("outlet_id"):
            keep &= {f["outlet_id"]}
        if f.get("route_id"):
            on_route = {a.customer_id for a in (await db.execute(select(m.FmcgCustomerAssignment).where(
                m.FmcgCustomerAssignment.tenant_id == tenant_id, m.FmcgCustomerAssignment.route_id == f["route_id"]))).scalars().all()}
            keep &= on_route
        table = [{"outlet": names.get(r["customer_id"], "?"), "current": r["current"], "d1_30": r["d1_30"], "d31_60": r["d31_60"], "d61_plus": r["d61_plus"], "total": r["total"]} for r in data["rows"] if r["customer_id"] in keep]
        return ([_col("outlet", "Outlet"), _col("current", "Not yet due", "money"), _col("d1_30", "1-30 days late", "money"), _col("d31_60", "31-60 days late", "money"),
                 _col("d61_plus", "Over 60 days late", "money"), _col("total", "Total owed", "money")], sorted(table, key=lambda r: -r["total"]), "")
    if rid == "promotions":
        data = await promos_svc.list_promotions(db, tenant_id=tenant_id, status=f.get("status"))
        table = [{"code": p["code"], "name": p["name"], "status": p["status"] if p["is_active"] else "stopped", "budget": p["budget"], "spent": p["spent"],
                  "uses": p["uses"], "max_uses": p["max_uses"], "for": ", ".join(t["name"] or t["kind"] for t in p["targets"]) or "Everyone"} for p in data]
        return ([_col("code", "Code"), _col("name", "Name"), _col("status", "Status"), _col("budget", "Budget", "money"), _col("spent", "Spent", "money"),
                 _col("uses", "Uses", "number"), _col("max_uses", "Use limit", "number"), _col("for", "For")], table, "")
    if rid == "stock_valuation":
        cats = {c.id: c.name for c in (await db.execute(select(m.ProductCategory).where(m.ProductCategory.tenant_id == tenant_id))).scalars().all()}
        stmt = select(m.Product).where(m.Product.tenant_id == tenant_id, m.Product.is_active.is_(True))
        for key, col in (("product_id", m.Product.id), ("category_id", m.Product.category_id), ("brand_id", m.Product.brand_id)):
            if f.get(key):
                stmt = stmt.where(col == f[key])
        products = (await db.execute(stmt.order_by(m.Product.name))).scalars().all()
        table = [{"product": p.name, "category": cats.get(p.category_id, "No category"), "stock": money_json(p.stock_qty), "cost": _m(p.cost_price),
                  "value": _m(float(p.stock_qty or 0) * float(p.cost_price or 0))} for p in products]
        return ([_col("product", "Product"), _col("category", "Category"), _col("stock", "In stock", "number"), _col("cost", "Unit cost", "money"), _col("value", "Value at cost", "money")], table, "")
    if rid == "batch_expiry":
        if f.get("status") and f["status"] not in batches_svc.STATUSES:
            raise HTTPException(status_code=422, detail=f"status must be one of: {', '.join(batches_svc.STATUSES)}")
        data = await batches_svc.list_batches(db, tenant_id=tenant_id, status=f.get("status") or "all")
        words = {"ok": "Good", "near": "Expiring soon", "expired": "Expired", "held": "On hold"}
        meta = {p.id: p for p in (await db.execute(select(m.Product).where(m.Product.tenant_id == tenant_id))).scalars().all()}
        batches = [b for b in data["batches"]
                   if (not f.get("product_id") or b["product_id"] == f["product_id"])
                   and (not f.get("category_id") or getattr(meta.get(b["product_id"]), "category_id", None) == f["category_id"])
                   and (not f.get("brand_id") or getattr(meta.get(b["product_id"]), "brand_id", None) == f["brand_id"])]
        table = [{"product": b["product_name"], "batch": b["batch_number"], "quantity": b["quantity"], "expiry": b["expiry_date"], "days_left": b["days_to_expiry"],
                  "status": words[b["state"]], "value": b["value_at_cost"]} for b in batches]
        return ([_col("product", "Product"), _col("batch", "Batch"), _col("quantity", "Quantity", "number"), _col("expiry", "Expires"), _col("days_left", "Days left", "number"),
                 _col("status", "Status"), _col("value", "Value at cost", "money")], table, "")
    if rid == "forecast_orders":
        data = await forecast_svc.forecast(db, tenant_id=tenant_id)
        if f.get("status") and f["status"] not in ("stockout_risk", "ok", "overstock", "dead", "no_forecast"):
            raise HTTPException(status_code=422, detail="status must be stockout_risk, ok, overstock, dead or no_forecast")
        cat_of = {p.id: p.category_id for p in (await db.execute(select(m.Product).where(m.Product.tenant_id == tenant_id))).scalars().all()}
        data["products"] = [p for p in data["products"]
                            if (not f.get("product_id") or p["product_id"] == f["product_id"]) and (not f.get("status") or p["status"] == f["status"])
                            and (not f.get("category_id") or cat_of.get(p["product_id"]) == f["category_id"])]
        table = [{"product": p["product"], "status": p["status"], "stock": p["stock"], "daily": p.get("daily_forecast"), "cover": p.get("days_of_cover"),
                  "reorder_point": p.get("reorder_point"), "order": p.get("suggested_order"), "trust": p.get("confidence")} for p in data["products"]]
        return ([_col("product", "Product"), _col("status", "Status"), _col("stock", "In stock", "number"), _col("daily", "Per day (est.)", "number"),
                 _col("cover", "Days of cover", "number"), _col("reorder_point", "Reorder at", "number"), _col("order", "Order (est.)", "number"), _col("trust", "Trust")],
                table, "Estimates from past deliveries, not sales. " + data["meta"]["note"])
    if rid == "van_trips":
        data = await van_svc.performance(db, tenant_id=tenant_id)
        if f.get("vehicle_id"):
            mine = {d.id for d in (await db.execute(select(m.FmcgDispatch).where(m.FmcgDispatch.tenant_id == tenant_id, m.FmcgDispatch.vehicle_id == f["vehicle_id"]))).scalars().all()}
            data = [r for r in data if r["dispatch_id"] in mine]
        table = [{"dispatch": r["dispatch_number"], "date": r["date"], "vehicle": r["vehicle"], "driver": r["driver_name"], "status": r["status"], "sales": r["sales"],
                  "cash": r["cash_collected"], "credit": r["credit_sales"], "costs": r["expenses"], "stock_variance": r["stock_variance_value"], "cash_variance": r["cash_variance"]} for r in data]
        return ([_col("dispatch", "Dispatch"), _col("date", "Date"), _col("vehicle", "Vehicle"), _col("driver", "Driver"), _col("status", "Status"), _col("sales", "Sales", "money"),
                 _col("cash", "Cash", "money"), _col("credit", "On credit", "money"), _col("costs", "Costs", "money"), _col("stock_variance", "Stock difference", "money"),
                 _col("cash_variance", "Cash difference", "money")], table, "Latest 60 trips.")
    if rid == "fleet_costs":
        data = await fleet_svc.cost_report(db, tenant_id=tenant_id, start=start, end=end)
        if f.get("vehicle_id"):
            data = [r for r in data if r["vehicle_id"] == f["vehicle_id"]]
        return ([_col("plate", "Vehicle"), _col("trips", "Trips", "number"), _col("sales_delivered", "Sales delivered", "money"), _col("fuel_cost", "Fuel", "money"),
                 _col("service_cost", "Service", "money"), _col("repair_cost", "Repairs", "money"), _col("tyre_cost", "Tyres", "money"), _col("total_cost", "Total cost", "money"),
                 _col("km_driven", "Km", "number"), _col("cost_per_km", "Cost per km", "number"), _col("km_per_litre", "Km per litre", "number")], data, "")
    if rid == "missing_pod":
        data = await quality_svc.missing_pod(db, tenant_id=tenant_id, days=max(1, (date.today() - start).days))
        if f.get("outlet_id") or f.get("route_id"):
            keep = {o.id for o in (await db.execute(select(m.FmcgOrder).where(
                m.FmcgOrder.tenant_id == tenant_id, *([m.FmcgOrder.customer_id == f["outlet_id"]] if f.get("outlet_id") else []),
                *([m.FmcgOrder.route_id == f["route_id"]] if f.get("route_id") else [])))).scalars().all()}
            data = [r for r in data if r["order_id"] in keep]
        return ([_col("order_number", "Order"), _col("outlet", "Outlet"), _col("delivered_at", "Delivered"), _col("total", "Total", "money")], data, "")
    if rid == "supplier_quality":
        data = await quality_svc.supplier_quality(db, tenant_id=tenant_id)
        if f.get("supplier_id"):
            data = [r for r in data if r["supplier_id"] == f["supplier_id"]]
        return ([_col("supplier", "Supplier"), _col("inspected", "Inspected", "number"), _col("passed", "Passed", "number"), _col("conditional", "Conditional", "number"),
                 _col("failed", "Failed", "number"), _col("fail_rate_pct", "Fail rate %", "number")], data, "")
    if rid == "complaints":
        if f.get("status") and f["status"] not in quality_svc.COMPLAINT_STATUSES:
            raise HTTPException(status_code=422, detail=f"status must be one of: {', '.join(quality_svc.COMPLAINT_STATUSES)}")
        data = await quality_svc.list_complaints(db, tenant_id=tenant_id, status=f.get("status"))
        data = [c for c in data if (not f.get("outlet_id") or c["customer_id"] == f["outlet_id"]) and (not f.get("product_id") or c["product_id"] == f["product_id"])]
        table = [{"number": c["complaint_number"], "date": (c["created_at"] or "")[:10], "outlet": c["outlet"], "product": c["product_name"], "batch": c["batch_number"],
                  "kind": c["category"], "status": c["status"], "resolution": c["resolution"]} for c in data]
        return ([_col("number", "No."), _col("date", "Date"), _col("outlet", "Outlet"), _col("product", "Product"), _col("batch", "Batch"), _col("kind", "Kind"),
                 _col("status", "Status"), _col("resolution", "Resolution")], table, "Latest 200.")
    if rid == "recalls":
        data = await batches_svc.list_recalls(db, tenant_id=tenant_id)
        if f.get("status"):
            if f["status"] not in ("open", "closed"):
                raise HTTPException(status_code=422, detail="status must be open or closed")
            data = [r for r in data if r["status"] == f["status"]]
        table = [{"number": r["recall_number"], "title": r["title"], "status": r["status"], "opened": (r["created_at"] or "")[:10], "closed": (r["closed_at"] or "")[:10]} for r in data]
        return ([_col("number", "No."), _col("title", "Title"), _col("status", "Status"), _col("opened", "Opened"), _col("closed", "Closed")], table, "")
    raise HTTPException(status_code=404, detail="Unknown report")


def _check_period(start: date | None, end: date | None) -> tuple[date, date]:
    end = end or date.today()
    start = start or end - timedelta(days=29)
    if end < start:
        raise HTTPException(status_code=422, detail="The end date is before the start date")
    if (end - start).days > MAX_DAYS:
        raise HTTPException(status_code=422, detail=f"Pick a period of {MAX_DAYS} days or less")
    return start, end


async def _filters_text(db, tenant_id: str, f: dict) -> str:
    parts = []
    for k, v in f.items():
        name = v
        model = {"product_id": m.Product, "outlet_id": m.Party, "supplier_id": m.Party, "category_id": m.ProductCategory, "route_id": m.FmcgRoute,
                 "territory_id": m.FmcgTerritory, "vehicle_id": m.FmcgVehicle}.get(k)
        if model is not None:
            # Only this company's own records may be named; anything else shows as given.
            row = (await db.execute(select(model).where(model.id == v, model.tenant_id == tenant_id))).scalar_one_or_none()
            name = (getattr(row, "name", None) or getattr(row, "plate", None) or v) if row is not None else v
        parts.append(f"{k.replace('_id', '').replace('_', ' ')} = {name}")
    return "; ".join(parts)


async def run(db: AsyncSession, *, tenant_id: str, report_id: str, start: date | None, end: date | None, filters: dict | None = None) -> dict:
    entry = next((c for c in CATALOGUE if c["id"] == report_id), None)
    if entry is None:
        raise HTTPException(status_code=404, detail="Unknown report")
    f = {k: v for k, v in (filters or {}).items() if v not in (None, "")}
    _check_filters(report_id, f)
    s, e = _check_period(start, end)
    columns, rows, note = await _build(db, tenant_id, report_id, s, e, f)
    truncated = len(rows) > MAX_ROWS
    return {
        "id": report_id, "title": entry["title"], "period": {"start": s.isoformat(), "end": e.isoformat()} if entry["period"] else None,
        "columns": columns, "rows": rows[:MAX_ROWS], "row_count": len(rows), "truncated": truncated, "note": note,
        "filters": f, "filters_text": await _filters_text(db, tenant_id, f),
        "generated_at": datetime.utcnow().isoformat(timespec="seconds"),
    }


def _safe(value) -> str:
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") and not _is_number(text) else text


def _is_number(text: str) -> bool:
    try:
        float(text)
        return True
    except ValueError:
        return False


def to_csv(report: dict) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([report["title"]])
    if report["period"]:
        writer.writerow([f"{report['period']['start']} to {report['period']['end']}"])
    if report.get("filters_text"):
        writer.writerow([f"Filters: {report['filters_text']}"])
    if report["note"]:
        writer.writerow([report["note"]])
    writer.writerow([c["label"] for c in report["columns"]])
    for row in report["rows"]:
        writer.writerow([_safe(row.get(c["key"])) for c in report["columns"]])
    if report["truncated"]:
        writer.writerow([f"Only the first {MAX_ROWS} of {report['row_count']} rows are shown."])
    return buf.getvalue()
