"""OpenAPI honesty tips #1663–#1706: purchasing/sales_docs/inventory/tax/stores/expenses/catalog/POS money_json + residual FE aria."""

from __future__ import annotations

import inspect
from pathlib import Path

from app.honesty import money_json
from app import purchasing as purchasing_mod
from app import sales_docs as sales_docs_mod
from app import inventory as inventory_mod
from app import tax as tax_mod
from app import stores as stores_mod
from app import expenses as expenses_mod
from app import catalog as catalog_mod
from app import pos as pos_mod

ROOT = Path(__file__).resolve().parents[2]


def test_honesty_batch31_docs_and_agents():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for title in (
        "Purchasing PO line discount disc money_json Decimal pilot OpenAPI",
        "Purchasing PO line discount merch money_json Decimal pilot OpenAPI",
        "Purchasing PO line discount line_total money_json Decimal pilot OpenAPI",
        "Purchasing supplier payment exchange_rate money_json Decimal pilot OpenAPI",
        "Purchasing returned qty accumulate money_json Decimal pilot OpenAPI",
        "Purchasing PR create qty money_json Decimal pilot OpenAPI",
        "Purchasing PR create available money_json Decimal pilot OpenAPI",
        "Purchasing PR create unit/rate money_json Decimal pilot OpenAPI",
        "Purchasing PR create ordered/line_disc money_json Decimal pilot OpenAPI",
        "Purchasing PR post available/qty money_json Decimal pilot OpenAPI",
        "Purchasing PR post stock qty money_json Decimal pilot OpenAPI",
        "Purchasing PR post received_qty money_json Decimal pilot OpenAPI",
        "Purchasing PR post credit/balance money_json Decimal pilot OpenAPI",
        "Purchasing PI create line qty/price/discount money_json Decimal pilot OpenAPI",
        "Purchasing PI create from GRN money_json Decimal pilot OpenAPI",
        "Purchasing PI create discount_amount money_json Decimal pilot OpenAPI",
        "Purchasing PI approve balance/status money_json Decimal pilot OpenAPI",
        "Purchasing PI cancel balance money_json Decimal pilot OpenAPI",
        "Purchasing PI line_gross money_json Decimal pilot OpenAPI",
        "Sales docs prepare_lines qty money_json Decimal pilot OpenAPI",
        "Sales docs prepare_lines discount money_json Decimal pilot OpenAPI",
        "Sales docs prepare_lines tax_rate money_json Decimal pilot OpenAPI",
        "Sales docs QT/SO discount_amount money_json Decimal pilot OpenAPI",
        "Sales docs SO create notification total money_json Decimal pilot OpenAPI",
        "Sales docs SR create qty money_json Decimal pilot OpenAPI",
        "Sales docs SR create unit/rate money_json Decimal pilot OpenAPI",
        "Sales docs SR post paid/balance money_json Decimal pilot OpenAPI",
        "Sales docs SR restock qty money_json Decimal pilot OpenAPI",
        "Inventory stock change before/after money_json Decimal pilot OpenAPI",
        "Inventory located/unlocated stock money_json Decimal pilot OpenAPI",
        "Inventory reorder_level check money_json Decimal pilot OpenAPI",
        "Inventory set reorder levels money_json Decimal pilot OpenAPI",
        "Tax compute_line_total qty/price money_json Decimal pilot OpenAPI",
        "Tax rate_pct / report money_json Decimal pilot OpenAPI",
        "Stores reorder + transfer qty money_json Decimal pilot OpenAPI",
        "Expense thresholds/amounts money_json Decimal pilot OpenAPI",
        "Catalog price/stock qty money_json Decimal pilot OpenAPI",
        "POS cash/tender money_json Decimal pilot OpenAPI",
        "Sales Toggle customer active aria OpenAPI",
        "POS Browse all products aria OpenAPI",
        "Purchasing Toggle supplier active aria OpenAPI",
        "Purchasing Dismiss invoice OCR aria OpenAPI",
        "Expenses Dismiss OCR aria OpenAPI",
        "Inventory Select product aria OpenAPI",
    ):
        assert title in agents, title

    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    standards = docs.split("## 1. API Standards")[1].split("## 2.")[0]
    assert "PO-line-discount" in standards or "sales-docs" in standards
    assert "POS cash/tender" in standards or "catalog price/stock" in standards

    sales = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Toggle customer active status"' in sales

    pos = (ROOT / "frontend/app/pos/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Browse all POS products"' in pos

    purchasing = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Toggle supplier active status"' in purchasing
    assert 'aria-label="Dismiss purchase invoice OCR"' in purchasing

    expenses = (ROOT / "frontend/app/expenses/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Dismiss expense OCR"' in expenses

    inventory = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert "Select inventory product ${p.id}" in inventory


def test_money_json_wired_batch31():
    assert money_json("12.50") == 12.5

    disc_src = inspect.getsource(purchasing_mod._po_line_discount)
    assert "disc = money_json(discount or 0)" in disc_src
    assert "merch = money_json(qty) * money_json(unit_price)" in disc_src
    assert "max(money_json(line_total) - disc, 0)" in disc_src

    purch_src = Path(purchasing_mod.__file__).read_text(encoding="utf-8")
    assert "pay_rate = money_json(exchange_rate)" in purch_src
    assert "money_json(qty or 0)" in purch_src
    assert 'qty = money_json(raw["quantity"])' in purch_src
    assert "available = money_json(grn_item.accepted_qty or 0)" in purch_src
    assert "unit = money_json(po_item.unit_price)" in purch_src
    assert "rate = money_json(po_item.tax_rate or 0)" in purch_src
    assert "ordered = money_json(po_item.quantity or 0)" in purch_src
    assert "line_disc_po = money_json(getattr(po_item, \"discount\", 0) or 0)" in purch_src
    assert "money_json(item.quantity)" in purch_src
    assert "quantity=money_json(item.quantity)" in purch_src
    assert "money_json(po_item.received_qty or 0)" in purch_src
    assert "credit = money_json(ret.total_amount)" in purch_src or "money_json(ret.total_amount)" in purch_src
    assert 'qty = money_json(item["quantity"])' in purch_src
    assert "discount = money_json(item.get(\"discount\") or 0)" in purch_src
    assert "qty = money_json(gi.accepted_qty or 0)" in purch_src
    assert "discount_amount = money_json(discount_amount or 0)" in purch_src
    assert "money_json(supplier.balance or 0)" in purch_src
    assert "money_json(inv.total_amount)" in purch_src
    assert "money_json(item.quantity or 0) * money_json(item.unit_price or 0)" in purch_src

    prep_src = inspect.getsource(sales_docs_mod._prepare_lines)
    assert 'quantity=money_json(item["quantity"])' in prep_src
    assert "discount = money_json(item.get(\"discount\") or 0)" in prep_src
    assert "explicit_rate=money_json(explicit)" in prep_src

    sales_src = Path(sales_docs_mod.__file__).read_text(encoding="utf-8")
    assert "discount_amount = money_json(discount_amount or 0)" in sales_src
    assert "money_json(order.total_amount or 0)" in sales_src
    assert 'qty = money_json(item["quantity"])' in sales_src
    assert "money_json(src.quantity)" in sales_src
    assert "unit = money_json(src.unit_price)" in sales_src or "money_json(src.unit_price)" in sales_src
    assert "money_json(src.tax_rate or 0)" in sales_src
    assert "money_json(invoice.total_amount)" in sales_src
    assert "money_json(customer.balance or 0)" in sales_src
    assert "qty = money_json(item.quantity)" in sales_src
    assert "money_json(variant.stock_qty or 0)" in sales_src

    inv_src = Path(inventory_mod.__file__).read_text(encoding="utf-8")
    assert "money_json(row.quantity or 0)" in inv_src
    assert "money_json(quantity_delta)" in inv_src
    assert "money_json(product.stock_qty or 0)" in inv_src
    assert "located = money_json(" in inv_src or "money_json(product.stock_qty or 0) - located" in inv_src
    assert "money_json(product.reorder_level or 0)" in inv_src
    assert "money_json(reorder_level or 0)" in inv_src
    assert "money_json(reorder_qty or 0)" in inv_src

    tax_src = inspect.getsource(tax_mod.compute_line_total)
    assert "qty = money_json(quantity or 0)" in tax_src
    assert "price = money_json(unit_price or 0)" in tax_src
    tax_file = Path(tax_mod.__file__).read_text(encoding="utf-8")
    assert "rate_pct=money_json(rate.rate)" in tax_file
    assert "tax = money_json(inv.tax_amount or 0)" in tax_file

    stores_src = Path(stores_mod.__file__).read_text(encoding="utf-8")
    assert "money_json(reorder_level or 0)" in stores_src
    assert 'money_json(item["quantity"])' in stores_src
    assert "money_json(item.quantity)" in stores_src

    exp_src = Path(expenses_mod.__file__).read_text(encoding="utf-8")
    assert "money_json(budget_monthly or 0)" in exp_src
    assert "amount=round(money_json(amount), 2)" in exp_src
    assert "money_json(normalized[0][\"min_amount\"])" in exp_src or "money_json(normalized[0]" in exp_src

    cat_src = Path(catalog_mod.__file__).read_text(encoding="utf-8")
    assert 'money_json(item["unit_price"])' in cat_src
    assert "money_json(quantity)" in cat_src
    assert "money_json(batch.quantity or 0)" in cat_src
    assert "money_json(variant.stock_qty or 0)" in cat_src

    pos_src = Path(pos_mod.__file__).read_text(encoding="utf-8")
    assert "float(" not in pos_src
    assert "money_json(round(money_json(opening_cash or 0)" in pos_src
