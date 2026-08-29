"""OpenAPI honesty tips #983–#1022: phone/URL/AI defense + audit/feed/insight money_json + residual aria."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.honesty import money_json, optional_honest_narrative, require_honest_narrative
from app import ai as ai_mod
from app import ai_customer as ai_customer_mod
from app import api as api_mod
from app import bank_connectors as bank_connectors_mod
from app import bank_feed as bank_feed_mod
from app import org_units as org_units_mod
from app import party_contacts as party_contacts_mod
from app import purchasing as purchasing_mod
from app import sales as sales_mod
from app import stores as stores_mod
from app import tenants as tenants_mod

ROOT = Path(__file__).resolve().parents[2]


def test_honesty_batch14_docs_and_agents():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for title in (
        "AI chat message defense-in-depth OpenAPI",
        "AI customer assist query defense-in-depth OpenAPI",
        "Company website defense-in-depth OpenAPI",
        "Company phone defense-in-depth OpenAPI",
        "Bank feed URL defense-in-depth OpenAPI",
        "Purchase invoice attachment URL defense-in-depth OpenAPI",
        "Store phone defense-in-depth OpenAPI",
        "Branch phone defense-in-depth OpenAPI",
        "Profile phone defense-in-depth OpenAPI",
        "User phone defense-in-depth OpenAPI",
        "Party phone defense-in-depth OpenAPI",
        "Party contact phone defense-in-depth OpenAPI",
        "Purchase order create audit money_json Decimal pilot OpenAPI",
        "Purchase invoice approve audit money_json Decimal pilot OpenAPI",
        "Expense update audit money_json Decimal pilot OpenAPI",
        "Sales invoice create audit money_json Decimal pilot OpenAPI",
        "Sales invoice post audit money_json Decimal pilot OpenAPI",
        "Bank CSV feed import money_json Decimal pilot OpenAPI",
        "Bank OFX feed import money_json Decimal pilot OpenAPI",
        "Bank OFX balances money_json Decimal pilot OpenAPI",
        "AI insights dashboard totals money_json Decimal pilot OpenAPI",
        "AI insights restock recommendation money_json Decimal pilot OpenAPI",
        "Accounting Add opening balance line aria OpenAPI",
        "Accounting Open bank statement aria OpenAPI",
        "Accounting Dissolve clearing group aria OpenAPI",
        "Accounting Ignore bank statement line aria OpenAPI",
        "Accounting Deposit cheque aria OpenAPI",
        "Accounting Clear cheque aria OpenAPI",
        "Accounting Mark statement reconciled aria OpenAPI",
        "Accounting Remove bank connection aria OpenAPI",
        "AI Load insights aria OpenAPI",
        "AI Email insight digest aria OpenAPI",
        "AI Load security alerts aria OpenAPI",
        "Audit Verify chain aria OpenAPI",
        "Backup Save settings aria OpenAPI",
        "Company Activate aria OpenAPI",
        "Credit Load party statement aria OpenAPI",
        "Expenses Submit expense aria OpenAPI",
        "Expenses Apply OCR suggestion aria OpenAPI",
        "Integrations Create webhook aria OpenAPI",
        "Integrations Revoke API key aria OpenAPI",
    ):
        assert title in agents, title

    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    standards = docs.split("## 1. API Standards")[1].split("## 2. Authentication")[0]
    assert "money_json" in standards
    assert "CSV/OFX" in standards or "csv/ofx" in standards.lower()
    assert "insight" in standards.lower()
    assert "audit" in standards.lower()

    accounting = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Add opening balance line"' in accounting
    assert "Open bank statement" in accounting
    assert "Dissolve clearing group" in accounting
    assert "Ignore bank statement line" in accounting
    assert "Deposit cheque" in accounting
    assert "Clear cheque" in accounting
    assert 'aria-label="Mark bank statement reconciled"' in accounting
    assert "Remove bank connection" in accounting

    ai_page = (ROOT / "frontend/app/ai/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Load AI insights"' in ai_page
    assert 'aria-label="Email AI insight digest"' in ai_page
    assert 'aria-label="Load AI security alerts"' in ai_page

    audit = (ROOT / "frontend/app/audit/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Verify audit chain"' in audit

    backup = (ROOT / "frontend/app/backup/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Save backup settings"' in backup

    company = (ROOT / "frontend/app/company/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Activate company"' in company

    credit = (ROOT / "frontend/app/credit/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Load party statement"' in credit

    expenses = (ROOT / "frontend/app/expenses/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Submit expense"' in expenses
    assert 'aria-label="Apply expense OCR suggestion"' in expenses

    integ = (ROOT / "frontend/app/integrations/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Create webhook"' in integ
    assert "Revoke API key" in integ


def test_optional_helpers_and_money_json_batch14():
    assert optional_honest_narrative(None, label="AI customer assist query") is None
    assert (
        optional_honest_narrative("show overdue", label="AI customer assist query")
        == "show overdue"
    )
    with pytest.raises(HTTPException) as exc:
        optional_honest_narrative("!!!", label="AI customer assist query")
    assert exc.value.status_code == 400
    with pytest.raises(HTTPException):
        require_honest_narrative("http://evil", label="AI chat message")
    assert money_json("12.50") == 12.5


def test_services_wire_honest_narrative_batch14():
    parse_src = inspect.getsource(ai_mod.parse_chat_message)
    assert "require_honest_narrative" in parse_src
    assert "AI chat message" in parse_src

    assist_src = inspect.getsource(ai_customer_mod.customer_assist)
    assert "optional_honest_narrative" in assist_src
    assert "AI customer assist query" in assist_src

    profile_src = inspect.getsource(tenants_mod.update_profile)
    assert "validate_webhook_url_value" in profile_src
    assert "validate_e164_phone_value" in profile_src

    create_conn = inspect.getsource(bank_connectors_mod.create_connection)
    assert "validate_webhook_url_value" in create_conn
    update_conn = inspect.getsource(bank_connectors_mod.update_connection)
    assert "validate_webhook_url_value" in update_conn

    attach_src = inspect.getsource(purchasing_mod._optional_attachment_url)
    assert "validate_webhook_url_value" in attach_src

    store_src = inspect.getsource(stores_mod._optional_store_phone)
    assert "validate_e164_phone_value" in store_src

    branch_src = inspect.getsource(org_units_mod._optional_branch_phone)
    assert "validate_e164_phone_value" in branch_src

    user_src = inspect.getsource(api_mod._optional_user_phone)
    assert "validate_e164_phone_value" in user_src

    party_src = inspect.getsource(api_mod._normalize_party_profile)
    assert "validate_e164_phone_value" in party_src

    contact_src = inspect.getsource(party_contacts_mod._optional_contact_phone)
    assert "validate_e164_phone_value" in contact_src

    me_src = inspect.getsource(api_mod.update_me)
    assert "validate_e164_phone_value" in me_src


def test_money_json_wired_batch14():
    po_src = inspect.getsource(purchasing_mod.create_purchase_order)
    assert "money_json(po.total_amount)" in po_src

    pi_src = inspect.getsource(purchasing_mod.approve_purchase_invoice)
    assert "money_json(inv.total_amount)" in pi_src

    exp_src = inspect.getsource(api_mod.patch_expense)
    assert "money_json(expense.amount)" in exp_src

    si_create = inspect.getsource(sales_mod.create_sales_invoice)
    assert "money_json(invoice.total_amount)" in si_create

    si_post = inspect.getsource(sales_mod.post_sales_invoice)
    assert "money_json(invoice.total_amount)" in si_post

    csv_src = inspect.getsource(bank_feed_mod.parse_csv_feed)
    assert "money_json" in csv_src

    ofx_src = inspect.getsource(bank_feed_mod.parse_ofx_feed)
    assert "money_json" in ofx_src
    assert "opening_balance" in ofx_src

    notes_src = inspect.getsource(ai_mod.build_insight_notes)
    assert "money_json(dash.get(\"total_expenses\")" in notes_src or 'money_json(dash.get("total_expenses"' in notes_src

    compose_src = inspect.getsource(ai_mod.compose_insights)
    assert "money_json(row.get(\"recommended_order_qty\")" in compose_src or 'money_json(row.get("recommended_order_qty"' in compose_src
