"""Variant barcode generate/label + cross uniqueness (BR-5.1)."""

from __future__ import annotations

import pyotp
import pytest

from app import models as m
from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_variant_barcode_generate_and_clash(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    product = seed["p1"]

    created = await ac.post(
        f"/api/v1/products/{product.id}/variants",
        headers=headers,
        json={"name": "Small", "sku": "P1-SM", "size": "S"},
    )
    assert created.status_code == 200, created.text
    variant = created.json()["data"]
    vid = variant["id"]

    gen = await ac.post(
        f"/api/v1/products/{product.id}/variants/{vid}/barcode/generate"
        f"?force=true&symbology=ean13",
        headers=headers,
    )
    assert gen.status_code == 200, gen.text
    body = gen.json()["data"]
    assert body["symbology"] == "ean13"
    code = body["barcode"]
    assert code and len(code) == 13 and code.isdigit()

    png = await ac.get(
        f"/api/v1/products/{product.id}/variants/{vid}/barcode.png?symbology=ean13",
        headers=headers,
    )
    assert png.status_code == 200
    assert png.content[:8] == b"\x89PNG\r\n\x1a\n"

    # Clash: cannot assign same barcode to the parent product
    clash = await ac.patch(
        f"/api/v1/products/{product.id}",
        headers=headers,
        json={"barcode": code},
    )
    assert clash.status_code == 409, clash.text

    # Second variant cannot reuse the barcode
    other = await ac.post(
        f"/api/v1/products/{product.id}/variants",
        headers=headers,
        json={"name": "Large", "sku": "P1-LG", "barcode": code},
    )
    assert other.status_code == 409, other.text

    label = await ac.get(
        f"/api/v1/products/{product.id}/variants/{vid}/barcode/label?symbology=ean13",
        headers=headers,
    )
    assert label.status_code == 200
    assert "EAN13" in label.text or "ean13" in label.text.lower()
