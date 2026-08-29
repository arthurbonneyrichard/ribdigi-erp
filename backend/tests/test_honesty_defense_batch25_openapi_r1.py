"""OpenAPI honesty tips #1423–#1462: FX/POS/tax/line money_json + residual FE aria."""

from __future__ import annotations

import inspect
from pathlib import Path

from app.honesty import money_json
from app import accounting as accounting_mod
from app import cash_transfers as cash_transfers_mod
from app import expense_ocr as expense_ocr_mod
from app import fx as fx_mod
from app import opening_stock as opening_stock_mod
from app import pos as pos_mod
from app import purchasing as purchasing_mod
from app import sales as sales_mod
from app import sales_docs as sales_docs_mod
from app import tax as tax_mod

ROOT = Path(__file__).resolve().parents[2]


def test_honesty_batch25_docs_and_agents():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for title in (
        "FX to_base money_json Decimal pilot OpenAPI",
        "FX quotes_to_rate_to_base money_json Decimal pilot OpenAPI",
        "POS compute_expected_cash money_json Decimal pilot OpenAPI",
        "POS compute_variance money_json Decimal pilot OpenAPI",
        "Tax effective_rate_from_components money_json Decimal pilot OpenAPI",
        "Sales invoice line_tax zero money_json Decimal pilot OpenAPI",
        "Sales invoice line_tax derived money_json Decimal pilot OpenAPI",
        "Sales invoice line_tax rate-derived money_json Decimal pilot OpenAPI",
        "Purchase invoice line_subtotal stored money_json Decimal pilot OpenAPI",
        "Purchase invoice line_subtotal computed money_json Decimal pilot OpenAPI",
        "Purchase invoice line_tax stored money_json Decimal pilot OpenAPI",
        "Purchase invoice line_tax zero money_json Decimal pilot OpenAPI",
        "Purchase invoice line_tax rate-derived money_json Decimal pilot OpenAPI",
        "Purchase invoice line_tax derived money_json Decimal pilot OpenAPI",
        "Sales docs prepare_lines subtotal money_json Decimal pilot OpenAPI",
        "Sales docs prepare_lines tax_total money_json Decimal pilot OpenAPI",
        "Accounting compute_standard_cogs money_json Decimal pilot OpenAPI",
        "Accounting append_cogs_lines money_json Decimal pilot OpenAPI",
        "Expense OCR parse_amount money_json Decimal pilot OpenAPI",
        "Cash transfer create amount money_json Decimal pilot OpenAPI",
        "Opening stock line_value money_json Decimal pilot OpenAPI",
        "Sales Invoice next number aria OpenAPI",
        "Sales Quotation next number aria OpenAPI",
        "Sales Sales order next number aria OpenAPI",
        "Sales Sales return next number aria OpenAPI",
        "Sales Credit note next number aria OpenAPI",
        "Sales Payment receipt next number aria OpenAPI",
        "Sales Customer group status filter aria OpenAPI",
        "Sales Add group aria OpenAPI",
        "Sales Customer status filter aria OpenAPI",
        "Sales Manage customer aria OpenAPI",
        "Sales Create sales return aria OpenAPI",
        "Sales Sales return status filter aria OpenAPI",
        "Purchasing Purchase order next number aria OpenAPI",
        "Purchasing GRN next number aria OpenAPI",
        "Purchasing Purchase invoice next number aria OpenAPI",
        "Purchasing Purchase request next number aria OpenAPI",
        "Purchasing Purchase return next number aria OpenAPI",
        "Purchasing Supplier status filter aria OpenAPI",
        "Accounting Journal next number aria OpenAPI",
    ):
        assert title in agents, title

    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    standards = docs.split("## 1. API Standards")[1].split("## 2.")[0]
    assert "to_base" in standards
    assert "compute_expected_cash" in standards or "_prepare_lines" in standards
    assert "_pi_line_tax_value" in standards or "effective_rate_from_components" in standards

    sales = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Invoice next number"' in sales
    assert 'aria-label="Customer status filter"' in sales
    assert 'aria-label="Sales return status filter"' in sales

    purchasing = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Purchase order next number"' in purchasing
    assert 'aria-label="Supplier status filter"' in purchasing

    accounting = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Journal next number"' in accounting


def test_money_json_wired_batch25():
    assert money_json("12.50") == 12.5

    to_base_src = inspect.getsource(fx_mod.to_base)
    assert "return money_json(round(float(amount or 0)" in to_base_src

    quotes_src = inspect.getsource(fx_mod.quotes_to_rate_to_base)
    assert "return money_json(round(1.0 / q, 8))" in quotes_src

    expected_src = inspect.getsource(pos_mod.compute_expected_cash)
    assert "return money_json(round(float(opening_cash or 0)" in expected_src

    var_src = inspect.getsource(pos_mod.compute_variance)
    assert "return money_json(round(float(actual_cash)" in var_src

    eff_src = inspect.getsource(tax_mod.effective_rate_from_components)
    assert "return money_json(round(total, 4))" in eff_src

    si_tax = inspect.getsource(sales_mod._line_tax_value)
    assert "return money_json(0)" in si_tax
    assert "derived = money_json(round(total - sub + discount, 2))" in si_tax
    assert "return money_json(round(sub * rate / 100.0, 2))" in si_tax

    pi_sub = inspect.getsource(purchasing_mod._pi_line_subtotal)
    assert "stored = money_json(getattr(item, \"line_subtotal\"" in pi_sub
    assert "return money_json(round(float(item.quantity or 0)" in pi_sub

    pi_tax = inspect.getsource(purchasing_mod._pi_line_tax_value)
    assert "stored = money_json(getattr(item, \"line_tax\"" in pi_tax
    assert "return money_json(0)" in pi_tax
    assert "return money_json(round(sub * rate / 100.0, 2))" in pi_tax
    assert "derived = money_json(round(total - sub + discount, 2))" in pi_tax

    prep_src = inspect.getsource(sales_docs_mod._prepare_lines)
    assert "return money_json(round(subtotal, 2)), money_json(round(tax_total, 2)), prepared" in prep_src

    cogs_src = inspect.getsource(accounting_mod.compute_standard_cogs)
    assert "return money_json(round(total, 2))" in cogs_src

    append_src = inspect.getsource(accounting_mod.append_cogs_lines)
    assert "cogs = money_json(round(float(cogs or 0), 2))" in append_src

    ocr_src = inspect.getsource(expense_ocr_mod._parse_amount)
    assert "return money_json(round(float(str(raw).replace" in ocr_src

    xfer_src = inspect.getsource(cash_transfers_mod.create_transfer)
    assert "amt = money_json(round(float(amount or 0), 2))" in xfer_src

    open_src = inspect.getsource(opening_stock_mod.post_opening_stock)
    assert "line_value = money_json(round(float(moved[\"quantity_base\"])" in open_src
