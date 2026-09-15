"""OpenAPI honesty tips #948–#982: bank/SMTP/SMS/drawer/AI defense + feed/webhook money_json + residual aria."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.honesty import money_json, optional_honest_narrative, require_honest_narrative
from app import ai_reports as ai_reports_mod
from app import api as api_mod
from app import bank_connectors as bank_connectors_mod
from app import email_settings as email_settings_mod
from app import notifications as notifications_mod
from app import sales_docs as sales_docs_mod
from app import sms_settings as sms_settings_mod

ROOT = Path(__file__).resolve().parents[2]


def test_honesty_batch13_docs_and_agents():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for title in (
        "Bank connection access_token defense-in-depth OpenAPI",
        "Company SMTP host defense-in-depth OpenAPI",
        "Company SMS from_number defense-in-depth OpenAPI",
        "Cash drawer host defense-in-depth OpenAPI",
        "AI report prompt defense-in-depth OpenAPI",
        "AI report period defense-in-depth OpenAPI",
        "Stock low product webhook money_json Decimal pilot OpenAPI",
        "Stock low warehouse webhook money_json Decimal pilot OpenAPI",
        "Bank feed normalize money_json Decimal pilot OpenAPI",
        "Bank mock feed money_json Decimal pilot OpenAPI",
        "Bank sync statement balances money_json Decimal pilot OpenAPI",
        "Cash transfer audit money_json Decimal pilot OpenAPI",
        "Sales return discard audit money_json Decimal pilot OpenAPI",
        "Notification payment due money_json Decimal pilot OpenAPI",
        "Notification recurring expense due money_json Decimal pilot OpenAPI",
        "Users Validate CSV import aria OpenAPI",
        "Users Import valid CSV rows aria OpenAPI",
        "Inventory Generate product barcode aria OpenAPI",
        "Inventory Print product barcode label aria OpenAPI",
        "Inventory Validate product CSV aria OpenAPI",
        "Inventory Import valid product CSV aria OpenAPI",
        "Inventory Generate variant barcode aria OpenAPI",
        "Inventory Print variant barcode label aria OpenAPI",
        "Integrations Copy API key aria OpenAPI",
        "Integrations Copy webhook signing secret aria OpenAPI",
        "Integrations Retry webhook delivery aria OpenAPI",
        "Integrations Refresh webhook deliveries aria OpenAPI",
        "Accounting Sync bank connection aria OpenAPI",
        "Notifications Scan due alerts aria OpenAPI",
        "Jobs Refresh list aria OpenAPI",
        "Reports Run schedule now aria OpenAPI",
        "Reports Toggle schedule enabled aria OpenAPI",
        "Credit Save early pay terms aria OpenAPI",
        "Stores Save store allocation aria OpenAPI",
        "Login Resend verification email aria OpenAPI",
    ):
        assert title in agents, title

    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    standards = docs.split("## 1. API Standards")[1].split("## 2. Authentication")[0]
    assert "money_json" in standards
    assert "stock.low" in standards
    assert "bank feed" in standards.lower()

    users_page = (ROOT / "frontend/app/users/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Validate user CSV import"' in users_page
    assert 'aria-label="Import valid user CSV rows"' in users_page

    inv_page = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Generate product barcode"' in inv_page
    assert 'aria-label="Print product barcode label"' in inv_page
    assert 'aria-label="Validate product CSV import"' in inv_page
    assert 'aria-label="Import valid product CSV rows"' in inv_page

    integ = (ROOT / "frontend/app/integrations/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Copy API key"' in integ
    assert 'aria-label="Refresh webhook deliveries"' in integ

    accounting = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert "Sync bank connection" in accounting

    notif = (ROOT / "frontend/app/notifications/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Scan due notification alerts"' in notif

    login = (ROOT / "frontend/app/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Resend verification email"' in login


def test_optional_helpers_and_money_json_batch13():
    assert optional_honest_narrative(None, label="bank connection access token") is None
    assert (
        optional_honest_narrative("tok_abc123", label="bank connection access token")
        == "tok_abc123"
    )
    with pytest.raises(HTTPException) as exc:
        optional_honest_narrative("!!!", label="bank connection access token")
    assert exc.value.status_code == 400
    with pytest.raises(HTTPException):
        require_honest_narrative("http://evil", label="AI report prompt")
    assert money_json("12.50") == 12.5


def test_services_wire_honest_narrative_batch13():
    create_src = inspect.getsource(bank_connectors_mod.create_connection)
    assert "optional_honest_narrative" in create_src
    assert "bank connection access token" in create_src

    update_src = inspect.getsource(bank_connectors_mod.update_connection)
    assert "bank connection access token" in update_src
    assert "optional_honest_narrative" in update_src

    email_src = inspect.getsource(email_settings_mod.apply_email_settings_update)
    assert "validate_smtp_host_value" in email_src

    sms_src = inspect.getsource(sms_settings_mod.apply_sms_settings_update)
    assert "validate_e164_phone_value" in sms_src

    drawer_src = inspect.getsource(api_mod.update_store_drawer)
    assert "validate_smtp_host_value" in drawer_src

    parse_src = inspect.getsource(ai_reports_mod.parse_prompt)
    assert "require_honest_narrative" in parse_src
    assert "AI report prompt" in parse_src

    gen_src = inspect.getsource(ai_reports_mod.generate_report)
    assert "optional_honest_narrative" in gen_src
    assert "AI report period" in gen_src


def test_money_json_wired_batch13():
    low_src = inspect.getsource(notifications_mod.notify_low_stock_if_needed)
    assert "money_json(product.stock_qty" in low_src
    assert 'event="stock.low"' in low_src

    wh_src = inspect.getsource(notifications_mod.notify_warehouse_low_stock_if_needed)
    assert "money_json(stock.quantity" in wh_src
    assert "suggested_order_qty" in wh_src

    norm = inspect.getsource(bank_connectors_mod._normalize_txn)
    assert "money_json(amount)" in norm or "money_json(raw.get" in norm

    mock = inspect.getsource(bank_connectors_mod._mock_transactions)
    assert "money_json(base_amt)" in mock

    sync = inspect.getsource(bank_connectors_mod.sync_connection)
    assert "money_json(ln[" in sync or 'money_json(ln["amount"])' in sync

    xfer = inspect.getsource(api_mod.create_cash_transfer)
    assert "money_json(row.amount)" in xfer

    discard = inspect.getsource(sales_docs_mod.post_return)
    assert "money_json(item.quantity)" in discard
    assert "return_discarded" in discard

    pay = inspect.getsource(notifications_mod.scan_payment_due)
    assert "money_json(inv.total_amount)" in pay

    rec = inspect.getsource(notifications_mod.scan_recurring_expense_due)
    assert "money_json(row.amount" in rec
