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

    qr = await ac.get(
        f"/api/v1/products/{product.id}/variants/{vid}/qr.png",
        headers=headers,
    )
    assert qr.status_code == 200, qr.text
    assert qr.content[:8] == b"\x89PNG\r\n\x1a\n"


@pytest.mark.asyncio
async def test_variant_barcode_generate_does_not_overwrite_without_force(client):
    ac, seed = client
    headers = await _admin(ac, seed)
    product = seed["p1"]
    created = await ac.post(
        f"/api/v1/products/{product.id}/variants",
        headers=headers,
        json={"name": "KeepCode", "sku": "P1-KEEP"},
    )
    assert created.status_code == 200, created.text
    vid = created.json()["data"]["id"]
    first = await ac.post(
        f"/api/v1/products/{product.id}/variants/{vid}/barcode/generate",
        headers=headers,
    )
    assert first.status_code == 200, first.text
    code = first.json()["data"]["barcode"]
    second = await ac.post(
        f"/api/v1/products/{product.id}/variants/{vid}/barcode/generate",
        headers=headers,
    )
    assert second.status_code == 200, second.text
    assert second.json()["data"]["barcode"] == code
    assert "already" in second.json()["message"].lower()
