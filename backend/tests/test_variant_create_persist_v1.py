"""Variant create persists, lists, and stays tenant-scoped."""

from __future__ import annotations

from uuid import uuid4

import pyotp
import pytest

from tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_variant_create_persists_and_isolates(client):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    headers = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:8]
    prod = await ac.post(
        "/api/v1/products",
        headers=headers,
        json={"name": f"Variant parent {suffix}"},
    )
    assert prod.status_code == 200, prod.text
    product_id = prod.json()["data"]["id"]

    first = await ac.post(
        f"/api/v1/products/{product_id}/variants",
        headers=headers,
        json={"name": f"Size Large {suffix}"},
    )
    assert first.status_code == 200, first.text
    body = first.json()["data"]
    assert body["id"]
    assert body["name"] == f"Size Large {suffix}"
    assert body["sku"]
    variant_id = body["id"]

    second = await ac.post(
        f"/api/v1/products/{product_id}/variants",
        headers=headers,
        json={"name": f"Size Small {suffix}"},
    )
    assert second.status_code == 200, second.text
    assert second.json()["data"]["id"] != variant_id

    listed = await ac.get(f"/api/v1/products/{product_id}/variants", headers=headers)
    assert listed.status_code == 200, listed.text
    ids = {row["id"] for row in listed.json()["data"]}
    assert variant_id in ids
    assert second.json()["data"]["id"] in ids

    other = await auth_headers(ac, email="cashier@beta.example.com", tenant_slug="beta")
    steal = await ac.get(f"/api/v1/products/{product_id}/variants", headers=other)
    assert steal.status_code in (200, 403, 404)
    if steal.status_code == 200:
        stolen_ids = {row["id"] for row in steal.json()["data"]}
        assert variant_id not in stolen_ids
