"""Offline owner alerts API + soft-lockdown / email notify tests."""

from __future__ import annotations

from datetime import datetime, timedelta

import pyotp
import pytest
from sqlalchemy import select

from app import emailer
from app import models as m
from app.notifications import DEFAULT_PREFERENCES
from tests.conftest import auth_headers


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


def test_security_email_default_on_for_offline_alerts():
    assert DEFAULT_PREFERENCES["security"]["email"] is True


@pytest.mark.asyncio
async def test_offline_alerts_never_bound_device(client):
    ac, seed = client
    headers = await _super(ac, seed)
    created = await ac.post(
        "/api/v1/offline/devices",
        headers=headers,
        json={"name": "Unbound Till", "platform": "web"},
    )
    assert created.status_code == 200
    device_id = created.json()["data"]["id"]

    r = await ac.get("/api/v1/offline/alerts", headers=headers)
    assert r.status_code == 200
    body = r.json()["data"]
    codes = [a["code"] for a in body["alerts"]]
    assert "OFFLINE_DEVICE_NEVER_BOUND" in codes
    bound = [a for a in body["alerts"] if a.get("device_id") == device_id]
    assert any(a["code"] == "OFFLINE_DEVICE_NEVER_BOUND" for a in bound)


@pytest.mark.asyncio
async def test_offline_alerts_expired_envelope(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)
    created = await ac.post(
        "/api/v1/offline/devices",
        headers=headers,
        json={"name": "Expired Till", "platform": "web"},
    )
    device_id = created.json()["data"]["id"]
    bind = await ac.post(f"/api/v1/offline/devices/{device_id}/bind", headers=headers, json={})
    assert bind.status_code == 200

    row = await db_session.get(m.OfflineDevice, device_id)
    row.offline_authorized_until = datetime.utcnow() - timedelta(hours=1)
    await db_session.commit()

    r = await ac.get("/api/v1/offline/alerts", headers=headers)
    assert r.status_code == 200
    alerts = r.json()["data"]["alerts"]
    assert any(
        a["code"] == "OFFLINE_ENVELOPE_EXPIRED" and a["device_id"] == device_id for a in alerts
    )


@pytest.mark.asyncio
async def test_offline_alerts_open_conflicts(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)
    db_session.add(
        m.SyncConflict(
            tenant_id=seed["t1"].id,
            op_type="pos_sale",
            client_payload={"x": 1},
            server_snapshot={"x": 2},
            status="open",
        )
    )
    await db_session.commit()

    r = await ac.get("/api/v1/offline/alerts", headers=headers)
    assert r.status_code == 200
    codes = [a["code"] for a in r.json()["data"]["alerts"]]
    assert "SYNC_CONFLICTS_OPEN" in codes


@pytest.mark.asyncio
async def test_revoke_soft_lockdown_expires_envelope_and_notifies(client, db_session, monkeypatch):
    emailer.clear_dev_outbox()
    monkeypatch.setattr("app.emailer.settings.EMAIL_ENABLED", True)
    monkeypatch.setattr("app.emailer.settings.SMTP_HOST", "")
    monkeypatch.setattr("app.emailer.settings.SMTP_FROM_EMAIL", "noreply@localhost")

    ac, seed = client
    headers = await _super(ac, seed)
    created = await ac.post(
        "/api/v1/offline/devices",
        headers=headers,
        json={"name": "Lockdown Till", "platform": "web"},
    )
    assert created.status_code == 200
    device_id = created.json()["data"]["id"]
    bind = await ac.post(f"/api/v1/offline/devices/{device_id}/bind", headers=headers, json={})
    assert bind.status_code == 200
    until_before = bind.json()["data"]["auth_envelope"]["offline_valid_until"]
    assert until_before

    revoked = await ac.delete(f"/api/v1/offline/devices/{device_id}", headers=headers)
    assert revoked.status_code == 200, revoked.text
    body = revoked.json()["data"]
    assert body["status"] == "revoked"
    assert body.get("soft_lockdown") is True
    assert body["offline_authorized_until"] is not None
    assert "envelope" in (body.get("message") or "").lower()

    row = await db_session.get(m.OfflineDevice, device_id)
    assert row.revoked_at is not None
    assert row.offline_authorized_until is not None
    assert row.offline_authorized_until <= datetime.utcnow() + timedelta(seconds=2)

    notes = (
        await db_session.execute(
            select(m.Notification).where(
                m.Notification.tenant_id == seed["t1"].id,
                m.Notification.category == "security",
                m.Notification.entity_type == "offline_device",
                m.Notification.entity_id == device_id,
            )
        )
    ).scalars().all()
    assert notes
    assert any("soft-locked" in (n.title or "").lower() for n in notes)

    outbox = emailer.get_dev_outbox()
    assert any("soft-locked" in (o.get("subject") or "").lower() for o in outbox)


@pytest.mark.asyncio
async def test_offline_alerts_notify_critical_emails(client, db_session, monkeypatch):
    emailer.clear_dev_outbox()
    monkeypatch.setattr("app.emailer.settings.EMAIL_ENABLED", True)
    monkeypatch.setattr("app.emailer.settings.SMTP_HOST", "")
    monkeypatch.setattr("app.emailer.settings.SMTP_FROM_EMAIL", "noreply@localhost")

    ac, seed = client
    headers = await _super(ac, seed)
    created = await ac.post(
        "/api/v1/offline/devices",
        headers=headers,
        json={"name": "Notify Till", "platform": "web"},
    )
    device_id = created.json()["data"]["id"]
    bind = await ac.post(f"/api/v1/offline/devices/{device_id}/bind", headers=headers, json={})
    assert bind.status_code == 200

    row = await db_session.get(m.OfflineDevice, device_id)
    row.offline_authorized_until = datetime.utcnow() - timedelta(hours=2)
    await db_session.commit()

    r = await ac.post("/api/v1/offline/alerts/notify", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["critical_count"] >= 1
    assert data["notifications_created"] >= 1
    assert data["channels"]["push"] == "deferred"
    assert any(a["code"] == "OFFLINE_ENVELOPE_EXPIRED" for a in data["alerts"])

    notes = (
        await db_session.execute(
            select(m.Notification).where(
                m.Notification.tenant_id == seed["t1"].id,
                m.Notification.category == "security",
                m.Notification.entity_type == "offline_alert",
                m.Notification.entity_id == device_id,
            )
        )
    ).scalars().all()
    assert notes

    outbox = emailer.get_dev_outbox()
    assert any("OFFLINE_ENVELOPE_EXPIRED" in (o.get("subject") or "") for o in outbox)
