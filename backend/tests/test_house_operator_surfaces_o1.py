"""Stage 90 O1 — Operator contact / security / runbook surfaces."""

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


async def _platform_headers(ac, db_engine, email="opsurf-o1@ribdigi.example.com"):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        await ensure_platform_tenant(db)
        pt = await db.get(m.Tenant, PLATFORM_TENANT_ID)
        pt.email = "house-support@ribdigi.example.com"
        pt.phone = "+233000000000"
        secret = pyotp.random_base32()
        user = m.User(
            tenant_id=PLATFORM_TENANT_ID,
            email=email,
            full_name="Op Surf O1",
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
async def test_health_includes_contacts_and_security(client, db_engine):
    ac, _seed = client
    headers = await _platform_headers(ac, db_engine)
    r = await ac.get("/api/v1/platform/health", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert "checks" in data
    assert "security" in data
    assert "rate_limit_enabled" in data["security"]
    contacts = data.get("operator_contacts") or {}
    assert contacts.get("support_email") == "house-support@ribdigi.example.com"
    assert contacts.get("support_phone") == "+233000000000"


def test_health_and_settings_ui_operator_surfaces():
    health = (ROOT / "frontend/app/platform/health/page.tsx").read_text(encoding="utf-8")
    assert "operator_contacts" in health or "support_email" in health
    assert "rate_limit" in health
    assert "security" in health
    settings = (ROOT / "frontend/app/platform/settings/page.tsx").read_text(encoding="utf-8")
    assert "SUPPORT_RUNBOOK_MVP.md" in settings
    assert "INCIDENT_PACK_MVP.md" in settings
    assert "ops/mvp/README.md" in settings
