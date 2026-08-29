"""OpenAPI honesty tips #668–#692: free-text defense-in-depth + money_json pilots + residual aria."""

from __future__ import annotations

import inspect
from pathlib import Path

from app.honesty import require_honest_narrative
from app import accounting as accounting_mod
from app import cash_drawer as cash_drawer_mod
from app import cheques as cheques_mod
from app import credit as credit_mod
from app import expenses as expenses_mod
from app import purchase_requests as purchase_requests_mod
from app import purchasing as purchasing_mod
from app import sales as sales_mod
from app import sales_docs as sales_docs_mod
from app import stock_counts as stock_counts_mod
from app import stores as stores_mod

ROOT = Path(__file__).resolve().parents[2]


def test_honesty_batch2_docs_and_agents():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for title in (
        "Quotation reject reason defense-in-depth OpenAPI",
        "Purchase request reject reason defense-in-depth OpenAPI",
        "Stock transfer reject/cancel reason defense-in-depth OpenAPI",
        "Sales invoice cancel reason defense-in-depth OpenAPI",
        "Sales order cancel reason defense-in-depth OpenAPI",
        "Sales return cancel reason defense-in-depth OpenAPI",
        "PO cancel reason defense-in-depth OpenAPI",
        "PO amend reason defense-in-depth OpenAPI",
        "PI cancel reason defense-in-depth OpenAPI",
        "Purchase return cancel reason defense-in-depth OpenAPI",
        "Stock count cancel reason defense-in-depth OpenAPI",
        "GRN rejection reason defense-in-depth OpenAPI",
        "Credit override reason defense-in-depth OpenAPI",
        "POS drawer open reason defense-in-depth OpenAPI",
        "Cheque money_json Decimal pilot OpenAPI",
        "Expense money_json Decimal pilot OpenAPI",
        "Journal money_json Decimal pilot OpenAPI",
        "Quotation money_json Decimal pilot OpenAPI",
        "Purchase order money_json Decimal pilot OpenAPI",
        "Payment FX rate aria OpenAPI",
        "Payment terms days aria OpenAPI",
        "Customer credit limit aria OpenAPI",
        "Purchase request quantity aria OpenAPI",
        "Purchase order qty/price aria OpenAPI",
        "Purchase invoice qty/price aria OpenAPI",
        "Tax calculator amount aria OpenAPI",
    ):
        assert title in agents, title

    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    standards = docs.split("## 1. API Standards")[1].split("## 2. Authentication")[0]
    assert "money_json" in standards
    assert "quotation" in standards.lower() or "purchase order" in standards.lower()

    sales = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Customer credit limit"' in sales

    purchasing = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Purchase request quantity"' in purchasing
    assert 'aria-label="Purchase order quantity"' in purchasing
    assert 'aria-label="Purchase order unit price"' in purchasing
    assert 'aria-label="Purchase invoice quantity"' in purchasing
    assert 'aria-label="Purchase invoice unit price"' in purchasing

    tax = (ROOT / "frontend/app/tax/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Tax calculator amount"' in tax

    credit = (ROOT / "frontend/app/credit/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Payment FX rate"' in credit
    assert 'aria-label="Customer payment terms days"' in credit
    assert 'aria-label="Supplier payment terms days"' in credit


def test_services_wire_require_honest_narrative_batch2():
    assert "require_honest_narrative" in inspect.getsource(sales_mod.cancel_sales_invoice)
    assert "require_honest_narrative" in inspect.getsource(sales_docs_mod.reject_quotation)
    assert "require_honest_narrative" in inspect.getsource(sales_docs_mod.cancel_order)
    assert "require_honest_narrative" in inspect.getsource(sales_docs_mod.cancel_return)
    assert "require_honest_narrative" in inspect.getsource(stores_mod.reject_transfer)
    assert "require_honest_narrative" in inspect.getsource(stores_mod.cancel_transfer)
    assert "require_honest_narrative" in inspect.getsource(purchase_requests_mod.reject_request)
    assert "require_honest_narrative" in inspect.getsource(purchasing_mod.cancel_purchase_order)
    assert "require_honest_narrative" in inspect.getsource(purchasing_mod.amend_purchase_order)
    assert "require_honest_narrative" in inspect.getsource(purchasing_mod.cancel_purchase_invoice)
    assert "require_honest_narrative" in inspect.getsource(purchasing_mod.cancel_purchase_return)
    assert "require_honest_narrative" in inspect.getsource(stock_counts_mod.cancel_count)
    assert "require_honest_narrative" in inspect.getsource(credit_mod.enforce_customer_credit_limit)
    assert "require_honest_narrative" in inspect.getsource(cash_drawer_mod.open_drawer)
    assert "require_honest_narrative" in inspect.getsource(purchasing_mod.create_grn)


def test_money_json_pilots_batch2():
    assert "money_json" in inspect.getsource(sales_docs_mod.serialize_quotation)
    assert "float(quote.subtotal)" not in inspect.getsource(sales_docs_mod.serialize_quotation)
    assert "money_json" in inspect.getsource(purchasing_mod.serialize_po)
    assert "float(po.subtotal)" not in inspect.getsource(purchasing_mod.serialize_po)
    assert "money_json" in inspect.getsource(expenses_mod.serialize_expense)
    assert "money_json" in inspect.getsource(expenses_mod.serialize_recurring)
    assert "money_json" in inspect.getsource(cheques_mod.serialize_cheque)
    assert "money_json" in inspect.getsource(accounting_mod.serialize_journal)
    assert callable(require_honest_narrative)
