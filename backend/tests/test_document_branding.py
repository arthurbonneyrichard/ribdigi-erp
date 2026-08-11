"""Stage 1 B4 — company logo and legal name on invoices/receipts (BR-20.1)."""

from __future__ import annotations

from datetime import datetime

import pytest

from app import storage as storage_svc
from app.print_branding import (
    document_company_name,
    load_logo_data_url,
    platform_print_footer_html,
    platform_print_footer_text_lines,
    PLATFORM_PRINT_FOOTER_LINES,
    tenant_document_brand,
)
from app.receipts import build_receipt_payload, render_thermal_text
from app.sales import render_invoice_html, render_invoice_text
from tests.conftest import auth_headers


# Minimal valid 1x1 PNG
_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
    b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


def test_document_company_name_prefers_legal():
    tenant = type(
        "T",
        (),
        {"company_name": "Alpha Trading", "legal_name": "Alpha Retail Ltd"},
    )()
    assert document_company_name(tenant) == "Alpha Retail Ltd"
    tenant2 = type("T", (), {"company_name": "Alpha Trading", "legal_name": None})()
    assert document_company_name(tenant2) == "Alpha Trading"


def test_invoice_html_embeds_logo_and_legal_name(tmp_path, monkeypatch):
    monkeypatch.setattr(storage_svc.settings, "MEDIA_DIR", str(tmp_path))
    monkeypatch.setattr(storage_svc.settings, "STORAGE_BACKEND", "local")
    key = f"t1/logos/test.png"
    path = tmp_path / "t1" / "logos"
    path.mkdir(parents=True)
    (path / "test.png").write_bytes(_PNG)
    tenant = type(
        "T",
        (),
        {
            "id": "t1",
            "company_name": "Alpha Trading",
            "legal_name": "Alpha Retail Ltd",
            "logo_url": key,
            "address": "Accra",
            "phone": None,
            "email": None,
            "tax_registration_number": None,
        },
    )()
    brand = tenant_document_brand(tenant)
    assert brand["has_logo"] is True
    assert brand["logo_data_url"] and brand["logo_data_url"].startswith("data:image/png;base64,")
    assert brand["company_name"] == "Alpha Retail Ltd"
    assert brand["trading_name"] == "Alpha Trading"

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
    html = render_invoice_html(
        data,
        customer_name="Buyer",
        item_labels={"p1": "Widget"},
        **{k: brand[k] for k in (
            "company_name",
            "company_address",
            "company_phone",
            "company_email",
            "tax_registration_number",
            "logo_data_url",
            "trading_name",
            "legal_name",
            "has_logo",
        )},
    )
    assert "data:image/png;base64," in html
    assert 'class="logo"' in html
    assert "Alpha Retail Ltd" in html
    assert "Trading as Alpha Trading" in html

    text = render_invoice_text(
        data,
        customer_name="Buyer",
        item_labels={"p1": "Widget"},
        company_name=brand["company_name"],
        trading_name=brand["trading_name"],
        has_logo=True,
    )
    assert "Alpha Retail Ltd" in text
    assert "Trading as Alpha Trading" in text
    assert "[Company logo on file]" in text


def test_receipt_payload_includes_logo_and_legal(tmp_path, monkeypatch):
    monkeypatch.setattr(storage_svc.settings, "MEDIA_DIR", str(tmp_path))
    monkeypatch.setattr(storage_svc.settings, "STORAGE_BACKEND", "local")
    path = tmp_path / "t1" / "logos"
    path.mkdir(parents=True)
    (path / "test.png").write_bytes(_PNG)
    tenant = type(
        "T",
        (),
        {
            "id": "t1",
            "company_name": "Demo Mart",
            "legal_name": "Demo Mart Limited",
            "logo_url": "t1/logos/test.png",
            "phone": "+233000000000",
            "address": "Accra",
            "currency": "GHS",
            "email": None,
            "tax_registration_number": None,
        },
    )()
    tx = type(
        "Tx",
        (),
        {
            "id": "sale-1",
            "reference": "POS_SALE-1",
            "subtotal": 20.0,
            "tax": 2.5,
            "total": 22.5,
            "created_at": datetime(2026, 8, 8, 12, 0, 0),
            "payload": {
                "payment_method": "cash",
                "items": [
                    {
                        "name": "Bottled Water",
                        "quantity": 2,
                        "unit_price": 10,
                        "line_total": 20,
                    }
                ],
            },
        },
    )()
    receipt = build_receipt_payload(tx=tx, tenant=tenant, cashier_name="Ama")
    assert receipt["company_name"] == "Demo Mart Limited"
    assert receipt["trading_name"] == "Demo Mart"
    assert receipt["has_logo"] is True
    assert receipt["logo_data_url"].startswith("data:image/png;base64,")
    text = render_thermal_text(receipt, paper="80mm")
    assert "Demo Mart Limited" in text
    assert "[Company logo on file]" in text


