"""OpenAPI honesty tips #753–#779: reference/description defense + money_json + residual aria."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.honesty import money_json, optional_honest_narrative, require_honest_narrative
from app import accounting as accounting_mod
from app import api as api_mod
from app import bank_recon as bank_recon_mod
from app import cash_transfers as cash_transfers_mod
from app import catalog as catalog_mod
from app import credit as credit_mod
from app import expenses as expenses_mod
from app import inventory as inventory_mod
from app import invoice_print as invoice_print_mod
from app import opening_balances as opening_balances_mod
from app import opening_stock as opening_stock_mod
from app import pos as pos_mod
from app import print_branding as print_branding_mod
from app import purchase_requests as purchase_requests_mod
from app import purchasing as purchasing_mod
from app import receipts as receipts_mod
from app import sales as sales_mod
from app import stores as stores_mod

ROOT = Path(__file__).resolve().parents[2]


def test_honesty_batch5_docs_and_agents():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for title in (
        "Expense description defense-in-depth OpenAPI",
        "Expense payee defense-in-depth OpenAPI",
        "Expense reference defense-in-depth OpenAPI",
        "Cash transfer reference defense-in-depth OpenAPI",
        "Journal reference defense-in-depth OpenAPI",
        "Payment reference defense-in-depth OpenAPI",
        "POS payment reference defense-in-depth OpenAPI",
        "Opening balance reference defense-in-depth OpenAPI",
        "Opening stock reference defense-in-depth OpenAPI",
        "Product description defense-in-depth OpenAPI",
        "Approval matrix label defense-in-depth OpenAPI",
        "Purchase request department defense-in-depth OpenAPI",
        "Bank statement line external_ref defense-in-depth OpenAPI",
        "Print header/footer text defense-in-depth OpenAPI",
        "Credit AR aging money_json Decimal pilot OpenAPI",
        "Credit AP aging money_json Decimal pilot OpenAPI",
        "Credit statement money_json Decimal pilot OpenAPI",
        "Credit history money_json Decimal pilot OpenAPI",
        "POS receipt money_json Decimal pilot OpenAPI",
        "Invoice print money_json Decimal pilot OpenAPI",
        "Inventory warehouse stock money_json Decimal pilot OpenAPI",
        "Stock-in/out response money_json Decimal pilot OpenAPI",
        "Opening balance response money_json Decimal pilot OpenAPI",
        "Store inventory stock money_json Decimal pilot OpenAPI",
        "Product cost price aria OpenAPI",
        "Edit product cost price aria OpenAPI",
        "Variant cost price aria OpenAPI",
    ):
        assert title in agents, title

    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    standards = docs.split("## 1. API Standards")[1].split("## 2. Authentication")[0]
    assert "money_json" in standards
    assert "credit AR/AP aging" in standards.lower() or "credit" in standards.lower()
    assert "invoice print" in standards.lower()
    assert "warehouse stock" in standards.lower()

    inventory = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Product cost price"' in inventory
    assert 'aria-label="Edit product cost price"' in inventory
    assert "aria-label={`Variant cost price" in inventory


def test_optional_and_require_helpers_still_exported():
    assert optional_honest_narrative(None, label="reference") is None
    assert optional_honest_narrative("REF-1", label="reference") == "REF-1"
    with pytest.raises(HTTPException) as exc:
        optional_honest_narrative("!!!", label="reference")
    assert exc.value.status_code == 400
    assert require_honest_narrative("Journal OK", label="journal description", min_length=2) == "Journal OK"
    assert callable(money_json)


def test_services_wire_optional_honest_narrative_batch5():
    assert "optional_honest_narrative" in inspect.getsource(expenses_mod.create_expense)
    assert "optional_honest_narrative" in inspect.getsource(expenses_mod.update_expense)
    assert "optional_honest_narrative" in inspect.getsource(expenses_mod.create_recurring)
    assert "optional_honest_narrative" in inspect.getsource(expenses_mod.update_recurring)
    assert "optional_honest_narrative" in inspect.getsource(expenses_mod.normalize_approval_matrix)
    assert "optional_honest_narrative" in inspect.getsource(cash_transfers_mod.create_transfer)
    assert "optional_honest_narrative" in inspect.getsource(accounting_mod.post_journal_entry)
    assert "optional_honest_narrative" in inspect.getsource(sales_mod.record_customer_payment)
    assert "optional_honest_narrative" in inspect.getsource(purchasing_mod.record_supplier_payment)
    assert "optional_honest_narrative" in inspect.getsource(pos_mod.resolve_sale_payments)
    assert "optional_honest_narrative" in inspect.getsource(opening_balances_mod.post_coa_opening_balances)
    assert "optional_honest_narrative" in inspect.getsource(opening_stock_mod.post_opening_stock)
    assert "optional_honest_narrative" in inspect.getsource(purchase_requests_mod.create_request)
    assert "optional_honest_narrative" in inspect.getsource(
        purchase_requests_mod.normalize_approval_matrix
    )
    assert "optional_honest_narrative" in inspect.getsource(bank_recon_mod.create_statement)
    assert "optional_honest_narrative" in inspect.getsource(
        print_branding_mod.apply_print_branding_update
    )
    assert "optional_honest_narrative" in inspect.getsource(api_mod.add_product)
    assert "optional_honest_narrative" in inspect.getsource(api_mod.patch_product)


def test_money_json_wired_batch5_serializers():
    assert "money_json" in inspect.getsource(credit_mod.ar_aging)
    assert "money_json" in inspect.getsource(credit_mod.ap_aging)
    assert "money_json" in inspect.getsource(credit_mod.customer_statement)
    assert "money_json" in inspect.getsource(credit_mod.supplier_statement)
    assert "money_json" in inspect.getsource(credit_mod.customer_history)
    assert "money_json" in inspect.getsource(credit_mod.supplier_history)
    assert "money_json" in inspect.getsource(receipts_mod.build_receipt_payload)
    assert "money_json" in inspect.getsource(invoice_print_mod.build_invoice_print_payload)
    assert "money_json" in inspect.getsource(inventory_mod.list_warehouse_stock)
    assert "money_json" in inspect.getsource(inventory_mod.list_product_warehouse_stock)
    assert "money_json" in inspect.getsource(catalog_mod.stock_in_with_batch)
    assert "money_json" in inspect.getsource(catalog_mod.stock_out_with_batch)
    assert "money_json" in inspect.getsource(opening_balances_mod.post_coa_opening_balances)
    assert "money_json" in inspect.getsource(stores_mod.store_inventory)
    assert "float(tx.subtotal" not in inspect.getsource(receipts_mod.build_receipt_payload)
    assert "float(invoice.subtotal" not in inspect.getsource(
        invoice_print_mod.build_invoice_print_payload
    )
