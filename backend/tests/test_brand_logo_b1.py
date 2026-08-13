"""Brand logo upload/get/delete (BR-5.1)."""

from __future__ import annotations

import io

import pyotp
import pytest
from PIL import Image

from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


def _png_bytes() -> bytes:
    img = Image.new("RGB", (24, 24), color=(40, 120, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.mark.asyncio
async def test_brand_logo_upload_get_replace_delete_and_isolation(client):
    ac, seed = client
    headers = await _admin(ac, seed)

    created = await ac.post(
        "/api/v1/catalog/brands",
        headers=headers,
        json={
            "code": "LOGO-BR",
            "name": "Logo Brand",
            "description": "Premium line",
        },
    )
    assert created.status_code == 200, created.text
    brand = created.json()["data"]
    assert brand["description"] == "Premium line"
    assert brand["has_logo"] is False
    bid = brand["id"]

    upload = await ac.post(
        f"/api/v1/catalog/brands/{bid}/logo",
        headers=headers,
        files={"file": ("brand.png", _png_bytes(), "image/png")},
    )
    assert upload.status_code == 200, upload.text
    udata = upload.json()["data"]
    assert udata["has_logo"] is True
    assert udata["logo_url"]
    first_key = udata["logo_url"]

    got = await ac.get(f"/api/v1/catalog/brands/{bid}/logo", headers=headers)
    assert got.status_code == 200
    assert got.headers.get("content-type", "").startswith("image/")
    assert got.content[:8] == b"\x89PNG\r\n\x1a\n"

    replace = await ac.post(
        f"/api/v1/catalog/brands/{bid}/logo",
        headers=headers,
        files={"file": ("brand2.png", _png_bytes(), "image/png")},
    )
    assert replace.status_code == 200
    assert replace.json()["data"]["logo_url"] != first_key

    deleted = await ac.delete(f"/api/v1/catalog/brands/{bid}/logo", headers=headers)
    assert deleted.status_code == 200
    assert deleted.json()["data"]["has_logo"] is False
    missing = await ac.get(f"/api/v1/catalog/brands/{bid}/logo", headers=headers)
    assert missing.status_code == 404

    other = await ac.get(
        "/api/v1/catalog/brands/00000000-0000-0000-0000-000000000000/logo",
        headers=headers,
    )
    assert other.status_code == 404
