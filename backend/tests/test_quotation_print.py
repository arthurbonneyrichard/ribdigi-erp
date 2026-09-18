"""BR-7.2 branded quotation print text/html/pdf."""

from __future__ import annotations

import pytest

from app.emailer import clear_dev_outbox, get_dev_outbox
from app.sales_docs import render_quotation_html, render_quotation_pdf, render_quotation_text
from tests.conftest import auth_headers


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


def test_render_quotation_text_html_pdf_branded():
    data = {
        "quotation_number": "Q-100",
        "status": "draft",
        "valid_until": "2026-08-20",
        "subtotal": 20,
        "tax_amount": 0,
        "discount_amount": 0,
        "total_amount": 20,
        "items": [{"product_id": "p1", "quantity": 2, "unit_price": 10, "line_total": 20}],
    }
    text = render_quotation_text(
        data,
        company_name="Alpha Co",
        customer_name="Buyer",
        template="a4",
        company_address="Accra",
        item_labels={"p1": "Widget"},
    )
    assert "QUOTATION Q-100" in text
    assert "Alpha Co" in text and "Widget" in text and "Valid until" in text

    html = render_quotation_html(
        data,
        company_name="Alpha Co",
        customer_name="Buyer",
        template="a4",
        item_labels={"p1": "Widget"},
    )
    assert "Quotation Q-100" in html and "Widget" in html and "Quote for" in html

    pdf = render_quotation_pdf(
        data, company_name="Alpha Co", customer_name="Buyer", template="a4"
    )
    assert pdf.startswith(b"%PDF")
    thermal = render_quotation_pdf(
        data, company_name="Alpha Co", customer_name="Buyer", template="thermal_58"
    )
    assert thermal.startswith(b"%PDF")


@pytest.mark.asyncio
async def test_quotation_print_formats_and_foreign_404(client):
    ac, seed = client
    headers = await _mgr(ac)

    cust = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "Quote Print Buyer", "credit_limit": 1000},
    )
    assert cust.status_code == 200, cust.text
    customer_id = cust.json()["data"]["id"]

    created = await ac.post(
        "/api/v1/sales/quotations",
        headers=headers,
        json={
            "customer_id": customer_id,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 12}],
        },
    )
    assert created.status_code == 200, created.text
    quote = created.json()["data"]
    quote_id = quote["id"]
    number = quote["quotation_number"]

    text_r = await ac.get(f"/api/v1/sales/quotations/{quote_id}/print", headers=headers)
    assert text_r.status_code == 200, text_r.text
    body = text_r.json()["data"]
    assert body["format"] == "text"
    assert number in body["text"]
    assert "QUOTATION" in body["text"]
    assert "Alpha Co" in body["text"]

    html_r = await ac.get(
        f"/api/v1/sales/quotations/{quote_id}/print",
        headers=headers,
        params={"format": "html", "template": "a4"},
    )
    assert html_r.status_code == 200
    assert "text/html" in html_r.headers.get("content-type", "")
    assert number in html_r.text
    assert "Quote Print Buyer" in html_r.text

    pdf_r = await ac.get(
        f"/api/v1/sales/quotations/{quote_id}/print",
        headers=headers,
        params={"format": "pdf", "template": "thermal_80"},
    )
    assert pdf_r.status_code == 200
    assert pdf_r.content[:4] == b"%PDF"
    assert "filename=" in pdf_r.headers.get("content-disposition", "")

    bad = await ac.get(
        f"/api/v1/sales/quotations/{quote_id}/print",
        headers=headers,
        params={"format": "docx"},
    )
    assert bad.status_code == 400

    # Cross-tenant: beta user cannot print alpha quotation
    beta = await auth_headers(ac, email="cashier@beta.example.com", tenant_slug="beta")
    foreign = await ac.get(f"/api/v1/sales/quotations/{quote_id}/print", headers=beta)
    assert foreign.status_code == 404


@pytest.mark.asyncio
async def test_quotation_send_attaches_print_pdf_and_foreign_404(client, monkeypatch):
    ac, seed = client
    headers = await _mgr(ac)
    clear_dev_outbox()
    monkeypatch.setattr("app.emailer.settings.EMAIL_ENABLED", True)
    monkeypatch.setattr("app.emailer.settings.SMTP_HOST", "")
    monkeypatch.setattr("app.emailer.settings.SMTP_FROM_EMAIL", "noreply@localhost")

    cust = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={
            "name": "Quote Mail Buyer",
            "email": "quote-buyer@example.com",
            "credit_limit": 1000,
        },
    )
    assert cust.status_code == 200, cust.text
    customer_id = cust.json()["data"]["id"]

    created = await ac.post(
        "/api/v1/sales/quotations",
        headers=headers,
        json={
            "customer_id": customer_id,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 15}],
        },
    )
    assert created.status_code == 200, created.text
    quote_id = created.json()["data"]["id"]
    number = created.json()["data"]["quotation_number"]

    sent = await ac.post(
        f"/api/v1/sales/quotations/{quote_id}/send",
        headers=headers,
        json={"template": "a4"},
    )
    assert sent.status_code == 200, sent.text
    data = sent.json()["data"]
    assert data["status"] == "sent"
    assert data["emailed_to"] == "quote-buyer@example.com"
    assert data["delivery"]["mode"] == "console"
    assert data["delivery"]["template"] == "a4"
    attach = data["delivery"]["attachment"]
    assert attach["filename"].startswith("quotation_")
    assert attach["filename"].endswith(".pdf")
    assert number.replace("/", "-") in attach["filename"]
    assert attach["content_type"] == "application/pdf"
    assert attach["size_bytes"] > 4

    out = get_dev_outbox()
    assert out and number in out[0]["subject"]
    assert out[0]["attachments"][0]["filename"] == attach["filename"]
    assert "branded PDF" in (out[0].get("text_body") or "")

    resend = await ac.post(
        f"/api/v1/sales/quotations/{quote_id}/send",
        headers=headers,
        json={"to": "override@example.com", "template": "thermal_58"},
    )
    assert resend.status_code == 200, resend.text
    assert resend.json()["data"]["emailed_to"] == "override@example.com"
    assert resend.json()["data"]["delivery"]["template"] == "thermal_58"

    bad_tpl = await ac.post(
        f"/api/v1/sales/quotations/{quote_id}/send",
        headers=headers,
        json={"template": "poster"},
    )
    assert bad_tpl.status_code == 400

    foreign = await ac.post(
        f"/api/v1/sales/quotations/{seed['inv2'].id}/send",
        headers=headers,
    )
    assert foreign.status_code == 404
