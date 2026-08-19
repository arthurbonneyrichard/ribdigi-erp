"""Stage 145 S1 — AI security alerts CSV export."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select

from app import audit as audit_svc
from app import models as m
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


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
async def test_security_alerts_export_csv(client, db_session):
    ac, seed = client
    headers = await _mgr(ac)
    now = datetime.utcnow()
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
            ip_address="192.0.2.145",
            user_agent="Stage145",
        )
        await _backdate_latest(
            db_session,
            seed["t1"].id,
            now - timedelta(minutes=i),
            action="login_failed",
        )
    await db_session.commit()

    exported = await ac.get(
        "/api/v1/ai/security/alerts/export?lookback_hours=24", headers=headers
    )
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    text = exported.text
    header = text.splitlines()[0]
    assert "kind" in header and "severity" in header and "score" in header
    assert "failed_login" in text or "login" in text.lower()
    assert "secret" not in header.lower()
    assert "password" not in header.lower()


def test_security_alerts_export_ui_s1():
    page = (ROOT / "frontend/app/ai/page.tsx").read_text(encoding="utf-8")
    assert "Stage 145" in page
    assert "/ai/security/alerts/export" in page
    assert "Export security alerts CSV" in page
    assert 'id="security"' in page
