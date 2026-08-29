"""OpenAPI honesty tips #1223–#1262: account_code defense + report money_json + residual aria."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.honesty import money_json
from app import accounting as accounting_mod
from app import reports as reports_mod

ROOT = Path(__file__).resolve().parents[2]


def test_honesty_batch20_docs_and_agents():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for title in (
        "Journal line account_code defense-in-depth OpenAPI",
        "Opening balance account_code defense-in-depth OpenAPI",
        "Sales daily invoice_revenue money_json Decimal pilot OpenAPI",
        "Sales daily pos_revenue money_json Decimal pilot OpenAPI",
        "Sales daily total_revenue money_json Decimal pilot OpenAPI",
        "Sales daily tax money_json Decimal pilot OpenAPI",
        "Sales daily discounts money_json Decimal pilot OpenAPI",
        "Sales daily net_sales money_json Decimal pilot OpenAPI",
        "Sales monthly total_revenue money_json Decimal pilot OpenAPI",
        "Sales by product total_revenue money_json Decimal pilot OpenAPI",
        "Sales by customer total_revenue money_json Decimal pilot OpenAPI",
        "Sales returns total_amount money_json Decimal pilot OpenAPI",
        "Sales returns posted_amount money_json Decimal pilot OpenAPI",
        "Sales returns refunded_amount money_json Decimal pilot OpenAPI",
        "Purchases summary total_amount money_json Decimal pilot OpenAPI",
        "Purchases summary outstanding_amount money_json Decimal pilot OpenAPI",
        "Expenses summary total_amount money_json Decimal pilot OpenAPI",
        "Expenses summary by_category amount money_json Decimal pilot OpenAPI",
        "Budget vs actual budget_monthly money_json Decimal pilot OpenAPI",
        "Budget vs actual actual money_json Decimal pilot OpenAPI",
        "Budget vs actual total_actual money_json Decimal pilot OpenAPI",
        "Balance sheet total_assets money_json Decimal pilot OpenAPI",
        "Balance sheet compare prior_balance money_json Decimal pilot OpenAPI",
        "Cash flow inflows money_json Decimal pilot OpenAPI",
        "Login Sign in aria OpenAPI",
        "Login Use passkey aria OpenAPI",
        "Forgot password Send reset link aria OpenAPI",
        "Notifications Filter unread aria OpenAPI",
        "Notifications Filter all aria OpenAPI",
        "Onboarding Expand checklist aria OpenAPI",
        "Onboarding Dismiss checklist aria OpenAPI",
        "Inventory Run product lookup aria OpenAPI",
        "Multi-Store Cancel branch edit aria OpenAPI",
        "Multi-Store Cancel department edit aria OpenAPI",
        "Multi-Store Cancel store edit aria OpenAPI",
        "Multi-Store Cancel warehouse edit aria OpenAPI",
        "Accounting Show ledger tab aria OpenAPI",
        "Accounting Show cash and bank tab aria OpenAPI",
        "Accounting Show reconcile tab aria OpenAPI",
        "Accounting Show cheques tab aria OpenAPI",
    ):
        assert title in agents, title

    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    standards = docs.split("## 1. API Standards")[1].split("## 2.")[0]
    assert "money_json" in standards
    assert "require_account_code" in standards or "account_code" in standards.lower()

    login = (ROOT / "frontend/app/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Sign in"' in login
    assert 'aria-label="Use passkey"' in login

    forgot = (ROOT / "frontend/app/forgot-password/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Send password reset link"' in forgot

    notif = (ROOT / "frontend/app/notifications/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Filter unread notifications"' in notif
    assert 'aria-label="Filter all notifications"' in notif

    onboarding = (ROOT / "frontend/components/OnboardingChecklist.tsx").read_text(
        encoding="utf-8"
    )
    assert "Expand onboarding checklist" in onboarding
    assert 'aria-label="Dismiss onboarding checklist"' in onboarding

    inventory = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Run product lookup"' in inventory

    stores = (ROOT / "frontend/app/stores/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Cancel branch edit"' in stores
    assert 'aria-label="Cancel department edit"' in stores
    assert 'aria-label="Cancel store edit"' in stores
    assert 'aria-label="Cancel warehouse edit"' in stores

    accounting = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Show accounting ledger tab"' in accounting
    assert 'aria-label="Show accounting cash and bank tab"' in accounting
    assert 'aria-label="Show accounting reconcile tab"' in accounting
    assert 'aria-label="Show accounting cheques tab"' in accounting


def test_account_code_defense_batch20():
    with pytest.raises(HTTPException) as exc:
        accounting_mod.require_account_code("!!!")
    assert exc.value.status_code == 400

    with pytest.raises(HTTPException):
        accounting_mod.require_account_code("a b")

    with pytest.raises(HTTPException):
        accounting_mod.require_account_code("http://evil")

    with pytest.raises(HTTPException):
        accounting_mod.require_account_code("")

    assert accounting_mod.require_account_code("1200") == "1200"
    assert accounting_mod.require_account_code(" A-1_b ") == "A-1_b"

    src = inspect.getsource(accounting_mod.get_account_by_code)
    assert "require_account_code" in src


def test_money_json_wired_batch20():
    assert money_json("12.50") == 12.5

    daily_src = inspect.getsource(reports_mod.sales_daily)
    assert "money_json(round(invoice_total, 2))" in daily_src
    assert "money_json(round(pos_total, 2))" in daily_src
    assert "money_json(round(invoice_total + pos_total, 2))" in daily_src
    assert "money_json(round(invoice_tax + pos_tax, 2))" in daily_src
    assert "money_json(round(invoice_discount, 2))" in daily_src

    monthly_src = inspect.getsource(reports_mod.sales_monthly)
    assert 'money_json(round(total, 2))' in monthly_src

    prod_src = inspect.getsource(reports_mod.sales_by_product)
    assert "money_json(round(sum(p[\"revenue\"] for p in products), 2))" in prod_src

    cust_src = inspect.getsource(reports_mod.sales_by_customer)
    assert "money_json(round(sum(c[\"revenue\"] for c in customers), 2))" in cust_src

    ret_src = inspect.getsource(reports_mod.sales_returns_summary)
    assert "money_json(round(total_amount, 2))" in ret_src
    assert "money_json(round(posted_amount, 2))" in ret_src
    assert "money_json(round(refunded_total, 2))" in ret_src

    purch_src = inspect.getsource(reports_mod.purchases_summary)
    assert "money_json(round(total, 2))" in purch_src
    assert "money_json(round(pending, 2))" in purch_src

    exp_src = inspect.getsource(reports_mod.expenses_summary)
    assert 'money_json(round(v, 2))' in exp_src
    assert "money_json(round(sum(money_json(e.amount)" in exp_src

    budget_src = inspect.getsource(reports_mod.budget_vs_actual)
    assert "money_json(round(budget_monthly, 2))" in budget_src
    assert "money_json(round(actual, 2))" in budget_src
    assert "money_json(round(total_actual, 2))" in budget_src

    pack_src = inspect.getsource(reports_mod._pack_balance_sheet)
    assert "money_json(round(sum(money_json(r[\"balance\"])" in pack_src

    compare_src = inspect.getsource(reports_mod._merge_bs_compare)
    assert "money_json(round(prior_bal, 2))" in compare_src
    assert "money_json(round(bal - prior_bal, 2))" in compare_src

    cf_src = inspect.getsource(reports_mod.cash_flow)
    assert "money_json(round(money_json(inflows), 2))" in cf_src


def test_opening_balance_account_code_path_batch20():
    ob_src = (ROOT / "backend/app/opening_balances.py").read_text(encoding="utf-8")
    assert "get_account_by_code(db, tenant_id, account_code)" in ob_src
    # No longer strip-only before lookup (defense lives in require_account_code).
    assert "account_code.strip()" not in ob_src
