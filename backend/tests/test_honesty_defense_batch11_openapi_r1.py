"""OpenAPI honesty tips #905–#923: passkey/SMTP/SMS defense + POS/payment money_json + export aria."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.honesty import money_json, optional_honest_narrative
from app import ai_sales as ai_sales_mod
from app import api as api_mod
from app import email_settings as email_settings_mod
from app import inventory as inventory_mod
from app import pos as pos_mod
from app import purchasing as purchasing_mod
from app import sales as sales_mod
from app import sms_settings as sms_settings_mod
from app import webauthn_svc as webauthn_mod

ROOT = Path(__file__).resolve().parents[2]


def test_honesty_batch11_docs_and_agents():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for title in (
        "Passkey name defense-in-depth OpenAPI",
        "Company SMTP from_name defense-in-depth OpenAPI",
        "Company SMS account_sid defense-in-depth OpenAPI",
        "POS sale create money_json Decimal pilot OpenAPI",
        "POS sale webhook money_json Decimal pilot OpenAPI",
        "POS product search money_json Decimal pilot OpenAPI",
        "Customer payment response money_json Decimal pilot OpenAPI",
        "Supplier payment response money_json Decimal pilot OpenAPI",
        "POS session payment_breakdown money_json Decimal pilot OpenAPI",
        "AI sales analysis money_json Decimal pilot OpenAPI",
        "Stock adjustment money_json Decimal pilot OpenAPI",
        "Product warehouse-stock reorder money_json Decimal pilot OpenAPI",
        "Sales invoice post webhook money_json Decimal pilot OpenAPI",
        "Expense approve webhook money_json Decimal pilot OpenAPI",
        "AR payment webhook money_json Decimal pilot OpenAPI",
        "PO amend snapshot money_json Decimal pilot OpenAPI",
        "Inventory Export products CSV aria OpenAPI",
        "Inventory Download product CSV template aria OpenAPI",
        "Audit Export CSV aria OpenAPI",
    ):
        assert title in agents, title

    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    standards = docs.split("## 1. API Standards")[1].split("## 2. Authentication")[0]
    assert "money_json" in standards
    assert "POS sale create" in standards or "product search" in standards.lower()

    inventory_page = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Export products CSV"' in inventory_page
    assert 'aria-label="Download product CSV template"' in inventory_page

    audit_page = (ROOT / "frontend/app/audit/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Export audit CSV"' in audit_page


def test_optional_helpers_and_money_json_batch11():
    assert optional_honest_narrative(None, label="passkey name") is None
    assert optional_honest_narrative("Office key", label="passkey name") == "Office key"
    with pytest.raises(HTTPException) as exc:
        optional_honest_narrative("!!!", label="passkey name")
    assert exc.value.status_code == 400
    with pytest.raises(HTTPException):
        optional_honest_narrative("http://evil", label="SMTP from name")
    assert money_json("12.50") == 12.5


def test_services_wire_honest_narrative_batch11():
    src = inspect.getsource(webauthn_mod.verify_registration)
    assert "optional_honest_narrative" in src
    assert 'or "Passkey"' in src

    email_src = inspect.getsource(email_settings_mod.apply_email_settings_update)
    assert "optional_honest_narrative" in email_src
    assert "SMTP from name" in email_src

    sms_src = inspect.getsource(sms_settings_mod.apply_sms_settings_update)
    assert "optional_honest_narrative" in sms_src
    assert "Twilio account SID" in sms_src


def test_money_json_wired_batch11():
    pos_sale = inspect.getsource(api_mod.pos_sale)
    assert "money_json(tx.subtotal)" in pos_sale
    assert "money_json(tx.tax)" in pos_sale
    assert "money_json(tx.total)" in pos_sale

    pos_search = inspect.getsource(api_mod.pos_search)
    assert "money_json(p.selling_price" in pos_search
    assert "money_json(p.stock_qty" in pos_search
    assert "money_json(spec.rate_pct" in pos_search

    cust_pay = inspect.getsource(api_mod.record_sales_payment)
    assert "money_json(payment.amount)" in cust_pay

    cust_pay2 = inspect.getsource(api_mod.customer_payment_alias)
    assert "money_json(payment.amount)" in cust_pay2

    sup_pay = inspect.getsource(api_mod.supplier_payment)
    assert "money_json(payment.amount)" in sup_pay

    adjust = inspect.getsource(api_mod.adjust)
    assert "money_json(product.stock_qty)" in adjust

    post_inv = inspect.getsource(api_mod.post_sales_invoice)
    assert "money_json(invoice.total_amount" in post_inv

    approve = inspect.getsource(api_mod.approve_expense)
    assert "money_json(expense.amount" in approve

    zrep = inspect.getsource(pos_mod.shift_report)
    assert "money_json(session.cash_sales" in zrep
    assert "money_json(session.total_sales" in zrep

    baskets = inspect.getsource(ai_sales_mod._invoice_baskets)
    assert "money_json(inv.total_amount" in baskets
    pos_ev = inspect.getsource(ai_sales_mod._pos_events)
    assert "money_json(tx.total" in pos_ev

    wh = inspect.getsource(inventory_mod.list_product_warehouse_stock)
    assert "money_json(product.reorder_level" in wh

    snap_items = inspect.getsource(purchasing_mod._po_items_snapshot)
    assert "money_json(i.unit_price)" in snap_items
    snap_hdr = inspect.getsource(purchasing_mod._po_header_snapshot)
    assert "money_json(po.subtotal)" in snap_hdr

    ar_wh = inspect.getsource(sales_mod.record_customer_payment)
    assert "money_json(payment.amount" in ar_wh
