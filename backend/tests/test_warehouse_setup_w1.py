"""Warehouse setup fields (BR-2.4)."""

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
async def test_warehouse_create_get_patch_and_type_validation(client):
    ac, seed = client
    headers = await _admin(ac, seed)
    manager_id = seed["super"].id

    created = await ac.post(
        "/api/v1/warehouses",
        headers=headers,
        json={
            "name": "Cold Room A",
            "code": "WH-COLD-A",
            "warehouse_type": "cold_storage",
            "manager_id": manager_id,
            "address": "Zone 3, Industrial Area",
            "capacity": 1200.5,
        },
    )
    assert created.status_code == 200, created.text
    data = created.json()["data"]
    assert data["code"] == "WH-COLD-A"
    assert data["warehouse_type"] == "cold_storage"
    assert data["manager_id"] == manager_id
    assert data["address"] == "Zone 3, Industrial Area"
    assert abs(float(data["capacity"]) - 1200.5) < 0.01
    wid = data["id"]

    got = await ac.get(f"/api/v1/warehouses/{wid}", headers=headers)
    assert got.status_code == 200
    assert got.json()["data"]["warehouse_type"] == "cold_storage"

    listed = await ac.get("/api/v1/warehouses", headers=headers)
    assert listed.status_code == 200
    assert any(w["id"] == wid for w in listed.json()["data"])

    patched = await ac.patch(
        f"/api/v1/warehouses/{wid}",
        headers=headers,
        json={"warehouse_type": "bulk", "capacity": 2000, "clear_manager": True},
    )
    assert patched.status_code == 200, patched.text
    pdata = patched.json()["data"]
    assert pdata["warehouse_type"] == "bulk"
    assert abs(float(pdata["capacity"]) - 2000) < 0.01
    assert pdata["manager_id"] is None

    bad = await ac.post(
        "/api/v1/warehouses",
        headers=headers,
        json={"name": "Bad", "code": "WH-BAD", "warehouse_type": "vault"},
    )
    assert bad.status_code == 422

    dup = await ac.post(
        "/api/v1/warehouses",
        headers=headers,
        json={"name": "Dup", "code": "WH-COLD-A"},
    )
    assert dup.status_code == 409
