"""7-day offline authorization envelope tests (§13–14)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pyotp
import pytest

from app import accounting as accounting_svc
from app import models as m
from tests.conftest import auth_headers


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


async def _pos_push_setup(ac, seed, db_session, *, headers):
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
        json={"name": "Envelope POS", "platform": "web"},
    )
    assert device.status_code == 200, device.text
    device_id = device.json()["data"]["id"]

    bind = await ac.post(
        f"/api/v1/offline/devices/{device_id}/bind",
        headers=headers,
        json={"app_version": "test-mvp"},
    )
    assert bind.status_code == 200, bind.text
    envelope = bind.json()["data"]["auth_envelope"]
    assert envelope["device_id"] == device_id
    assert envelope.get("offline_valid_until")

    opened = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=headers,
        json={"opening_cash": 50},
    )
    assert opened.status_code == 200, opened.text
    session_id = opened.json()["data"]["session_id"]
    return device_id, session_id, product.id, envelope


def _sale_op(client_request_id: str, session_id: str, product_id: str) -> dict:
    return {
        "client_op_id": f"op-{client_request_id}",
        "op_type": "pos_sale",
        "payload": {
            "client_request_id": client_request_id,
            "session_id": session_id,
            "items": [{"product_id": product_id, "quantity": 1}],
            "payment_method": "cash",
        },
    }


@pytest.mark.asyncio
async def test_offline_bind_issues_valid_envelope(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)
    device_id, _session_id, _product_id, envelope = await _pos_push_setup(
        ac, seed, db_session, headers=headers
    )

    until = datetime.fromisoformat(envelope["offline_valid_until"].replace("Z", ""))
    assert until > datetime.utcnow()
    assert envelope["tenant_id"] == seed["t1"].id
    assert envelope["device_id"] == device_id
    assert isinstance(envelope.get("permissions"), dict)


@pytest.mark.asyncio
async def test_sync_push_accepts_valid_envelope(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)
    device_id, session_id, product_id, envelope = await _pos_push_setup(
        ac, seed, db_session, headers=headers
    )

    pushed = await ac.post(
        "/api/v1/sync/push",
        headers=headers,
        json={
            "device_id": device_id,
            "auth_envelope": envelope,
            "ops": [_sale_op("valid-env-req-01", session_id, product_id)],
        },
    )
    assert pushed.status_code == 200, pushed.text
    body = pushed.json()["data"]
    assert body["results"][0]["status"] == "applied"
    assert body.get("auth_envelope", {}).get("offline_valid_until")


@pytest.mark.asyncio
async def test_sync_push_rejects_expired_envelope(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)
    device_id, session_id, product_id, envelope = await _pos_push_setup(
        ac, seed, db_session, headers=headers
    )

    row = await db_session.get(m.OfflineDevice, device_id)
    expired_at = datetime.utcnow() - timedelta(hours=1)
    row.offline_authorized_until = expired_at
    row.last_online_at = expired_at - timedelta(days=8)
    await db_session.commit()

    envelope["offline_valid_until"] = expired_at.isoformat() + "Z"

    pushed = await ac.post(
        "/api/v1/sync/push",
        headers=headers,
        json={
            "device_id": device_id,
            "auth_envelope": envelope,
            "ops": [_sale_op("expired-env-req-01", session_id, product_id)],
        },
    )
    assert pushed.status_code == 409, pushed.text
    detail = pushed.json()["detail"]
    if isinstance(detail, dict):
        assert detail.get("code") == "OFFLINE_ENVELOPE_EXPIRED"
    else:
        assert "OFFLINE_ENVELOPE_EXPIRED" in str(detail)


@pytest.mark.asyncio
async def test_sync_push_rejects_device_mismatch(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)
    device_id, session_id, product_id, envelope = await _pos_push_setup(
        ac, seed, db_session, headers=headers
    )

    other = await ac.post(
        "/api/v1/offline/devices",
        headers=headers,
        json={"name": "Other device", "platform": "web"},
    )
    assert other.status_code == 200, other.text
    other_id = other.json()["data"]["id"]

    envelope["device_id"] = other_id

    pushed = await ac.post(
        "/api/v1/sync/push",
        headers=headers,
        json={
            "device_id": device_id,
            "auth_envelope": envelope,
            "ops": [_sale_op("mismatch-env-req-01", session_id, product_id)],
        },
    )
    assert pushed.status_code == 409, pushed.text
    detail = pushed.json()["detail"]
    if isinstance(detail, dict):
        assert detail.get("code") == "OFFLINE_ENVELOPE_DEVICE_MISMATCH"
    else:
        assert "OFFLINE_ENVELOPE_DEVICE_MISMATCH" in str(detail)
