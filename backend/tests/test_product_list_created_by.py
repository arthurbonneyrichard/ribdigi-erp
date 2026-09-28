"""Product list includes unit name and created_by after create."""

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
async def test_product_create_returns_created_by(client):
    ac, seed = client
    headers = await _admin(ac, seed)
    created = await ac.post(
        "/api/v1/products",
        headers=headers,
        json={"name": "Listed widget", "selling_price": 3, "cost_price": 1},
    )
    assert created.status_code == 200, created.text
    row = created.json()["data"]
    assert row["created_by"]
    assert row.get("created_by_email") or row.get("created_by_name")
    listed = await ac.get("/api/v1/products", headers=headers)
    assert listed.status_code == 200, listed.text
    match = next(p for p in listed.json()["data"] if p["id"] == row["id"])
    assert match["created_by"] == row["created_by"]
