"""Offline payment safety + queue reset guard tests (2026-08-23 implementation pass)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from app import accounting as accounting_svc
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


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
        json={"name": "Safety POS", "platform": "web"},
    )
    assert device.status_code == 200, device.text
    device_id = device.json()["data"]["id"]

    opened = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=headers,
        json={"opening_cash": 50},
    )
    assert opened.status_code == 200, opened.text
    session_id = opened.json()["data"]["session_id"]
    return device_id, session_id, product.id


@pytest.mark.asyncio
async def test_sync_push_accepts_offline_cash_sale(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)
    device_id, session_id, product_id = await _pos_push_setup(ac, seed, db_session, headers=headers)

    pushed = await ac.post(
        "/api/v1/sync/push",
        headers=headers,
        json={
            "device_id": device_id,
            "ops": [
                {
                    "client_op_id": "cash-sale-op-01",
                    "op_type": "pos_sale",
                    "payload": {
                        "client_request_id": "cash-sale-req-01",
                        "session_id": session_id,
                        "items": [{"product_id": product_id, "quantity": 1}],
                        "payment_method": "cash",
                    },
                }
            ],
        },
    )
    assert pushed.status_code == 200, pushed.text
    result = pushed.json()["data"]["results"][0]
    assert result["status"] == "applied", pushed.text


@pytest.mark.asyncio
async def test_sync_push_rejects_offline_card_without_supervisor_ack(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)
    device_id, session_id, product_id = await _pos_push_setup(ac, seed, db_session, headers=headers)

    pushed = await ac.post(
        "/api/v1/sync/push",
        headers=headers,
        json={
            "device_id": device_id,
            "ops": [
                {
                    "client_op_id": "card-sale-op-01",
                    "op_type": "pos_sale",
                    "payload": {
                        "client_request_id": "card-sale-req-01",
                        "session_id": session_id,
                        "items": [{"product_id": product_id, "quantity": 1}],
                        "payment_method": "card",
                    },
                }
            ],
        },
    )
    assert pushed.status_code == 200, pushed.text
    result = pushed.json()["data"]["results"][0]
    assert result["status"] == "failed"
    assert "OFFLINE_PAYMENT_BLOCKED" in (result.get("error") or "")


@pytest.mark.asyncio
async def test_sync_push_accepts_offline_card_with_supervisor_ack(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)
    device_id, session_id, product_id = await _pos_push_setup(ac, seed, db_session, headers=headers)

    pushed = await ac.post(
        "/api/v1/sync/push",
        headers=headers,
        json={
            "device_id": device_id,
            "ops": [
                {
                    "client_op_id": "card-ack-op-01",
                    "op_type": "pos_sale",
                    "payload": {
                        "client_request_id": "card-ack-req-01",
                        "session_id": session_id,
                        "items": [{"product_id": product_id, "quantity": 1}],
                        "payment_method": "card",
                        "payload": {
                            "offline_supervisor_ack": True,
                            "offline_supervisor_reason": "Manager verified card receipt offline",
                            "offline_provider_pending_verification": True,
                        },
                    },
                }
            ],
        },
    )
    assert pushed.status_code == 200, pushed.text
    result = pushed.json()["data"]["results"][0]
    assert result["status"] == "applied", pushed.text


@pytest.mark.asyncio
async def test_sync_push_rejects_offline_credit_without_cached_ack(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)
    device_id, session_id, product_id = await _pos_push_setup(ac, seed, db_session, headers=headers)
    customer_id = seed["party1"].id

    pushed = await ac.post(
        "/api/v1/sync/push",
        headers=headers,
        json={
            "device_id": device_id,
            "ops": [
                {
                    "client_op_id": "credit-sale-op-01",
                    "op_type": "pos_sale",
                    "payload": {
                        "client_request_id": "credit-sale-req-01",
                        "session_id": session_id,
                        "party_id": customer_id,
                        "items": [{"product_id": product_id, "quantity": 1}],
                        "payment_method": "credit",
                    },
                }
            ],
        },
    )
    assert pushed.status_code == 200, pushed.text
    result = pushed.json()["data"]["results"][0]
    assert result["status"] == "failed"
    assert "OFFLINE_CREDIT_BLOCKED" in (result.get("error") or "")


def test_offline_payment_frontend_modules_present():
    payments = (ROOT / "frontend/lib/offlinePayments.ts").read_text(encoding="utf-8")
    assert "prepareOfflineSalePayments" in payments
    assert "OFFLINE_PAYMENT_BLOCKED" not in payments  # server-side code string
    assert "offline_supervisor_ack" in payments
    queue = (ROOT / "frontend/lib/offlineQueue.ts").read_text(encoding="utf-8")
    assert "OfflineQueuePendingError" in queue
    assert "resetOfflineQueueData" in queue
    assert "exportOfflineQueueRecovery" in queue
    pos = (ROOT / "frontend/app/pos/page.tsx").read_text(encoding="utf-8")
    assert "prepareOfflineSalePayments" in pos
    assert "OfflineQueuePendingError" not in pos  # guard lives in offlineQueue util
