"""OpenAPI honesty tips #807–#830: remaining reports/P&L/TB/BS/party money_json + export aria."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from app.honesty import money_json
from app import accounting as accounting_mod
from app import api as api_mod
from app import opening_stock as opening_stock_mod
from app import reports as reports_mod

ROOT = Path(__file__).resolve().parents[2]


def test_honesty_batch7_docs_and_agents():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for title in (
        "Sales by product report money_json Decimal pilot OpenAPI",
        "Sales by customer report money_json Decimal pilot OpenAPI",
        "Sales returns report money_json Decimal pilot OpenAPI",
        "Sales by salesperson report money_json Decimal pilot OpenAPI",
        "Sales by store report money_json Decimal pilot OpenAPI",
        "Sales by department report money_json Decimal pilot OpenAPI",
        "Inventory low-stock report money_json Decimal pilot OpenAPI",
        "Inventory expiry report money_json Decimal pilot OpenAPI",
        "Inventory transfers report money_json Decimal pilot OpenAPI",
        "Inventory stock-counts report money_json Decimal pilot OpenAPI",
        "Purchases summary report money_json Decimal pilot OpenAPI",
        "Purchases pending orders report money_json Decimal pilot OpenAPI",
        "Purchases returns report money_json Decimal pilot OpenAPI",
        "Purchases by supplier report money_json Decimal pilot OpenAPI",
        "Expenses summary report money_json Decimal pilot OpenAPI",
        "Cash flow report money_json Decimal pilot OpenAPI",
        "Balance sheet report money_json Decimal pilot OpenAPI",
        "Trial balance money_json Decimal pilot OpenAPI",
        "Profit and loss money_json Decimal pilot OpenAPI",
        "Party credit/balance money_json Decimal pilot OpenAPI",
        "Opening stock list qty money_json Decimal pilot OpenAPI",
        "Report export CSV aria OpenAPI",
        "Report export Excel aria OpenAPI",
        "Report export PDF aria OpenAPI",
    ):
        assert title in agents, title

    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    standards = docs.split("## 1. API Standards")[1].split("## 2. Authentication")[0]
    assert "money_json" in standards
    assert "by-product" in standards.lower() or "salesperson" in standards.lower()
    assert "cash-flow" in standards.lower() or "balance sheet" in standards.lower()
    assert "trial balance" in standards.lower() or "p&l" in standards.lower() or "P&L" in standards

    reports_page = (ROOT / "frontend/app/reports/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Export report CSV"' in reports_page
    assert 'aria-label="Export report Excel"' in reports_page
    assert 'aria-label="Export report PDF"' in reports_page


def test_money_json_helper_batch7():
    assert money_json("19.99") == 19.99
    assert money_json(None) == 0.0
    with pytest.raises(ValueError):
        money_json(float("nan"))


def test_money_json_wired_batch7_serializers():
    assert "money_json" in inspect.getsource(reports_mod.sales_by_product)
    assert "money_json" in inspect.getsource(reports_mod.sales_by_customer)
    assert "money_json" in inspect.getsource(reports_mod.sales_returns_summary)
    assert "money_json" in inspect.getsource(reports_mod.sales_by_salesperson)
    assert "money_json" in inspect.getsource(reports_mod.sales_by_store)
    assert "money_json" in inspect.getsource(reports_mod.sales_by_department)
    assert "money_json" in inspect.getsource(reports_mod.inventory_low_stock)
    assert "money_json" in inspect.getsource(reports_mod.inventory_expiry)
    assert "money_json" in inspect.getsource(reports_mod.inventory_transfers)
    assert "money_json" in inspect.getsource(reports_mod.inventory_stock_counts)
    assert "money_json" in inspect.getsource(reports_mod.purchases_summary)
    assert "money_json" in inspect.getsource(reports_mod.purchases_pending_orders)
    assert "money_json" in inspect.getsource(reports_mod.purchases_returns_summary)
    assert "money_json" in inspect.getsource(reports_mod.purchases_by_supplier)
    assert "money_json" in inspect.getsource(reports_mod.expenses_summary)
    assert "money_json" in inspect.getsource(reports_mod.cash_flow)
    assert "money_json" in inspect.getsource(reports_mod._pack_balance_sheet)
    assert "money_json" in inspect.getsource(reports_mod._merge_bs_compare)
    assert "money_json" in inspect.getsource(reports_mod._balance_sheet_at)
    assert "money_json" in inspect.getsource(accounting_mod.trial_balance)
    assert "money_json" in inspect.getsource(accounting_mod._pnl_pack)
    assert "money_json" in inspect.getsource(accounting_mod.profit_and_loss)
    assert "money_json" in inspect.getsource(api_mod._serialize_party)
    assert "money_json" in inspect.getsource(opening_stock_mod.list_opening_stock_movements)
