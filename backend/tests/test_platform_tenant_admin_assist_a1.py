"""Stage 89 A1 — House Tenant Admin assist."""

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


async def _platform_headers(ac, db_engine, email="assist-a1@ribdigi.example.com"):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        await ensure_platform_tenant(db)
        secret = pyotp.random_base32()
        user = m.User(
            tenant_id=PLATFORM_TENANT_ID,
            email=email,
            full_name="Assist A1",
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
async def test_house_admin_password_reset_and_resend_verify(client, db_engine):
    ac, seed = client
    headers = await _platform_headers(ac, db_engine)
    tid = seed["t1"].id

    detail = await ac.get(f"/api/v1/platform/tenants/{tid}", headers=headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()["data"].get("tenant_admin", {}).get("email") == "admin@alpha.example.com"

    reset = await ac.post(
        f"/api/v1/platform/tenants/{tid}/admin/password-reset-email",
        headers=headers,
        json={},
    )
    assert reset.status_code == 200, reset.text
    assert reset.json()["data"]["impersonation"] is False
    assert reset.json()["data"].get("reset_token")

    session_factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        admin = (
            await db.execute(
                select(m.User).where(
                    m.User.tenant_id == tid,
                    m.User.role == "company_admin",
                )
            )
        ).scalar_one()
        admin.email_verified = False
        await db.commit()

    resend = await ac.post(
        f"/api/v1/platform/tenants/{tid}/admin/resend-verification",
        headers=headers,
        json={},
    )
    assert resend.status_code == 200, resend.text
    assert resend.json()["data"]["already_verified"] is False
    assert resend.json()["data"].get("email_verification_token")
    assert resend.json()["data"]["impersonation"] is False


@pytest.mark.asyncio
async def test_tenant_cannot_house_admin_assist(client, db_engine):
    ac, seed = client
    mgr = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    r = await ac.post(
        f"/api/v1/platform/tenants/{seed['t1'].id}/admin/password-reset-email",
        headers=mgr,
        json={},
    )
    assert r.status_code == 403


def test_tenant_detail_ui_has_admin_assist():
    page = (ROOT / "frontend/app/platform/tenants/[id]/page.tsx").read_text(encoding="utf-8")
    assert "/admin/" in page
    assert "password-reset-email" in page
    assert "resend-verification" in page
    assert "impersonation" in page.lower()
