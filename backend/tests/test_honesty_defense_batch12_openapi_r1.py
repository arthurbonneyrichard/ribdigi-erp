"""OpenAPI honesty tips #924–#947: SMTP/SMS/webhook/AI-doc defense + tax/webhook money_json + download aria."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.honesty import money_json, optional_honest_narrative
from app import ai_documents as ai_documents_mod
from app import api as api_mod
from app import bank_recon as bank_recon_mod
from app import email_settings as email_settings_mod
from app import inventory as inventory_mod
from app import purchasing as purchasing_mod
from app import sales as sales_mod
from app import sms_settings as sms_settings_mod
from app import stores as stores_mod
from app import webhooks as webhooks_mod

ROOT = Path(__file__).resolve().parents[2]


def test_honesty_batch12_docs_and_agents():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for title in (
        "Company SMTP username defense-in-depth OpenAPI",
        "Company SMTP password defense-in-depth OpenAPI",
        "Company SMS auth_token defense-in-depth OpenAPI",
        "Webhook secret defense-in-depth OpenAPI",
        "AI document expense description defense-in-depth OpenAPI",
        "AI document expense payee defense-in-depth OpenAPI",
        "AI document expense reference defense-in-depth OpenAPI",
        "AI document purchase invoice notes defense-in-depth OpenAPI",
        "Sales invoice tax_breakdown money_json Decimal pilot OpenAPI",
        "Purchase invoice tax_breakdown money_json Decimal pilot OpenAPI",
        "PO created webhook money_json Decimal pilot OpenAPI",
        "Stock in webhook money_json Decimal pilot OpenAPI",
        "Stock out webhook money_json Decimal pilot OpenAPI",
        "Store reorder policy money_json Decimal pilot OpenAPI",
        "AI document amount flag money_json Decimal pilot OpenAPI",
        "Bank recon statement arithmetic money_json Decimal pilot OpenAPI",
        "Users Download CSV template aria OpenAPI",
        "Sales Print A4 aria OpenAPI",
        "Sales Print thermal aria OpenAPI",
        "Backup Download aria OpenAPI",
        "Expenses Download attachment aria OpenAPI",
        "Purchasing Download PI attachment aria OpenAPI",
        "Accounting Download journal attachment aria OpenAPI",
        "Accounting Import bank CSV/OFX aria OpenAPI",
    ):
        assert title in agents, title

    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    standards = docs.split("## 1. API Standards")[1].split("## 2. Authentication")[0]
    assert "money_json" in standards
    assert "tax_breakdown" in standards
    assert "statement arithmetic" in standards.lower() or "stock amount" in standards.lower()

    users_page = (ROOT / "frontend/app/users/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Download user CSV template"' in users_page

    sales_page = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Print sales invoice A4"' in sales_page
    assert 'aria-label="Print sales invoice thermal"' in sales_page

    backup_page = (ROOT / "frontend/app/backup/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Download backup"' in backup_page

    expenses_page = (ROOT / "frontend/app/expenses/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Download expense attachment"' in expenses_page

    purchasing_page = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Download purchase invoice attachment"' in purchasing_page

    accounting_page = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Download journal attachment"' in accounting_page
    assert 'aria-label="Import bank statement CSV or OFX"' in accounting_page


def test_optional_helpers_and_money_json_batch12():
    assert optional_honest_narrative(None, label="webhook signing secret") is None
    assert optional_honest_narrative("whsec_abc123", label="webhook signing secret") == "whsec_abc123"
    with pytest.raises(HTTPException) as exc:
        optional_honest_narrative("!!!", label="SMTP password")
    assert exc.value.status_code == 400
    with pytest.raises(HTTPException):
        optional_honest_narrative("http://evil", label="Twilio auth token")
    assert money_json("9.99") == 9.99


def test_services_wire_honest_narrative_batch12():
    email_src = inspect.getsource(email_settings_mod.apply_email_settings_update)
    assert "SMTP username is required" in email_src
    assert "optional_honest_narrative" in email_src
    assert "SMTP password" in email_src

    sms_src = inspect.getsource(sms_settings_mod.apply_sms_settings_update)
    assert "Twilio auth token" in sms_src
    assert "optional_honest_narrative" in sms_src

    wh_src = inspect.getsource(webhooks_mod.create_endpoint)
    assert "optional_honest_narrative" in wh_src
    assert "webhook signing secret" in wh_src

    exp_src = inspect.getsource(ai_documents_mod.create_expense_from_extract)
    assert "optional_honest_narrative" in exp_src
    assert "expense description" in exp_src
    assert "expense payee" in exp_src
    assert "expense reference" in exp_src

    pi_src = inspect.getsource(ai_documents_mod.create_purchase_invoice_from_extract)
    assert "optional_honest_narrative" in pi_src
    assert "purchase invoice notes" in pi_src


def test_money_json_wired_batch12():
    si_tax = inspect.getsource(sales_mod._invoice_tax_breakdown)
    assert "money_json(invoice.tax_amount" in si_tax
    assert "money_json(getattr(i, \"line_subtotal\"" in si_tax or 'money_json(getattr(i, "line_subtotal"' in si_tax

    pi_tax = inspect.getsource(purchasing_mod._purchase_invoice_tax_breakdown)
    assert "money_json(inv.tax_amount" in pi_tax

    create_po = inspect.getsource(api_mod.create_purchase_order)
    assert "money_json(getattr(po, \"total_amount\"" in create_po or 'money_json(getattr(po, "total_amount"' in create_po

    stock_src = inspect.getsource(inventory_mod.apply_stock_change)
    assert 'event="stock.in"' in stock_src
    assert 'event="stock.out"' in stock_src
    assert "money_json(quantity_delta)" in stock_src
    assert "money_json(after)" in stock_src

    reorder = inspect.getsource(stores_mod.set_store_reorder_policy)
    assert "money_json(row.quantity" in reorder
    assert "money_json(row.reorder_qty" in reorder

    flags = inspect.getsource(ai_documents_mod.build_discrepancies)
    assert "money_json(fields[\"amount\"])" in flags or "money_json(fields['amount'])" in flags
    assert "money_json(expected_amount)" in flags

    recon = inspect.getsource(bank_recon_mod.complete_statement)
    assert "money_json(stmt.closing_balance" in recon
    assert "STATEMENT_ARITHMETIC" in recon
