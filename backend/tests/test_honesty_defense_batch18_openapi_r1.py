"""OpenAPI honesty tips #1143–#1182: prefix/tax/bank defense + credit/POS/dashboard money_json + residual aria."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.honesty import money_json, optional_honest_narrative, require_honest_narrative
from app import cash_transfers as cash_transfers_mod
from app import credit as credit_mod
from app import dashboard as dashboard_mod
from app import doc_numbers as doc_numbers_mod
from app import expenses as expenses_mod
from app import inventory as inventory_mod
from app import pos as pos_mod
from app import tax as tax_mod

ROOT = Path(__file__).resolve().parents[2]


def test_honesty_batch18_docs_and_agents():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for title in (
        "Document prefix defense-in-depth OpenAPI",
        "Tax component code defense-in-depth OpenAPI",
        "Tax component name defense-in-depth OpenAPI",
        "Bank name defense-in-depth OpenAPI",
        "Bank branch defense-in-depth OpenAPI",
        "Credit limit exceeded credit_limit money_json Decimal pilot OpenAPI",
        "Credit limit exceeded current_balance money_json Decimal pilot OpenAPI",
        "Credit limit exceeded amount money_json Decimal pilot OpenAPI",
        "Credit limit exceeded projected_balance money_json Decimal pilot OpenAPI",
        "Credit limit exceeded over_by money_json Decimal pilot OpenAPI",
        "Sales invoice early discount discount_amount money_json Decimal pilot OpenAPI",
        "Sales invoice early discount cash_to_settle money_json Decimal pilot OpenAPI",
        "Sales invoice early discount balance_due money_json Decimal pilot OpenAPI",
        "Purchase invoice early discount discount_amount money_json Decimal pilot OpenAPI",
        "Customer credit info credit_limit money_json Decimal pilot OpenAPI",
        "Customer credit info outstanding_balance money_json Decimal pilot OpenAPI",
        "Customer credit info available_credit money_json Decimal pilot OpenAPI",
        "Customer credit info open_invoice_total money_json Decimal pilot OpenAPI",
        "Supplier credit info outstanding_balance money_json Decimal pilot OpenAPI",
        "POS Z-report summary subtotal money_json Decimal pilot OpenAPI",
        "POS Z-report summary tax money_json Decimal pilot OpenAPI",
        "POS Z-report summary discounts money_json Decimal pilot OpenAPI",
        "POS Z-report summary net_sales money_json Decimal pilot OpenAPI",
        "Dashboard monthly sales total money_json Decimal pilot OpenAPI",
        "Dashboard daily sales money_json Decimal pilot OpenAPI",
        "Inventory warehouse stock total_quantity money_json Decimal pilot OpenAPI",
        "Expense approval matrix min_amount money_json Decimal pilot OpenAPI",
        "Platform Activate platform staff aria OpenAPI",
        "Platform Deactivate platform staff aria OpenAPI",
        "Platform Revoke dashboard access aria OpenAPI",
        "Integrations View API key usage aria OpenAPI",
        "Integrations Rotate webhook secret aria OpenAPI",
        "Notifications Mark all notifications read aria OpenAPI",
        "Security Remove passkey aria OpenAPI",
        "Security Start 2FA setup aria OpenAPI",
        "Sales View quotation aria OpenAPI",
        "Sales View sales order aria OpenAPI",
        "Sales View sales invoice aria OpenAPI",
        "Sales View sales return aria OpenAPI",
        "Sales Pay sales invoice aria OpenAPI",
    ):
        assert title in agents, title

    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    standards = docs.split("## 1. API Standards")[1].split("## 2.")[0]
    assert "money_json" in standards
    assert "Document" in standards or "prefix" in standards.lower()
    assert "tax" in standards.lower() and "component" in standards.lower()

    staff = (ROOT / "frontend/app/platform/staff/page.tsx").read_text(encoding="utf-8")
    assert "Activate platform staff" in staff
    assert "Deactivate platform staff" in staff
    assert "Revoke dashboard access" in staff

    integrations = (ROOT / "frontend/app/integrations/page.tsx").read_text(encoding="utf-8")
    assert "View API key usage" in integrations
    assert "Rotate webhook secret" in integrations

    notifications = (ROOT / "frontend/app/notifications/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Mark all notifications read"' in notifications

    security = (ROOT / "frontend/app/security/page.tsx").read_text(encoding="utf-8")
    assert "Remove passkey" in security
    assert 'aria-label="Start 2FA setup"' in security

    sales = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert "View quotation" in sales
    assert "View sales order" in sales
    assert "View sales invoice" in sales
    assert "View sales return" in sales
    assert "Pay sales invoice" in sales


def test_prefix_tax_bank_defense_batch18():
    with pytest.raises(HTTPException) as exc:
        require_honest_narrative("!!!", label="document prefix", max_length=20)
    assert exc.value.status_code == 400

    with pytest.raises(HTTPException):
        doc_numbers_mod.normalize_prefix("!!!")

    with pytest.raises(HTTPException):
        doc_numbers_mod.normalize_prefix("http://evil")

    assert doc_numbers_mod.normalize_prefix("inv") == "INV"
    assert doc_numbers_mod.normalize_prefix(None) == "INV"

    prefix_src = inspect.getsource(doc_numbers_mod.normalize_prefix)
    assert "require_honest_narrative" in prefix_src
    assert 'label="document prefix"' in prefix_src

    with pytest.raises(HTTPException):
        tax_mod.normalize_components([{"rate": 5, "code": "!!!", "basis": "net"}])

    with pytest.raises(HTTPException):
        tax_mod.normalize_components(
            [{"rate": 5, "name": "http://evil", "basis": "net"}]
        )

    comps = tax_mod.normalize_components([{"rate": 5, "basis": "net"}])
    assert comps and comps[0]["code"].startswith("c")
    assert comps[0]["name"] == comps[0]["code"]

    comps2 = tax_mod.normalize_components(
        [{"rate": 12.5, "code": "VAT", "name": "Value added", "basis": "net"}]
    )
    assert comps2[0]["code"] == "VAT"
    assert comps2[0]["name"] == "Value added"

    comp_src = inspect.getsource(tax_mod.normalize_components)
    assert "optional_honest_narrative" in comp_src
    assert 'label="tax component code"' in comp_src
    assert 'label="tax component name"' in comp_src

    create_src = inspect.getsource(cash_transfers_mod.create_account)
    assert 'label="bank name"' in create_src
    assert 'label="bank branch"' in create_src

    upd_src = inspect.getsource(cash_transfers_mod.update_account)
    assert 'label="bank name"' in upd_src
    assert 'label="bank branch"' in upd_src

    with pytest.raises(HTTPException):
        optional_honest_narrative("http://bank", label="bank name", max_length=120)


def test_money_json_wired_batch18():
    assert money_json("12.50") == 12.5

    enforce_src = inspect.getsource(credit_mod.enforce_customer_credit_limit)
    assert "money_json(credit_limit)" in enforce_src
    assert "money_json(current)" in enforce_src
    assert 'money_json(round(projected, 2))' in enforce_src
    assert "money_json(round(projected - credit_limit, 2))" in enforce_src

    si_early = inspect.getsource(credit_mod.invoice_early_discount)
    assert 'money_json(round(due, 2))' in si_early
    assert "money_json(round(due * pct / 100.0, 2))" in si_early

    pi_early = inspect.getsource(credit_mod.purchase_invoice_early_discount)
    assert "money_json(round(due * pct / 100.0, 2))" in pi_early

    cust_src = inspect.getsource(credit_mod.customer_credit_info)
    assert "money_json(customer.credit_limit or 0)" in cust_src
    assert 'money_json(round(outstanding, 2))' in cust_src
    assert 'money_json(round(open_invoice_total, 2))' in cust_src

    supp_src = inspect.getsource(credit_mod.supplier_credit_info)
    assert 'money_json(round(outstanding, 2))' in supp_src

    pos_src = Path(pos_mod.__file__).read_text(encoding="utf-8")
    assert 'money_json(round(subtotal_sum, 2))' in pos_src
    assert 'money_json(round(tax_sum, 2))' in pos_src
    assert 'money_json(round(discount_sum, 2))' in pos_src
    assert 'money_json(round(net_sum, 2))' in pos_src

    dash_src = Path(dashboard_mod.__file__).read_text(encoding="utf-8")
    assert 'money_json(round(month_totals[(yy, mm)], 2))' in dash_src
    assert 'money_json(round(daily[d]["sales"], 2))' in dash_src

    inv_src = Path(inventory_mod.__file__).read_text(encoding="utf-8")
    assert 'money_json(round(sum(i["quantity"] for i in items), 3))' in inv_src

    matrix_src = inspect.getsource(expenses_mod.normalize_approval_matrix)
    assert 'money_json(round(min_amount, 2))' in matrix_src
