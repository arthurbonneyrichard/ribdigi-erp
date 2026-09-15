"""Offline receipt numbering tests."""

from __future__ import annotations

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
        json={"name": "Receipt POS", "platform": "web"},
    )
    assert device.status_code == 200, device.text
    device_id = device.json()["data"]["id"]

    bind = await ac.post(f"/api/v1/offline/devices/{device_id}/bind", headers=headers, json={})
    assert bind.status_code == 200, bind.text

    opened = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=headers,
        json={"opening_cash": 50},
    )
    assert opened.status_code == 200, opened.text
    session_id = opened.json()["data"]["session_id"]
    return device_id, session_id, product.id


@pytest.mark.asyncio
async def test_sync_push_preserves_offline_receipt_number(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)
    device_id, session_id, product_id = await _pos_push_setup(
        ac, seed, db_session, headers=headers
    )
    receipt_no = "OFF-deadbeef-000001"

    pushed = await ac.post(
        "/api/v1/sync/push",
        headers=headers,
        json={
            "device_id": device_id,
            "ops": [
                {
                    "client_op_id": "offline-rcpt-op-01",
                    "op_type": "pos_sale",
                    "payload": {
                        "client_request_id": "offline-rcpt-req-01",
                        "offline_receipt_number": receipt_no,
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
    sale_payload = (result.get("queue_item") or {}).get("result_payload") or {}
    assert sale_payload.get("reference") == receipt_no

    from sqlalchemy import select

    tx = (
        await db_session.execute(
            select(m.Transaction).where(m.Transaction.reference == receipt_no)
        )
    ).scalar_one_or_none()
    assert tx is not None


@pytest.mark.asyncio
async def test_sync_push_rejects_duplicate_offline_receipt_number(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)
    device_id, session_id, product_id = await _pos_push_setup(
        ac, seed, db_session, headers=headers
    )
    receipt_no = "OFF-cafebabe-000002"
    base = {
        "device_id": device_id,
        "ops": [
            {
                "client_op_id": "offline-rcpt-op-a",
                "op_type": "pos_sale",
                "payload": {
                    "client_request_id": "offline-rcpt-req-a",
                    "offline_receipt_number": receipt_no,
                    "session_id": session_id,
                    "items": [{"product_id": product_id, "quantity": 1}],
                    "payment_method": "cash",
                },
            }
        ],
    }
    first = await ac.post("/api/v1/sync/push", headers=headers, json=base)
    assert first.status_code == 200, first.text

    dup = await ac.post(
        "/api/v1/sync/push",
        headers=headers,
        json={
            "device_id": device_id,
            "ops": [
                {
                    "client_op_id": "offline-rcpt-op-b",
                    "op_type": "pos_sale",
                    "payload": {
                        "client_request_id": "offline-rcpt-req-b",
                        "offline_receipt_number": receipt_no,
                        "session_id": session_id,
                        "items": [{"product_id": product_id, "quantity": 1}],
                        "payment_method": "cash",
                    },
                }
            ],
        },
    )
    assert dup.status_code == 200, dup.text
    result = dup.json()["data"]["results"][0]
    assert result["status"] == "failed"
    assert "OFFLINE_RECEIPT" in (result.get("error") or "") or "duplicate" in (
        result.get("error") or ""
    ).lower()
