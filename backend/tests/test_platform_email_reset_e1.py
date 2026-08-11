"""Stage 86 E1 — Platform staff email password reset."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app import models as m
from app import totp as totp_svc
from app.platform import ensure_platform_tenant
from app.platform_const import PLATFORM_ADMIN, PLATFORM_SUPER_ADMIN, PLATFORM_TENANT_ID
from app.rbac import permissions_for_role
from app.security import hash_password
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _seed_platform(ac, db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        await ensure_platform_tenant(db)
        secret = pyotp.random_base32()
        super_u = m.User(
            tenant_id=PLATFORM_TENANT_ID,
            email="house-super@ribdigi.example.com",
            full_name="House Super",
            password_hash=hash_password("SecurePass123!"),
            role=PLATFORM_SUPER_ADMIN,
            email_verified=True,
            permissions=permissions_for_role(PLATFORM_SUPER_ADMIN),
            totp_enabled=True,
            totp_secret_enc=totp_svc.encrypt_secret(secret),
            totp_confirmed_at=__import__("datetime").datetime.utcnow(),
        )
        staff = m.User(
            tenant_id=PLATFORM_TENANT_ID,
            email="house-staff@ribdigi.example.com",
            full_name="House Staff",
            password_hash=hash_password("SecurePass123!"),
            role=PLATFORM_ADMIN,
            email_verified=True,
            permissions=permissions_for_role(PLATFORM_ADMIN),
            is_active=True,
        )
        db.add_all([super_u, staff])
        await db.commit()
        staff_id = staff.id
    code = pyotp.TOTP(secret).now()
    login = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": "house-super@ribdigi.example.com",
            "password": "SecurePass123!",
            "tenant_id": "ribdigi-platform",
            "totp_code": code,
        },
    )
    assert login.status_code == 200, login.text
    token = login.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}", "X-Tenant-ID": PLATFORM_TENANT_ID}
    return headers, staff_id


@pytest.mark.asyncio
async def test_platform_email_password_reset_issues_token(client, db_engine):
    ac, _seed = client
    headers, staff_id = await _seed_platform(ac, db_engine)
    r = await ac.post(
        f"/api/v1/platform/users/{staff_id}/password-reset-email",
        headers=headers,
        json={},
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["email"] == "house-staff@ribdigi.example.com"
    assert data.get("reset_token")

    session_factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        tok = (
            await db.execute(
                select(m.AuthToken).where(
                    m.AuthToken.user_id == staff_id,
                    m.AuthToken.purpose == "password_reset",
                )
            )
        ).scalars().first()
        assert tok is not None
        assert tok.tenant_id == PLATFORM_TENANT_ID


@pytest.mark.asyncio
async def test_platform_email_reset_foreign_user_404(client, db_engine):
    ac, seed = client
    headers, _staff_id = await _seed_platform(ac, db_engine)
    foreign_id = seed["u1"].id  # alpha cashier
    r = await ac.post(
        f"/api/v1/platform/users/{foreign_id}/password-reset-email",
        headers=headers,
        json={},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_tenant_cannot_platform_email_reset(client):
    ac, _seed = client
    mgr = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    r = await ac.post(
        "/api/v1/platform/users/x/password-reset-email",
        headers=mgr,
        json={},
    )
    assert r.status_code == 403


def test_platform_users_ui_has_email_reset():
    page = (ROOT / "frontend/app/platform/users/page.tsx").read_text(encoding="utf-8")
    assert "password-reset-email" in page
    assert "Email reset link" in page
