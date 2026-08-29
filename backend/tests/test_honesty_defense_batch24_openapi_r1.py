"""OpenAPI honesty tips #1383–#1422: AI/credit money_json + residual FE aria."""

from __future__ import annotations

import inspect
from pathlib import Path

from app.honesty import money_json
from app import ai as ai_mod
from app import ai_customer as ai_customer_mod
from app import ai_documents as ai_documents_mod
from app import ai_inventory as ai_inventory_mod
from app import bank_recon as bank_recon_mod
from app import credit as credit_mod
from app import customer_groups as customer_groups_mod
from app import expense_ocr as expense_ocr_mod
from app import expenses as expenses_mod
from app import reports as reports_mod

ROOT = Path(__file__).resolve().parents[2]


def test_honesty_batch24_docs_and_agents():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for title in (
        "AI insight pct_delta money_json Decimal pilot OpenAPI",
        "AI insight pct_delta 100 money_json Decimal pilot OpenAPI",
        "AI customer churn_risk money_json Decimal pilot OpenAPI",
        "AI inventory confidence_score money_json Decimal pilot OpenAPI",
        "AI inventory confidence no-velocity money_json Decimal pilot OpenAPI",
        "AI inventory recommended_order_qty helper money_json Decimal pilot OpenAPI",
        "Expense OCR confidence money_json Decimal pilot OpenAPI",
        "Credit customer history purchase_total money_json Decimal pilot OpenAPI",
        "Credit customer history return_total money_json Decimal pilot OpenAPI",
        "Credit customer history payment_total money_json Decimal pilot OpenAPI",
        "Credit supplier history purchase_total money_json Decimal pilot OpenAPI",
        "Credit supplier history return_total money_json Decimal pilot OpenAPI",
        "Credit supplier history payment_total money_json Decimal pilot OpenAPI",
        "Reports sales_monthly_total money_json Decimal pilot OpenAPI",
        "Customer group apply_discount money_json Decimal pilot OpenAPI",
        "Bank recon journal_line_signed_amount money_json Decimal pilot OpenAPI",
        "Credit AR aging document balance_due money_json Decimal pilot OpenAPI",
        "Credit AP aging document balance_due money_json Decimal pilot OpenAPI",
        "Credit aging add_to_bucket money_json Decimal pilot OpenAPI",
        "AI document PI draft discount_amount money_json Decimal pilot OpenAPI",
        "Expenses approval matrix min_amount money_json Decimal pilot OpenAPI",
        "Credit statement line balance_due money_json Decimal pilot OpenAPI",
        "Expenses Save expense numbering aria OpenAPI",
        "Expenses Add expense approval level aria OpenAPI",
        "Expenses Save expense approval matrix aria OpenAPI",
        "Expenses Add expense category aria OpenAPI",
        "Expenses Expense category status filter aria OpenAPI",
        "Expenses Generate due recurring expenses aria OpenAPI",
        "Expenses Recurring expense status filter aria OpenAPI",
        "Users Custom role status filter aria OpenAPI",
        "Users User status filter aria OpenAPI",
        "Stores Branch status filter aria OpenAPI",
        "Stores Department status filter aria OpenAPI",
        "Stores Store status filter aria OpenAPI",
        "Stores Warehouse status filter aria OpenAPI",
        "Credit Early pay discount days aria OpenAPI",
        "Credit FX currency code aria OpenAPI",
        "Credit Save FX rate aria OpenAPI",
        "Credit Refresh FX rates from feed aria OpenAPI",
        "Credit Load party history aria OpenAPI",
    ):
        assert title in agents, title

    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    standards = docs.split("## 1. API Standards")[1].split("## 2.")[0]
    assert "churn_risk" in standards
    assert "journal_line_signed_amount" in standards
    assert "_month_revenue" in standards or "apply_discount" in standards or "sales_monthly_total" in standards or "churn_risk" in standards

    expenses = (ROOT / "frontend/app/expenses/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Save expense numbering"' in expenses
    assert 'aria-label="Expense category status filter"' in expenses
    assert 'aria-label="Recurring expense status filter"' in expenses

    users = (ROOT / "frontend/app/users/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Custom role status filter"' in users
    assert 'aria-label="User status filter"' in users

    stores = (ROOT / "frontend/app/stores/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Branch status filter"' in stores
    assert 'aria-label="Warehouse status filter"' in stores

    credit = (ROOT / "frontend/app/credit/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="FX currency code"' in credit
    assert 'aria-label="Load party history"' in credit


def test_money_json_wired_batch24():
    assert money_json("12.50") == 12.5

    pct_src = inspect.getsource(ai_mod._pct_delta)
    assert "money_json(100.0)" in pct_src
    assert "return money_json(round((current - previous)" in pct_src

    churn_src = inspect.getsource(ai_customer_mod.churn_score)
    assert "score = money_json(round(min(0.99" in churn_src

    conf_src = inspect.getsource(ai_inventory_mod.confidence_score)
    assert "return money_json(0.25)" in conf_src
    assert "return money_json(round(_clamp(" in conf_src

    rec_src = inspect.getsource(ai_inventory_mod._recommended_qty)
    assert "return money_json(round(max(reorder_qty, gap), 3))" in rec_src
    assert "return money_json(0)" in rec_src

    ocr_src = inspect.getsource(expense_ocr_mod.parse_receipt_text)
    assert '"confidence": money_json(round(confidence, 2))' in ocr_src

    cust_hist = inspect.getsource(credit_mod.customer_history)
    assert "purchase_total = money_json(round(sum(" in cust_hist
    assert "return_total = money_json(round(sum(" in cust_hist
    assert "payment_total = money_json(round(sum(" in cust_hist

    sup_hist = inspect.getsource(credit_mod.supplier_history)
    assert "purchase_total = money_json(round(sum(" in sup_hist
    assert "return_total = money_json(round(sum(" in sup_hist
    assert "payment_total = money_json(round(sum(" in sup_hist

    month_src = inspect.getsource(reports_mod.sales_monthly_total)
    assert "return money_json(round(inv + pos, 2))" in month_src

    disc_src = inspect.getsource(customer_groups_mod.apply_discount)
    assert "return money_json(round(base * (1.0 - pct / 100.0), 2))" in disc_src

    jl_src = inspect.getsource(bank_recon_mod.journal_line_signed_amount)
    assert "return money_json(round(float(line.debit or 0)" in jl_src

    bucket_src = inspect.getsource(credit_mod.add_to_bucket)
    assert "buckets[key] = money_json(round(" in bucket_src

    ar_src = inspect.getsource(credit_mod.ar_aging)
    assert '"balance_due": money_json(due)' in ar_src

    ap_src = inspect.getsource(credit_mod.ap_aging)
    assert '"balance_due": money_json(due)' in ap_src

    pi_src = inspect.getsource(ai_documents_mod.create_purchase_invoice_from_extract)
    assert "discount_amount = money_json(round(sum(" in pi_src

    exp_src = inspect.getsource(expenses_mod.update_approval_settings)
    assert '"min_amount": money_json(round(auto_t, 2))' in exp_src
    assert '"min_amount": money_json(round(l2_t, 2))' in exp_src

    stmt_src = inspect.getsource(credit_mod.customer_statement)
    assert '"balance_due": money_json(' in stmt_src
    assert '"debit": money_json(0)' in stmt_src
