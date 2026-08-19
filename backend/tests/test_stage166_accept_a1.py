"""Stage 166 A1 — accept_client safe re-apply (never double-post applied ops)."""

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


@pytest.mark.asyncio
async def test_accept_client_blocked_when_original_applied_a1(client):
    ac, seed = client
    headers = await _super(ac, seed)
    device = await ac.post(
        "/api/v1/offline/devices",
        headers=headers,
        json={"name": "Accept block device", "platform": "web"},
    )
    device_id = device.json()["data"]["id"]

    await ac.post(
        "/api/v1/sync/push",
        headers=headers,
        json={
            "device_id": device_id,
            "ops": [
                {"client_op_id": "accept-block-1", "op_type": "ping", "payload": {"n": 1}}
            ],
        },
    )
    conflicted = await ac.post(
        "/api/v1/sync/push",
        headers=headers,
        json={
            "device_id": device_id,
            "ops": [
                {"client_op_id": "accept-block-1", "op_type": "ping", "payload": {"n": 2}}
            ],
        },
    )
    assert conflicted.status_code == 200, conflicted.text
    conflict_id = conflicted.json()["data"]["results"][0]["conflict"]["id"]

    resolved = await ac.post(
        f"/api/v1/sync/conflicts/{conflict_id}/resolve",
        headers=headers,
        json={"resolution": "accept_client"},
    )
    assert resolved.status_code == 200, resolved.text
    data = resolved.json()["data"]
    assert data["status"] == "resolved"
    assert data["resolution"] == "accept_client"
    assert data.get("reapplied") is False
    assert data.get("reapply_blocked_reason") == "original_op_already_applied"


@pytest.mark.asyncio
async def test_accept_client_reapplies_when_original_failed_a1(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)
    await accounting_svc.ensure_default_accounts(db_session, seed["t1"].id)

    product = seed["p1"]
    product.selling_price = 12
    product.stock_qty = 30
    product.reserved_qty = 0
    product.tax_exempt = True
    product.tax_rate_id = None
    await db_session.commit()

    device = await ac.post(
        "/api/v1/offline/devices",
        headers=headers,
        json={"name": "Accept reapply device", "platform": "web"},
    )
    device_id = device.json()["data"]["id"]

    opened = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=headers,
        json={"opening_cash": 40},
    )
    assert opened.status_code == 200, opened.text
    session_id = opened.json()["data"]["session_id"]

    # First push fails (missing client_request_id) → not applied.
    failed = await ac.post(
        "/api/v1/sync/push",
        headers=headers,
        json={
            "device_id": device_id,
            "ops": [
                {
                    "client_op_id": "accept-reapply-1",
                    "op_type": "pos_sale",
                    "payload": {
                        "session_id": session_id,
                        "items": [{"product_id": product.id, "quantity": 1}],
                        "payments": [{"payment_method": "cash", "amount": 12}],
                    },
                }
            ],
        },
    )
    assert failed.status_code == 200, failed.text
    assert failed.json()["data"]["results"][0]["status"] == "failed"

    # Same client_op_id, different (valid) payload → conflict; original never applied.
    conflicted = await ac.post(
        "/api/v1/sync/push",
        headers=headers,
        json={
            "device_id": device_id,
            "ops": [
                {
                    "client_op_id": "accept-reapply-1",
                    "op_type": "pos_sale",
                    "payload": {
                        "client_request_id": "accept-reapply-sale-1",
                        "session_id": session_id,
                        "items": [{"product_id": product.id, "quantity": 1}],
                        "payments": [{"payment_method": "cash", "amount": 12}],
                    },
                }
            ],
        },
    )
    assert conflicted.status_code == 200, conflicted.text
    result = conflicted.json()["data"]["results"][0]
    assert result["status"] == "conflict", conflicted.text
    conflict_id = result["conflict"]["id"]

    resolved = await ac.post(
        f"/api/v1/sync/conflicts/{conflict_id}/resolve",
        headers=headers,
        json={"resolution": "accept_client"},
    )
    assert resolved.status_code == 200, resolved.text
    data = resolved.json()["data"]
    assert data["resolution"] == "accept_client"
    assert data.get("reapplied") is True
    assert data.get("reapply_queue_item", {}).get("status") == "applied"
    assert data.get("reapply_queue_item", {}).get("client_op_id", "").startswith("reapply-")

    await db_session.refresh(product)
    assert float(product.stock_qty) == 29.0


def test_settings_accept_client_ui_a1():
    company = (ROOT / "frontend/app/company/page.tsx").read_text(encoding="utf-8")
    assert "Accept client" in company
    assert "accept_client" in company
    engine = (ROOT / "backend/app/sync_engine.py").read_text(encoding="utf-8")
    assert "original_op_already_applied" in engine
    assert "reapply-" in engine
