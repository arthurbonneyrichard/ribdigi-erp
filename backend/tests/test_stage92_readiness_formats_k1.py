"""Stage 92 K1 — House regional formats + runtime evidence detail."""

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


async def _platform_headers(ac, db_engine, email="formats-k1@ribdigi.example.com"):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        await ensure_platform_tenant(db)
        secret = pyotp.random_base32()
        user = m.User(
            tenant_id=PLATFORM_TENANT_ID,
            email=email,
            full_name="Formats K1",
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
async def test_house_formats_cors_detail_and_db_required(client, db_engine):
    ac, _seed = client
    headers = await _platform_headers(ac, db_engine)

    patched = await ac.patch(
        "/api/v1/platform/settings",
        headers=headers,
        json={"date_format": "YYYY-MM-DD", "time_format": "12h"},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["data"].get("date_format") == "YYYY-MM-DD"
    assert patched.json()["data"].get("time_format") == "12h"

    bad = await ac.patch(
        "/api/v1/platform/settings",
        headers=headers,
        json={"date_format": "BAD"},
    )
    assert bad.status_code == 400

    health = await ac.get("/api/v1/platform/health", headers=headers)
    assert health.status_code == 200, health.text
    body = health.json()["data"]
    assert body["checks"]["database"].get("required") is True
    sec = body.get("security") or {}
    assert isinstance(sec.get("cors_origins"), list)
    assert sec.get("cors_origins_count") == len(sec["cors_origins"])

    public = await ac.get("/api/v1/health")
    assert public.status_code == 200
    public_sec = public.json().get("security") or public.json().get("data", {}).get("security") or {}
    # Public posture must not expose the allowlist array.
    if isinstance(public_sec, dict):
        assert "cors_origins" not in public_sec or not isinstance(
            public_sec.get("cors_origins"), list
        )

    evidence = await ac.get("/api/v1/platform/evidence", headers=headers)
    assert evidence.status_code == 200, evidence.text
    ev = evidence.json()["data"]
    assert isinstance((ev.get("security") or {}).get("cors_origins"), list)
    assert ev.get("house", {}).get("date_format") == "YYYY-MM-DD"
    assert ev.get("house", {}).get("time_format") == "12h"


def test_settings_and_format_ui_wiring():
    settings = (ROOT / "frontend/app/platform/settings/page.tsx").read_text(encoding="utf-8")
    assert "date_format" in settings and "time_format" in settings
    assert "DD/MM/YYYY" in settings
    house = (ROOT / "frontend/lib/houseFormats.ts").read_text(encoding="utf-8")
    assert "fetchHouseFormats" in house
    assert "format.ts" in house or "RegionalFormats" in house
    audit = (ROOT / "frontend/app/platform/audit/page.tsx").read_text(encoding="utf-8")
    assert "formatDateTime" in audit
    health = (ROOT / "frontend/app/platform/health/page.tsx").read_text(encoding="utf-8")
    assert "cors_origins" in health
