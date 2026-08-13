"""Stage 164 C1 — GET /sync/conflicts."""

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
async def test_sync_conflict_on_payload_mismatch_c1(client):
    ac, seed = client
    headers = await _super(ac, seed)
    device = await ac.post(
        "/api/v1/offline/devices",
        headers=headers,
        json={"name": "Conflict device", "platform": "web"},
    )
    device_id = device.json()["data"]["id"]

    first = await ac.post(
        "/api/v1/sync/push",
        headers=headers,
        json={
            "device_id": device_id,
            "ops": [
                {
                    "client_op_id": "conflict-op-1",
                    "op_type": "ping",
                    "payload": {"n": 1},
                }
            ],
        },
    )
    assert first.status_code == 200, first.text
    assert first.json()["data"]["results"][0]["status"] == "applied"

    second = await ac.post(
        "/api/v1/sync/push",
        headers=headers,
        json={
            "device_id": device_id,
            "ops": [
                {
                    "client_op_id": "conflict-op-1",
                    "op_type": "ping",
                    "payload": {"n": 2},
                }
            ],
        },
    )
    assert second.status_code == 200, second.text
    result = second.json()["data"]["results"][0]
    assert result["status"] == "conflict"
    assert result["conflict"]["status"] == "open"

    listed = await ac.get("/api/v1/sync/conflicts?status=open", headers=headers)
    assert listed.status_code == 200, listed.text
    rows = listed.json()["data"]
    assert any(r["client_op_id"] == "conflict-op-1" for r in rows)
