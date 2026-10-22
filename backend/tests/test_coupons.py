"""Coupon codes: validate, apply on invoice, reject invalid, record redemption."""

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
async def test_coupon_invoice_and_reject_invalid(client):
    ac, seed = client
    headers = await _admin(ac, seed)
    created = await ac.post(
        "/api/v1/sales/coupons",
        headers=headers,
        json={
            "code": "SAVE10",
            "name": "Ten percent off",
            "discount_type": "percent",
            "amount": 10,
            "min_spend": 50,
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()["data"]
    assert body["code"] == "SAVE10"

    ok = await ac.post(
        "/api/v1/sales/coupons/validate",
        headers=headers,
        json={
            "code": "SAVE10",
            "header_base": 100,
            "product_ids": [seed["p1"].id],
        },
    )
    assert ok.status_code == 200, ok.text
    assert float(ok.json()["data"]["discount_amount"]) == 10

    low = await ac.post(
        "/api/v1/sales/coupons/validate",
        headers=headers,
        json={"code": "SAVE10", "header_base": 10, "product_ids": [seed["p1"].id]},
    )
    assert low.status_code == 400, low.text

    bogus = await ac.post(
        "/api/v1/sales/coupons/validate",
        headers=headers,
        json={"code": "NOPE", "header_base": 100, "product_ids": [seed["p1"].id]},
    )
    assert bogus.status_code == 400, bogus.text

    inv = await ac.post(
        "/api/v1/sales/invoices",
        headers=headers,
        json={
            "customer_id": seed["party1"].id,
            "coupon_code": "SAVE10",
            "items": [
                {
                    "product_id": seed["p1"].id,
                    "quantity": 1,
                    "unit_price": 100,
                    "tax_rate": 0,
                }
            ],
        },
    )
    assert inv.status_code == 200, inv.text
    data = inv.json()["data"]
    assert float(data["discount_amount"]) == 10
    assert data.get("coupon_id") == body["id"]
    assert float(data["total_amount"]) == 90
