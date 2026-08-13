"""Stage 164 P1 — POST /sync/push."""

from __future__ import annotations

import pyotp
import pytest

from app import accounting as accounting_svc
from tests.conftest import auth_headers


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_sync_push_ping_and_replay_p1(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)

    device = await ac.post(
        "/api/v1/offline/devices",
        headers=headers,
        json={"name": "Push tablet", "platform": "web"},
    )
    assert device.status_code == 200, device.text
    device_id = device.json()["data"]["id"]

    pushed = await ac.post(
        "/api/v1/sync/push",
        headers=headers,
        json={
            "device_id": device_id,
            "ops": [{"client_op_id": "ping-op-0001", "op_type": "ping", "payload": {}}],
        },
    )
    assert pushed.status_code == 200, pushed.text
    results = pushed.json()["data"]["results"]
    assert len(results) == 1
    assert results[0]["status"] == "applied"
    assert results[0]["replayed"] is False

    replay = await ac.post(
        "/api/v1/sync/push",
        headers=headers,
        json={
            "device_id": device_id,
            "ops": [{"client_op_id": "ping-op-0001", "op_type": "ping", "payload": {}}],
        },
    )
    assert replay.status_code == 200, replay.text
    assert replay.json()["data"]["results"][0]["replayed"] is True
    assert replay.json()["data"]["results"][0]["status"] == "applied"


@pytest.mark.asyncio
async def test_sync_push_pos_sale_p1(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)
    await accounting_svc.ensure_default_accounts(db_session, seed["t1"].id)

    product = seed["p1"]
    product.selling_price = 25
    product.stock_qty = 50
    product.reserved_qty = 0
    product.tax_exempt = True
    product.tax_rate_id = None
    await db_session.commit()

    device = await ac.post(
        "/api/v1/offline/devices",
        headers=headers,
        json={"name": "POS device", "platform": "android"},
    )
    device_id = device.json()["data"]["id"]

    opened = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=headers,
        json={"opening_cash": 50},
    )
    assert opened.status_code == 200, opened.text
    session_id = opened.json()["data"]["session_id"]

    pushed = await ac.post(
        "/api/v1/sync/push",
        headers=headers,
        json={
            "device_id": device_id,
            "ops": [
                {
                    "client_op_id": "sale-op-0001",
                    "op_type": "pos_sale",
                    "payload": {
                        "client_request_id": "sale-req-0001",
                        "session_id": session_id,
                        "items": [{"product_id": product.id, "quantity": 1}],
                        "payments": [{"payment_method": "cash", "amount": 25}],
                    },
                }
            ],
        },
    )
    assert pushed.status_code == 200, pushed.text
    result = pushed.json()["data"]["results"][0]
    assert result["status"] == "applied", pushed.text
    assert result["queue_item"]["result_entity_id"]
