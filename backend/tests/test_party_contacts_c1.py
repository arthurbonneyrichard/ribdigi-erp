"""Party multi-contact CRUD (BR-6.1)."""

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
async def test_supplier_and_customer_contacts_primary_sync_and_isolation(client):
    ac, seed = client
    headers = await _admin(ac, seed)

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=headers,
        json={"name": "Acme Supplies", "email": "office@acme.example.com"},
    )
    assert supplier.status_code == 200, supplier.text
    sid = supplier.json()["data"]["id"]

    c1 = await ac.post(
        f"/api/v1/suppliers/{sid}/contacts",
        headers=headers,
        json={
            "name": "Ada Buyer",
            "phone": "+233200000001",
            "email": "ada@acme.example.com",
            "designation": "Purchasing",
        },
    )
    assert c1.status_code == 200, c1.text
    first = c1.json()["data"]
    assert first["is_primary"] is True
    assert first["designation"] == "Purchasing"

    got = await ac.get(f"/api/v1/suppliers/{sid}", headers=headers)
    assert got.status_code == 200
    body = got.json()["data"]
    assert body["email"] == "ada@acme.example.com"
    assert body["phone"] == "+233200000001"
    assert len(body["contacts"]) == 1

    c2 = await ac.post(
        f"/api/v1/suppliers/{sid}/contacts",
        headers=headers,
        json={
            "name": "Kojo Accounts",
            "email": "kojo@acme.example.com",
            "designation": "Accounts",
            "is_primary": True,
        },
    )
    assert c2.status_code == 200, c2.text
    second = c2.json()["data"]
    assert second["is_primary"] is True

    listed = await ac.get(f"/api/v1/suppliers/{sid}/contacts", headers=headers)
    rows = listed.json()["data"]
    assert len(rows) == 2
    assert sum(1 for r in rows if r["is_primary"]) == 1
    assert next(r for r in rows if r["is_primary"])["id"] == second["id"]

    refreshed = await ac.get(f"/api/v1/suppliers/{sid}", headers=headers)
    assert refreshed.json()["data"]["email"] == "kojo@acme.example.com"

    deleted = await ac.delete(
        f"/api/v1/suppliers/{sid}/contacts/{second['id']}",
        headers=headers,
    )
    assert deleted.status_code == 200
    after = await ac.get(f"/api/v1/suppliers/{sid}/contacts", headers=headers)
    remaining = after.json()["data"]
    assert len(remaining) == 1
    assert remaining[0]["is_primary"] is True
    assert remaining[0]["id"] == first["id"]

    customer = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "Retail Buyer Co"},
    )
    assert customer.status_code == 200
    cid = customer.json()["data"]["id"]
    cc = await ac.post(
        f"/api/v1/customers/{cid}/contacts",
        headers=headers,
        json={"name": "Ama Retail", "email": "ama@retail.example.com", "phone": "+233200000099"},
    )
    assert cc.status_code == 200
    cg = await ac.get(f"/api/v1/customers/{cid}", headers=headers)
    assert cg.json()["data"]["email"] == "ama@retail.example.com"
    assert len(cg.json()["data"]["contacts"]) == 1

    # Wrong kind / foreign tenant must 404
    wrong_kind = await ac.get(f"/api/v1/customers/{sid}/contacts", headers=headers)
    assert wrong_kind.status_code == 404
    foreign = await ac.get(
        f"/api/v1/suppliers/{sid}/contacts",
        headers={**headers, "X-Tenant-ID": seed["t2"].id},
    )
    assert foreign.status_code == 403
