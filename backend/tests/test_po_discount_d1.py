"""Purchase order line discount (BR-6.3)."""

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
async def test_po_create_with_line_discount(client):
    ac, seed = client
    headers = await _admin(ac, seed)
    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=headers,
        json={"name": "PO Disc Vendor", "kind": "supplier", "email": "po-disc@example.com"},
    )
    assert supplier.status_code == 200, supplier.text

    # qty 2 * 10 = 20; tax 10% = 2; discount 3 → line_total 19; total 19
    created = await ac.post(
        "/api/v1/purchasing/orders",
        headers=headers,
        json={
            "supplier_id": supplier.json()["data"]["id"],
            "items": [
                {
                    "product_id": seed["p1"].id,
                    "quantity": 2,
                    "unit_price": 10,
                    "tax_rate": 10,
                    "discount": 3,
                }
            ],
        },
    )
    assert created.status_code == 200, created.text
    po = created.json()["data"]
    assert po["subtotal"] == 20
    assert po["tax_amount"] == 2
    assert po["total_amount"] == 19
    assert po["items"][0]["discount"] == 3
    assert po["items"][0]["line_total"] == 19

    got = await ac.get(f"/api/v1/purchasing/orders/{po['id']}", headers=headers)
    assert got.status_code == 200
    assert got.json()["data"]["items"][0]["discount"] == 3
    assert got.json()["data"]["total_amount"] == 19


@pytest.mark.asyncio
async def test_po_discount_cannot_exceed_merchandise(client):
    ac, seed = client
    headers = await _admin(ac, seed)
    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=headers,
        json={"name": "PO Over Disc", "kind": "supplier", "email": "po-over@example.com"},
    )
    assert supplier.status_code == 200
    created = await ac.post(
        "/api/v1/purchasing/orders",
        headers=headers,
        json={
            "supplier_id": supplier.json()["data"]["id"],
            "items": [
                {
                    "product_id": seed["p1"].id,
                    "quantity": 1,
                    "unit_price": 10,
                    "tax_rate": 0,
                    "discount": 11,
                }
            ],
        },
    )
    assert created.status_code == 400, created.text
    assert "discount" in created.text.lower()


@pytest.mark.asyncio
async def test_po_amend_updates_discount(client):
    ac, seed = client
    headers = await _admin(ac, seed)
    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=headers,
        json={"name": "PO Amend Disc", "kind": "supplier", "email": "po-amend-d@example.com"},
    )
    assert supplier.status_code == 200
    created = await ac.post(
        "/api/v1/purchasing/orders",
        headers=headers,
        json={
            "supplier_id": supplier.json()["data"]["id"],
            "items": [
                {
                    "product_id": seed["p1"].id,
                    "quantity": 2,
                    "unit_price": 10,
                    "tax_rate": 0,
                    "discount": 1,
                }
            ],
        },
    )
    assert created.status_code == 200, created.text
    po = created.json()["data"]
    assert po["total_amount"] == 19
    line = po["items"][0]

    amended = await ac.post(
        f"/api/v1/purchasing/orders/{po['id']}/amend",
        headers=headers,
        json={
            "reason": "increase discount",
            "items": [
                {
                    "product_id": line["product_id"],
                    "quantity": 2,
                    "unit_price": 10,
                    "tax_rate": 0,
                    "discount": 5,
                }
            ],
        },
    )
    assert amended.status_code == 200, amended.text
    body = amended.json()["data"]
    assert body["items"][0]["discount"] == 5
    assert body["items"][0]["line_total"] == 15
    assert body["total_amount"] == 15
