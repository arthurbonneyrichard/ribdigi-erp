"""Store-assigned inventory writes require a warehouse; cashiers cannot adjust stock."""

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
async def test_cashier_cannot_adjust_stock(client):
    ac, seed = client
    cashier = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    r = await ac.post(
        f"/api/v1/inventory/adjust/{seed['p1'].id}",
        headers=cashier,
        json={"quantity": -1, "reason": "damage", "notes": "Broken on shelf"},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_assigned_user_adjust_requires_warehouse(client):
    ac, seed = client
    admin = await _admin(ac, seed)
    store = await ac.post(
        "/api/v1/stores",
        headers=admin,
        json={"code": "ADJ1", "name": "Adjust Store"},
    )
    assert store.status_code == 200, store.text
    store_id = store.json()["data"]["id"]
    assigned = await ac.put(
        f"/api/v1/users/{seed['mgr1'].id}/stores",
        headers=admin,
        json={"store_ids": [store_id]},
    )
    assert assigned.status_code == 200, assigned.text
    mgr = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    missing = await ac.post(
        f"/api/v1/inventory/adjust/{seed['p1'].id}",
        headers=mgr,
        json={"quantity": -1, "reason": "damage", "notes": "Store assigned no warehouse"},
    )
    assert missing.status_code == 400, missing.text
    wh = await ac.post(
        "/api/v1/warehouses",
        headers=admin,
        json={"code": "ADJWH", "name": "Adjust WH", "store_id": store_id},
    )
    assert wh.status_code == 200, wh.text
    ok = await ac.post(
        f"/api/v1/inventory/adjust/{seed['p1'].id}",
        headers=mgr,
        json={
            "quantity": -1,
            "reason": "damage",
            "notes": "Damaged at assigned store",
            "warehouse_id": wh.json()["data"]["id"],
        },
    )
    assert ok.status_code == 200, ok.text
