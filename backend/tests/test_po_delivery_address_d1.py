"""PO delivery address (BR-6.3)."""

from __future__ import annotations

import pyotp
import pytest

from app.emailer import render_purchase_order_bodies
from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_po_delivery_address_create_amend_and_email_body(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    product = seed["p1"]

    suppliers = await ac.get("/api/v1/suppliers", headers=headers)
    assert suppliers.status_code == 200
    data = suppliers.json()["data"]
    if data:
        supplier_id = data[0]["id"]
    else:
        created = await ac.post(
            "/api/v1/suppliers",
            headers=headers,
            json={"name": "Delivery Supplier", "email": "sup-delivery@example.com"},
        )
        assert created.status_code == 200, created.text
        supplier_id = created.json()["data"]["id"]

    po = await ac.post(
        "/api/v1/purchasing/orders",
        headers=headers,
        json={
            "supplier_id": supplier_id,
            "delivery_address": "  Gate B, Tema Wharf  ",
            "items": [
                {"product_id": product.id, "quantity": 3, "unit_price": 10, "tax_rate": 0}
            ],
        },
    )
    assert po.status_code == 200, po.text
    po_data = po.json()["data"]
    assert po_data["delivery_address"] == "Gate B, Tema Wharf"
    po_id = po_data["id"]

    got = await ac.get(f"/api/v1/purchasing/orders/{po_id}", headers=headers)
    assert got.status_code == 200
    assert got.json()["data"]["delivery_address"] == "Gate B, Tema Wharf"

    amended = await ac.post(
        f"/api/v1/purchasing/orders/{po_id}/amend",
        headers=headers,
        json={"delivery_address": "Warehouse 2, Spintex Road"},
    )
    assert amended.status_code == 200, amended.text
    assert amended.json()["data"]["delivery_address"] == "Warehouse 2, Spintex Road"

    text, html = render_purchase_order_bodies(
        company_name="Alpha",
        currency="GHS",
        supplier_name="Delivery Supplier",
        purchase_order={
            "po_number": "PO-1",
            "due_date": None,
            "delivery_address": "Warehouse 2, Spintex Road",
            "subtotal": 30,
            "tax_amount": 0,
            "total_amount": 30,
            "items": [],
        },
    )
    assert "Delivery address: Warehouse 2, Spintex Road" in text
    assert "Delivery address: Warehouse 2, Spintex Road" in html
