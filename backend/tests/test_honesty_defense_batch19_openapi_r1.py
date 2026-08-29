"""OpenAPI honesty tips #1183–#1222: slug/category defense + aging/TB/tax money_json + residual aria."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.honesty import money_json, optional_honest_narrative, require_honest_narrative
from app import accounting as accounting_mod
from app import ai_expenses as ai_expenses_mod
from app import catalog_meta as catalog_meta_mod
from app import credit as credit_mod
from app import expenses as expenses_mod
from app import opening_stock as opening_stock_mod
from app import purchasing as purchasing_mod
from app import sales as sales_mod
from app import tax as tax_mod
from app import tenants as tenants_mod

ROOT = Path(__file__).resolve().parents[2]


def test_honesty_batch19_docs_and_agents():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for title in (
        "Tenant slug defense-in-depth OpenAPI",
        "Tenant create company_name defense-in-depth OpenAPI",
        "Product category label defense-in-depth OpenAPI",
        "Expense category label defense-in-depth OpenAPI",
        "Opening stock inventory_value money_json Decimal pilot OpenAPI",
        "Sales invoice balance_due_base money_json Decimal pilot OpenAPI",
        "Purchase return discount_amount money_json Decimal pilot OpenAPI",
        "Purchase return line discount money_json Decimal pilot OpenAPI",
        "Credit AR aging total_due money_json Decimal pilot OpenAPI",
        "Credit AR aging balance_due_base money_json Decimal pilot OpenAPI",
        "Credit AP aging total_due money_json Decimal pilot OpenAPI",
        "Credit AP aging balance_due_base money_json Decimal pilot OpenAPI",
        "Supplier payment schedule balance_due money_json Decimal pilot OpenAPI",
        "Supplier payment schedule total_due money_json Decimal pilot OpenAPI",
        "Trial balance total_debit money_json Decimal pilot OpenAPI",
        "Trial balance total_credit money_json Decimal pilot OpenAPI",
        "Trial balance row balance money_json Decimal pilot OpenAPI",
        "Tax report schedule net_amount money_json Decimal pilot OpenAPI",
        "Tax report schedule tax_amount money_json Decimal pilot OpenAPI",
        "Tax report schedule gross_amount money_json Decimal pilot OpenAPI",
        "Tax report schedule reverse_charge_tax money_json Decimal pilot OpenAPI",
        "AI expenses unusual category_mean money_json Decimal pilot OpenAPI",
        "AI expenses unusual category_std money_json Decimal pilot OpenAPI",
        "AI expenses duplicate amount money_json Decimal pilot OpenAPI",
        "Accounting Remove journal line aria OpenAPI",
        "Accounting Remove opening balance line aria OpenAPI",
        "Accounting Apply trial balance filters aria OpenAPI",
        "Accounting Apply profit and loss filters aria OpenAPI",
        "Accounting Preview journal attachment aria OpenAPI",
        "Accounting Remove journal attachment aria OpenAPI",
        "Accounting Unmatch bank statement line aria OpenAPI",
        "Credit Show receivables aging aria OpenAPI",
        "Credit Show payables aging aria OpenAPI",
        "Shell Mark bell notification read aria OpenAPI",
        "Shell Mark all bell notifications read aria OpenAPI",
        "Company Remove company logo aria OpenAPI",
        "Party contact Make primary aria OpenAPI",
        "Party contact Delete aria OpenAPI",
        "Onboarding Open step aria OpenAPI",
        "Purchasing View purchase invoice aria OpenAPI",
    ):
        assert title in agents, title

    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    standards = docs.split("## 1. API Standards")[1].split("## 2.")[0]
    assert "money_json" in standards
    assert "slug" in standards.lower()
    assert "category label" in standards.lower() or "category" in standards.lower()

    accounting = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert "Remove journal line" in accounting
    assert "Remove opening balance line" in accounting
    assert 'aria-label="Apply trial balance filters"' in accounting
    assert 'aria-label="Apply profit and loss filters"' in accounting
    assert "Preview journal attachment" in accounting
    assert "Remove journal attachment" in accounting
    assert "Unmatch bank statement line" in accounting

    credit = (ROOT / "frontend/app/credit/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Show receivables aging"' in credit
    assert 'aria-label="Show payables aging"' in credit

    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "Mark bell notification" in shell
    assert 'aria-label="Mark all bell notifications read"' in shell

    company = (ROOT / "frontend/app/company/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Remove company logo"' in company

    party = (ROOT / "frontend/components/PartyContactsPanel.tsx").read_text(encoding="utf-8")
    assert "Make party contact" in party
    assert "Delete party contact" in party

    onboarding = (ROOT / "frontend/components/OnboardingChecklist.tsx").read_text(
        encoding="utf-8"
    )
    assert "Open onboarding step" in onboarding

    purchasing = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert "View purchase invoice" in purchasing


def test_slug_category_defense_batch19():
    with pytest.raises(HTTPException) as exc:
        tenants_mod.require_tenant_slug("!!!")
    assert exc.value.status_code == 400

    with pytest.raises(HTTPException):
        tenants_mod.require_tenant_slug("http://evil")

    with pytest.raises(HTTPException):
        tenants_mod.require_tenant_slug("-bad")

    assert tenants_mod.require_tenant_slug("Acme-Co") == "acme-co"

    with pytest.raises(HTTPException):
        tenants_mod.require_company_name("!!!")

    with pytest.raises(HTTPException):
        tenants_mod.require_company_name("X")

    assert tenants_mod.require_company_name("  Acme Trading  ") == "Acme Trading"

    with pytest.raises(HTTPException):
        optional_honest_narrative("!!!", label="product category label", max_length=100)

    refs_src = inspect.getsource(catalog_meta_mod.resolve_product_refs)
    assert "optional_honest_narrative" in refs_src
    assert 'label="product category label"' in refs_src

    with pytest.raises(HTTPException):
        require_honest_narrative("http://evil", label="expense category label", max_length=100)

    cat_src = inspect.getsource(expenses_mod.resolve_category)
    assert "require_honest_narrative" in cat_src
    assert 'label="expense category label"' in cat_src


def test_money_json_wired_batch19():
    assert money_json("12.50") == 12.5

    open_src = Path(opening_stock_mod.__file__).read_text(encoding="utf-8")
    assert 'money_json(round(inventory_value, 2))' in open_src

    si_src = inspect.getsource(sales_mod.serialize_invoice)
    assert "money_json(round(balance_due * fx, 2))" in si_src

    pr_src = inspect.getsource(purchasing_mod.serialize_purchase_return)
    assert "money_json(round(discount_total, 2))" in pr_src
    assert "money_json(disc)" in pr_src

    ar_src = inspect.getsource(credit_mod.ar_aging)
    assert 'money_json(round(sum(totals.values()), 2))' in ar_src
    assert "money_json(" in ar_src and "balance_due_base" in ar_src

    ap_src = inspect.getsource(credit_mod.ap_aging)
    assert 'money_json(round(sum(totals.values()), 2))' in ap_src

    sched_src = inspect.getsource(credit_mod.supplier_payment_schedule)
    assert "money_json(round(balance, 2))" in sched_src
    assert 'money_json(round(sum(r["balance_due"] for r in items), 2))' in sched_src

    tb_src = Path(accounting_mod.__file__).read_text(encoding="utf-8")
    assert 'money_json(round(debit_total, 2))' in tb_src
    assert 'money_json(round(credit_total, 2))' in tb_src

    tax_src = Path(tax_mod.__file__).read_text(encoding="utf-8")
    assert 'money_json(round(net, 2))' in tax_src
    assert 'money_json(round(tax, 2))' in tax_src
    assert "money_json(round(float(po.total_amount or 0), 2))" in tax_src
    assert 'money_json(round(rc, 2))' in tax_src

    ai_src = Path(ai_expenses_mod.__file__).read_text(encoding="utf-8")
    assert "money_json(round(mean, 2))" in ai_src
    assert "money_json(round(std, 2))" in ai_src
    assert "money_json(k[1])" in ai_src
