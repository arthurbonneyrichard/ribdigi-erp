"""Purchase invoice line + header discount (BR-6.5)."""

from __future__ import annotations

import pyotp
import pytest

from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_manual_pi_line_and_header_discount(client):
    ac, seed = client
    headers = await _admin(ac, seed)
    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=headers,
        json={"name": "Discount PI Vendor", "kind": "supplier", "email": "disc-pi@example.com"},
    )
    assert supplier.status_code == 200, supplier.text

    # qty 2 * $10 = $20 net; tax 10% = $2; line discount $3 → line_total 19
    # header discount $4 → total = (20+2) - 4 = 18
    created = await ac.post(
        "/api/v1/purchasing/invoices",
        headers=headers,
        json={
            "supplier_id": supplier.json()["data"]["id"],
            "discount_amount": 4,
            "items": [
                {
                    "product_id": seed["p1"].id,
                    "quantity": 2,
                    "unit_price": 10,
                    "tax_rate": 10,
                    "discount": 3,
                }
            ],
            "notes": "pi discount test",
        },
    )
    assert created.status_code == 200, created.text
    inv = created.json()["data"]
    assert inv["discount_amount"] == 4
    assert inv["subtotal"] == 20
    assert inv["tax_amount"] == 2
    assert inv["total_amount"] == 18
    assert len(inv["items"]) == 1
    line = inv["items"][0]
    assert line["discount"] == 3
    assert line["line_subtotal"] == 20
    assert line["line_tax"] == 2
    assert line["line_total"] == 19

    got = await ac.get(f"/api/v1/purchasing/invoices/{inv['id']}", headers=headers)
    assert got.status_code == 200
    body = got.json()["data"]
    assert body["discount_amount"] == 4
    assert body["items"][0]["discount"] == 3
    assert body["total_amount"] == 18


@pytest.mark.asyncio
async def test_manual_pi_reverse_charge_header_discount(client):
    ac, seed = client
    headers = await _admin(ac, seed)
    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=headers,
        json={"name": "RC Discount Vendor", "kind": "supplier", "email": "rc-disc@example.com"},
    )
    assert supplier.status_code == 200, supplier.text

    # RC: AP total = subtotal - header discount (tax self-assessed, not in AP)
    created = await ac.post(
        "/api/v1/purchasing/invoices",
        headers=headers,
        json={
            "supplier_id": supplier.json()["data"]["id"],
            "is_reverse_charge": True,
            "discount_amount": 5,
            "items": [
                {
                    "product_id": seed["p1"].id,
                    "quantity": 1,
                    "unit_price": 50,
                    "tax_rate": 10,
                    "discount": 0,
                }
            ],
        },
    )
    assert created.status_code == 200, created.text
    inv = created.json()["data"]
    assert inv["is_reverse_charge"] is True
    assert inv["subtotal"] == 50
    assert inv["tax_amount"] == 0
    assert inv["reverse_charge_tax"] == 5
    assert inv["discount_amount"] == 5
    assert inv["total_amount"] == 45
