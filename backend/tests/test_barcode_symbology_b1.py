"""Product barcode symbology generate/render (BR-5.1)."""

from __future__ import annotations

import pyotp
import pytest

from app.barcodes import detect_symbology
from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_generate_ean13_and_png(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    product = seed["p1"]

    bad = await ac.post(
        f"/api/v1/products/{product.id}/barcode/generate?force=true&symbology=qr",
        headers=headers,
    )
    assert bad.status_code == 400, bad.text

    gen = await ac.post(
        f"/api/v1/products/{product.id}/barcode/generate?force=true&symbology=ean13",
        headers=headers,
    )
    assert gen.status_code == 200, gen.text
    body = gen.json()["data"]
    assert body["symbology"] == "ean13"
    code = body["barcode"]
    assert code and len(code) == 13 and code.isdigit()
    assert detect_symbology(code) == "ean13"

    png = await ac.get(
        f"/api/v1/products/{product.id}/barcode.png?symbology=ean13",
        headers=headers,
    )
    assert png.status_code == 200, png.text
    assert png.headers.get("content-type", "").startswith("image/png")
    assert png.content[:8] == b"\x89PNG\r\n\x1a\n"

    upc = await ac.post(
        f"/api/v1/products/{product.id}/barcode/generate?force=true&symbology=upca",
        headers=headers,
    )
    assert upc.status_code == 200, upc.text
    ucode = upc.json()["data"]["barcode"]
    assert len(ucode) == 12 and ucode.isdigit()

    label = await ac.get(
        f"/api/v1/products/{product.id}/barcode/label?symbology=upca&copies=1",
        headers=headers,
    )
    assert label.status_code == 200, label.text
    assert "UPC-A" in label.text or "UPCA" in label.text or "upca" in label.text.lower()
