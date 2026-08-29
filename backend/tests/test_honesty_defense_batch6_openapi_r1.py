"""OpenAPI honesty tips #780–#806: batch/ref/party/POS/bank/cheque defense + reports/dashboard/AI money_json + tax aria."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.honesty import money_json, optional_honest_narrative
from app import api as api_mod
from app import bank_connectors as bank_connectors_mod
from app import catalog as catalog_mod
from app import cheques as cheques_mod
from app import dashboard as dashboard_mod
from app import opening_stock as opening_stock_mod
from app import purchasing as purchasing_mod
from app import reports as reports_mod
from app import tax as tax_mod
from app import ai_customer as ai_customer_mod
from app import ai_expenses as ai_expenses_mod
from app import ai_inventory as ai_inventory_mod
from app import ai_sales as ai_sales_mod

ROOT = Path(__file__).resolve().parents[2]


def test_honesty_batch6_docs_and_agents():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for title in (
        "Batch number defense-in-depth OpenAPI",
        "Stock-in reference_type defense-in-depth OpenAPI",
        "Stock movement reference_id defense-in-depth OpenAPI",
        "POS customer_name defense-in-depth OpenAPI",
        "Bank connection display_name defense-in-depth OpenAPI",
        "Bank external_account_id defense-in-depth OpenAPI",
        "Party code defense-in-depth OpenAPI",
        "Party category defense-in-depth OpenAPI",
        "Party address defense-in-depth OpenAPI",
        "Cheque number defense-in-depth OpenAPI",
        "Cheque bank_name defense-in-depth OpenAPI",
        "Sales daily report money_json Decimal pilot OpenAPI",
        "Sales monthly report money_json Decimal pilot OpenAPI",
        "Inventory balance report money_json Decimal pilot OpenAPI",
        "Inventory valuation report money_json Decimal pilot OpenAPI",
        "Inventory movements report money_json Decimal pilot OpenAPI",
        "Budget vs actual report money_json Decimal pilot OpenAPI",
        "Dashboard money_json Decimal pilot OpenAPI",
        "AI inventory predictions money_json Decimal pilot OpenAPI",
        "AI sales analysis money_json Decimal pilot OpenAPI",
        "AI expenses analysis money_json Decimal pilot OpenAPI",
        "AI customer assist money_json Decimal pilot OpenAPI",
        "Tax calculate money_json Decimal pilot OpenAPI",
        "Tax report money_json Decimal pilot OpenAPI",
        "Opening stock response money_json Decimal pilot OpenAPI",
        "Tax reverse charge aria OpenAPI",
        "Tax calculate button aria OpenAPI",
    ):
        assert title in agents, title

    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    standards = docs.split("## 1. API Standards")[1].split("## 2. Authentication")[0]
    assert "money_json" in standards
    assert "dashboard" in standards.lower()
    assert "sales daily" in standards.lower() or "inventory balance" in standards.lower()

    tax_page = (ROOT / "frontend/app/tax/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Tax reverse charge"' in tax_page
    assert 'aria-label="Calculate tax"' in tax_page


def test_optional_helpers_and_money_json_batch6():
    assert optional_honest_narrative(None, label="batch number") is None
    assert optional_honest_narrative("LOT-1", label="batch number") == "LOT-1"
    with pytest.raises(HTTPException) as exc:
        optional_honest_narrative("!!!", label="batch number")
    assert exc.value.status_code == 400
    assert money_json("12.50") == 12.5
    assert callable(money_json)


def test_services_wire_optional_honest_narrative_batch6():
    assert "optional_honest_narrative" in inspect.getsource(catalog_mod.stock_in_with_batch)
    assert "optional_honest_narrative" in inspect.getsource(catalog_mod.stock_out_with_batch)
    assert "optional_honest_narrative" in inspect.getsource(purchasing_mod.create_grn)
    assert "optional_honest_narrative" in inspect.getsource(api_mod._normalize_party_profile)
    assert "optional_honest_narrative" in inspect.getsource(
        bank_connectors_mod.create_connection
    )
    assert "optional_honest_narrative" in inspect.getsource(
        bank_connectors_mod.update_connection
    )
    assert "optional_honest_narrative" in inspect.getsource(
        cheques_mod.create_from_customer_payment
    )
    assert "optional_honest_narrative" in inspect.getsource(
        cheques_mod.create_from_supplier_payment
    )
    # POS customer_name defense lives in the sale create handler source.
    assert "POS customer name" in inspect.getsource(api_mod)


def test_money_json_wired_batch6_serializers():
    assert "money_json" in inspect.getsource(reports_mod.sales_daily)
    assert "money_json" in inspect.getsource(reports_mod.sales_monthly)
    assert "money_json" in inspect.getsource(reports_mod.inventory_balance)
    assert "money_json" in inspect.getsource(reports_mod.inventory_valuation)
    assert "money_json" in inspect.getsource(reports_mod.inventory_movements)
    assert "money_json" in inspect.getsource(reports_mod.budget_vs_actual)
    assert "money_json" in inspect.getsource(dashboard_mod.build_dashboard)
    assert "money_json" in inspect.getsource(ai_inventory_mod.build_product_forecasts)
    assert "money_json" in inspect.getsource(ai_sales_mod.sales_analysis)
    assert "money_json" in inspect.getsource(ai_expenses_mod.expense_analysis)
    assert "money_json" in inspect.getsource(ai_customer_mod.customer_assist)
    assert "money_json" in inspect.getsource(tax_mod.compute_tax_breakdown)
    assert "money_json" in inspect.getsource(tax_mod.tax_report)
    assert "money_json" in inspect.getsource(opening_stock_mod.post_opening_stock)
