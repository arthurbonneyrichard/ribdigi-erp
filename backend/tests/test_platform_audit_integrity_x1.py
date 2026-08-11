"""Stage 87 X1 — Platform audit export + chain verify."""

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
            email="audit-x1@ribdigi.example.com",
            full_name="Audit X1",
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
            "email": "audit-x1@ribdigi.example.com",
            "password": "SecurePass123!",
            "tenant_id": "ribdigi-platform",
            "totp_code": code,
        },
    )
    assert login.status_code == 200, login.text
    token = login.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}", "X-Tenant-ID": PLATFORM_TENANT_ID}


@pytest.mark.asyncio
async def test_platform_audit_export_csv(client, db_engine):
    ac, _seed = client
    headers = await _platform_headers(ac, db_engine)
    await ac.get("/api/v1/platform/tenants", headers=headers)
    r = await ac.get("/api/v1/platform/audit/export?format=csv", headers=headers)
    assert r.status_code == 200, r.text
    assert "text/csv" in r.headers.get("content-type", "")
    assert "platform-audit-logs.csv" in r.headers.get("content-disposition", "")


@pytest.mark.asyncio
async def test_platform_audit_verify(client, db_engine):
    ac, _seed = client
    headers = await _platform_headers(ac, db_engine)
    r = await ac.get("/api/v1/platform/audit/verify", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert "valid" in data
    assert "checked" in data


@pytest.mark.asyncio
async def test_tenant_cannot_platform_audit_export(client):
    ac, _seed = client
    mgr = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    r = await ac.get("/api/v1/platform/audit/export", headers=mgr)
    assert r.status_code == 403


def test_platform_audit_ui_has_export_verify():
    page = (ROOT / "frontend/app/platform/audit/page.tsx").read_text(encoding="utf-8")
    assert "Export CSV" in page and "Export PDF" in page
    assert "/platform/audit/verify" in page
    assert "/platform/audit/export" in page
