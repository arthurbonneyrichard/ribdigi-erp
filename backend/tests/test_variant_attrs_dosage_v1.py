"""Product variant size/color/flavor/dosage (BR-5.1)."""

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
async def test_variant_attrs_create_patch_and_clear(client):
    ac, seed = client
    headers = await _admin(ac, seed)
    product_id = seed["p1"].id

    created = await ac.post(
        f"/api/v1/products/{product_id}/variants",
        headers=headers,
        json={
            "name": "Syrup 5ml",
            "sku": "VAR-DOSE-1",
            "size": "100ml",
            "color": "amber",
            "flavor": "orange",
            "dosage": "5mg/5ml",
        },
    )
    assert created.status_code == 200, created.text
    data = created.json()["data"]
    assert data["size"] == "100ml"
    assert data["color"] == "amber"
    assert data["flavor"] == "orange"
    assert data["dosage"] == "5mg/5ml"
    vid = data["id"]

    listed = await ac.get(f"/api/v1/products/{product_id}/variants", headers=headers)
    assert listed.status_code == 200
    row = next(v for v in listed.json()["data"] if v["id"] == vid)
    assert row["dosage"] == "5mg/5ml"

    patched = await ac.patch(
        f"/api/v1/products/{product_id}/variants/{vid}",
        headers=headers,
        json={"dosage": "10mg/5ml", "color": "red"},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["data"]["dosage"] == "10mg/5ml"
    assert patched.json()["data"]["color"] == "red"

    cleared = await ac.patch(
        f"/api/v1/products/{product_id}/variants/{vid}",
        headers=headers,
        json={"dosage": None, "flavor": None},
    )
    assert cleared.status_code == 200, cleared.text
    cdata = cleared.json()["data"]
    assert cdata["dosage"] is None
    assert cdata["flavor"] is None
    assert cdata["size"] == "100ml"
