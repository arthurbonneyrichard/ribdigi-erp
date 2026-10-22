"""Percent and fixed discounts on sales invoices and POS."""

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
async def test_sales_invoice_percent_line_and_header_discount(client):
    ac, seed = client
    headers = await _admin(ac, seed)
    created = await ac.post(
        "/api/v1/sales/invoices",
        headers=headers,
        json={
            "customer_id": seed["party1"].id,
            "discount_type": "percent",
            "discount_percent": 10,
            "items": [
                {
                    "product_id": seed["p1"].id,
                    "quantity": 1,
                    "unit_price": 100,
                    "tax_rate": 0,
                    "discount_type": "percent",
                    "discount_percent": 10,
                }
            ],
        },
    )
    assert created.status_code == 200, created.text
    data = created.json()["data"]
    assert data["discount_type"] == "percent"
    assert float(data["discount_percent"]) == 10
    assert float(data["items"][0]["discount"]) == 10
    assert float(data["items"][0]["discount_percent"]) == 10
    # 100 - 10% line = 90 net; then 10% header of 90 = 9; total 81
    assert float(data["subtotal"]) == 90
    assert float(data["discount_amount"]) == 9
    assert float(data["total_amount"]) == 81

    over = await ac.post(
        "/api/v1/sales/invoices",
        headers=headers,
        json={
            "customer_id": seed["party1"].id,
            "items": [
                {
                    "product_id": seed["p1"].id,
                    "quantity": 1,
                    "unit_price": 10,
                    "tax_rate": 0,
                    "discount": 99,
                    "discount_type": "fixed",
                }
            ],
        },
    )
    assert over.status_code == 400, over.text


@pytest.mark.asyncio
async def test_inventory_low_stock_endpoint_shape(client):
    ac, seed = client
    headers = await _admin(ac, seed)
    r = await ac.get("/api/v1/inventory/low-stock", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert "products" in data
    assert "warehouse_low_stock" in data


@pytest.mark.asyncio
async def test_logo_rejects_empty_and_bad_type(client):
    ac, seed = client
    headers = await _admin(ac, seed)
    empty = await ac.post(
        "/api/v1/tenants/me/logo",
        headers=headers,
        files={"file": ("x.png", b"", "image/png")},
    )
    assert empty.status_code == 400, empty.text

    bad = await ac.post(
        "/api/v1/tenants/me/logo",
        headers=headers,
        files={"file": ("x.txt", b"not-an-image", "text/plain")},
    )
    assert bad.status_code == 400, bad.text
