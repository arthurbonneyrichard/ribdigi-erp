"""OpenAPI honesty tips #693–#717: free-text defense-in-depth + money_json pilots + residual aria."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.honesty import optional_honest_narrative, require_honest_narrative
from app import bank_recon as bank_recon_mod
from app import cash_transfers as cash_transfers_mod
from app import expenses as expenses_mod
from app import fx as fx_mod
from app import pos as pos_mod
from app import purchase_requests as purchase_requests_mod
from app import purchasing as purchasing_mod
from app import sales_docs as sales_docs_mod
from app import stock_counts as stock_counts_mod
from app import stores as stores_mod

ROOT = Path(__file__).resolve().parents[2]


def test_honesty_batch3_docs_and_agents():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for title in (
        "Optional narrative defense-in-depth OpenAPI",
        "Expense approve comment defense-in-depth OpenAPI",
        "POS shift close notes defense-in-depth OpenAPI",
        "Cash transfer notes defense-in-depth OpenAPI",
        "Stock count notes defense-in-depth OpenAPI",
        "Sales order money_json Decimal pilot OpenAPI",
        "Sales return money_json Decimal pilot OpenAPI",
        "Purchase invoice money_json Decimal pilot OpenAPI",
        "Purchase return money_json Decimal pilot OpenAPI",
        "GRN money_json Decimal pilot OpenAPI",
        "Cash account/transfer money_json Decimal pilot OpenAPI",
        "Bank statement money_json Decimal pilot OpenAPI",
        "POS payment/drawer money_json Decimal pilot OpenAPI",
        "FX rate money_json Decimal pilot OpenAPI",
        "Purchase request qty money_json Decimal pilot OpenAPI",
        "Stock count qty money_json Decimal pilot OpenAPI",
        "Stock transfer qty money_json Decimal pilot OpenAPI",
        "Company inactivity timeout aria OpenAPI",
        "Company store allocation aria OpenAPI",
        "Report schedule hour UTC aria OpenAPI",
        "Sales customer payment terms days aria OpenAPI",
        "Stock count line notes defense-in-depth OpenAPI",
        "Purchase order line discount aria OpenAPI",
        "Purchase invoice FX/tax aria OpenAPI",
    ):
        assert title in agents, title

    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    standards = docs.split("## 1. API Standards")[1].split("## 2. Authentication")[0]
    assert "money_json" in standards
    assert "sales order" in standards.lower() or "purchase invoice" in standards.lower()

    company = (ROOT / "frontend/app/company/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Company inactivity timeout minutes"' in company

    reports = (ROOT / "frontend/app/reports/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Report schedule hour UTC"' in reports

    stores = (ROOT / "frontend/app/stores/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Company store allocation"' in stores

    purchasing = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Purchase order line discount"' in purchasing
    assert 'aria-label="PO amend unit price"' in purchasing
    assert 'aria-label="PO amend line discount"' in purchasing
    assert 'aria-label="Purchase invoice FX rate"' in purchasing
    assert 'aria-label="Purchase invoice tax rate percent"' in purchasing

    sales = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Customer payment terms days"' in sales


def test_optional_honest_narrative():
    assert optional_honest_narrative(None, label="notes") is None
    assert optional_honest_narrative("   ", label="notes") is None
    assert optional_honest_narrative("Shift ok A1", label="notes") == "Shift ok A1"
    for bad in ("!!!", "http://evil", "@@@@"):
        with pytest.raises(HTTPException) as exc:
            optional_honest_narrative(bad, label="notes")
        assert exc.value.status_code == 400
        assert "plain narrative" in exc.value.detail
    assert callable(require_honest_narrative)


def test_services_wire_optional_honest_narrative_batch3():
    assert "optional_honest_narrative" in inspect.getsource(expenses_mod.approve_expense)
    assert "optional_honest_narrative" in inspect.getsource(pos_mod.close_session)
    assert "optional_honest_narrative" in inspect.getsource(cash_transfers_mod.create_transfer)
    assert "optional_honest_narrative" in inspect.getsource(stock_counts_mod.create_count)
    assert "optional_honest_narrative" in inspect.getsource(stock_counts_mod.update_count_items)


def test_money_json_pilots_batch3():
    assert "money_json" in inspect.getsource(sales_docs_mod.serialize_order)
    assert "float(order.subtotal)" not in inspect.getsource(sales_docs_mod.serialize_order)
    assert "money_json" in inspect.getsource(sales_docs_mod.serialize_return)
    assert "float(ret.subtotal)" not in inspect.getsource(sales_docs_mod.serialize_return)
    assert "money_json" in inspect.getsource(purchasing_mod.serialize_purchase_invoice)
    assert "float(inv.subtotal)" not in inspect.getsource(purchasing_mod.serialize_purchase_invoice)
    assert "money_json" in inspect.getsource(purchasing_mod.serialize_purchase_return)
    assert "money_json" in inspect.getsource(purchasing_mod.serialize_grn)
    assert "money_json" in inspect.getsource(pos_mod.serialize_payment)
    assert "money_json" in inspect.getsource(pos_mod.drawer_summary)
    assert "money_json" in inspect.getsource(cash_transfers_mod.serialize_transfer)
    assert "money_json" in inspect.getsource(cash_transfers_mod.serialize_account)
    assert "money_json" in inspect.getsource(bank_recon_mod.serialize_line)
    assert "money_json" in inspect.getsource(bank_recon_mod.serialize_statement)
    assert "money_json" in inspect.getsource(purchase_requests_mod.serialize_request)
    assert "money_json" in inspect.getsource(stores_mod.serialize_transfer)
    assert "money_json" in inspect.getsource(stock_counts_mod.serialize_item)
    assert "money_json" in inspect.getsource(fx_mod.serialize_rate)
