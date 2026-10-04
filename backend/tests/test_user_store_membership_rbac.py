"""Store membership RBAC — cashiers cannot open unauthorized stores."""

from __future__ import annotations

import pyotp
import pytest

from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


async def _cashier(ac):
    return await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")


@pytest.mark.asyncio
async def test_cashier_pos_store_membership_enforced(client, db_session):
    ac, seed = client
    admin = await _admin(ac, seed)
    cashier = await _cashier(ac)
    tenant_id = seed["t1"].id

    # Create two stores under alpha
    r1 = await ac.post(
        "/api/v1/stores",
        headers=admin,
        json={"name": "Weija Store", "code": "WEIJA"},
    )
    r2 = await ac.post(
        "/api/v1/stores",
        headers=admin,
        json={"name": "Tema Store", "code": "TEMA"},
    )
    stores = (await ac.get("/api/v1/stores", headers=admin)).json()["data"]
    assert isinstance(stores, list) and len(stores) >= 1

    if r1.status_code < 400 and r2.status_code < 400:
        store_a = r1.json()["data"]["id"]
        store_b = r2.json()["data"]["id"]
    elif len(stores) >= 2:
        store_a = stores[0]["id"]
        store_b = stores[1]["id"]
    else:
        pytest.skip("Need at least two stores under entitlement to test membership")

    users = (await ac.get("/api/v1/users", headers=admin)).json()["data"]
    cashier_user = next((u for u in users if u.get("role") == "cashier"), None)
    if not cashier_user:
        pytest.skip("No cashier user in seed")
    uid = cashier_user["id"]

    put = await ac.put(
        f"/api/v1/users/{uid}/stores",
        headers=admin,
        json={"store_ids": [store_a]},
    )
    assert put.status_code == 200, put.text
    assert store_a in put.json()["data"]["store_ids"]
    assert put.json()["data"]["all_stores"] is False

    pos_stores = (await ac.get("/api/v1/pos/stores", headers=cashier)).json()["data"]
    ids = {s["id"] for s in pos_stores}
    assert store_a in ids
    assert store_b not in ids

    denied = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=cashier,
        json={"store_id": store_b, "opening_cash": 0},
    )
    assert denied.status_code in (403, 404), denied.text

    allowed = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=cashier,
        json={"store_id": store_a, "opening_cash": 0},
    )
    assert allowed.status_code == 200, allowed.text
    assert (allowed.json()["data"].get("store_id") or store_a) == store_a
    _ = tenant_id  # seeded tenant used via auth headers
