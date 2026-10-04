"""POS device heartbeat upsert + list."""

from __future__ import annotations

import pyotp
import pytest

from tests.conftest import auth_headers


async def _cashier(ac):
    return await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_pos_device_heartbeat_upsert_and_list(client):
    ac, seed = client
    cashier = await _cashier(ac)
    admin = await _admin(ac, seed)

    first = await ac.post(
        "/api/v1/pos/devices/heartbeat",
        headers=cashier,
        json={
            "device_id": "dev-heartbeat-test01",
            "app_version": "web-mvp",
            "pending_queue_count": 2,
        },
    )
    assert first.status_code == 200, first.text
    data = first.json()["data"]
    assert data["device_id"] == "dev-heartbeat-test01"
    assert data["pending_queue_count"] == 2
    assert data["last_seen_at"]

    second = await ac.post(
        "/api/v1/pos/devices/heartbeat",
        headers=cashier,
        json={
            "device_id": "dev-heartbeat-test01",
            "pending_queue_count": 0,
            "label": "Front counter",
        },
    )
    assert second.status_code == 200, second.text
    assert second.json()["data"]["id"] == data["id"]
    assert second.json()["data"]["pending_queue_count"] == 0
    assert second.json()["data"]["label"] == "Front counter"

    listed = await ac.get("/api/v1/pos/devices", headers=admin)
    assert listed.status_code == 200, listed.text
    ids = {d["device_id"] for d in listed.json()["data"]}
    assert "dev-heartbeat-test01" in ids

    bad = await ac.post(
        "/api/v1/pos/devices/heartbeat",
        headers=cashier,
        json={"device_id": "short"},
    )
    assert bad.status_code == 422, bad.text
