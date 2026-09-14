"""Offline VAPID wipe-via-push automated evidence (PARTIAL — not Offline Complete).

Strengthens delivery proofs beyond unit skips:

- Generate real VAPID key material via ``py_vapid`` (never commit production keys)
- Subscribe an offline device (PushManager-shaped payload)
- Request remote wipe and assert push send was attempted with the correct
  ``remote_wipe`` JSON payload + VAPID claims
- HTTP 410 Gone revokes the stored subscription; wipe stays pending for poll
- Optional mock of ``pywebpush.webpush`` (default sender path)

Automated evidence ≠ push-delivery Complete / Offline Complete / 7-day VERIFIED.
Operator browser staging remains required — see
``docs/offline_wipe_push_staging_checklist.md``.
"""

from __future__ import annotations

import json
from base64 import urlsafe_b64encode
from pathlib import Path
from typing import Any

import pyotp
import pytest
from cryptography.hazmat.primitives import serialization
from py_vapid import Vapid
from pywebpush import WebPushException
from sqlalchemy import select

from app import models as m
from app import offline_push as offline_push_svc
from app.config import settings
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def _generate_vapid_keypair() -> tuple[str, str]:
    """Fixture-quality VAPID keys for tests only (not production secrets)."""
    v = Vapid()
    v.generate_keys()
    pub = v.public_key.public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    public_b64 = urlsafe_b64encode(pub).decode().rstrip("=")
    pem = v.private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    return public_b64, pem


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.fixture
def vapid_keys():
    return _generate_vapid_keypair()


@pytest.fixture
def configure_vapid(monkeypatch, vapid_keys):
    public_key, private_pem = vapid_keys
    monkeypatch.setattr(settings, "OFFLINE_PUSH_ENABLED", True)
    monkeypatch.setattr(settings, "OFFLINE_PUSH_VAPID_PUBLIC_KEY", public_key)
    monkeypatch.setattr(settings, "OFFLINE_PUSH_VAPID_PRIVATE_KEY", private_pem)
    monkeypatch.setattr(settings, "OFFLINE_PUSH_VAPID_SUBJECT", "mailto:evidence@example.com")
    monkeypatch.setattr(settings, "OFFLINE_PUSH_MAX_ATTEMPTS", 3)
    monkeypatch.setattr(settings, "OFFLINE_PUSH_RETRY_DELAY_MS", 0)
    return {"public_key": public_key, "private_pem": private_pem}


@pytest.fixture
def mock_push_sender(monkeypatch, configure_vapid):
    """Injectable sender capturing args (no network)."""
    calls: list[dict[str, Any]] = []

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
    yield calls
    offline_push_svc.set_push_sender(None)


async def _subscribe_device(ac, headers, *, name: str, endpoint: str) -> str:
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
            "keys": {
                "p256dh": "BNcRzejnsEWBP3McYkgI5kKFyX7tY69IwU8b87h5y5k",
                "auth": "tBHItJI5svbpez7KI0CCXg",
            },
        },
    )
    assert sub.status_code == 200, sub.text
    assert sub.json()["data"]["status"] == "active"
    return device_id


def _assert_remote_wipe_payload(data_str: str, *, device_id: str) -> dict:
    payload = json.loads(data_str)
    assert payload["type"] == offline_push_svc.EVENT_REMOTE_WIPE
    assert payload["action"] == offline_push_svc.EVENT_REMOTE_WIPE
    assert payload["device_id"] == device_id
    assert payload["wipe_pending"] is True
    assert "Offline Complete" in payload["message"] or "deferred" in payload["message"].lower()
    return payload


def test_evidence_fail_closed_defaults_ops_enable(monkeypatch):
    """Prod example stays fail-closed; empty VAPID keys keep push disabled."""
    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "OFFLINE_PUSH_ENABLED" in example
    assert "OFFLINE_PUSH_VAPID_PUBLIC_KEY" in example

    prod = (ROOT / ".env.production.example").read_text(encoding="utf-8")
    assert "OFFLINE_PUSH_ENABLED=false" in prod
    assert "OFFLINE_PUSH_VAPID_PUBLIC_KEY" in prod
    assert "OFFLINE_PUSH_VAPID_PRIVATE_KEY" in prod

    # Even if ENABLED=true, missing keys → not push_enabled (fail-closed).
    monkeypatch.setattr(settings, "OFFLINE_PUSH_ENABLED", True)
    monkeypatch.setattr(settings, "OFFLINE_PUSH_VAPID_PUBLIC_KEY", "")
    monkeypatch.setattr(settings, "OFFLINE_PUSH_VAPID_PRIVATE_KEY", "")
    assert offline_push_svc.push_configured() is False
    assert offline_push_svc.push_enabled() is False

    # Evidence suite must not flip production template to enabled.
    assert "OFFLINE_PUSH_ENABLED=true" not in prod


