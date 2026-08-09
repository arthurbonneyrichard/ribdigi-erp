"""POS cart discounts, customer selection, and credit payment rules."""

from __future__ import annotations

import pytest

from app import models as m
from tests.conftest import auth_headers


async def _open_shift(ac, headers):
    opened = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=headers,
        json={"opening_cash": 100},
    )
    assert opened.status_code == 200, opened.text
    return opened.json()["data"]["session_id"]


@pytest.mark.asyncio
async def test_pos_cart_discount_and_customer(client, db_session):
    ac, seed = client
    cashier = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    session_id = await _open_shift(ac, cashier)

    product = await db_session.get(m.Product, seed["p1"].id)
    product.selling_price = 100
    product.stock_qty = 50
    customer = seed["party1"]
    await db_session.commit()

    sale = await ac.post(
        "/api/v1/pos/sales",
        headers=cashier,
        json={
            "session_id": session_id,
            "party_id": customer.id,
            "payment_method": "wallet",
            "discount_amount": 5,
            "items": [
                {"product_id": product.id, "quantity": 2, "discount": 10},
            ],
        },
    )
    assert sale.status_code == 200, sale.text
    data = sale.json()["data"]
    assert data["party_id"] == customer.id
    assert data["discount_amount"] == 5
    # line net 190 + tax (may be 0 in seed) - cart discount 5
    assert float(data["total"]) == pytest.approx(float(data["subtotal"]) + float(data["tax"]) - 5, abs=0.02)

    receipt = await ac.get(f"/api/v1/pos/sales/{data['id']}/receipt", headers=cashier)
    assert receipt.status_code == 200, receipt.text
    body = receipt.json()["data"]
    assert body["discount_amount"] == 5
    assert body.get("customer_name") == customer.name
    assert "Discount" in (body.get("text") or "")


@pytest.mark.asyncio
async def test_pos_credit_requires_customer(client, db_session):
    ac, seed = client
    cashier = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    session_id = await _open_shift(ac, cashier)
    product = seed["p1"]

    missing = await ac.post(
        "/api/v1/pos/sales",
        headers=cashier,
        json={
            "session_id": session_id,
            "payment_method": "credit",
            "items": [{"product_id": product.id, "quantity": 1}],
        },
    )
    assert missing.status_code == 400
    assert "customer" in missing.json()["detail"].lower()

    ok = await ac.post(
        "/api/v1/pos/sales",
        headers=cashier,
        json={
            "session_id": session_id,
            "party_id": seed["party1"].id,
            "payment_method": "credit",
            "items": [{"product_id": product.id, "quantity": 1}],
        },
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["payment_method"] == "credit"
