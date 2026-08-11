"""Stage 91 P1 — Staff presence, health required badges, House TZ, evidence export."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app import models as m
from app import totp as totp_svc
from app.platform import ensure_platform_tenant
from app.platform_const import PLATFORM_SUPER_ADMIN, PLATFORM_TENANT_ID
from app.rbac import permissions_for_role
from app.security import hash_password

ROOT = Path(__file__).resolve().parents[2]


async def _platform_headers(ac, db_engine, email="posture-p1@ribdigi.example.com"):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        await ensure_platform_tenant(db)
        secret = pyotp.random_base32()
        user = m.User(
            tenant_id=PLATFORM_TENANT_ID,
            email=email,
            full_name="Posture P1",
            password_hash=hash_password("SecurePass123!"),
            role=PLATFORM_SUPER_ADMIN,
            email_verified=True,
            permissions=permissions_for_role(PLATFORM_SUPER_ADMIN),
            totp_enabled=True,
            totp_secret_enc=totp_svc.encrypt_secret(secret),
            totp_confirmed_at=__import__("datetime").datetime.utcnow(),
        )
        db.add(user)
        await db.commit()
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
    return {"Authorization": f"Bearer {token}", "X-Tenant-ID": PLATFORM_TENANT_ID}


@pytest.mark.asyncio
async def test_users_session_presence_settings_tz_health_evidence(client, db_engine):
    ac, _seed = client
    headers = await _platform_headers(ac, db_engine)

    users = await ac.get("/api/v1/platform/users", headers=headers)
    assert users.status_code == 200, users.text
    rows = users.json()["data"]
    assert rows
    me = next(u for u in rows if u.get("email") == "posture-p1@ribdigi.example.com")
    assert "last_session_at" in me
    assert me.get("active_session_count", 0) >= 1
    assert me.get("last_session_at")

    patched = await ac.patch(
        "/api/v1/platform/settings",
        headers=headers,
        json={"timezone": "Africa/Lagos"},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["data"].get("timezone") == "Africa/Lagos"
    got = await ac.get("/api/v1/platform/settings", headers=headers)
    assert got.json()["data"].get("timezone") == "Africa/Lagos"

    health = await ac.get("/api/v1/platform/health", headers=headers)
    assert health.status_code == 200, health.text
    checks = health.json()["data"].get("checks") or {}
    assert "required" in (checks.get("redis") or {})
    assert "required" in (checks.get("celery_broker") or {})
    security = health.json()["data"].get("security") or {}
    assert "celery_enabled" in security

    evidence = await ac.get("/api/v1/platform/evidence", headers=headers)
    assert evidence.status_code == 200, evidence.text
    body = evidence.json()["data"]
    assert body.get("packaging_only") is True
    flags = body.get("honesty_flags") or {}
    assert flags.get("go_live_claimed") is False
    assert flags.get("sections_1_3_verified") is False
    assert flags.get("mrr_fabricated_claimed") is False
    assert body.get("house", {}).get("timezone") == "Africa/Lagos"
    assert "health" in body and "security" in body


def test_house_ui_surfaces_presence_required_tz_evidence():
    users = (ROOT / "frontend/app/platform/users/page.tsx").read_text(encoding="utf-8")
    assert "last_session_at" in users and "active_session_count" in users
    health = (ROOT / "frontend/app/platform/health/page.tsx").read_text(encoding="utf-8")
    assert "Required" in health or "required" in health
    assert "/platform/evidence" in health
    settings = (ROOT / "frontend/app/platform/settings/page.tsx").read_text(encoding="utf-8")
    assert "timezone" in settings
