"""FMCG assistant: answers business questions from the company's own figures.

It does not use a language model and cannot make a number up. Each question is matched to a fixed set
of questions it knows, answered by the same code that feeds the dashboard and reports, and returned
with the figures, the period, where they came from and whether they are actual or an estimate
(forecasts are always labelled as estimates). It only reads; it never posts, approves or changes
anything. A question it does not know gets a list of the ones it does.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app import fmcg_batches as batches_svc
from app import fmcg_dashboard as dash_svc
from app import fmcg_distributors as dist_svc
from app import fmcg_fleet as fleet_svc
from app import fmcg_forecast as forecast_svc
from app import fmcg_orders as orders
from app import fmcg_reports as reports_svc
from app import fmcg_van as van_svc

EXAMPLES = [
    "What were my total sales today?",
    "Which products made the highest profit this month?",
    "Which products are expiring?",
    "What should I reorder?",
    "Which customers owe me money?",
    "Which salesperson made the most sales this month?",
    "Which products have not sold for 90 days?",
    "Which products have too much stock?",
    "How did my van sales perform?",
    "What is my total inventory valuation?",
    "How much did I spend on delivery this month?",
    "Which products are likely to run out next month?",
    "Which distributors are performing poorly?",
    "Which route sold the most this month?",
    "Which outlets bought the most in the last 30 days?",
]

# (intent, patterns). The first intent with a matching pattern wins, so put the specific ones first.
INTENTS: list[tuple[str, list[str]]] = [
    ("distributors", [r"distributor"]),
    ("run_out", [r"run out", r"stock.?out", r"out of stock soon", r"next month.*(short|run)"]),
    ("overstock", [r"too much stock", r"excess stock", r"overstock", r"over.?stocked"]),
    ("not_selling", [r"not sold", r"not selling", r"dead stock", r"slow.?moving", r"haven'?t sold", r"no sales"]),
    ("expiring", [r"expir", r"near.?expiry", r"best before"]),
    ("reorder", [r"reorder", r"re-order", r"what (should|must) i (buy|order)", r"restock"]),
    ("owed", [r"owe", r"debtor", r"receivable", r"outstanding (balance|payment)", r"unpaid"]),
    ("valuation", [r"valuation", r"value of (my )?(stock|inventory)", r"stock value", r"inventory value"]),
    ("delivery_cost", [r"deliver\w* (cost|spend|expense)", r"spend on deliver", r"fuel", r"fleet cost", r"transport cost"]),
    ("van", [r"\bvan\b"]),
    ("profit_products", [r"profit\w* product", r"product\w* .*profit", r"most profit", r"highest profit", r"margin"]),
    ("top_rep", [r"sales ?person", r"sales ?rep", r"\brep\b", r"who sold the most"]),
    ("top_route", [r"\broute"]),
    ("top_outlets", [r"outlet\w*", r"customer\w* (bought|buy|purchased)", r"best customer", r"top customer"]),
    ("sales_total", [r"total sales", r"how much (did|have) i sold", r"\bsales\b", r"revenue", r"turnover"]),
]


def parse_period(q: str, today: date | None = None) -> tuple[date, date, str, bool]:
    """Return (start, end, label, was_stated). Defaults to the last 30 days and says so."""
    today = today or date.today()
    if "yesterday" in q:
        d = today - timedelta(days=1)
        return d, d, "yesterday", True
    if "today" in q:
        return today, today, "today", True
    if re.search(r"last month|previous month", q):
        end = today.replace(day=1) - timedelta(days=1)
        return end.replace(day=1), end, "last month", True
    if re.search(r"this month|month to date|mtd", q):
        return today.replace(day=1), today, "this month", True
    if re.search(r"this year|year to date|ytd", q):
        return today.replace(month=1, day=1), today, "this year", True
    if re.search(r"this week|last 7 days|past week", q):
        return today - timedelta(days=6), today, "the last 7 days", True
    found = re.search(r"last (\d{1,3}) days", q)
    if found and 1 <= int(found.group(1)) <= 366:
        n = int(found.group(1))
        return today - timedelta(days=n - 1), today, f"the last {n} days", True
    return today - timedelta(days=29), today, "the last 30 days", False


def match_intent(question: str) -> str | None:
    q = question.lower()
    for intent, patterns in INTENTS:
        if any(re.search(p, q) for p in patterns):
            return intent
    return None


def _money(v) -> str:
    return f"{float(v or 0):,.2f}"


async def _sales_table(db, tenant_id, report_id, start, end, key, limit=5):
    data = await reports_svc.run(db, tenant_id=tenant_id, report_id=report_id, start=start, end=end)
    rows = sorted(data["rows"], key=lambda r: -(r.get(key) or 0))[:limit]
    return data, rows


async def answer(db: AsyncSession, *, tenant_id: str, question: str) -> dict:
    q = (question or "").strip()
    intent = match_intent(q)
    start, end, label, stated = parse_period(q.lower())
    base = {"question": q, "intent": intent, "kind": "actual", "period": None, "source": None, "link": None, "table": None}
    note = "" if stated else " (I used the last 30 days because you did not say which period.)"

    if intent is None:
        return {**base, "answer": "I can only answer questions I can work out from your own records. Try one of these.", "examples": EXAMPLES}

    if intent == "sales_total":
        n = await orders.period_numbers(db, tenant_id, start=start, end=end)
        return {**base, "period": {"start": start.isoformat(), "end": end.isoformat(), "label": label}, "source": "Delivered orders before tax, net of returns", "link": "/fmcg?tab=command",
                "answer": f"Sales for {label}: {_money(n['net_sales'])} from {n['delivered_orders']} delivered orders. Gross profit {_money(n['gross_profit'])} ({n['gross_margin_percent']}%). Collected {_money(n['collected'])}.{note}"}

    if intent == "profit_products":
        data, rows = await _sales_table(db, tenant_id, "sales_by_product", start, end, "gross_profit")
        text = "; ".join(f"{r['name']} {_money(r['gross_profit'])}" for r in rows) or "no deliveries in that period"
        return {**base, "period": {"start": start.isoformat(), "end": end.isoformat(), "label": label}, "source": "Sales by product report (cost at current cost price)", "link": "/fmcg?tab=centre",
                "answer": f"Highest gross profit for {label}: {text}.{note}", "table": {"columns": ["name", "sales", "cost", "gross_profit", "margin_pct"], "rows": rows}}

    if intent in ("top_rep", "top_route", "top_outlets"):
        rid, who = {"top_rep": ("sales_by_rep", "salesperson"), "top_route": ("sales_by_route", "route"), "top_outlets": ("sales_by_outlet", "outlets")}[intent]
        data, rows = await _sales_table(db, tenant_id, rid, start, end, "sales", limit=5 if intent == "top_outlets" else 3)
        text = "; ".join(f"{r['name']} {_money(r['sales'])}" for r in rows) or "no deliveries in that period"
        return {**base, "period": {"start": start.isoformat(), "end": end.isoformat(), "label": label}, "source": f"{data['title']} (delivered orders before tax)", "link": "/fmcg?tab=centre",
                "answer": f"Top {who} for {label}: {text}.{note}", "table": {"columns": ["name", "orders", "sales", "gross_profit"], "rows": rows}}

    if intent == "distributors":
        rows = await dist_svc.ranking(db, tenant_id=tenant_id, start=start, end=end)
        words = {"behind_target": "behind target", "sales_falling": "sales falling", "paying_late": "paying late", "over_credit_limit": "over credit limit", "no_orders": "no orders"}
        weak = [r for r in rows if r["flags"]]
        text = "; ".join(f"{r['distributor']} ({', '.join(words[f] for f in r['flags'])})" for r in weak[:6])
        table = [{"distributor": r["distributor"], "net_sales": r["net_sales"], "target_pct": r["target_pct"], "growth_pct": r["growth_pct"], "owed_late": r["owed_late"], "flags": ", ".join(words[f] for f in r["flags"])} for r in rows[:10]]
        return {**base, "period": {"start": start.isoformat(), "end": end.isoformat(), "label": label}, "source": "Distributor performance (target, growth, lateness, credit limit)", "link": "/fmcg?tab=distributors",
                "answer": (f"{len(weak)} of {len(rows)} distributors need attention for {label}: {text}." if weak else f"No distributor needs attention for {label}." if rows else "You have no distributor profiles yet.") + note,
                "table": {"columns": ["distributor", "net_sales", "target_pct", "growth_pct", "owed_late", "flags"], "rows": table}}

    if intent == "expiring":
        data = await batches_svc.list_batches(db, tenant_id=tenant_id)
        soon = [b for b in data["batches"] if b["state"] in ("near", "expired")][:8]
        c = data["counts"]
        text = "; ".join(f"{b['product_name']} batch {b['batch_number']} ({'expired' if b['state'] == 'expired' else str(b['days_to_expiry']) + ' days left'}, {b['quantity']:g} units)" for b in soon)
        return {**base, "source": "Batches and expiry", "link": "/fmcg?tab=batches",
                "answer": f"{c['expired']} batches have expired and {c['near']} expire soon ({c['held']} are on hold). " + (f"Soonest: {text}." if text else "Nothing is close to expiry."),
                "table": {"columns": ["product_name", "batch_number", "quantity", "expiry_date", "days_to_expiry", "state"], "rows": soon}}

    if intent == "owed":
        data = await orders.aging(db, tenant_id)
        rep = await reports_svc.run(db, tenant_id=tenant_id, report_id="receivables_aging", start=None, end=None)
        rows = rep["rows"][:5]
        text = "; ".join(f"{r['outlet']} {_money(r['total'])}" for r in rows) or "nobody owes you anything"
        late = sum(r["total"] - r["current"] for r in data["rows"])
        return {**base, "source": "Delivered, unpaid orders by age", "link": "/fmcg?tab=centre",
                "answer": f"Outlets owe you {_money(data['total'])} in total, of which {_money(late)} is past its due date. Largest: {text}.",
                "table": {"columns": ["outlet", "current", "d1_30", "d31_60", "d61_plus", "total"], "rows": rows}}

    if intent == "not_selling":
        d = await dash_svc.command_centre(db, tenant_id=tenant_id)
        rows = d["stock"]["dead_stock"]
        text = "; ".join(f"{r['product']} ({r['units']:g} units, {_money(r['value'])})" for r in rows)
        return {**base, "source": "Stock with no delivered sales in 90 days", "link": "/fmcg?tab=command",
                "answer": f"{d['stock']['dead_stock_products']} products have stock but no sales in 90 days." + (f" Biggest by value: {text}." if text else ""),
                "table": {"columns": ["product", "units", "value"], "rows": rows}}

    if intent == "valuation":
        d = await dash_svc.command_centre(db, tenant_id=tenant_id)
        s = d["stock"]
        return {**base, "source": "Products x cost price", "link": "/fmcg?tab=command",
                "answer": f"Stock is worth {_money(s['valuation'])} at cost: {s['units']:g} units across {s['products']} products. {_money(s['value_at_risk'])} of it is in batches that are expired, on hold or close to expiry."}

    if intent == "delivery_cost":
        rows = await fleet_svc.cost_report(db, tenant_id=tenant_id, start=start, end=end)
        total = sum(r["total_cost"] for r in rows)
        fuel = sum(r["fuel_cost"] for r in rows)
        trips = sum(r["trips"] for r in rows)
        return {**base, "period": {"start": start.isoformat(), "end": end.isoformat(), "label": label}, "source": "Vehicle running costs", "link": "/fmcg?tab=fleet",
                "answer": f"Vehicle running costs for {label}: {_money(total)} (fuel {_money(fuel)}) over {trips} trips.{note} Costs paid from van takings are included only when the dispatch had a vehicle.",
                "table": {"columns": ["plate", "trips", "fuel_cost", "total_cost", "km_driven", "cost_per_km"], "rows": rows}}

    if intent == "van":
        rows = (await van_svc.performance(db, tenant_id=tenant_id))[:5]
        if not rows:
            return {**base, "source": "Van trips", "link": "/fmcg?tab=van", "answer": "There are no van trips yet."}
        sales = sum(r["sales"] for r in rows)
        diffs = sum(1 for r in rows if (r["stock_variance_value"] or 0) or (r["cash_variance"] or 0))
        return {**base, "source": "Latest van trips", "link": "/fmcg?tab=van",
                "answer": f"The last {len(rows)} van trips sold {_money(sales)}; {diffs} had a stock or cash difference.",
                "table": {"columns": ["dispatch_number", "date", "sales", "cash_collected", "credit_sales", "expenses", "stock_variance_value", "cash_variance"], "rows": rows}}

    # The remaining questions use the demand forecast, which is an estimate.
    fc = await forecast_svc.forecast(db, tenant_id=tenant_id)
    if intent == "overstock":
        rows = [p for p in fc["products"] if p["status"] == "overstock"][:8]
        text = "; ".join(f"{p['product']} ({p['days_of_cover']:g} days of cover)" for p in rows)
        return {**base, "kind": "estimate", "source": "Demand forecast (estimate)", "link": "/fmcg?tab=forecast",
                "answer": (f"Estimated too much stock: {text}." if text else "No product looks overstocked on the forecast.") + " These are estimates from past deliveries, not actual sales.",
                "table": {"columns": ["product", "stock", "daily_forecast", "days_of_cover"], "rows": rows}}
    if intent == "run_out":
        rows = [p for p in fc["products"] if p["status"] == "stockout_risk" or (p.get("stockout_date") and p["days_of_cover"] is not None and p["days_of_cover"] <= 30)][:8]
        text = "; ".join(f"{p['product']} (about {p['days_of_cover']:g} days left, runs out {p['stockout_date'] or 'soon'})" for p in rows)
        return {**base, "kind": "estimate", "source": "Demand forecast (estimate)", "link": "/fmcg?tab=forecast",
                "answer": (f"Likely to run out: {text}." if text else "Nothing looks likely to run out in the next month.") + " These are estimates from past deliveries, not actual sales.",
                "table": {"columns": ["product", "stock", "days_of_cover", "stockout_date", "suggested_order"], "rows": rows}}
    rows = [p for p in fc["products"] if (p.get("suggested_order") or 0) > 0][:8]
    text = "; ".join(f"{p['product']} {p['suggested_order']:g}" for p in rows)
    return {**base, "kind": "estimate", "source": "Demand forecast (estimate)", "link": "/fmcg?tab=forecast",
            "answer": (f"Suggested orders: {text}." if text else "Nothing needs ordering on the forecast.") + " Quantities are estimates from past deliveries and already count orders on the way.",
            "table": {"columns": ["product", "stock", "on_order", "reorder_point", "suggested_order"], "rows": rows}}
