"""Stage 94 W1 — Platform staff discovery."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app import models as m
from app import totp as totp_svc
from app.platform import ensure_platform_tenant
from app.platform_const import PLATFORM_ADMIN, PLATFORM_SUPER_ADMIN, PLATFORM_TENANT_ID
from app.rbac import permissions_for_role
from app.security import hash_password

ROOT = Path(__file__).resolve().parents[2]


async def _platform_headers(ac, db_engine, email="staff-w1@ribdigi.example.com"):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        await ensure_platform_tenant(db)
        secret = pyotp.random_base32()
        user = m.User(
            tenant_id=PLATFORM_TENANT_ID,
            email=email,
            full_name="Staff W1 Super",
            password_hash=hash_password("SecurePass123!"),
            role=PLATFORM_SUPER_ADMIN,
            email_verified=True,
            permissions=permissions_for_role(PLATFORM_SUPER_ADMIN),
            totp_enabled=True,
            totp_secret_enc=totp_svc.encrypt_secret(secret),
            totp_confirmed_at=__import__("datetime").datetime.utcnow(),
        )
        admin = m.User(
            tenant_id=PLATFORM_TENANT_ID,
            email="staff-w1-admin@ribdigi.example.com",
            full_name="Staff W1 Admin",
            password_hash=hash_password("SecurePass123!"),
            role=PLATFORM_ADMIN,
            email_verified=True,
            is_active=False,
            permissions=permissions_for_role(PLATFORM_ADMIN),
            totp_enabled=True,
            totp_secret_enc=totp_svc.encrypt_secret(secret),
            totp_confirmed_at=__import__("datetime").datetime.utcnow(),
        )
        db.add(user)
        db.add(admin)
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
async def test_platform_users_q_role_is_active_filters(client, db_engine):
    ac, _seed = client
    headers = await _platform_headers(ac, db_engine)

    by_q = await ac.get("/api/v1/platform/users?q=Staff%20W1%20Admin", headers=headers)
    assert by_q.status_code == 200, by_q.text
    emails = {u["email"] for u in by_q.json()["data"]}
    assert "staff-w1-admin@ribdigi.example.com" in emails
    assert "staff-w1@ribdigi.example.com" not in emails

    by_role = await ac.get(
        "/api/v1/platform/users?role=platform_admin",
        headers=headers,
    )
    assert by_role.status_code == 200, by_role.text
    assert all(u["role"] == "platform_admin" for u in by_role.json()["data"])
    assert any(u["email"] == "staff-w1-admin@ribdigi.example.com" for u in by_role.json()["data"])

    inactive = await ac.get("/api/v1/platform/users?is_active=false", headers=headers)
    assert inactive.status_code == 200, inactive.text
    assert all(u["is_active"] is False for u in inactive.json()["data"])
    assert any(u["email"] == "staff-w1-admin@ribdigi.example.com" for u in inactive.json()["data"])

    bad = await ac.get("/api/v1/platform/users?role=company_admin", headers=headers)
    assert bad.status_code == 400


def test_users_dashboard_ui_w1():
    users = (ROOT / "frontend/app/platform/users/page.tsx").read_text(encoding="utf-8")
    assert "searchParams" in users or "useSearchParams" in users
    assert "is_active" in users
    assert "role" in users
    assert "q" in users
    dash = (ROOT / "frontend/app/platform/dashboard/page.tsx").read_text(encoding="utf-8")
    assert 'href="/platform/users"' in dash or "href=\"/platform/users\"" in dash
