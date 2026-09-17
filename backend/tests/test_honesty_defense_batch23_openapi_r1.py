"""OpenAPI honesty tips #1343–#1382: dashboard/packages/AI money_json + residual tab aria."""

from __future__ import annotations

import inspect
from pathlib import Path

from app.honesty import money_json
from app import ai_documents as ai_documents_mod
from app import ai_expenses as ai_expenses_mod
from app import ai_sales as ai_sales_mod
from app import dashboard as dashboard_mod
from app import packages as packages_mod
from app import reports as reports_mod

ROOT = Path(__file__).resolve().parents[2]


def test_honesty_batch23_docs_and_agents():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for title in (
        "Dashboard sales_today_pct money_json Decimal pilot OpenAPI",
        "Dashboard sales_mtd_pct money_json Decimal pilot OpenAPI",
        "Packages years_assigned money_json Decimal pilot OpenAPI",
        "Packages years_used money_json Decimal pilot OpenAPI",
        "Packages years_remaining money_json Decimal pilot OpenAPI",
        "AI document name_similarity money_json Decimal pilot OpenAPI",
        "AI document party match score money_json Decimal pilot OpenAPI",
        "AI document PO match score money_json Decimal pilot OpenAPI",
        "Inventory balance aggregated quantity money_json Decimal pilot OpenAPI",
        "Inventory balance item value zero money_json Decimal pilot OpenAPI",
        "Inventory low-stock product suggested zero money_json Decimal pilot OpenAPI",
        "AI sales RFM monetary money_json Decimal pilot OpenAPI",
        "AI sales monthly series total money_json Decimal pilot OpenAPI",
        "AI sales forecast_next_month money_json Decimal pilot OpenAPI",
        "AI sales seasonality stable ratio money_json Decimal pilot OpenAPI",
        "AI expenses budget_scaled money_json Decimal pilot OpenAPI",
        "AI expenses spent money_json Decimal pilot OpenAPI",
        "AI expenses variance_pct money_json Decimal pilot OpenAPI",
        "Sales returns by_reason quantity money_json Decimal pilot OpenAPI",
        "Sales returns by_customer quantity money_json Decimal pilot OpenAPI",
        "Purchases returns by_reason quantity money_json Decimal pilot OpenAPI",
        "Purchases returns by_supplier quantity money_json Decimal pilot OpenAPI",
        "Inventory balance item cost_price money_json Decimal pilot OpenAPI",
        "Inventory Show lookup tab aria OpenAPI",
        "Inventory Show import tab aria OpenAPI",
        "Inventory Show opening tab aria OpenAPI",
        "Inventory Show stockout tab aria OpenAPI",
        "Inventory Show whstock tab aria OpenAPI",
        "Inventory Show expiry tab aria OpenAPI",
        "Inventory Show adjust tab aria OpenAPI",
        "Reports Show salesperson tab aria OpenAPI",
        "Reports Show customers tab aria OpenAPI",
        "Reports Show stores tab aria OpenAPI",
        "Reports Show departments tab aria OpenAPI",
        "Reports Show expenses tab aria OpenAPI",
        "Reports Show cashflow tab aria OpenAPI",
        "Reports Show pnl tab aria OpenAPI",
        "Reports Show trialbalance tab aria OpenAPI",
        "Reports Show balancesheet tab aria OpenAPI",
        "Reports Show schedules tab aria OpenAPI",
    ):
        assert title in agents, title

    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    standards = docs.split("## 1. API Standards")[1].split("## 2.")[0]
    assert "sales_today_pct" in standards
    assert "years_assigned" in standards
    assert "forecast_next_month" in standards or "RFM monetary" in standards

    inventory = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label={`Show inventory ${id} tab`}' in inventory

    reports = (ROOT / "frontend/app/reports/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label={`Show reports ${id} tab`}' in reports


def test_money_json_wired_batch23():
    assert money_json("12.50") == 12.5

    pct_src = inspect.getsource(dashboard_mod._pct_change)
    assert "money_json(100)" in pct_src
    assert "money_json(round((current - previous)" in pct_src

    pkg_src = inspect.getsource(packages_mod.usage_snapshot)
    assert "years_assigned = money_json(round(months_assigned / 12, 2))" in pkg_src
    assert "years_used = money_json(round(months_used / 12, 2))" in pkg_src
    assert "years_remaining = money_json(round(months_remaining / 12, 2))" in pkg_src

    sim_src = inspect.getsource(ai_documents_mod.name_similarity)
    assert "return money_json(round(max(j, cover * 0.85), 3))" in sim_src

    party_src = inspect.getsource(ai_documents_mod.match_parties)
    assert '"score": money_json(round(score, 3))' in party_src

    po_src = inspect.getsource(ai_documents_mod.match_purchase_orders)
    assert "money_json(1) if po_n.upper() in blob else money_json(0.8)" in po_src

    bal_src = inspect.getsource(reports_mod.inventory_balance)
    assert 'row["quantity"] = money_json(' in bal_src
    assert '"value": money_json(0)' in bal_src
    assert '"cost_price": money_json(product.cost_price)' in bal_src

    low_src = inspect.getsource(reports_mod.inventory_low_stock)
    assert "else money_json(0)" in low_src

    rfm_src = inspect.getsource(ai_sales_mod.build_rfm)
    assert '"monetary": money_json(round(money_json(row["monetary"]), 2))' in rfm_src

    sales_src = inspect.getsource(ai_sales_mod.sales_analysis)
    assert '"total": money_json(round(money_json(v), 2))' in sales_src
    assert "forecast_next = money_json(round(" in sales_src
    assert '"ratio": money_json(1)' in sales_src
    assert "forecast_next = money_json(0)" in sales_src

    exp_src = inspect.getsource(ai_expenses_mod.expense_analysis)
    assert "money_json(round((spent - scaled) / scaled * 100.0, 1))" in exp_src
    assert '"budget_scaled": money_json(round(money_json(scaled), 2))' in exp_src
    assert '"spent": money_json(round(money_json(spent), 2))' in exp_src

    sret_src = inspect.getsource(reports_mod.sales_returns_summary)
    assert 'row["quantity"] = money_json(round(row["quantity"], 3))' in sret_src

    pret_src = inspect.getsource(reports_mod.purchases_returns_summary)
    assert 'row["quantity"] = money_json(round(row["quantity"], 3))' in pret_src
