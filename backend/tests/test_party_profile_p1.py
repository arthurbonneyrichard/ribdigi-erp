"""Customer/supplier profile fields (BR-7.1 / BR-6.1)."""

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
async def test_customer_profile_create_get_patch_and_code_unique(client):
    ac, seed = client
    headers = await _admin(ac, seed)

    created = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={
            "name": "Profile Customer",
            "code": "CUST-PROF-1",
            "profile_type": "walk_in",
            "status": "active",
            "phone": "+233200000001",
            "email": "profile.cust@example.com",
            "address": "12 Independence Ave, Accra",
            "latitude": 5.6037,
            "longitude": -0.1870,
            "credit_limit": 100,
            "payment_terms_days": 14,
        },
    )
    assert created.status_code == 200, created.text
    data = created.json()["data"]
    assert data["code"] == "CUST-PROF-1"
    assert data["profile_type"] == "walk_in"
    assert data["status"] == "active"
    assert data["address"] == "12 Independence Ave, Accra"
    assert abs(float(data["latitude"]) - 5.6037) < 1e-4
    assert abs(float(data["longitude"]) - (-0.1870)) < 1e-4
    cid = data["id"]

    got = await ac.get(f"/api/v1/customers/{cid}", headers=headers)
    assert got.status_code == 200
    assert got.json()["data"]["code"] == "CUST-PROF-1"

    patched = await ac.patch(
        f"/api/v1/customers/{cid}",
        headers=headers,
        json={"status": "inactive", "profile_type": "registered"},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["data"]["status"] == "inactive"
    assert patched.json()["data"]["profile_type"] == "registered"

    active_only = await ac.get("/api/v1/customers?status=active", headers=headers)
    assert active_only.status_code == 200
    assert all(c["id"] != cid for c in active_only.json()["data"])

    dup = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "Dup Code", "code": "CUST-PROF-1"},
    )
    assert dup.status_code == 409

    bad_type = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "Bad", "profile_type": "trade"},
    )
    assert bad_type.status_code == 400


@pytest.mark.asyncio
async def test_supplier_profile_create_get_and_category(client):
    ac, seed = client
    headers = await _admin(ac, seed)

    created = await ac.post(
        "/api/v1/suppliers",
        headers=headers,
        json={
            "name": "Profile Supplier",
            "code": "SUP-PROF-1",
            "profile_type": "manufacturer",
            "category": "packaging",
            "status": "active",
            "phone": "+233200000002",
            "email": "profile.sup@example.com",
            "address": "Tema Industrial Area",
            "latitude": 5.6698,
            "longitude": -0.0166,
            "payment_terms_days": 45,
        },
    )
    assert created.status_code == 200, created.text
    data = created.json()["data"]
    assert data["code"] == "SUP-PROF-1"
    assert data["profile_type"] == "manufacturer"
    assert data["category"] == "packaging"
    assert data["address"] == "Tema Industrial Area"
    sid = data["id"]

    got = await ac.get(f"/api/v1/suppliers/{sid}", headers=headers)
    assert got.status_code == 200
    assert got.json()["data"]["category"] == "packaging"

    listed = await ac.get("/api/v1/suppliers?status=active", headers=headers)
    assert listed.status_code == 200
    assert any(s["id"] == sid for s in listed.json()["data"])
