"""Offline remote IndexedDB wipe scaffold — Offline Complete still MISSING."""

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
async def test_offline_remote_wipe_request_and_ack(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)

    created = await ac.post(
        "/api/v1/offline/devices",
        headers=headers,
        json={"name": "Wipe Till", "platform": "web"},
    )
    assert created.status_code == 200, created.text
    device_id = created.json()["data"]["id"]

    bind = await ac.post(f"/api/v1/offline/devices/{device_id}/bind", headers=headers, json={})
    assert bind.status_code == 200, bind.text

    wiped = await ac.post(f"/api/v1/offline/devices/{device_id}/wipe", headers=headers)
    assert wiped.status_code == 200, wiped.text
    body = wiped.json()["data"]
    assert body["status"] == "revoked"
    assert body.get("soft_lockdown") is True
    assert body.get("wipe_pending") is True
    assert body.get("wipe_status") == "pending"
    assert "Offline Complete" in body.get("message", "") or "deferred" in body.get("message", "")

    row = (
        await db_session.execute(select(m.OfflineDevice).where(m.OfflineDevice.id == device_id))
    ).scalar_one()
    assert row.wipe_status == "pending"
    assert row.wipe_requested_at is not None
    assert row.revoked_at is not None

    got = await ac.get(f"/api/v1/offline/devices/{device_id}", headers=headers)
    assert got.status_code == 200, got.text
    assert got.json()["data"]["wipe_pending"] is True

    acked = await ac.post(f"/api/v1/offline/devices/{device_id}/wipe/ack", headers=headers)
    assert acked.status_code == 200, acked.text
    abody = acked.json()["data"]
    assert abody.get("wipe_pending") is False
    assert abody.get("wipe_status") == "acked"

    await db_session.refresh(row)
    assert row.wipe_status == "acked"
    assert row.wipe_acked_at is not None

    # Second ack fails — no pending wipe
    again = await ac.post(f"/api/v1/offline/devices/{device_id}/wipe/ack", headers=headers)
    assert again.status_code == 400, again.text


@pytest.mark.asyncio
async def test_offline_remote_wipe_store_manager_denied(client):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    created = await ac.post(
        "/api/v1/offline/devices",
        headers=await _super(ac, seed),
        json={"name": "Mgr Deny Wipe", "platform": "web"},
    )
    assert created.status_code == 200, created.text
    device_id = created.json()["data"]["id"]

    denied = await ac.post(f"/api/v1/offline/devices/{device_id}/wipe", headers=headers)
    assert denied.status_code == 403, denied.text


def test_offline_remote_wipe_client_scaffold_exists():
    src = (ROOT / "frontend/lib/offlineRemoteWipe.ts").read_text(encoding="utf-8")
    assert "clearOfflineIndexedDatabases" in src
    assert "processPendingRemoteWipeIfNeeded" in src
    assert "offlineCompleteClaimed: false" in src
    assert "pushDelivery: false" in src
    assert "ribdigi-offline-queue" in src


def test_offline_remote_wipe_migration_exists():
    mig = (
        ROOT / "backend/alembic/versions/20260914_0111_offline_remote_wipe.py"
    ).read_text(encoding="utf-8")
    assert "wipe_requested_at" in mig
    assert "wipe_status" in mig
    assert "20260828_0110" in mig
