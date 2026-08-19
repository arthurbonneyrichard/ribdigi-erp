"""Stage 91 I1 — Audit/Activity date-range investigation."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pyotp
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app import audit
from app import models as m
from app import totp as totp_svc
from app.platform import ensure_platform_tenant
from app.platform_const import PLATFORM_SUPER_ADMIN, PLATFORM_TENANT_ID
from app.rbac import permissions_for_role
from app.security import hash_password

ROOT = Path(__file__).resolve().parents[2]


async def _platform_headers(ac, db_engine, email="audit-i1@ribdigi.example.com"):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        await ensure_platform_tenant(db)
        secret = pyotp.random_base32()
        user = m.User(
            tenant_id=PLATFORM_TENANT_ID,
            email=email,
            full_name="Audit I1",
            password_hash=hash_password("SecurePass123!"),
            role=PLATFORM_SUPER_ADMIN,
            email_verified=True,
            permissions=permissions_for_role(PLATFORM_SUPER_ADMIN),
            totp_enabled=True,
            totp_secret_enc=totp_svc.encrypt_secret(secret),
            totp_confirmed_at=datetime.utcnow(),
        )
        db.add(user)
        await db.commit()
        user_id = user.id
    code = pyotp.TOTP(secret).now()
    login = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": "SecurePass123!",
            "tenant_id": "ribdigi-platform",
            "totp_code": code,
        },
    )
    assert login.status_code == 200, login.text
    token = login.json()["data"]["access_token"]
    return {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": PLATFORM_TENANT_ID,
    }, user_id


@pytest.mark.asyncio
async def test_audit_and_activity_date_range_filters(client, db_engine):
    ac, _seed = client
    headers, user_id = await _platform_headers(ac, db_engine)
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    old_day = (datetime.utcnow() - timedelta(days=20)).strftime("%Y-%m-%d")
    recent_day = datetime.utcnow().strftime("%Y-%m-%d")
    async with session_factory() as db:
        await audit.record_event(
            db,
            tenant_id=PLATFORM_TENANT_ID,
            user_id=user_id,
            action="platform.test.old",
            entity="platform",
            entity_id=PLATFORM_TENANT_ID,
            details={"fixture": "old"},
            module="platform_test",
        )
        await audit.record_event(
            db,
            tenant_id=PLATFORM_TENANT_ID,
            user_id=user_id,
            action="platform.test.recent",
            entity="platform",
            entity_id=PLATFORM_TENANT_ID,
            details={"fixture": "recent"},
            module="platform_test",
        )
        await db.commit()
        row = (
            await db.execute(select(m.AuditLog).where(m.AuditLog.action == "platform.test.old"))
        ).scalar_one()
        row.created_at = datetime.utcnow() - timedelta(days=20)
        await db.commit()

    listed = await ac.get(
        f"/api/v1/platform/audit?module=platform_test&from_date={recent_day}&to_date={recent_day}",
        headers=headers,
    )
    assert listed.status_code == 200, listed.text
    actions = {i.get("action") for i in listed.json()["data"]["items"]}
    assert "platform.test.recent" in actions
    assert "platform.test.old" not in actions
    assert listed.json()["data"]["filters"].get("from_date") == recent_day

    activity = await ac.get("/api/v1/platform/activity?module=platform_test", headers=headers)
    assert activity.status_code == 200, activity.text
    body = activity.json()["data"]
    assert body.get("alias_of") == "/platform/audit"
    assert body["filters"].get("default_recent_days") == 7
    act_actions = {i.get("action") for i in body["items"]}
    assert "platform.test.recent" in act_actions
    assert "platform.test.old" not in act_actions

    old_window = await ac.get(
        f"/api/v1/platform/audit?module=platform_test&from_date={old_day}&to_date={old_day}",
        headers=headers,
    )
    assert old_window.status_code == 200, old_window.text
    old_actions = {i.get("action") for i in old_window.json()["data"]["items"]}
    assert "platform.test.old" in old_actions


def test_audit_ui_wires_date_inputs_to_list_and_export():
    page = (ROOT / "frontend/app/platform/audit/page.tsx").read_text(encoding="utf-8")
    assert "from_date" in page and "to_date" in page
    assert 'type="date"' in page
    assert "/platform/activity" in page
