"""Stage 94 H1 — Configuration integrity & release identity."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app import models as m
from app import totp as totp_svc
from app.config import settings
from app.platform import ensure_platform_tenant
from app.platform_const import PLATFORM_SUPER_ADMIN, PLATFORM_TENANT_ID
from app.rbac import permissions_for_role
from app.security import hash_password

ROOT = Path(__file__).resolve().parents[2]


async def _platform_headers(ac, db_engine, email="config-h1@ribdigi.example.com"):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        await ensure_platform_tenant(db)
        secret = pyotp.random_base32()
        user = m.User(
            tenant_id=PLATFORM_TENANT_ID,
            email=email,
            full_name="Config H1",
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
async def test_settings_validation_and_runtime_identity(client, db_engine):
    ac, _seed = client
    headers = await _platform_headers(ac, db_engine)

    bad_email = await ac.patch(
        "/api/v1/platform/settings",
        headers=headers,
        json={"support_email": "not-an-email"},
    )
    assert bad_email.status_code == 400, bad_email.text

    bad_tz = await ac.patch(
        "/api/v1/platform/settings",
        headers=headers,
        json={"timezone": "Not/A_Zone"},
    )
    assert bad_tz.status_code == 400, bad_tz.text

    ok = await ac.patch(
        "/api/v1/platform/settings",
        headers=headers,
        json={"support_email": "ops@ribdigi.example.com", "timezone": "Africa/Lagos"},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"].get("support_email") == "ops@ribdigi.example.com"
    assert ok.json()["data"].get("timezone") == "Africa/Lagos"

    health = await ac.get("/api/v1/platform/health", headers=headers)
    assert health.status_code == 200, health.text
    identity = health.json()["data"].get("runtime_identity") or {}
    assert identity.get("version") == (settings.APP_VERSION or "1.0.0")
    assert "build_id" in identity
    assert identity.get("app_env") == settings.APP_ENV
    assert "debug" in identity

    evidence = await ac.get("/api/v1/platform/evidence", headers=headers)
    assert evidence.status_code == 200, evidence.text
    ev_id = evidence.json()["data"].get("runtime_identity") or {}
    assert ev_id.get("version") == identity.get("version")
    assert "build_id" in ev_id

    public = await ac.get("/api/v1/health")
    assert public.status_code == 200
    public_body = public.json()
    nested = public_body.get("data") if isinstance(public_body.get("data"), dict) else {}
    assert "runtime_identity" not in public_body
    assert "runtime_identity" not in nested


def test_settings_health_ui_h1():
    settings_ui = (ROOT / "frontend/app/platform/settings/page.tsx").read_text(encoding="utf-8")
    assert "IANA" in settings_ui
    health = (ROOT / "frontend/app/platform/health/page.tsx").read_text(encoding="utf-8")
    assert "runtime_identity" in health
    assert "build_id" in health
    cfg = (ROOT / "backend/app/config.py").read_text(encoding="utf-8")
    assert "APP_VERSION" in cfg and "APP_BUILD_ID" in cfg
