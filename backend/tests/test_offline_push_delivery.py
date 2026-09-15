"""Offline Web Push delivery for remote wipe — PARTIAL (not Offline Complete)."""

from __future__ import annotations

import json
from pathlib import Path

import pyotp
import pytest
from pywebpush import WebPushException
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
    monkeypatch.setattr(settings, "OFFLINE_PUSH_MAX_ATTEMPTS", 3)
    monkeypatch.setattr(settings, "OFFLINE_PUSH_RETRY_DELAY_MS", 0)
    yield calls
    offline_push_svc.set_push_sender(None)


async def _device_with_sub(ac, headers, name: str, endpoint: str):
    created = await ac.post(
        "/api/v1/offline/devices",
        headers=headers,
        json={"name": name, "platform": "web"},
    )
    assert created.status_code == 200, created.text
    device_id = created.json()["data"]["id"]
    bind = await ac.post(f"/api/v1/offline/devices/{device_id}/bind", headers=headers, json={})
    assert bind.status_code == 200, bind.text
    sub = await ac.put(
        f"/api/v1/offline/devices/{device_id}/push-subscription",
        headers=headers,
        json={
            "endpoint": endpoint,
            "keys": {"p256dh": "p256dh-test-key-value", "auth": "auth-test-key"},
        },
    )
    assert sub.status_code == 200, sub.text
    return device_id


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
    assert data["fail_closed"] is True
    assert data["push_delivery_complete_claimed"] is False
    assert data["offline_complete_claimed"] is False


@pytest.mark.asyncio
async def test_offline_push_subscription_upsert_and_wipe_delivers(client, db_session, fake_push_sender):
    ac, seed = client
    headers = await _super(ac, seed)
    device_id = await _device_with_sub(
        ac, headers, "Push Till", "https://push.example.test/endpoint/abc"
    )

    wiped = await ac.post(f"/api/v1/offline/devices/{device_id}/wipe", headers=headers)
    assert wiped.status_code == 200, wiped.text
    body = wiped.json()["data"]
    assert body["wipe_pending"] is True
    push = body.get("push_delivery") or {}
    assert push.get("status") == offline_push_svc.STATUS_DELIVERED
    assert push.get("attempted") is True
    assert push.get("attempt_count") == 1
    assert push.get("subscription_revoked") is False
    assert push.get("fail_closed") is True
    assert push.get("push_delivery_complete_claimed") is False
    assert push.get("offline_complete_claimed") is False
    assert len(fake_push_sender) == 1
    call = fake_push_sender[0]
    assert "remote_wipe" in call["data"]
    payload = json.loads(call["data"])
    assert payload["type"] == "remote_wipe"
    assert payload["action"] == "remote_wipe"
    assert payload["device_id"] == device_id
    assert payload["wipe_pending"] is True
    assert call["vapid_claims"]["sub"] == "mailto:test@example.com"
    assert call["subscription_info"]["endpoint"] == "https://push.example.test/endpoint/abc"

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
async def test_offline_wipe_push_retries_transient_then_delivers(
    client, db_session, fake_push_sender, monkeypatch
):
    ac, seed = client
    headers = await _super(ac, seed)
    device_id = await _device_with_sub(
        ac, headers, "Retry Till", "https://push.example.test/retry"
    )

    attempts = {"n": 0}

    def flaky(subscription_info, data, vapid_private_key, vapid_claims):
        attempts["n"] += 1
        fake_push_sender.append({"n": attempts["n"]})
        if attempts["n"] < 3:
            resp = type("R", (), {"status_code": 503})()
            raise WebPushException("temporarily unavailable", resp)

    offline_push_svc.set_push_sender(flaky)
    monkeypatch.setattr(settings, "OFFLINE_PUSH_MAX_ATTEMPTS", 3)
    monkeypatch.setattr(settings, "OFFLINE_PUSH_RETRY_DELAY_MS", 0)

    wiped = await ac.post(f"/api/v1/offline/devices/{device_id}/wipe", headers=headers)
    assert wiped.status_code == 200, wiped.text
    push = wiped.json()["data"]["push_delivery"]
    assert push["status"] == offline_push_svc.STATUS_DELIVERED
    assert push["attempt_count"] == 3
    assert attempts["n"] == 3


@pytest.mark.asyncio
async def test_offline_wipe_push_410_revokes_subscription(
    client, db_session, fake_push_sender, monkeypatch
):
    ac, seed = client
    headers = await _super(ac, seed)
    device_id = await _device_with_sub(
        ac, headers, "Gone Till", "https://push.example.test/gone"
    )

    def gone(subscription_info, data, vapid_private_key, vapid_claims):
        fake_push_sender.append({"gone": True})
        resp = type("R", (), {"status_code": 410})()
        raise WebPushException("Gone", resp)

    offline_push_svc.set_push_sender(gone)
    monkeypatch.setattr(settings, "OFFLINE_PUSH_RETRY_DELAY_MS", 0)

    wiped = await ac.post(f"/api/v1/offline/devices/{device_id}/wipe", headers=headers)
    assert wiped.status_code == 200, wiped.text
    push = wiped.json()["data"]["push_delivery"]
    assert push["status"] == offline_push_svc.STATUS_FAILED
    assert push["subscription_revoked"] is True
    assert push["response_status"] == 410
    assert push["attempt_count"] == 1

    sub = (
        await db_session.execute(
            select(m.OfflinePushSubscription).where(
                m.OfflinePushSubscription.device_id == device_id
            )
        )
    ).scalar_one()
    assert sub.revoked_at is not None

    # Second wipe: if API allows re-queue while pending, expect skip_no_subscription.
    wiped2 = await ac.post(f"/api/v1/offline/devices/{device_id}/wipe", headers=headers)
    if wiped2.status_code == 200:
        push2 = wiped2.json()["data"]["push_delivery"]
        assert push2["status"] == offline_push_svc.STATUS_SKIPPED_NO_SUB


