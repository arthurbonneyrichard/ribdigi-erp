"""Stage 86 P1 — House tenant provision."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app import models as m
from app import totp as totp_svc
from app.platform import ensure_platform_tenant
from app.platform_const import PLATFORM_SUPER_ADMIN, PLATFORM_TENANT_ID
from app.rbac import permissions_for_role
from app.security import hash_password
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _platform_headers(ac, db_engine, email="provision-ops@ribdigi.example.com"):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        await ensure_platform_tenant(db)
        secret = pyotp.random_base32()
        user = m.User(
            tenant_id=PLATFORM_TENANT_ID,
            email=email,
            full_name="Provision Ops",
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
async def test_platform_provisions_customer_tenant(client, db_engine):
    ac, _seed = client
    headers = await _platform_headers(ac, db_engine)
    r = await ac.post(
        "/api/v1/platform/tenants",
        headers=headers,
        json={
            "company_name": "Gamma Co",
            "slug": "gamma",
            "admin_email": "admin@gamma.example.com",
            "admin_password": "SecurePass123!",
            "admin_full_name": "Gamma Admin",
            "plan_code": "starter",
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["slug"] == "gamma"
    assert data["status"] == "trial"
    assert data["plan_code"] == "starter"
    assert data.get("email_verification_token")

    session_factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        tenant = (
            await db.execute(select(m.Tenant).where(m.Tenant.slug == "gamma"))
        ).scalar_one()
        assert tenant.id != PLATFORM_TENANT_ID
        admin = (
            await db.execute(
                select(m.User).where(
                    m.User.tenant_id == tenant.id,
                    m.User.email == "admin@gamma.example.com",
                )
            )
        ).scalar_one()
        assert admin.role == "company_admin"


@pytest.mark.asyncio
async def test_platform_provision_rejects_reserved_slug(client, db_engine):
    ac, _seed = client
    headers = await _platform_headers(ac, db_engine, email="provision-ops2@ribdigi.example.com")
    r = await ac.post(
        "/api/v1/platform/tenants",
        headers=headers,
        json={
            "company_name": "Bad",
            "slug": "ribdigi-platform",
            "admin_email": "bad@example.com",
            "admin_password": "SecurePass123!",
        },
    )
    assert r.status_code in (400, 409)


@pytest.mark.asyncio
async def test_tenant_cannot_provision_via_platform(client):
    ac, _seed = client
    mgr = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    r = await ac.post(
        "/api/v1/platform/tenants",
        headers=mgr,
        json={
            "company_name": "Nope",
            "slug": "nope",
            "admin_email": "n@example.com",
            "admin_password": "SecurePass123!",
        },
    )
    assert r.status_code == 403


def test_platform_tenants_ui_has_provision_form():
    page = (ROOT / "frontend/app/platform/tenants/page.tsx").read_text(encoding="utf-8")
    assert "Provision tenant" in page
    assert "/platform/tenants" in page
    assert "admin_password" in page
