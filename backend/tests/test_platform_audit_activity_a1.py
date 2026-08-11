"""Stage 86 A1 — Platform audit filters + Activity alias."""

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
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _platform_headers(ac, db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        await ensure_platform_tenant(db)
        secret = pyotp.random_base32()
        user = m.User(
            tenant_id=PLATFORM_TENANT_ID,
            email="audit-ops@ribdigi.example.com",
            full_name="Audit Ops",
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
            "email": "audit-ops@ribdigi.example.com",
            "password": "SecurePass123!",
            "tenant_id": "ribdigi-platform",
            "totp_code": code,
        },
    )
    assert login.status_code == 200, login.text
    token = login.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}", "X-Tenant-ID": PLATFORM_TENANT_ID}


@pytest.mark.asyncio
async def test_platform_audit_accepts_filters(client, db_engine):
    ac, _seed = client
    headers = await _platform_headers(ac, db_engine)
    # Create an audited event via settings/list tenants
    await ac.get("/api/v1/platform/tenants", headers=headers)
    r = await ac.get(
        "/api/v1/platform/audit?module=platform_tenants&limit=20",
        headers=headers,
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert "items" in data
    assert data.get("filters", {}).get("module") == "platform_tenants"


@pytest.mark.asyncio
async def test_platform_activity_alias(client, db_engine):
    ac, _seed = client
    headers = await _platform_headers(ac, db_engine)
    r = await ac.get("/api/v1/platform/activity", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert "items" in data
    assert data.get("alias_of") == "/platform/audit"


@pytest.mark.asyncio
async def test_tenant_cannot_access_platform_activity(client):
    ac, _seed = client
    mgr = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    r = await ac.get("/api/v1/platform/activity", headers=mgr)
    assert r.status_code == 403


def test_platform_shell_and_activity_page():
    shell = (ROOT / "frontend/components/PlatformShell.tsx").read_text(encoding="utf-8")
    assert "/platform/activity" in shell
    assert "Activity" in shell
    assert (ROOT / "frontend/app/platform/activity/page.tsx").is_file()
    audit = (ROOT / "frontend/app/platform/audit/page.tsx").read_text(encoding="utf-8")
    assert "module" in audit and "Filter" in audit
