"""Stage 168 R1 — device revoke mid-queue honesty."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest
from sqlalchemy import select

from app import models as m
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_revoke_retains_pending_and_blocks_push_r1(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)

    device = await ac.post(
        "/api/v1/offline/devices",
        headers=headers,
        json={"name": "Revoke mid-queue", "platform": "web"},
    )
    device_id = device.json()["data"]["id"]

    # Create a failed pending-style queue item, then force status pending for honesty count.
    pushed = await ac.post(
        "/api/v1/sync/push",
        headers=headers,
        json={
            "device_id": device_id,
            "ops": [
                {
                    "client_op_id": "revoke-pending-op-1",
                    "op_type": "pos_sale",
                    "payload": {"items": []},  # invalid → failed
                }
            ],
        },
    )
    assert pushed.status_code == 200, pushed.text
    assert pushed.json()["data"]["results"][0]["status"] == "failed"

    item = (
        await db_session.execute(
            select(m.SyncQueueItem).where(
                m.SyncQueueItem.tenant_id == seed["t1"].id,
                m.SyncQueueItem.client_op_id == "revoke-pending-op-1",
            )
        )
    ).scalar_one()
    item.status = "pending"
    await db_session.commit()

    revoked = await ac.delete(f"/api/v1/offline/devices/{device_id}", headers=headers)
    assert revoked.status_code == 200, revoked.text
    data = revoked.json()["data"]
    assert data["status"] == "revoked"
    assert data["pending_queue"]["pending_pushes"] >= 1
    assert data["pending_queue"]["pending_total"] >= 1
    assert "not" in (data.get("message") or "").lower() or "retained" in (
        data.get("message") or ""
    ).lower() or "auto-applied" in (data.get("message") or "").lower()

    # Queue row still present — not deleted on revoke.
    await db_session.refresh(item)
    assert item.status == "pending"

    blocked = await ac.post(
        "/api/v1/sync/push",
        headers=headers,
        json={
            "device_id": device_id,
            "ops": [
                {"client_op_id": "revoke-blocked-op-2", "op_type": "ping", "payload": {"n": 1}}
            ],
        },
    )
    assert blocked.status_code == 409, blocked.text
    detail = blocked.json()["detail"]
    if isinstance(detail, dict):
        assert detail.get("code") == "OFFLINE_DEVICE_REVOKED"
        assert detail.get("pending_queue", {}).get("pending_total", 0) >= 1
    else:
        assert "revoked" in str(detail).lower()


def test_settings_revoke_pending_ui_r1():
    company = (ROOT / "frontend/app/company/page.tsx").read_text(encoding="utf-8")
    assert "pending_queue" in company
    assert "retained" in company.lower() or "not auto-applied" in company.lower()
    api = (ROOT / "backend/app/api.py").read_text(encoding="utf-8")
    assert "pending_queue" in api
    engine = (ROOT / "backend/app/sync_engine.py").read_text(encoding="utf-8")
    assert "device_pending_queue_stats" in engine
    assert "OFFLINE_DEVICE_REVOKED" in engine
