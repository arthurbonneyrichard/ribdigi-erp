"""Stage 1 E14 — receipt template selection + document header/footer (BR-20.4)."""

from __future__ import annotations

from datetime import datetime

import pytest

from app.receipts import (
    RECEIPT_PRINT_TEMPLATES,
    build_receipt_payload,
    render_thermal_text,
    resolve_receipt_paper,
)
from app.sales import render_invoice_html, render_invoice_text
from tests.conftest import auth_headers


def test_resolve_receipt_paper_from_tenant_default():
    tenant = type("T", (), {"receipt_print_template": "thermal_58"})()
    assert resolve_receipt_paper(tenant, None) == "58mm"
    assert resolve_receipt_paper(tenant, "80mm") == "80mm"
    assert resolve_receipt_paper(None, None) == "80mm"
    assert RECEIPT_PRINT_TEMPLATES == frozenset({"thermal_80", "thermal_58"})


def test_receipt_text_includes_custom_header_footer():
    tx = type(
        "Tx",
        (),
        {
            "id": "sale-1",
            "reference": "POS-1",
            "payload": {
                "items": [{"name": "Widget", "quantity": 1, "unit_price": 10, "line_total": 10}],
                "payment_method": "cash",
            },
            "subtotal": 10,
            "tax": 0,
            "total": 10,
            "created_at": datetime(2026, 8, 9, 12, 0, 0),
        },
    )()
    tenant = type(
        "T",
        (),
        {
            "id": "t1",
            "company_name": "Alpha Trading",
            "legal_name": "Alpha Retail Ltd",
            "logo_url": None,
            "address": "Accra",
            "phone": "0200000000",
            "email": None,
            "currency": "GHS",
            "tax_registration_number": None,
            "receipt_print_template": "thermal_58",
            "document_header": "Welcome shoppers",
            "document_footer": "No returns after 7 days",
        },
    )()
    receipt = build_receipt_payload(tx=tx, tenant=tenant, cashier_name="Ama")
    assert receipt["default_paper"] == "58mm"
    assert receipt["receipt_print_template"] == "thermal_58"
    assert receipt["document_header"] == "Welcome shoppers"
    text = render_thermal_text(receipt, paper="58mm")
    assert "Welcome shoppers" in text
    assert "No returns after 7 days" in text
    assert "Thank you" not in text


def test_invoice_text_and_html_use_header_footer():
    data = {
        "invoice_number": "INV-1",
        "status": "posted",
        "subtotal": 10,
        "tax_amount": 0,
        "discount_amount": 0,
        "total_amount": 10,
        "paid_amount": 0,
        "balance_due": 10,
        "items": [{"product_id": "p1", "quantity": 1, "unit_price": 10, "line_total": 10}],
    }
    text = render_invoice_text(
        data,
        company_name="Alpha Retail Ltd",
        customer_name="Buyer",
        item_labels={"p1": "Widget"},
        document_header="GST registered",
        document_footer="Pay within 14 days",
    )
    assert "GST registered" in text
    assert "Pay within 14 days" in text
    html = render_invoice_html(
        data,
        company_name="Alpha Retail Ltd",
        customer_name="Buyer",
        item_labels={"p1": "Widget"},
        document_header="GST registered",
        document_footer="Pay within 14 days",
    )
    assert "doc-header" in html
    assert "GST registered" in html
    assert "Pay within 14 days" in html
    assert "Thank you for your business" not in html


@pytest.mark.asyncio
async def test_tenant_receipt_template_and_header_footer_api(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    bad = await ac.patch(
        "/api/v1/tenants/me",
        headers=headers,
        json={"receipt_print_template": "a4"},
    )
    assert bad.status_code == 400

    ok = await ac.patch(
        "/api/v1/tenants/me",
        headers=headers,
        json={
            "receipt_print_template": "thermal_58",
            "document_header": "Branch hours 9-5",
            "document_footer": "Keep receipt for warranty",
        },
    )
    assert ok.status_code == 200, ok.text
    data = ok.json()["data"]
    assert data["receipt_print_template"] == "thermal_58"
    assert data["document_header"] == "Branch hours 9-5"
    assert data["document_footer"] == "Keep receipt for warranty"

    cleared = await ac.patch(
        "/api/v1/tenants/me",
        headers=headers,
        json={"document_header": "  ", "document_footer": ""},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["data"]["document_header"] is None
    assert cleared.json()["data"]["document_footer"] is None
