"""Stage 93 V1 — Format, evidence & runtime posture."""

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


async def _platform_headers(ac, db_engine, email="runtime-v1@ribdigi.example.com"):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        await ensure_platform_tenant(db)
        secret = pyotp.random_base32()
        user = m.User(
            tenant_id=PLATFORM_TENANT_ID,
            email=email,
            full_name="Runtime V1",
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
async def test_number_format_house_runtime_parity(client, db_engine):
    ac, _seed = client
    headers = await _platform_headers(ac, db_engine)

    patched = await ac.patch(
        "/api/v1/platform/settings",
        headers=headers,
        json={"number_format": "1.234,56", "inactivity_timeout_minutes": 45},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["data"].get("number_format") == "1.234,56"

    health = await ac.get("/api/v1/platform/health", headers=headers)
    assert health.status_code == 200, health.text
    runtime = health.json()["data"].get("house_runtime") or {}
    assert runtime.get("number_format") == "1.234,56"
    assert runtime.get("inactivity_timeout_minutes") == 45
    assert "celery_enabled" in (health.json()["data"].get("security") or {})

    evidence = await ac.get("/api/v1/platform/evidence", headers=headers)
    assert evidence.status_code == 200, evidence.text
    ev_runtime = evidence.json()["data"].get("house_runtime") or {}
    assert ev_runtime.get("number_format") == "1.234,56"
    assert ev_runtime.get("inactivity_timeout_minutes") == 45

    public = await ac.get("/api/v1/health")
    assert public.status_code == 200
    public_body = public.json()
    public_sec = public_body.get("security") or public_body.get("data", {}).get("security") or {}
    if isinstance(public_sec, dict):
        assert not isinstance(public_sec.get("cors_origins"), list)


def test_settings_health_evidence_ui_v1():
    settings = (ROOT / "frontend/app/platform/settings/page.tsx").read_text(encoding="utf-8")
    assert "number_format" in settings
    assert "Download evidence JSON" in settings
    assert "platformEvidence" in settings
    health = (ROOT / "frontend/app/platform/health/page.tsx").read_text(encoding="utf-8")
    assert "celery_enabled" in health
    assert "house_runtime" in health or "inactivity_timeout_minutes" in health
    assert 'role="alert"' in health
    assert "downloadPlatformEvidence" in health
    house = (ROOT / "frontend/lib/houseFormats.ts").read_text(encoding="utf-8")
    assert "number_format" in house
    assert "r.data?.number_format" in house
