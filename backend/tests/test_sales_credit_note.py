"""BR-7.5 sales return credit note numbering and branded print."""

from __future__ import annotations

import pytest

from app.document_numbering import format_document_number, normalize_document_numbering
from app.sales_docs import render_credit_note_html, render_credit_note_pdf, render_credit_note_text
from tests.conftest import auth_headers


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


async def _admin(ac):
    return await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")


def test_credit_note_numbering_defaults():
    cfg = normalize_document_numbering(None)
    assert "sales_credit_note" in cfg and "sales_return" in cfg
    assert format_document_number(cfg["sales_credit_note"], number=1).startswith("CN-")


def test_render_credit_note_branded():
    data = {
        "credit_note_number": "CN-9",
        "return_number": "SR-1",
        "status": "posted",
        "reason": "damaged",
        "subtotal": 10,
        "tax_amount": 0,
        "total_amount": 10,
        "items": [{"product_id": "p1", "quantity": 1, "unit_price": 10, "line_total": 10}],
    }
    text = render_credit_note_text(
        data,
        company_name="Alpha Co",
        customer_name="Buyer",
        invoice_number="INV-1",
        item_labels={"p1": "Widget"},
    )
    assert "CREDIT NOTE CN-9" in text
    assert "INV-1" in text and "Widget" in text
    html = render_credit_note_html(
        data,
        company_name="Alpha Co",
        customer_name="Buyer",
        invoice_number="INV-1",
        item_labels={"p1": "Widget"},
    )
    assert "Credit Note CN-9" in html and "Widget" in html
    pdf = render_credit_note_pdf(data, company_name="Alpha Co", customer_name="Buyer")
    assert pdf.startswith(b"%PDF")


@pytest.mark.asyncio
async def test_sales_return_credit_note_allocate_and_print(client):
    ac, seed = client
    headers = await _mgr(ac)
    admin = await _admin(ac)

    patched = await ac.patch(
        "/api/v1/tenants/me",
        headers=admin,
        json={
            "document_numbering": {
                "sales_return": {
                    "prefix": "SR",
                    "include_year": False,
                    "pad": 4,
                    "next_number": 21,
                },
                "sales_credit_note": {
                    "prefix": "CN",
                    "include_year": False,
                    "pad": 4,
                    "next_number": 5,
                },
            }
        },
    )
    assert patched.status_code == 200, patched.text

    cust = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "Credit Note Buyer", "credit_limit": 2000},
    )
    customer_id = cust.json()["data"]["id"]

    inv = await ac.post(
        "/api/v1/sales/invoices",
        headers=headers,
        json={
            "customer_id": customer_id,
            "items": [{"product_id": seed["p1"].id, "quantity": 2, "unit_price": 8}],
        },
    )
    assert inv.status_code == 200, inv.text
    invoice_id = inv.json()["data"]["id"]
    invoice_number = inv.json()["data"]["invoice_number"]
    posted_inv = await ac.post(f"/api/v1/sales/invoices/{invoice_id}/post", headers=headers)
    assert posted_inv.status_code == 200, posted_inv.text

    created = await ac.post(
        "/api/v1/sales/returns",
        headers=headers,
        json={
            "sales_invoice_id": invoice_id,
            "reason": "damaged",
            "restock": True,
            "items": [{"product_id": seed["p1"].id, "quantity": 1}],
        },
    )
    assert created.status_code == 200, created.text
    ret = created.json()["data"]
    assert ret["return_number"] == "SR-0021"
    assert ret["credit_note_number"] is None
    return_id = ret["id"]

    draft_print = await ac.get(f"/api/v1/sales/returns/{return_id}/print", headers=headers)
    assert draft_print.status_code == 409

    posted = await ac.post(f"/api/v1/sales/returns/{return_id}/post", headers=headers)
    assert posted.status_code == 200, posted.text
    data = posted.json()["data"]
    assert data["status"] == "posted"
    assert data["credit_note_number"] == "CN-0005"

    text_r = await ac.get(f"/api/v1/sales/returns/{return_id}/print", headers=headers)
    assert text_r.status_code == 200, text_r.text
    body = text_r.json()["data"]
    assert body["invoice_number"] == invoice_number
    assert "CREDIT NOTE CN-0005" in body["text"]
    assert "SR-0021" in body["text"]
    assert "Credit Note Buyer" in body["text"]
    assert "Alpha Co" in body["text"]

    html_r = await ac.get(
        f"/api/v1/sales/returns/{return_id}/print",
        headers=headers,
        params={"format": "html"},
    )
    assert html_r.status_code == 200
    assert "Credit Note CN-0005" in html_r.text

    pdf_r = await ac.get(
        f"/api/v1/sales/returns/{return_id}/print",
        headers=headers,
        params={"format": "pdf", "template": "a4"},
    )
    assert pdf_r.status_code == 200
    assert pdf_r.content[:4] == b"%PDF"

    beta = await auth_headers(ac, email="cashier@beta.example.com", tenant_slug="beta")
    foreign = await ac.get(f"/api/v1/sales/returns/{return_id}/print", headers=beta)
    assert foreign.status_code == 404