def test_invoice_html_without_logo_still_renders():
    html = render_invoice_html(
        {
            "invoice_number": "INV-2",
            "status": "draft",
            "subtotal": 1,
            "tax_amount": 0,
            "discount_amount": 0,
            "total_amount": 1,
            "paid_amount": 0,
            "balance_due": 1,
            "items": [],
        },
        company_name="Solo Co",
        customer_name="Buyer",
    )
    assert "Solo Co" in html
    assert "data:image" not in html
    assert load_logo_data_url(None) is None


@pytest.mark.asyncio
async def test_invoice_print_html_includes_uploaded_logo(client, db_session, tmp_path, monkeypatch):
    monkeypatch.setattr(storage_svc.settings, "MEDIA_DIR", str(tmp_path))
    monkeypatch.setattr(storage_svc.settings, "STORAGE_BACKEND", "local")
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    t = seed["t1"]
    t.legal_name = "Alpha Retail Limited"
    logo_dir = tmp_path / t.id / "logos"
    logo_dir.mkdir(parents=True)
    logo_path = logo_dir / "brand.png"
    logo_path.write_bytes(_PNG)
    t.logo_url = f"{t.id}/logos/brand.png"
    await db_session.commit()

    inv = await ac.post(
        "/api/v1/sales/invoices",
        headers=headers,
        json={
            "customer_id": seed["party1"].id,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 8}],
        },
    )
    assert inv.status_code == 200, inv.text
    invoice_id = inv.json()["data"]["id"]
    posted = await ac.post(f"/api/v1/sales/invoices/{invoice_id}/post", headers=headers)
    assert posted.status_code == 200, posted.text

    printed = await ac.get(
        f"/api/v1/sales/invoices/{invoice_id}/print",
        headers=headers,
        params={"format": "html"},
    )
    assert printed.status_code == 200, printed.text
    body = printed.text
    assert "data:image/png;base64," in body
    assert "Alpha Retail Limited" in body
    assert 'class="logo"' in body

    text_print = await ac.get(
        f"/api/v1/sales/invoices/{invoice_id}/print",
        headers=headers,
        params={"format": "text"},
    )
    assert text_print.status_code == 200, text_print.text
    payload = text_print.json()["data"]
    assert payload["has_logo"] is True
    assert payload["logo_data_url"].startswith("data:image/")
    assert payload["company_name"] == "Alpha Retail Limited"
    assert "[Company logo on file]" in payload["text"]

def test_platform_print_footer_branding():
    lines = platform_print_footer_text_lines(width=48, center=False)
    assert lines[0] == ""
    assert "RIBDIGI ERP" in lines
    assert "One System. Total Business Control." in lines
    assert "A Ribdigi House Product" in lines
    assert PLATFORM_PRINT_FOOTER_LINES == (
        "RIBDIGI ERP",
        "One System. Total Business Control.",
        "A Ribdigi House Product",
    )
    html = platform_print_footer_html()
    assert "platform-footer" in html
    assert "RIBDIGI ERP" in html
    assert "One System. Total Business Control." in html
    assert "A Ribdigi House Product" in html


def test_invoice_and_receipt_include_platform_footer():
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
        company_name="Acme",
        customer_name="Buyer",
        item_labels={"p1": "Widget"},
        template="a4",
    )
    assert "RIBDIGI ERP" in text
    assert "One System. Total Business Control." in text
    assert "A Ribdigi House Product" in text
    html = render_invoice_html(
        data,
        company_name="Acme",
        customer_name="Buyer",
        item_labels={"p1": "Widget"},
        template="a4",
    )
    assert "platform-footer" in html
    assert "A Ribdigi House Product" in html

    receipt = {
        "company_name": "Acme",
        "receipt_number": "R1",
        "currency": "GHS",
        "subtotal": 10,
        "tax": 0,
        "discount_amount": 0,
        "total": 10,
        "payment_method": "cash",
        "items": [{"name": "Widget", "quantity": 1, "unit_price": 10, "line_total": 10}],
    }
    rtext = render_thermal_text(receipt, paper="80mm")
    assert "RIBDIGI ERP" in rtext
    assert "One System. Total Business Control." in rtext
    assert "A Ribdigi House Product" in rtext
    assert "Powered by RIBDIGI" not in rtext

