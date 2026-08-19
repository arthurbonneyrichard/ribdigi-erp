"""Stage 164 A1 — POST /sync/ack."""

from __future__ import annotations

import pyotp
import pytest

from tests.conftest import auth_headers


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_sync_ack_pull_ops_a1(client):
    ac, seed = client
    headers = await _super(ac, seed)
    device = await ac.post(
        "/api/v1/offline/devices",
        headers=headers,
        json={"name": "Ack device", "platform": "web"},
    )
    device_id = device.json()["data"]["id"]

    pulled = await ac.post(
        "/api/v1/sync/pull",
        headers=headers,
        json={"device_id": device_id, "include_catalog": True},
    )
    assert pulled.status_code == 200, pulled.text
    op_ids = [op["id"] for op in pulled.json()["data"]["ops"]]
    assert op_ids

    acked = await ac.post(
        "/api/v1/sync/ack",
        headers=headers,
        json={"device_id": device_id, "op_ids": op_ids},
    )
    assert acked.status_code == 200, acked.text
    data = acked.json()["data"]
    assert data["count"] == len(op_ids)
    assert all(row["status"] == "acked" for row in data["acked"])
    assert all(row["acked_at"] is not None for row in data["acked"])
