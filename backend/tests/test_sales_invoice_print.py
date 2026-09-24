"""Sales invoice print templates A4 + thermal (BR-7.4)."""

from __future__ import annotations

import pyotp
import pytest

from app.invoice_print import (
    render_invoice_thermal_text,
    to_invoice_a4_pdf,
    to_invoice_thermal_pdf,
)
from tests.conftest import auth_headers


def test_invoice_thermal_and_a4_pdf_bytes():
    payload = {
        "company_name": "Sunrise Mart",
        "invoice_number": "I260812-001",
        "status": "posted",
        "customer_name": "Walk-in",
        "currency": "GHS",
        "subtotal": 10,
        "tax": 1.5,
        "discount_amount": 0,
        "total": 11.5,
        "paid_amount": 0,
        "balance_due": 11.5,
        "items": [
            {
                "name": "Water 500ml",
                "quantity": 2,
                "unit_price": 5,
                "tax_rate": 15,
                "line_total": 11.5,
            }
        ],
    }
    text = render_invoice_thermal_text(payload, paper="80mm")
    assert "SALES INVOICE" in text
    assert "I260812-001" in text
    assert "11.50" in text
    thermal = to_invoice_thermal_pdf(payload, paper="58mm")
    assert thermal.startswith(b"%PDF")
    a4 = to_invoice_a4_pdf(payload)
    assert a4.startswith(b"%PDF")
    assert b"SALES INVOICE" in a4 or b"Invoice" in a4


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_print_route_a4_thermal_and_guards(client, db_session, seeded):
    ac, seed = client
    admin = await _super(ac, seed)

    created = await ac.post(
        "/api/v1/sales/invoices",
        headers=admin,
        json={
            "customer_id": seed["party1"].id,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 20}],
        },
    )
    assert created.status_code == 200, created.text
    iid = created.json()["data"]["id"]
    assert created.json()["data"]["can_print"] is False

    draft_print = await ac.get(f"/api/v1/sales/invoices/{iid}/print?template=a4&format=pdf", headers=admin)
    assert draft_print.status_code == 409

    posted = await ac.post(f"/api/v1/sales/invoices/{iid}/post", headers=admin)
    assert posted.status_code == 200, posted.text
    assert posted.json()["data"]["can_print"] is True

    a4 = await ac.get(f"/api/v1/sales/invoices/{iid}/print?template=a4&format=pdf", headers=admin)
    assert a4.status_code == 200, a4.text
    assert a4.headers["content-type"].startswith("application/pdf")
    assert a4.content.startswith(b"%PDF")

    thermal = await ac.get(
        f"/api/v1/sales/invoices/{iid}/print?template=thermal&format=pdf&paper=80mm",
        headers=admin,
    )
    assert thermal.status_code == 200
    assert thermal.content.startswith(b"%PDF")

    text = await ac.get(
        f"/api/v1/sales/invoices/{iid}/print?template=thermal&format=text&paper=58mm",
        headers=admin,
    )
    assert text.status_code == 200
    assert "SALES INVOICE" in text.text

    js = await ac.get(
        f"/api/v1/sales/invoices/{iid}/print?template=thermal&format=json",
        headers=admin,
    )
    assert js.status_code == 200
    assert js.json()["data"]["invoice_number"]
    assert "SALES INVOICE" in js.json()["data"]["text"]

    # Foreign tenant cannot print
    beta = await auth_headers(ac, email="cashier@beta.example.com", tenant_slug="beta")
    denied = await ac.get(f"/api/v1/sales/invoices/{iid}/print?template=a4&format=pdf", headers=beta)
    assert denied.status_code in {403, 404}
