"""OpenAPI honesty tips #719–#752: optional notes defense + money_json + residual aria."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.honesty import money_json, optional_honest_narrative, require_honest_narrative
from app import accounting as accounting_mod
from app import backup as backup_mod
from app import bank_recon as bank_recon_mod
from app import catalog as catalog_mod
from app import catalog_meta as catalog_meta_mod
from app import customer_groups as customer_groups_mod
from app import expenses as expenses_mod
from app import inventory as inventory_mod
from app import opening_balances as opening_balances_mod
from app import opening_stock as opening_stock_mod
from app import purchase_ocr as purchase_ocr_mod
from app import purchase_requests as purchase_requests_mod
from app import purchasing as purchasing_mod
from app import sales as sales_mod
from app import sales_docs as sales_docs_mod
from app import stores as stores_mod
from app import tax as tax_mod
from app import tenants as tenants_mod
from app import warehouses as warehouses_mod
from app import webhooks as webhooks_mod

ROOT = Path(__file__).resolve().parents[2]


def test_honesty_batch4_docs_and_agents():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for title in (
        "Purchase order notes defense-in-depth OpenAPI",
        "GRN notes defense-in-depth OpenAPI",
        "Purchase return notes defense-in-depth OpenAPI",
        "Purchase invoice notes defense-in-depth OpenAPI",
        "Sales document notes defense-in-depth OpenAPI",
        "Sales return notes defense-in-depth OpenAPI",
        "Payment notes defense-in-depth OpenAPI",
        "Stock transfer notes defense-in-depth OpenAPI",
        "Purchase request notes defense-in-depth OpenAPI",
        "Bank statement notes/line description defense-in-depth OpenAPI",
        "Bank clear-group notes defense-in-depth OpenAPI",
        "Backup notes defense-in-depth OpenAPI",
        "Webhook description defense-in-depth OpenAPI",
        "Brand description defense-in-depth OpenAPI",
        "Stock movement notes defense-in-depth OpenAPI",
        "Opening stock notes defense-in-depth OpenAPI",
        "Opening balance notes defense-in-depth OpenAPI",
        "Journal description defense-in-depth OpenAPI",
        "Product money_json Decimal pilot OpenAPI",
        "Variant money_json Decimal pilot OpenAPI",
        "Batch qty money_json Decimal pilot OpenAPI",
        "Tax rate money_json Decimal pilot OpenAPI",
        "Expense category budget money_json Decimal pilot OpenAPI",
        "Customer group discount money_json Decimal pilot OpenAPI",
        "Unit conversion money_json Decimal pilot OpenAPI",
        "Tenant threshold money_json Decimal pilot OpenAPI",
        "Warehouse capacity money_json Decimal pilot OpenAPI",
        "Variant selling price aria OpenAPI",
        "Opening stock unit cost aria OpenAPI",
        "Stock transfer quantity aria OpenAPI",
        "Supplier payment terms days aria OpenAPI",
        "Purchase return quantity aria OpenAPI",
        "Sales invoice FX rate aria OpenAPI",
        "Sales invoice pay amount aria OpenAPI",
    ):
        assert title in agents, title

    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    standards = docs.split("## 1. API Standards")[1].split("## 2. Authentication")[0]
    assert "money_json" in standards
    assert "product/variant/batch" in standards.lower() or "product" in standards.lower()
    assert "warehouse capacity" in standards.lower()

    inventory = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert "aria-label={`Variant selling price" in inventory
    assert 'aria-label="Opening stock unit cost"' in inventory
    assert 'aria-label="Stock transfer quantity"' in inventory

    purchasing = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Supplier payment terms days"' in purchasing
    assert 'aria-label="Purchase return quantity"' in purchasing

    sales = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Sales invoice FX rate"' in sales
    assert "aria-label={`Sales invoice pay amount" in sales

    stores = (ROOT / "frontend/app/stores/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Stock transfer quantity"' in stores


def test_optional_and_require_helpers_still_exported():
    assert optional_honest_narrative(None, label="notes") is None
    assert optional_honest_narrative("OK notes", label="notes") == "OK notes"
    with pytest.raises(HTTPException) as exc:
        optional_honest_narrative("!!!", label="notes")
    assert exc.value.status_code == 400
    assert require_honest_narrative("Journal OK", label="journal description", min_length=2) == "Journal OK"
    assert callable(money_json)


def test_services_wire_optional_honest_narrative_batch4():
    assert "optional_honest_narrative" in inspect.getsource(purchasing_mod.create_purchase_order)
    assert "optional_honest_narrative" in inspect.getsource(purchasing_mod.amend_purchase_order)
    assert "optional_honest_narrative" in inspect.getsource(purchasing_mod.create_grn)
    assert "optional_honest_narrative" in inspect.getsource(purchasing_mod.create_purchase_return)
    assert "optional_honest_narrative" in inspect.getsource(purchasing_mod.create_purchase_invoice)
    assert "optional_honest_narrative" in inspect.getsource(purchasing_mod.record_supplier_payment)
    assert "optional_honest_narrative" in inspect.getsource(sales_docs_mod.create_quotation)
    assert "optional_honest_narrative" in inspect.getsource(sales_docs_mod.create_order)
    assert "optional_honest_narrative" in inspect.getsource(sales_docs_mod.create_return)
    assert "optional_honest_narrative" in inspect.getsource(sales_mod.create_sales_invoice)
    assert "optional_honest_narrative" in inspect.getsource(sales_mod.record_customer_payment)
    assert "optional_honest_narrative" in inspect.getsource(stores_mod.create_transfer)
    assert "optional_honest_narrative" in inspect.getsource(purchase_requests_mod.create_request)
    assert "optional_honest_narrative" in inspect.getsource(bank_recon_mod.create_statement)
    assert "optional_honest_narrative" in inspect.getsource(bank_recon_mod.create_clearing_group)
    assert "optional_honest_narrative" in inspect.getsource(backup_mod.create_backup)
    assert "optional_honest_narrative" in inspect.getsource(webhooks_mod.create_endpoint)
    assert "optional_honest_narrative" in inspect.getsource(webhooks_mod.update_endpoint)
    assert "optional_honest_narrative" in inspect.getsource(catalog_meta_mod.create_brand)
    assert "optional_honest_narrative" in inspect.getsource(catalog_meta_mod.update_brand)
    assert "optional_honest_narrative" in inspect.getsource(catalog_mod.stock_in_with_batch)
    assert "optional_honest_narrative" in inspect.getsource(catalog_mod.stock_out_with_batch)
    assert "optional_honest_narrative" in inspect.getsource(inventory_mod.apply_stock_change)
    assert "optional_honest_narrative" in inspect.getsource(opening_stock_mod.post_opening_stock)
    assert "optional_honest_narrative" in inspect.getsource(opening_balances_mod.post_coa_opening_balances)
    assert "require_honest_narrative" in inspect.getsource(accounting_mod.post_journal_entry)
    assert "optional_honest_narrative" in inspect.getsource(accounting_mod.post_journal_entry)
    assert "optional_honest_narrative" in inspect.getsource(purchase_ocr_mod.update_purchase_invoice_draft)


def test_money_json_pilots_batch4():
    assert "money_json" in inspect.getsource(catalog_meta_mod.serialize_product)
    assert "float(row.cost_price" not in inspect.getsource(catalog_meta_mod.serialize_product)
    assert "money_json" in inspect.getsource(catalog_mod.serialize_variant)
    assert "float(v.cost_price" not in inspect.getsource(catalog_mod.serialize_variant)
    assert "money_json" in inspect.getsource(catalog_mod.serialize_batch)
    assert "money_json" in inspect.getsource(tax_mod.serialize_tax_rate)
    assert "money_json" in inspect.getsource(expenses_mod.serialize_category)
    assert "money_json" in inspect.getsource(customer_groups_mod.serialize_group)
    assert "money_json" in inspect.getsource(catalog_meta_mod.serialize_unit)
    assert "money_json" in inspect.getsource(tenants_mod.serialize_tenant)
    assert "money_json" in inspect.getsource(warehouses_mod.serialize_warehouse)