def test_evidence_honesty_helpers_never_claim_complete(configure_vapid):
    payload = offline_push_svc.vapid_public_key_payload()
    assert payload["configured"] is True
    assert payload["enabled"] is True
    assert payload["fail_closed"] is True
    assert payload["push_delivery_partial"] is True
    assert payload["push_delivery_complete_claimed"] is False
    assert payload["offline_complete_claimed"] is False
    assert payload["public_key"]
    assert "PARTIAL" in payload["message"] or "deferred" in payload["message"].lower()


def test_evidence_staging_checklist_and_ops_docs_present():
    checklist = (ROOT / "docs/offline_wipe_push_staging_checklist.md").read_text(
        encoding="utf-8"
    )
    assert "PARTIAL" in checklist
    assert "Offline Complete" in checklist
    assert "7-day VERIFIED" in checklist or "7-day" in checklist
    assert "OFFLINE_PUSH_ENABLED" in checklist
    assert "VAPID" in checklist
    assert "Bind browser" in checklist or "push-subscription" in checklist
    assert "410" in checklist
    assert "Cannot mark Complete" in checklist or "cannot mark Complete" in checklist.lower()

    ops = (ROOT / "docs/OFFLINE_WEB_PUSH_VAPID_OPS.md").read_text(encoding="utf-8")
    assert "offline_wipe_push_staging_checklist.md" in ops
    assert "PARTIAL" in ops
    assert "Fail-closed" in ops or "fail-closed" in ops


