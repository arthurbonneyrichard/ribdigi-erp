"""OpenAPI honesty tips #1063–#1102: code/CSV defense + audit/clearing money_json + residual aria."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest
from fastapi import HTTPException
from pydantic import TypeAdapter, ValidationError

from app.honesty import money_json, require_honest_narrative
from app.schemas import ProductBarcodeValue
from app import accounting as accounting_mod
from app import bank_recon as bank_recon_mod
from app import catalog_meta as catalog_meta_mod
from app import customer_groups as customer_groups_mod
from app import product_import as product_import_mod
from app import purchasing as purchasing_mod
from app import sales as sales_mod
from app import stores as stores_mod
from app import warehouses as warehouses_mod

ROOT = Path(__file__).resolve().parents[2]


def test_honesty_batch16_docs_and_agents():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for title in (
        "Store code defense-in-depth OpenAPI",
        "Warehouse code defense-in-depth OpenAPI",
        "Category code defense-in-depth OpenAPI",
        "Brand code defense-in-depth OpenAPI",
        "Unit code defense-in-depth OpenAPI",
        "Customer group code defense-in-depth OpenAPI",
        "Expense category code defense-in-depth OpenAPI",
        "Product CSV barcode defense-in-depth OpenAPI",
        "Customer payment audit money_json Decimal pilot OpenAPI",
        "Journal post audit money_json Decimal pilot OpenAPI",
        "Purchase return post audit money_json Decimal pilot OpenAPI",
        "GRN post accepted_value money_json Decimal pilot OpenAPI",
        "Bank clearing group money_json Decimal pilot OpenAPI",
        "Bank clearing mismatch money_json Decimal pilot OpenAPI",
        "Sale paid webhook amount_applied money_json Decimal pilot OpenAPI",
        "Accounting Activate account aria OpenAPI",
        "Accounting Deactivate account aria OpenAPI",
        "Accounting Apply bank match suggestion aria OpenAPI",
        "Accounting Auto-clear high confidence aria OpenAPI",
        "Accounting Auto-clear medium confidence aria OpenAPI",
        "Accounting Auto-clear low confidence aria OpenAPI",
        "Purchasing Save numbering aria OpenAPI",
        "Purchasing Submit request aria OpenAPI",
        "Purchasing Receive all aria OpenAPI",
        "Purchasing Approve invoice aria OpenAPI",
        "Purchasing Post return aria OpenAPI",
        "Stores Create transfer aria OpenAPI",
        "Stores Submit transfer aria OpenAPI",
        "Stores Ship transfer aria OpenAPI",
        "Stores Receive transfer aria OpenAPI",
        "Stores Approve transfer aria OpenAPI",
        "Stores Cancel transfer aria OpenAPI",
        "Stores Inventory reorder aria OpenAPI",
        "Sales Save group discount aria OpenAPI",
        "Expenses Save recurring schedule aria OpenAPI",
        "Expenses Create recurring schedule aria OpenAPI",
        "Expenses Edit recurring schedule aria OpenAPI",
        "Platform Save feature modules aria OpenAPI",
        "Credit Remove exchange rate aria OpenAPI",
        "POS Scan or search aria OpenAPI",
    ):
        assert title in agents, title

    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    standards = docs.split("## 1. API Standards")[1].split("## 2.")[0]
    assert "money_json" in standards
    assert "ProductBarcodeValue" in standards
    assert "StoreCodeValue" in standards or "store/warehouse" in standards.lower()

    accounting = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert "Activate account" in accounting
    assert "Deactivate account" in accounting
    assert 'aria-label="Apply bank match suggestion"' in accounting
    assert "Auto-clear high confidence matches" in accounting
    assert "Auto-clear medium confidence matches" in accounting
    assert "Auto-clear low confidence matches" in accounting

    purchasing = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Save purchasing numbering"' in purchasing
    assert "Submit purchase request" in purchasing
    assert "Receive all for purchase order" in purchasing
    assert "Approve purchase invoice" in purchasing
    assert "Post purchase return" in purchasing

    stores = (ROOT / "frontend/app/stores/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Create and request stock transfer"' in stores
    assert "Submit stock transfer" in stores
    assert "Ship stock transfer" in stores
    assert "Receive stock transfer" in stores
    assert "Approve stock transfer" in stores
    assert "Cancel stock transfer" in stores
    assert "Open inventory reorder for store" in stores

    sales = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert "Save customer group discount" in sales

    expenses = (ROOT / "frontend/app/expenses/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Save recurring expense schedule"' in expenses
    assert 'aria-label="Create recurring expense schedule"' in expenses
    assert "Edit recurring expense schedule" in expenses

    platform = (ROOT / "frontend/app/platform/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Save feature modules"' in platform

    credit = (ROOT / "frontend/app/credit/page.tsx").read_text(encoding="utf-8")
    assert "Remove exchange rate" in credit

    pos = (ROOT / "frontend/app/pos/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="POS scan or search products"' in pos


def test_code_defense_batch16():
    with pytest.raises(HTTPException) as exc:
        require_honest_narrative("!!!", label="store code", max_length=50)
    assert exc.value.status_code == 400

    store_src = inspect.getsource(stores_mod.create_store)
    assert 'label="store code"' in store_src
    assert "require_honest_narrative" in store_src

    wh_src = inspect.getsource(warehouses_mod.create_warehouse)
    assert 'label="warehouse code"' in wh_src

    cat_src = inspect.getsource(catalog_meta_mod.create_category)
    assert 'label="category code"' in cat_src
    brand_src = inspect.getsource(catalog_meta_mod.create_brand)
    assert 'label="brand code"' in brand_src
    unit_src = inspect.getsource(catalog_meta_mod.create_unit)
    assert 'label="unit code"' in unit_src

    grp_src = inspect.getsource(customer_groups_mod.create_group)
    assert 'label="customer group code"' in grp_src

    api_src = (ROOT / "backend/app/api.py").read_text(encoding="utf-8")
    assert 'label="expense category code"' in api_src


def test_product_csv_barcode_type_adapter_batch16():
    with pytest.raises(ValidationError):
        TypeAdapter(ProductBarcodeValue).validate_python("!!!!")
    with pytest.raises(ValidationError):
        TypeAdapter(ProductBarcodeValue).validate_python("ab")

    src = inspect.getsource(product_import_mod.validate_import_rows)
    assert "TypeAdapter(ProductBarcodeValue)" in src


def test_money_json_wired_batch16():
    assert money_json("12.50") == 12.5

    pay_src = inspect.getsource(sales_mod.record_customer_payment)
    assert "money_json(amount)" in pay_src
    assert "money_json(total_discount)" in pay_src
    assert "money_json(pay_rate)" in pay_src
    assert "amount_applied" in pay_src
    assert "money_json(amt)" in pay_src

    journal_src = inspect.getsource(accounting_mod.post_journal_entry)
    assert "money_json(total_debit)" in journal_src

    ret_src = inspect.getsource(purchasing_mod.post_purchase_return)
    assert "money_json(credit)" in ret_src

    grn_src = inspect.getsource(purchasing_mod.create_grn)
    assert "money_json(accepted_value)" in grn_src

    clear_src = inspect.getsource(bank_recon_mod.serialize_clearing_group)
    assert "money_json(bank_total)" in clear_src
    assert "money_json(book_total)" in clear_src

    mismatch_src = Path(bank_recon_mod.__file__).read_text(encoding="utf-8")
    assert '"code": "AMOUNT_MISMATCH"' in mismatch_src
    assert "money_json(bank_total)" in mismatch_src
