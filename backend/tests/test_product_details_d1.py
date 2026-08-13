"""Product description, weight, and dimensions (BR-5.1)."""

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
async def test_product_description_weight_dimensions_create_and_patch(client):
    ac, seed = client
    headers = await _admin(ac, seed)

    created = await ac.post(
        "/api/v1/products",
        headers=headers,
        json={
            "name": "Detail Bottle",
            "sku": "DET-BOT-1",
            "description": "  Still water PET  ",
            "selling_price": 5,
            "cost_price": 2,
            "weight": 0.52,
            "length": 6.5,
            "width": 6.5,
            "height": 22,
        },
    )
    assert created.status_code == 200, created.text
    data = created.json()["data"]
    assert data["description"] == "Still water PET"
    assert abs(float(data["weight"]) - 0.52) < 1e-6
    assert abs(float(data["length"]) - 6.5) < 1e-6
    assert abs(float(data["width"]) - 6.5) < 1e-6
    assert abs(float(data["height"]) - 22) < 1e-6
    pid = data["id"]

    got = await ac.get(f"/api/v1/products/{pid}", headers=headers)
    assert got.status_code == 200
    assert got.json()["data"]["description"] == "Still water PET"

    patched = await ac.patch(
        f"/api/v1/products/{pid}",
        headers=headers,
        json={"description": "", "weight": 0.55, "height": None},
    )
    assert patched.status_code == 200, patched.text
    pdata = patched.json()["data"]
    assert pdata["description"] is None
    assert abs(float(pdata["weight"]) - 0.55) < 1e-6
    assert pdata["height"] is None

    bad = await ac.post(
        "/api/v1/products",
        headers=headers,
        json={"name": "Bad", "sku": "DET-BAD", "weight": -1},
    )
    assert bad.status_code == 422