@pytest.mark.asyncio
async def test_evidence_vapid_public_endpoint_with_generated_keys(
    client, configure_vapid, vapid_keys
):
    ac, seed = client
    headers = await _super(ac, seed)
    public_key, _ = vapid_keys

    r = await ac.get("/api/v1/offline/push/vapid-public-key", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["configured"] is True
    assert data["enabled"] is True
    assert data["public_key"] == public_key
    assert data["subject"] == "mailto:evidence@example.com"
    assert data["push_delivery_complete_claimed"] is False
    assert data["offline_complete_claimed"] is False
    # Never leak private key material
    assert "BEGIN PRIVATE KEY" not in r.text
    assert "PRIVATE KEY" not in r.text


@pytest.mark.asyncio
async def test_evidence_subscribe_wipe_asserts_payload_and_vapid_claims(
    client, db_session, mock_push_sender, configure_vapid, vapid_keys
):
    """Core automated evidence: subscribe → wipe → push attempted with correct payload."""
    ac, seed = client
    headers = await _super(ac, seed)
    endpoint = "https://fcm.googleapis.com/fcm/send/evidence-endpoint-1"
    device_id = await _subscribe_device(
        ac, headers, name="Evidence Till", endpoint=endpoint
    )
    _, private_pem = vapid_keys

    wiped = await ac.post(f"/api/v1/offline/devices/{device_id}/wipe", headers=headers)
    assert wiped.status_code == 200, wiped.text
    body = wiped.json()["data"]
    assert body["wipe_pending"] is True
    assert body["wipe_status"] == "pending"
    assert body.get("soft_lockdown") is True

    push = body["push_delivery"]
    assert push["status"] == offline_push_svc.STATUS_DELIVERED
    assert push["attempted"] is True
    assert push["attempt_count"] == 1
    assert push["subscription_revoked"] is False
    assert push["event_type"] == offline_push_svc.EVENT_REMOTE_WIPE
    assert push["push_delivery_partial"] is True
    assert push["push_delivery_complete_claimed"] is False
    assert push["offline_complete_claimed"] is False
    assert push["fail_closed"] is True

    assert len(mock_push_sender) == 1
    call = mock_push_sender[0]
    assert call["subscription_info"]["endpoint"] == endpoint
    assert call["subscription_info"]["keys"]["p256dh"]
    assert call["subscription_info"]["keys"]["auth"]
    assert call["vapid_private_key"].strip() == private_pem.strip()
    assert "BEGIN PRIVATE KEY" in call["vapid_private_key"]
    assert call["vapid_claims"]["sub"] == "mailto:evidence@example.com"
    _assert_remote_wipe_payload(call["data"], device_id=device_id)

    row = (
        await db_session.execute(
            select(m.OfflinePushDelivery).where(
                m.OfflinePushDelivery.device_id == device_id,
                m.OfflinePushDelivery.event_type == offline_push_svc.EVENT_REMOTE_WIPE,
            )
        )
    ).scalar_one()
    assert row.status == "delivered"
    assert row.delivered_at is not None
    assert row.payload["type"] == "remote_wipe"
    assert row.payload["device_id"] == device_id
    assert row.payload["wipe_pending"] is True


@pytest.mark.asyncio
async def test_evidence_410_revokes_subscription_wipe_stays_pending(
    client, db_session, configure_vapid, monkeypatch
):
    ac, seed = client
    headers = await _super(ac, seed)
    device_id = await _subscribe_device(
        ac,
        headers,
        name="Gone Evidence Till",
        endpoint="https://push.example.test/gone-evidence",
    )

    def gone(subscription_info, data, vapid_private_key, vapid_claims):
        resp = type("R", (), {"status_code": 410})()
        raise WebPushException("Gone — subscription expired", resp)

    offline_push_svc.set_push_sender(gone)
    monkeypatch.setattr(settings, "OFFLINE_PUSH_RETRY_DELAY_MS", 0)
    try:
        wiped = await ac.post(f"/api/v1/offline/devices/{device_id}/wipe", headers=headers)
    finally:
        offline_push_svc.set_push_sender(None)

    assert wiped.status_code == 200, wiped.text
    body = wiped.json()["data"]
    assert body["wipe_pending"] is True
    push = body["push_delivery"]
    assert push["status"] == offline_push_svc.STATUS_FAILED
    assert push["attempted"] is True
    assert push["subscription_revoked"] is True
    assert push["response_status"] == 410
    assert push["offline_complete_claimed"] is False

    sub = (
        await db_session.execute(
            select(m.OfflinePushSubscription).where(
                m.OfflinePushSubscription.device_id == device_id
            )
        )
    ).scalar_one()
    assert sub.revoked_at is not None

    device = (
        await db_session.execute(
            select(m.OfflineDevice).where(m.OfflineDevice.id == device_id)
        )
    ).scalar_one()
    assert device.wipe_status == "pending"
    assert device.wipe_requested_at is not None


@pytest.mark.asyncio
async def test_evidence_mock_pywebpush_backend_default_sender(
    client, configure_vapid, vapid_keys, monkeypatch
):
    """Exercise default ``_default_webpush_send`` via mocked ``pywebpush.webpush``."""
    ac, seed = client
    headers = await _super(ac, seed)
    device_id = await _subscribe_device(
        ac,
        headers,
        name="Pywebpush Mock Till",
        endpoint="https://push.example.test/pywebpush-mock",
    )
    _, private_pem = vapid_keys
    calls: list[dict[str, Any]] = []

    def fake_webpush(*, subscription_info, data, vapid_private_key, vapid_claims):
        calls.append(
            {
                "subscription_info": subscription_info,
                "data": data,
                "vapid_private_key": vapid_private_key,
                "vapid_claims": vapid_claims,
            }
        )
        return type("Resp", (), {"status_code": 201})()

    # Ensure default sender path (no injectable override).
    offline_push_svc.set_push_sender(None)
    monkeypatch.setattr("pywebpush.webpush", fake_webpush)

    wiped = await ac.post(f"/api/v1/offline/devices/{device_id}/wipe", headers=headers)
    assert wiped.status_code == 200, wiped.text
    push = wiped.json()["data"]["push_delivery"]
    assert push["status"] == offline_push_svc.STATUS_DELIVERED
    assert push["attempted"] is True
    assert len(calls) == 1
    assert calls[0]["vapid_private_key"].strip() == private_pem.strip()
    assert "BEGIN PRIVATE KEY" in calls[0]["vapid_private_key"]
    assert calls[0]["vapid_claims"]["sub"] == "mailto:evidence@example.com"
    _assert_remote_wipe_payload(calls[0]["data"], device_id=device_id)


@pytest.mark.asyncio
async def test_evidence_wipe_ack_after_delivered_push(
    client, mock_push_sender, configure_vapid
):
    """Push delivered is not wipe completion — ack still required."""
    ac, seed = client
    headers = await _super(ac, seed)
    device_id = await _subscribe_device(
        ac,
        headers,
        name="Ack Evidence Till",
        endpoint="https://push.example.test/ack-evidence",
    )

    wiped = await ac.post(f"/api/v1/offline/devices/{device_id}/wipe", headers=headers)
    assert wiped.status_code == 200, wiped.text
    assert wiped.json()["data"]["push_delivery"]["status"] == "delivered"
    assert wiped.json()["data"]["wipe_pending"] is True

    acked = await ac.post(f"/api/v1/offline/devices/{device_id}/wipe/ack", headers=headers)
    assert acked.status_code == 200, acked.text
    abody = acked.json()["data"]
    assert abody["wipe_pending"] is False
    assert abody["wipe_status"] == "acked"
    assert len(mock_push_sender) == 1


def test_evidence_sw_and_client_contracts_for_payload():
    """SW must handle the same remote_wipe payload shape the server sends."""
    sw = (ROOT / "frontend/public/sw.js").read_text(encoding="utf-8")
    assert "addEventListener('push'" in sw or 'addEventListener("push"' in sw
    assert "remote_wipe" in sw
    assert "ribdigi-remote-wipe" in sw

    push_src = (ROOT / "frontend/lib/offlinePush.ts").read_text(encoding="utf-8")
    assert "pushDeliveryCompleteClaimed: false" in push_src
    assert "offlineCompleteClaimed: false" in push_src

    wipe_src = (ROOT / "frontend/lib/offlineRemoteWipe.ts").read_text(encoding="utf-8")
    assert "pushDeliveryPartial: true" in wipe_src
    assert "pushDeliveryCompleteClaimed: false" in wipe_src
    assert "offlineCompleteClaimed: false" in wipe_src
