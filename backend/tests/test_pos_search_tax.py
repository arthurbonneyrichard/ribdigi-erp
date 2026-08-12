"""POS product search exposes tax fields for cart preview (cashiers lack tax:read)."""

from __future__ import annotations

import pyotp
import pytest

from tests.conftest import auth_headers


async def _admin_headers(ac, seeded):
    code = pyotp.TOTP(seeded["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_pos_search_includes_tax_fields(client):
    ac, seeded = client
    admin = await _admin_headers(ac, seeded)

    rate = await ac.post(
        "/api/v1/tax/rates",
        headers=admin,
        json={
            "name": "VAT 15",
            "code": "VAT15",
            "rate": 15,
            "pricing_mode": "exclusive",
            "is_default": True,
        },
    )
    assert rate.status_code == 200, rate.text
    rate_id = rate.json()["data"]["id"]

    product = await ac.post(
        "/api/v1/products",
        headers=admin,
        json={
            "name": "Taxed Snack",
            "sku": "TAX-SNACK-1",
            "cost_price": 1,
            "selling_price": 10,
            "stock_qty": 50,
            "tax_rate_id": rate_id,
        },
    )
    assert product.status_code == 200, product.text

    cashier = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    search = await ac.get("/api/v1/pos/products/search?q=Taxed Snack", headers=cashier)
    assert search.status_code == 200, search.text
    rows = search.json()["data"]
    assert rows, "expected product hit"
    hit = next(r for r in rows if r.get("sku") == "TAX-SNACK-1")
    assert hit["tax_rate_pct"] == 15.0
    assert hit["tax_pricing_mode"] == "exclusive"
    assert hit["tax_reverse_charge"] is False
    assert hit.get("tax_components") in (None, [])
