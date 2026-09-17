"""Store membership RBAC — cashiers cannot open unauthorized stores."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_cashier_pos_store_membership_enforced(client: AsyncClient, seeded):
    admin = seeded["tokens"]["admin"]
    cashier = seeded["tokens"]["cashier"]
    tenant = seeded["tenant_id"]

    # Create two stores (MAIN may already exist from seed — create second)
    r1 = await client.post(
        "/api/v1/stores",
        headers={"Authorization": f"Bearer {admin}", "X-Tenant-ID": tenant},
        json={"name": "Weija Store", "code": "WEIJA"},
    )
    # May 201 or 409 if entitlement / duplicate — try list
    stores = (
        await client.get(
            "/api/v1/stores",
            headers={"Authorization": f"Bearer {admin}", "X-Tenant-ID": tenant},
        )
    ).json()["data"]
    assert isinstance(stores, list) and len(stores) >= 1
    store_a = stores[0]["id"]
    if r1.status_code < 400:
        store_b = r1.json()["data"]["id"]
    else:
        r2 = await client.post(
            "/api/v1/stores",
            headers={"Authorization": f"Bearer {admin}", "X-Tenant-ID": tenant},
            json={"name": "Tema Store", "code": "TEMA"},
        )
        if r2.status_code >= 400:
            pytest.skip("Cannot create second store under entitlement")
        store_b = r2.json()["data"]["id"]
        if store_a == store_b and len(stores) > 1:
            store_a = stores[0]["id"]
            store_b = stores[1]["id"]

    # Resolve cashier user id
    users = (
        await client.get(
            "/api/v1/users",
            headers={"Authorization": f"Bearer {admin}", "X-Tenant-ID": tenant},
        )
    ).json()["data"]
    cashier_user = next((u for u in users if u.get("role") == "cashier"), None)
    if not cashier_user:
        pytest.skip("No cashier user in seed")
    uid = cashier_user["id"]

    # Assign cashier only to store_a
    put = await client.put(
        f"/api/v1/users/{uid}/stores",
        headers={"Authorization": f"Bearer {admin}", "X-Tenant-ID": tenant},
        json={"store_ids": [store_a]},
    )
    assert put.status_code == 200, put.text
    assert store_a in put.json()["data"]["store_ids"]
    assert put.json()["data"]["all_stores"] is False

    # POS store list for cashier should only include store_a
    pos_stores = (
        await client.get(
            "/api/v1/pos/stores",
            headers={"Authorization": f"Bearer {cashier}", "X-Tenant-ID": tenant},
        )
    ).json()["data"]
    ids = {s["id"] for s in pos_stores}
    assert store_a in ids
    assert store_b not in ids

    # Opening unauthorized store denied
    denied = await client.post(
        "/api/v1/pos/sessions/open",
        headers={"Authorization": f"Bearer {cashier}", "X-Tenant-ID": tenant},
        json={"store_id": store_b, "opening_cash": 0},
    )
    assert denied.status_code == 403, denied.text

    # Opening authorized store allowed (or 409 if already open)
    ok = await client.post(
        "/api/v1/pos/sessions/open",
        headers={"Authorization": f"Bearer {cashier}", "X-Tenant-ID": tenant},
        json={"store_id": store_a, "opening_cash": 0},
    )
    assert ok.status_code in (200, 409), ok.text
