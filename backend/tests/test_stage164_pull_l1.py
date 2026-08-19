"""Stage 164 L1 — POST /sync/pull."""

from __future__ import annotations

import pyotp
import pytest

from tests.conftest import auth_headers


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_sync_pull_catalog_l1(client):
    ac, seed = client
    headers = await _super(ac, seed)
    device = await ac.post(
        "/api/v1/offline/devices",
        headers=headers,
        json={"name": "Pull device", "platform": "web"},
    )
    device_id = device.json()["data"]["id"]

    pulled = await ac.post(
        "/api/v1/sync/pull",
        headers=headers,
        json={"device_id": device_id, "include_catalog": True},
    )
    assert pulled.status_code == 200, pulled.text
    data = pulled.json()["data"]
    assert data["count"] >= 1
    assert any(op["op_type"] == "catalog_products" for op in data["ops"])
    catalog = next(op for op in data["ops"] if op["op_type"] == "catalog_products")
    assert "products" in (catalog.get("payload") or {})
    skus = [p.get("sku") for p in catalog["payload"]["products"]]
    assert seed["p1"].sku in skus
