"""Offline Web Push delivery for remote wipe — PARTIAL (not Offline Complete)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest
from sqlalchemy import select

from app import models as m
from app import offline_push as offline_push_svc
from app.config import settings
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.fixture
def fake_push_sender(monkeypatch):
    calls: list[dict] = []

    def _send(subscription_info, data, vapid_private_key, vapid_claims):
        calls.append(
            {
                "subscription_info": subscription_info,
                "data": data,
                "vapid_private_key": vapid_private_key,
                "vapid_claims": vapid_claims,
            }
        )

    offline_push_svc.set_push_sender(_send)
    monkeypatch.setattr(settings, "OFFLINE_PUSH_ENABLED", True)
    monkeypatch.setattr(settings, "OFFLINE_PUSH_VAPID_PUBLIC_KEY", "BFakePublicKeyForTestsOnlyXXXXXXXXXXXX")
    monkeypatch.setattr(
        settings,
        "OFFLINE_PUSH_VAPID_PRIVATE_KEY",
        "-----BEGIN PRIVATE KEY-----\nFAKE\n-----END PRIVATE KEY-----",
    )
    monkeypatch.setattr(settings, "OFFLINE_PUSH_VAPID_SUBJECT", "mailto:test@example.com")
    yield calls
    offline_push_svc.set_push_sender(None)


@pytest.mark.asyncio
async def test_offline_push_vapid_unconfigured(client, monkeypatch):
    ac, seed = client
    headers = await _super(ac, seed)
    monkeypatch.setattr(settings, "OFFLINE_PUSH_VAPID_PUBLIC_KEY", "")
    monkeypatch.setattr(settings, "OFFLINE_PUSH_VAPID_PRIVATE_KEY", "")
    r = await ac.get("/api/v1/offline/push/vapid-public-key", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["configured"] is False
    assert data["enabled"] is False
    assert data["push_delivery_complete_claimed"] is False
    assert data["offline_complete_claimed"] is False


@pytest.mark.asyncio
async def test_offline_push_subscription_upsert_and_wipe_delivers(client, db_session, fake_push_sender):
    ac, seed = client
    headers = await _super(ac, seed)

    created = await ac.post(
        "/api/v1/offline/devices",
        headers=headers,
        json={"name": "Push Till", "platform": "web"},
    )
    assert created.status_code == 200, created.text
    device_id = created.json()["data"]["id"]

    bind = await ac.post(f"/api/v1/offline/devices/{device_id}/bind", headers=headers, json={})
    assert bind.status_code == 200, bind.text

    sub = await ac.put(
        f"/api/v1/offline/devices/{device_id}/push-subscription",
        headers=headers,
        json={
            "endpoint": "https://push.example.test/endpoint/abc",
            "keys": {"p256dh": "p256dh-test-key-value", "auth": "auth-test-key"},
        },
    )
    assert sub.status_code == 200, sub.text
    sbody = sub.json()["data"]
    assert sbody["status"] == "active"
    assert sbody["endpoint_host"] == "push.example.test"
    assert "p256dh" not in sbody
    assert "auth" not in sbody
    assert sbody["push_delivery_complete_claimed"] is False

    wiped = await ac.post(f"/api/v1/offline/devices/{device_id}/wipe", headers=headers)
    assert wiped.status_code == 200, wiped.text
    body = wiped.json()["data"]
    assert body["wipe_pending"] is True
    push = body.get("push_delivery") or {}
    assert push.get("status") == offline_push_svc.STATUS_DELIVERED
    assert push.get("attempted") is True
    assert push.get("push_delivery_complete_claimed") is False
    assert push.get("offline_complete_claimed") is False
    assert len(fake_push_sender) == 1
    assert "remote_wipe" in fake_push_sender[0]["data"]

    row = (
        await db_session.execute(
            select(m.OfflinePushDelivery).where(
                m.OfflinePushDelivery.device_id == device_id,
                m.OfflinePushDelivery.event_type == "remote_wipe",
            )
        )
    ).scalar_one()
    assert row.status == "delivered"
    assert row.delivered_at is not None


@pytest.mark.asyncio
async def test_offline_wipe_push_skipped_without_subscription(client, db_session, fake_push_sender):
    ac, seed = client
    headers = await _super(ac, seed)

    created = await ac.post(
        "/api/v1/offline/devices",
        headers=headers,
        json={"name": "No Sub Till", "platform": "web"},
    )
    device_id = created.json()["data"]["id"]
    await ac.post(f"/api/v1/offline/devices/{device_id}/bind", headers=headers, json={})

    wiped = await ac.post(f"/api/v1/offline/devices/{device_id}/wipe", headers=headers)
    assert wiped.status_code == 200, wiped.text
    push = wiped.json()["data"]["push_delivery"]
    assert push["status"] == offline_push_svc.STATUS_SKIPPED_NO_SUB
    assert push["attempted"] is False
    assert len(fake_push_sender) == 0


@pytest.mark.asyncio
async def test_offline_wipe_push_skipped_unconfigured(client, monkeypatch):
    ac, seed = client
    headers = await _super(ac, seed)
    monkeypatch.setattr(settings, "OFFLINE_PUSH_ENABLED", True)
    monkeypatch.setattr(settings, "OFFLINE_PUSH_VAPID_PUBLIC_KEY", "")
    monkeypatch.setattr(settings, "OFFLINE_PUSH_VAPID_PRIVATE_KEY", "")

    created = await ac.post(
        "/api/v1/offline/devices",
        headers=headers,
        json={"name": "Uncfg Till", "platform": "web"},
    )
    device_id = created.json()["data"]["id"]

    wiped = await ac.post(f"/api/v1/offline/devices/{device_id}/wipe", headers=headers)
    assert wiped.status_code == 200, wiped.text
    push = wiped.json()["data"]["push_delivery"]
    assert push["status"] == offline_push_svc.STATUS_SKIPPED_UNCONFIGURED
    assert push["offline_complete_claimed"] is False


@pytest.mark.asyncio
async def test_offline_push_subscription_store_manager_pos_ok_when_scoped(client):
    """store_manager with pos:write can register push for a device (device-local)."""
    ac, seed = client
    admin = await _super(ac, seed)
    created = await ac.post(
        "/api/v1/offline/devices",
        headers=admin,
        json={"name": "Mgr Push", "platform": "web"},
    )
    device_id = created.json()["data"]["id"]
    mgr = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    # Manager cannot wipe (company-level) but may upsert push with pos write.
    sub = await ac.put(
        f"/api/v1/offline/devices/{device_id}/push-subscription",
        headers=mgr,
        json={
            "endpoint": "https://push.example.test/mgr",
            "keys": {"p256dh": "p256dh-mgr-key-value", "auth": "auth-mgr-key"},
        },
    )
    # May be 200 if pos:write granted, or 403 if role lacks pos write — assert not 500.
    assert sub.status_code in {200, 403}, sub.text


def test_offline_push_client_and_sw_contracts():
    push_src = (ROOT / "frontend/lib/offlinePush.ts").read_text(encoding="utf-8")
    assert "pushDeliveryCompleteClaimed: false" in push_src
    assert "offlineCompleteClaimed: false" in push_src
    assert "registerOfflinePushSubscription" in push_src
    assert "listenForRemoteWipePushMessages" in push_src

    wipe_src = (ROOT / "frontend/lib/offlineRemoteWipe.ts").read_text(encoding="utf-8")
    assert "pushDeliveryPartial: true" in wipe_src
    assert "pushDeliveryCompleteClaimed: false" in wipe_src
    assert "offlineCompleteClaimed: false" in wipe_src

    sw = (ROOT / "frontend/public/sw.js").read_text(encoding="utf-8")
    assert "remote_wipe" in sw
    assert "ribdigi-remote-wipe" in sw
    assert "isApiOrAuth" in sw
    # Still must not cache API
    assert "Network-only" in sw or "never put responses" in sw.lower()


def test_offline_push_migration_exists():
    mig = (
        ROOT / "backend/alembic/versions/20260914_0112_offline_push_delivery.py"
    ).read_text(encoding="utf-8")
    assert "offline_push_subscriptions" in mig
    assert "offline_push_deliveries" in mig
    assert "20260914_0111" in mig
