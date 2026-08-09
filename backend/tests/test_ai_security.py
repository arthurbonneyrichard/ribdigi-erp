"""Phase 4 / BR-21.10 AI security monitor."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app import ai_security as ai_security_svc
from app import audit as audit_svc
from app import models as m
from tests.conftest import auth_headers


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


async def _backdate_latest(db_session, tenant_id: str, when: datetime, *, action: str | None = None):
    q = select(m.AuditLog).where(m.AuditLog.tenant_id == tenant_id)
    if action:
        q = q.where(m.AuditLog.action == action)
    row = (
        await db_session.execute(q.order_by(m.AuditLog.created_at.desc()))
    ).scalars().first()
    row.created_at = when
    await db_session.flush()
    return row


@pytest.mark.asyncio
async def test_failed_login_burst_and_new_ip_alerts(db_session, seeded):
    tenant_id = seeded["t1"].id
    user = seeded["mgr1"]
    now = datetime.utcnow()

    for days_ago in (10, 8, 6, 4, 2):
        await audit_svc.record_event(
            db_session,
            tenant_id=tenant_id,
            user_id=user.id,
            module="auth",
            action="login",
            entity="user",
            entity_id=user.id,
            details={},
            ip_address="10.0.0.5",
            user_agent="AlphaBrowser/1.0",
        )
        await _backdate_latest(
            db_session, tenant_id, now - timedelta(days=days_ago, hours=3), action="login"
        )

    for i in range(5):
        await audit_svc.record_event(
            db_session,
            tenant_id=tenant_id,
            user_id=user.id,
            module="auth",
            action="login_failed",
            entity="user",
            entity_id=user.id,
            details={"email": user.email},
            ip_address="203.0.113.9",
            user_agent="EvilClient/0.1",
        )
        await _backdate_latest(
            db_session,
            tenant_id,
            now - timedelta(minutes=20 - i),
            action="login_failed",
        )

    await audit_svc.record_event(
        db_session,
        tenant_id=tenant_id,
        user_id=user.id,
        module="auth",
        action="login",
        entity="user",
        entity_id=user.id,
        details={},
        ip_address="203.0.113.9",
        user_agent="EvilClient/0.1",
    )
    await _backdate_latest(db_session, tenant_id, now - timedelta(minutes=1), action="login")
    await db_session.commit()

    data = await ai_security_svc.scan_security_alerts(db_session, tenant_id, lookback_hours=48)
    kinds = {a["kind"] for a in data["alerts"]}
    assert "failed_login_burst" in kinds or "failed_login_ip_burst" in kinds
    assert "login_after_failures" in kinds
    assert "unusual_login_ip" in kinds
    assert data["high_or_critical_count"] >= 1
    assert all("Beta" not in a["detail"] for a in data["alerts"])


@pytest.mark.asyncio
async def test_security_alerts_api_tenant_scoped(client, db_session):
    ac, seed = client
    headers = await _mgr(ac)
    now = datetime.utcnow()

    await audit_svc.record_event(
        db_session,
        tenant_id=seed["t2"].id,
        user_id=seed["u2"].id,
        module="auth",
        action="login_failed",
        entity="user",
        entity_id=seed["u2"].id,
        details={"email": "cashier@beta.example.com"},
        ip_address="198.51.100.1",
        user_agent="BetaBot",
    )
    for i in range(6):
        await audit_svc.record_event(
            db_session,
            tenant_id=seed["t1"].id,
            user_id=seed["mgr1"].id,
            module="auth",
            action="login_failed",
            entity="user",
            entity_id=seed["mgr1"].id,
            details={},
            ip_address="192.0.2.10",
            user_agent="Test",
        )
        await _backdate_latest(
            db_session,
            seed["t1"].id,
            now - timedelta(minutes=i),
            action="login_failed",
        )
    await db_session.commit()

    r = await ac.get("/api/v1/ai/security/alerts?lookback_hours=24", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert body["method"] == "rules_v1"
    assert body["alert_count"] >= 1
    blob = str(body)
    assert "BetaBot" not in blob
    assert "198.51.100.1" not in blob
