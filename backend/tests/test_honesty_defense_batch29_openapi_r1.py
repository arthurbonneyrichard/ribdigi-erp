"""OpenAPI honesty tips #1583–#1622: dashboard/AI/cheque/accounting money_json + residual FE aria."""

from __future__ import annotations

import inspect
from pathlib import Path

from app.honesty import money_json
from app import accounting as accounting_mod
from app import ai as ai_mod
from app import ai_documents as ai_documents_mod
from app import ai_expenses as ai_expenses_mod
from app import ai_inventory as ai_inventory_mod
from app import ai_sales as ai_sales_mod
from app import cheques as cheques_mod
from app import credit as credit_mod
from app import dashboard as dashboard_mod
from app import purchase_requests as purchase_requests_mod
from app import purchase_suggestions as purchase_suggestions_mod

ROOT = Path(__file__).resolve().parents[2]


def test_honesty_batch29_docs_and_agents():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for title in (
        "Dashboard month_totals accumulate money_json Decimal pilot OpenAPI",
        "Dashboard cost_map money_json Decimal pilot OpenAPI",
        "Dashboard daily sales accumulate money_json Decimal pilot OpenAPI",
        "Dashboard daily line qty money_json Decimal pilot OpenAPI",
        "Dashboard daily unit_price money_json Decimal pilot OpenAPI",
        "AI expenses by_cat_vals money_json Decimal pilot OpenAPI",
        "AI expenses by_cat_id_amount money_json Decimal pilot OpenAPI",
        "AI expenses budget read money_json Decimal pilot OpenAPI",
        "AI expenses spent read money_json Decimal pilot OpenAPI",
        "AI expenses unusual amt money_json Decimal pilot OpenAPI",
        "AI expenses dup key amount money_json Decimal pilot OpenAPI",
        "AI expenses recent/prior sum money_json Decimal pilot OpenAPI",
        "AI sales RFM monetary accumulate money_json Decimal pilot OpenAPI",
        "AI sales monthly series accumulate money_json Decimal pilot OpenAPI",
        "AI inventory sold map qty money_json Decimal pilot OpenAPI",
        "AI inventory reorder_qty_map money_json Decimal pilot OpenAPI",
        "AI inventory forecast stock money_json Decimal pilot OpenAPI",
        "AI inventory already_low compare money_json Decimal pilot OpenAPI",
        "Cheque reverse AR amount money_json Decimal pilot OpenAPI",
        "Cheque reverse AP amount money_json Decimal pilot OpenAPI",
        "Cheque bounce amount money_json Decimal pilot OpenAPI",
        "Cheque cancel amount money_json Decimal pilot OpenAPI",
        "Accounting lines_are_balanced money_json Decimal pilot OpenAPI",
        "Accounting unpost balance delta money_json Decimal pilot OpenAPI",
        "Accounting post balance delta money_json Decimal pilot OpenAPI",
        "Accounting SI post revenue money_json Decimal pilot OpenAPI",
        "Accounting COGS line qty money_json Decimal pilot OpenAPI",
        "Purchase suggestion list qty money_json Decimal pilot OpenAPI",
        "Purchase request line qty money_json Decimal pilot OpenAPI",
        "AI document expense amount money_json Decimal pilot OpenAPI",
        "Credit payment schedule balance money_json Decimal pilot OpenAPI",
        "AI insight WoW sales money_json Decimal pilot OpenAPI",
        "Tax Add tax rate aria OpenAPI",
        "Inventory Create draft count aria OpenAPI",
        "Inventory Create stock transfer aria OpenAPI",
        "Inventory Create variant aria OpenAPI",
        "POS Charge complete sale aria OpenAPI",
        "POS Clear POS cart aria OpenAPI",
        "Integrations Create API key aria OpenAPI",
        "Expenses Cancel recurring expense edit aria OpenAPI",
    ):
        assert title in agents, title

    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    standards = docs.split("## 1. API Standards")[1].split("## 2.")[0]
    assert "dashboard month/daily accumulate" in standards or "cheque reverse AR/AP" in standards
    assert "AI expenses by_cat" in standards or "purchase suggestion/PR qty" in standards

    tax = (ROOT / "frontend/app/tax/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Add tax rate"' in tax

    inventory = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Create draft count"' in inventory
    assert 'aria-label="Create stock transfer"' in inventory
    assert 'aria-label="Create variant"' in inventory

    pos = (ROOT / "frontend/app/pos/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Charge complete sale"' in pos
    assert 'aria-label="Clear POS cart"' in pos

    integrations = (ROOT / "frontend/app/integrations/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Create API key"' in integrations

    expenses = (ROOT / "frontend/app/expenses/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Cancel recurring expense edit"' in expenses


def test_money_json_wired_batch29():
    assert money_json("12.50") == 12.5

    dash_src = Path(dashboard_mod.__file__).read_text(encoding="utf-8")
    assert "month_totals[key] += money_json(total or 0)" in dash_src
    assert "cost_map = {pid: money_json(cost or 0) for pid, cost in cost_rows}" in dash_src
    assert 'daily[d]["sales"] += money_json(total or 0)' in dash_src
    assert 'qty = money_json(it.get("quantity") or 0)' in dash_src
    assert 'unit_price = money_json(it.get("unit_price") or 0)' in dash_src

    aie_src = Path(ai_expenses_mod.__file__).read_text(encoding="utf-8")
    assert "by_cat_vals[key].append(money_json(e.amount or 0))" in aie_src
    assert "by_cat_id_amount[e.category_id] += money_json(e.amount or 0)" in aie_src
    assert "budget = money_json(cat.budget_amount or 0)" in aie_src
    assert "spent = money_json(by_cat_id_amount.get(cat.id, 0)" in aie_src
    assert "amt = money_json(e.amount or 0)" in aie_src
    assert "round(money_json(e.amount or 0), 2)" in aie_src
    assert "sum(money_json(e.amount or 0) for e in rows if e.expense_date and e.expense_date >= mid)" in aie_src

    ais_src = Path(ai_sales_mod.__file__).read_text(encoding="utf-8")
    assert 'row["monetary"] += money_json(b["total"])' in ais_src
    assert 'mon = {cid: money_json(row["monetary"]) for cid, row in cust.items()}' in ais_src
    assert 'months[key] += money_json(b["total"])' in ais_src
    assert 'months[key] += money_json(p["total"])' in ais_src

    aii_src = Path(ai_inventory_mod.__file__).read_text(encoding="utf-8")
    assert 'money_json(p.get("quantity") or 0)' in aii_src
    assert "max(money_json(rq or 0), reorder_qty_map.get(str(pid), 0.0))" in aii_src
    assert "stock = money_json(p.stock_qty or 0)" in aii_src
    assert "sold = money_json(sold_all.get(pid, 0))" in aii_src
    assert "rq = money_json(reorder_qty_map.get(pid, 0))" in aii_src
    assert "reorder_level=money_json(p.reorder_level or 0)" in aii_src
    assert 'money_json(r["stock_qty"]) <= money_json(r["reorder_level"] or 0)' in aii_src

    chq_src = Path(cheques_mod.__file__).read_text(encoding="utf-8")
    assert "amount = money_json(payment.amount)" in chq_src
    assert "customer.balance = money_json(customer.balance or 0) + settlement_base" in chq_src
    assert "inv.paid_amount = max(money_json(inv.paid_amount or 0) - amt, 0)" in chq_src
    assert "supplier.balance = money_json(supplier.balance or 0) + settlement_base" in chq_src
    assert "po.paid_amount = max(money_json(po.paid_amount or 0) - settlement, 0)" in chq_src
    assert "amount = money_json(cheque.amount)" in chq_src
    assert "pay_amount = money_json(payment.amount)" in chq_src

    bal_src = inspect.getsource(accounting_mod.lines_are_balanced)
    assert "money_json(x.get(\"debit\") or 0)" in bal_src
    assert "money_json(x.get(\"credit\") or 0)" in bal_src

    acct_src = Path(accounting_mod.__file__).read_text(encoding="utf-8")
    assert "account.balance = money_json(account.balance or 0) - _signed_balance_delta(" in acct_src
    assert "account.balance = money_json(account.balance or 0) + _signed_balance_delta(" in acct_src
    assert "money_json(invoice.subtotal) - money_json(invoice.discount_amount or 0)" in acct_src
    assert 'qty = money_json(line.get("quantity") or 0)' in acct_src
    assert "revenue = money_json(sales_return.subtotal or 0)" in acct_src

    sug_src = Path(purchase_suggestions_mod.__file__).read_text(encoding="utf-8")
    assert 'qty = money_json(row.get("suggested_order_qty") or 0)' in sug_src
    assert "stock = money_json(row.get(\"stock_qty\") or 0)" in sug_src
    assert "qty = money_json(raw.get(\"quantity\") or 0)" in sug_src

    pr_src = inspect.getsource(purchase_requests_mod.create_request)
    assert 'qty = money_json(item.get("quantity") or 0)' in pr_src

    doc_src = Path(ai_documents_mod.__file__).read_text(encoding="utf-8")
    assert "amt = money_json(amount) if amount is not None else 0.0" in doc_src
    assert "qty = money_json(poi.quantity or 0)" in doc_src

    # payment schedule lives in credit module
    credit_src = Path(credit_mod.__file__).read_text(encoding="utf-8")
    assert "money_json(inv.total_amount) - money_json(inv.paid_amount or 0)" in credit_src
    assert "pct=money_json(ep[\"early_pay_discount_pct\"])" in credit_src

    ai_src = Path(ai_mod.__file__).read_text(encoding="utf-8")
    assert 'sum(money_json(d.get("sales") or 0) for d in daily[-7:])' in ai_src
