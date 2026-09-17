"""Offline wipe poll-path automated evidence (engineering-ready; Completes MISSING).

When Web Push / FCM is unavailable (Cloud Agent Chrome, fail-closed VAPID, no
subscription), remote wipe still works via:

  POST wipe → soft lockdown + wipe_pending
  GET device (poll) → wipe_pending true
  POST wipe/ack → wipe_status acked

This suite proves that **poll path** without any push subscription or VAPID
enablement. It does **not** claim:

- Offline Complete
- push-delivery Complete
- 7-day VERIFIED

Operator physical matrix + real-browser push proof remain separate gates.
See ``docs/OFFLINE_WIPE_POLL_LOCAL_ALTERNATIVE.md``.
"""

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
def push_fail_closed(monkeypatch):
    """Simulate Cloud Agent / prod-template: push disabled, no VAPID."""
    monkeypatch.setattr(settings, "OFFLINE_PUSH_ENABLED", False)
    monkeypatch.setattr(settings, "OFFLINE_PUSH_VAPID_PUBLIC_KEY", "")
    monkeypatch.setattr(settings, "OFFLINE_PUSH_VAPID_PRIVATE_KEY", "")
    return None


def test_poll_alternative_docs_and_honesty_labels_present():
    alt = (ROOT / "docs/OFFLINE_WIPE_POLL_LOCAL_ALTERNATIVE.md").read_text(encoding="utf-8")
    assert "engineering-ready" in alt.lower() or "Engineering-ready" in alt
    assert "Offline Complete" in alt
    assert "7-day VERIFIED" in alt or "7-day" in alt
    assert "MISSING" in alt
    assert "poll" in alt.lower()
    assert "FCM" in alt or "PushManager" in alt

    seven = (ROOT / "docs/OFFLINE_7DAY_EVIDENCE_TEMPLATE.md").read_text(encoding="utf-8")
    assert "7-day VERIFIED" in seven
    assert "MISSING" in seven
    assert "Day 0" in seven or "Day-0" in seven
    assert "Pass/Fail" in seven or "Pass / Fail" in seven

    attestation = (ROOT / "docs/OFFLINE_COMPLETE_ATTESTATION.md").read_text(encoding="utf-8")
    assert "offline_complete_claimed" in attestation.lower() or "Offline Complete" in attestation
    assert "MISSING" in attestation


@pytest.mark.asyncio
async def test_wipe_poll_path_without_push_subscription(client, db_session, push_fail_closed):
    """Core poll-path evidence: wipe → GET pending → ack, push honestly skipped."""
    ac, seed = client
    headers = await _super(ac, seed)

    assert offline_push_svc.push_enabled() is False
    assert offline_push_svc.push_configured() is False

    created = await ac.post(
        "/api/v1/offline/devices",
        headers=headers,
        json={"name": "Poll Path Till", "platform": "web"},
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
    assert "Offline Complete" in (body.get("message") or "") or "deferred" in (
        body.get("message") or ""
    ).lower()

    push = body.get("push_delivery") or {}
    assert push.get("status") in {
        offline_push_svc.STATUS_DISABLED,
        offline_push_svc.STATUS_SKIPPED_UNCONFIGURED,
    }
    assert push.get("attempted") is False
    assert push.get("push_delivery_complete_claimed") is False
    assert push.get("offline_complete_claimed") is False

    # Poll surface (same as Shell / company client GET)
    polled = await ac.get(f"/api/v1/offline/devices/{device_id}", headers=headers)
    assert polled.status_code == 200, polled.text
    pdata = polled.json()["data"]
    assert pdata["wipe_pending"] is True
    assert pdata["wipe_status"] == "pending"
    assert pdata["status"] == "revoked"

    # Client would clear IndexedDB here; API ack is the server-side completion signal.
    acked = await ac.post(f"/api/v1/offline/devices/{device_id}/wipe/ack", headers=headers)
    assert acked.status_code == 200, acked.text
    abody = acked.json()["data"]
    assert abody.get("wipe_pending") is False
    assert abody.get("wipe_status") == "acked"

    row = (
        await db_session.execute(select(m.OfflineDevice).where(m.OfflineDevice.id == device_id))
    ).scalar_one()
    assert row.wipe_status == "acked"
    assert row.wipe_acked_at is not None
    assert row.revoked_at is not None

    # No active push subscription was required for poll-path completion.
    sub = await offline_push_svc.get_active_subscription(db_session, row.tenant_id, device_id)
    assert sub is None


@pytest.mark.asyncio
async def test_wipe_poll_path_honesty_never_claims_completes(client, push_fail_closed):
    ac, seed = client
    headers = await _super(ac, seed)

    created = await ac.post(
        "/api/v1/offline/devices",
        headers=headers,
        json={"name": "Honesty Till", "platform": "web"},
    )
    device_id = created.json()["data"]["id"]
    await ac.post(f"/api/v1/offline/devices/{device_id}/bind", headers=headers, json={})
    wiped = await ac.post(f"/api/v1/offline/devices/{device_id}/wipe", headers=headers)
    body = wiped.json()["data"]
    push = body["push_delivery"]
    assert push["push_delivery_complete_claimed"] is False
    assert push["offline_complete_claimed"] is False
    msg = (body.get("message") or "") + (push.get("message") or "")
    assert "Complete" in msg or "deferred" in msg.lower() or "PARTIAL" in msg

    vapid = await ac.get("/api/v1/offline/push/vapid-public-key", headers=headers)
    assert vapid.status_code == 200, vapid.text
    vdata = vapid.json()["data"]
    assert vdata["enabled"] is False
    assert vdata["push_delivery_complete_claimed"] is False
    assert vdata["offline_complete_claimed"] is False
