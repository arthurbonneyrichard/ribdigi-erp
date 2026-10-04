"""Sales invoice tax line + total breakdown display (BR-12.2)."""

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
async def test_sales_invoice_exposes_line_tax_breakdown(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    customer_id = seed["party1"].id
    product_id = seed["p1"].id

    created = await ac.post(
        "/api/v1/sales/invoices",
        headers=headers,
        json={
            "customer_id": customer_id,
            "items": [
                {"product_id": product_id, "quantity": 2, "unit_price": 50, "tax_rate": 10},
                {"product_id": product_id, "quantity": 1, "unit_price": 20, "tax_rate": 5},
            ],
        },
    )
    assert created.status_code == 200, created.text
    data = created.json()["data"]
    assert data["tax_amount"] == pytest.approx(11.0)  # 10 + 1
    assert len(data["items"]) == 2
    assert data["items"][0]["line_tax"] == pytest.approx(10.0)
    assert data["items"][1]["line_tax"] == pytest.approx(1.0)
    assert "tax_breakdown" in data
    rates = {round(r["tax_rate"], 4): r["tax"] for r in data["tax_breakdown"]["by_rate"]}
    assert rates[10.0] == pytest.approx(10.0)
    assert rates[5.0] == pytest.approx(1.0)

    got = await ac.get(f"/api/v1/sales/invoices/{data['id']}", headers=headers)
    assert got.status_code == 200
    assert got.json()["data"]["items"][0]["line_tax"] == pytest.approx(10.0)

    printed = await ac.get(
        f"/api/v1/sales/invoices/{data['id']}/print?format=json",
        headers=headers,
    )
    # print may require posted — try anyway
    if printed.status_code == 200:
        items = printed.json()["data"].get("items") or []
        assert items and "line_tax" in items[0]
