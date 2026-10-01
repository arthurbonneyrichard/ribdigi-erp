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

    roster = await ac.get("/api/v1/products/variants", headers=headers)
    assert roster.status_code == 200, roster.text
    roster_ids = {row["id"] for row in roster.json()["data"]}
    assert variant_id in roster_ids
    assert second.json()["data"]["id"] in roster_ids
    assert all(row.get("is_active") is not False for row in roster.json()["data"] if row["id"] in ids)

    other_prod = await ac.post(
        "/api/v1/products",
        headers=headers,
        json={"name": f"Other parent {suffix}"},
    )
    assert other_prod.status_code == 200, other_prod.text
    other_id = other_prod.json()["data"]["id"]
    other_var = await ac.post(
        f"/api/v1/products/{other_id}/variants",
        headers=headers,
        json={"name": f"Other size {suffix}"},
    )
    assert other_var.status_code == 200, other_var.text
    other_vid = other_var.json()["data"]["id"]
    roster2 = await ac.get("/api/v1/products/variants", headers=headers)
    roster2_ids = {row["id"] for row in roster2.json()["data"]}
    assert variant_id in roster2_ids
    assert other_vid in roster2_ids

    active_only = await ac.get("/api/v1/products/variants?is_active=true", headers=headers)
    assert active_only.status_code == 200, active_only.text
    assert other_vid in {row["id"] for row in active_only.json()["data"]}

    other = await auth_headers(ac, email="cashier@beta.example.com", tenant_slug="beta")
    steal = await ac.get(f"/api/v1/products/{product_id}/variants", headers=other)
    assert steal.status_code in (200, 403, 404)
    if steal.status_code == 200:
        stolen_ids = {row["id"] for row in steal.json()["data"]}
        assert variant_id not in stolen_ids
    steal_roster = await ac.get("/api/v1/products/variants", headers=other)
    assert steal_roster.status_code in (200, 403, 404)
    if steal_roster.status_code == 200:
        stolen_roster = {row["id"] for row in steal_roster.json()["data"]}
        assert variant_id not in stolen_roster
        assert other_vid not in stolen_roster