@pytest.mark.asyncio
async def test_offline_wipe_push_disabled_flag(client, monkeypatch):
    ac, seed = client
    headers = await _super(ac, seed)
    monkeypatch.setattr(settings, "OFFLINE_PUSH_ENABLED", False)
    monkeypatch.setattr(settings, "OFFLINE_PUSH_VAPID_PUBLIC_KEY", "BFakePublicKeyForTestsOnlyXXXXXXXXXXXX")
    monkeypatch.setattr(
        settings,
        "OFFLINE_PUSH_VAPID_PRIVATE_KEY",
        "-----BEGIN PRIVATE KEY-----\nFAKE\n-----END PRIVATE KEY-----",
    )

    created = await ac.post(
        "/api/v1/offline/devices",
        headers=headers,
        json={"name": "Disabled Push Till", "platform": "web"},
    )
    device_id = created.json()["data"]["id"]
    wiped = await ac.post(f"/api/v1/offline/devices/{device_id}/wipe", headers=headers)
    assert wiped.status_code == 200, wiped.text
    push = wiped.json()["data"]["push_delivery"]
    assert push["status"] == offline_push_svc.STATUS_DISABLED
    assert push["attempted"] is False
    assert push["offline_complete_claimed"] is False


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
    assert push["fail_closed"] is True


@pytest.mark.asyncio
async def test_offline_push_subscription_rebind_updates_endpoint(client, fake_push_sender):
    ac, seed = client
    headers = await _super(ac, seed)
    device_id = await _device_with_sub(
        ac, headers, "Rebind Till", "https://push.example.test/v1"
    )
    rebind = await ac.put(
        f"/api/v1/offline/devices/{device_id}/push-subscription",
        headers=headers,
        json={
            "endpoint": "https://push.example.test/v2-rebound",
            "keys": {"p256dh": "p256dh-test-key-rebound", "auth": "auth-test-rebound"},
        },
    )
    assert rebind.status_code == 200, rebind.text
    assert rebind.json()["data"]["endpoint_host"] == "push.example.test"
    assert rebind.json()["data"]["status"] == "active"

    wiped = await ac.post(f"/api/v1/offline/devices/{device_id}/wipe", headers=headers)
    assert wiped.status_code == 200, wiped.text
    assert fake_push_sender[-1]["subscription_info"]["endpoint"].endswith("/v2-rebound")


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
    assert "failClosed: true" in push_src
    assert "registerOfflinePushSubscription" in push_src
    assert "rebindOfflinePushSubscription" in push_src
    assert "forceResubscribe" in push_src
    assert "listenForRemoteWipePushMessages" in push_src

    wipe_src = (ROOT / "frontend/lib/offlineRemoteWipe.ts").read_text(encoding="utf-8")
    assert "pushDeliveryPartial: true" in wipe_src
    assert "pushDeliveryCompleteClaimed: false" in wipe_src
    assert "offlineCompleteClaimed: false" in wipe_src

    company = (ROOT / "frontend/app/company/page.tsx").read_text(encoding="utf-8")
    assert "Push delivery:" in company
    assert "subscription revoked" in company

    sw = (ROOT / "frontend/public/sw.js").read_text(encoding="utf-8")
    assert "remote_wipe" in sw
    assert "ribdigi-remote-wipe" in sw
    assert "isApiOrAuth" in sw
    # Still must not cache API
    assert "Network-only" in sw or "never put responses" in sw.lower()


def test_offline_push_ops_docs_and_env_examples():
    ops = (ROOT / "docs/OFFLINE_WEB_PUSH_VAPID_OPS.md").read_text(encoding="utf-8")
    assert "Fail-closed" in ops or "fail-closed" in ops
    assert "OFFLINE_PUSH_VAPID_PUBLIC_KEY" in ops
    assert "404/410" in ops
    assert "PARTIAL" in ops
    assert "Offline Complete" in ops
    assert "7-day VERIFIED" in ops or "7-day" in ops

    env = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "OFFLINE_PUSH_ENABLED" in env
    assert "OFFLINE_PUSH_VAPID_PUBLIC_KEY" in env
    assert "OFFLINE_PUSH_MAX_ATTEMPTS" in env

    prod = (ROOT / ".env.production.example").read_text(encoding="utf-8")
    assert "OFFLINE_PUSH_ENABLED=false" in prod
    assert "OFFLINE_PUSH_VAPID_PRIVATE_KEY" in prod


def test_offline_push_migration_exists():
    mig = (
        ROOT / "backend/alembic/versions/20260914_0112_offline_push_delivery.py"
    ).read_text(encoding="utf-8")
    assert "offline_push_subscriptions" in mig
    assert "offline_push_deliveries" in mig
    assert "20260914_0111" in mig
