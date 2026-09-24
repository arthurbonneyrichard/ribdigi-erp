"""AI Security Monitor (BR-21.10) — rule-based anomaly alerts."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app import ai_security as mon
from app import models as m
from app import audit as audit_svc
from tests.conftest import auth_headers


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


async def _admin(ac):
    return await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")


@pytest.mark.asyncio
async def test_rapid_failed_logins_create_alert_and_notify(client, db_session):
    ac, seed = client
    uid = seed["mgr1"].id
    tid = seed["t1"].id
    now = datetime.utcnow()
    for i in range(5):
        await audit_svc.record_event(
            db_session,
            tenant_id=tid,
            user_id=uid,
            module="auth",
            action="login_failed",
            entity="user",
            entity_id=uid,
            details={"n": i},
            ip_address="203.0.113.9",
        )
    await db_session.commit()

    headers = await _mgr(ac)
    scanned = await ac.post("/api/v1/ai/security/scan", headers=headers)
    assert scanned.status_code == 200, scanned.text
    body = scanned.json()["data"]
    assert body["created"] >= 1
    kinds = {a["kind"] for a in body["alerts"]}
    assert mon.KIND_RAPID_FAILED_LOGINS in kinds
    alert = next(a for a in body["alerts"] if a["kind"] == mon.KIND_RAPID_FAILED_LOGINS)
    assert alert["risk_score"] >= 70
    assert alert["user_id"] == uid

    listed = await ac.get("/api/v1/ai/security/alerts", headers=headers)
    assert listed.status_code == 200
    assert any(a["kind"] == mon.KIND_RAPID_FAILED_LOGINS for a in listed.json()["data"]["alerts"])

    notes = (
        await db_session.execute(
            select(m.Notification).where(
                m.Notification.tenant_id == tid,
                m.Notification.category == "security",
            )
        )
    ).scalars().all()
    assert notes


@pytest.mark.asyncio
async def test_new_ip_login_alert(client, db_session):
    ac, seed = client
    tid = seed["t1"].id
    uid = seed["mgr1"].id
    # Prior session from known IP
    db_session.add(
        m.AuthSession(
            tenant_id=tid,
            user_id=uid,
            refresh_token_hash="hash-old-" + uid[:8],
            jti="jti-old-" + uid[:8],
            ip_address="10.0.0.1",
            user_agent="pytest",
            expires_at=datetime.utcnow() + timedelta(days=1),
            created_at=datetime.utcnow() - timedelta(days=2),
        )
    )
    await db_session.flush()
    await audit_svc.record_event(
        db_session,
        tenant_id=tid,
        user_id=uid,
        module="auth",
        action="login",
        entity="user",
        entity_id=uid,
        details={"email": "mgr@alpha.example.com"},
        ip_address="198.51.100.77",
    )
    await db_session.commit()

    headers = await _mgr(ac)
    r = await ac.post("/api/v1/ai/security/scan", headers=headers)
    assert r.status_code == 200, r.text
    kinds = {a["kind"] for a in r.json()["data"]["alerts"]}
    assert mon.KIND_NEW_IP_LOGIN in kinds


@pytest.mark.asyncio
async def test_alerts_are_tenant_isolated(client, db_session):
    ac, seed = client
    # Seed beta-only alert
    db_session.add(
        m.AiSecurityAlert(
            tenant_id=seed["t2"].id,
            kind=mon.KIND_ACCOUNT_LOCKED,
            risk_score=99,
            fingerprint="beta-only-fp",
            title="beta secret alert",
            user_id=seed["u2"].id,
            evidence={"note": "should-not-leak"},
        )
    )
    await db_session.commit()

    headers = await _mgr(ac)
    r = await ac.get("/api/v1/ai/security/alerts", headers=headers)
    assert r.status_code == 200
    blob = r.text
    assert "beta secret alert" not in blob
    assert "should-not-leak" not in blob


@pytest.mark.asyncio
async def test_account_locked_detector(client, db_session):
    ac, seed = client
    seed["u1"].locked_until = datetime.utcnow() + timedelta(minutes=30)
    await db_session.commit()
    headers = await _mgr(ac)
    r = await ac.post("/api/v1/ai/security/scan", headers=headers)
    assert r.status_code == 200, r.text
    kinds = {a["kind"] for a in r.json()["data"]["alerts"]}
    assert mon.KIND_ACCOUNT_LOCKED in kinds
    locked = next(a for a in r.json()["data"]["alerts"] if a["kind"] == mon.KIND_ACCOUNT_LOCKED)
    assert locked["user_id"] == seed["u1"].id


@pytest.mark.asyncio
async def test_status_includes_security_monitor(client):
    ac, _seed = client
    headers = await _mgr(ac)
    r = await ac.get("/api/v1/ai/status", headers=headers)
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["security_monitor_enabled"] is True
    assert data["security_alert_threshold"] >= 1
