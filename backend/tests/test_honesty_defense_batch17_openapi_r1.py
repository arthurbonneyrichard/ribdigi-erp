"""OpenAPI honesty tips #1103–#1142: org/COA code defense + print/receipt/settings money_json + residual aria."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.honesty import money_json, optional_honest_narrative, require_honest_narrative
from app import cash_transfers as cash_transfers_mod
from app import expenses as expenses_mod
from app import invoice_print as invoice_print_mod
from app import org_units as org_units_mod
from app import receipts as receipts_mod

ROOT = Path(__file__).resolve().parents[2]


def test_honesty_batch17_docs_and_agents():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for title in (
        "Branch code defense-in-depth OpenAPI",
        "Department code defense-in-depth OpenAPI",
        "Account code defense-in-depth OpenAPI",
        "Bank account number defense-in-depth OpenAPI",
        "Invoice print thermal line qty money_json Decimal pilot OpenAPI",
        "Invoice print thermal line unit_price money_json Decimal pilot OpenAPI",
        "Invoice print thermal line total money_json Decimal pilot OpenAPI",
        "Invoice print A4 line qty money_json Decimal pilot OpenAPI",
        "Invoice print A4 line unit_price money_json Decimal pilot OpenAPI",
        "Invoice print A4 line tax_rate money_json Decimal pilot OpenAPI",
        "Invoice print A4 line_tax money_json Decimal pilot OpenAPI",
        "Invoice print A4 line_total money_json Decimal pilot OpenAPI",
        "POS receipt thermal line qty money_json Decimal pilot OpenAPI",
        "POS receipt thermal line unit_price money_json Decimal pilot OpenAPI",
        "POS receipt thermal line total money_json Decimal pilot OpenAPI",
        "POS receipt thermal discount money_json Decimal pilot OpenAPI",
        "Expense approval threshold settings money_json Decimal pilot OpenAPI",
        "Expense L2 threshold settings money_json Decimal pilot OpenAPI",
        "Stores Reactivate department aria OpenAPI",
        "Stores Deactivate department aria OpenAPI",
        "Stores Activate warehouse aria OpenAPI",
        "Stores Deactivate warehouse aria OpenAPI",
        "Sales Activate customer group aria OpenAPI",
        "Sales Accept quotation aria OpenAPI",
        "Sales Convert quotation to order aria OpenAPI",
        "Sales Convert quotation to invoice aria OpenAPI",
        "Sales Confirm order aria OpenAPI",
        "Sales Process order aria OpenAPI",
        "Sales Ship order aria OpenAPI",
        "Sales Deliver order aria OpenAPI",
        "Sales Convert order to invoice aria OpenAPI",
        "Purchasing Approve purchase request aria OpenAPI",
        "Tax Activate tax rate aria OpenAPI",
        "Integrations Test webhook aria OpenAPI",
        "Platform Assign package aria OpenAPI",
        "Platform Save store entitlement override aria OpenAPI",
        "Platform Reset feature modules aria OpenAPI",
        "Expenses Edit expense aria OpenAPI",
        "Accounting Add journal line aria OpenAPI",
        "Reports Apply filters aria OpenAPI",
    ):
        assert title in agents, title

    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    standards = docs.split("## 1. API Standards")[1].split("## 2.")[0]
    assert "money_json" in standards
    assert "Branch/department/account" in standards or "AccountCodeValue" in standards
    assert "bank account number" in standards.lower() or "account_number" in standards

    stores = (ROOT / "frontend/app/stores/page.tsx").read_text(encoding="utf-8")
    assert "Reactivate department" in stores
    assert "Deactivate department" in stores
    assert "Activate warehouse" in stores
    assert "Deactivate warehouse" in stores

    sales = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert "Activate customer group" in sales
    assert "Accept quotation" in sales
    assert "Convert quotation to order" in sales
    assert "Convert quotation to invoice" in sales
    assert "Confirm sales order" in sales
    assert "Process sales order" in sales
    assert "Ship sales order" in sales
    assert "Deliver sales order" in sales
    assert "Convert sales order to invoice" in sales

    purchasing = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert "Approve purchase request" in purchasing

    tax = (ROOT / "frontend/app/tax/page.tsx").read_text(encoding="utf-8")
    assert "Activate tax rate" in tax

    integrations = (ROOT / "frontend/app/integrations/page.tsx").read_text(encoding="utf-8")
    assert "Test webhook" in integrations

    platform = (ROOT / "frontend/app/platform/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Assign package and term"' in platform
    assert 'aria-label="Save store entitlement override"' in platform
    assert "Reset feature modules to package default" in platform

    expenses = (ROOT / "frontend/app/expenses/page.tsx").read_text(encoding="utf-8")
    assert "Edit expense" in expenses

    accounting = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Add journal line"' in accounting

    reports = (ROOT / "frontend/app/reports/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Apply report filters"' in reports


def test_code_and_account_number_defense_batch17():
    with pytest.raises(HTTPException) as exc:
        require_honest_narrative("!!!", label="branch code", max_length=40)
    assert exc.value.status_code == 400

    with pytest.raises(HTTPException):
        optional_honest_narrative("http://evil", label="bank account number", max_length=64)

    clean_src = inspect.getsource(org_units_mod._clean_code)
    assert "require_honest_narrative" in clean_src
    assert "label" in clean_src

    branch_src = inspect.getsource(org_units_mod.create_branch)
    assert 'label="branch code"' in branch_src

    dept_src = inspect.getsource(org_units_mod.create_department)
    assert 'label="department code"' in dept_src

    acct_src = inspect.getsource(cash_transfers_mod.create_account)
    assert 'label="account code"' in acct_src
    assert 'label="bank account number"' in acct_src

    upd_src = inspect.getsource(cash_transfers_mod.update_account)
    assert 'label="bank account number"' in upd_src


def test_money_json_wired_batch17():
    assert money_json("12.50") == 12.5

    print_src = Path(invoice_print_mod.__file__).read_text(encoding="utf-8")
    assert 'money_json(item.get("quantity")' in print_src
    assert 'money_json(item.get("unit_price")' in print_src
    assert 'money_json(item.get("line_total")' in print_src
    assert 'money_json(item.get("tax_rate")' in print_src
    assert 'money_json(item.get("line_tax")' in print_src

    receipt_src = Path(receipts_mod.__file__).read_text(encoding="utf-8")
    assert 'money_json(item.get("quantity")' in receipt_src
    assert 'money_json(item.get("unit_price")' in receipt_src
    assert 'money_json(item.get("line_total")' in receipt_src
    assert 'money_json(receipt.get("discount_amount")' in receipt_src

    settings_src = inspect.getsource(expenses_mod.settings_from_levels)
    assert "money_json(auto_t)" in settings_src
    assert "money_json(l2_t)" in settings_src
