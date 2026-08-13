"""Auto-generated product/variant SKUs (BR-5.1)."""

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
async def test_product_and_variant_sku_auto_and_manual(client):
    ac, seed = client
    headers = await _admin(ac, seed)

    auto = await ac.post(
        "/api/v1/products",
        headers=headers,
        json={"name": "Auto SKU Product", "selling_price": 3},
    )
    assert auto.status_code == 200, auto.text
    auto_data = auto.json()["data"]
    assert auto_data["sku"].startswith("SKU-")
    assert len(auto_data["sku"]) >= 10
    pid = auto_data["id"]

    manual = await ac.post(
        "/api/v1/products",
        headers=headers,
        json={"name": "Manual SKU Product", "sku": "manual-sku-1", "selling_price": 4},
    )
    assert manual.status_code == 200, manual.text
    assert manual.json()["data"]["sku"] == "MANUAL-SKU-1"

    clash = await ac.post(
        "/api/v1/products",
        headers=headers,
        json={"name": "Clash", "sku": "MANUAL-SKU-1"},
    )
    assert clash.status_code == 409

    v_auto = await ac.post(
        f"/api/v1/products/{pid}/variants",
        headers=headers,
        json={"name": "Large"},
    )
    assert v_auto.status_code == 200, v_auto.text
    assert v_auto.json()["data"]["sku"].startswith("SKU-")
    assert v_auto.json()["data"]["sku"] != auto_data["sku"]

    v_manual = await ac.post(
        f"/api/v1/products/{pid}/variants",
        headers=headers,
        json={"name": "Small", "sku": "VAR-SMALL-1"},
    )
    assert v_manual.status_code == 200, v_manual.text
    assert v_manual.json()["data"]["sku"] == "VAR-SMALL-1"

    # Variant cannot reuse product SKU
    v_clash = await ac.post(
        f"/api/v1/products/{pid}/variants",
        headers=headers,
        json={"name": "Dup", "sku": auto_data["sku"]},
    )
    assert v_clash.status_code == 409
