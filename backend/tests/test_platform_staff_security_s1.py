"""Stage 88 S1 — Platform staff invite + session ops."""

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


async def _platform_headers(ac, db_engine, email="staff-s1@ribdigi.example.com"):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        await ensure_platform_tenant(db)
        secret = pyotp.random_base32()
        user = m.User(
            tenant_id=PLATFORM_TENANT_ID,
            email=email,
            full_name="Staff S1",
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
async def test_invite_platform_user_without_password(client, db_engine):
    ac, _seed = client
    headers = await _platform_headers(ac, db_engine)
    r = await ac.post(
        "/api/v1/platform/users",
        headers=headers,
        json={
            "email": "invited-ops@ribdigi.example.com",
            "full_name": "Invited Ops",
            "role": "platform_admin",
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["invite_by_email"] is True
    assert data.get("reset_token")
    assert data.get("email_delivery")

    session_factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        token = (
            await db.execute(
                select(m.AuthToken).where(
                    m.AuthToken.tenant_id == PLATFORM_TENANT_ID,
                    m.AuthToken.purpose == "password_reset",
                    m.AuthToken.user_id == data["id"],
                )
            )
        ).scalar_one_or_none()
        assert token is not None


@pytest.mark.asyncio
async def test_list_and_revoke_staff_sessions(client, db_engine):
    ac, _seed = client
    headers = await _platform_headers(ac, db_engine, email="sessions-s1@ribdigi.example.com")
    listed = await ac.get("/api/v1/platform/users/sessions", headers=headers)
    assert listed.status_code == 200, listed.text
    sessions = listed.json()["data"]
    assert isinstance(sessions, list)
    assert len(sessions) >= 1
    current = next((s for s in sessions if s.get("current")), sessions[0])
    rev = await ac.delete(f"/api/v1/platform/users/sessions/{current['id']}", headers=headers)
    assert rev.status_code == 200, rev.text
    assert rev.json()["data"]["revoked"] is True


@pytest.mark.asyncio
async def test_tenant_cannot_list_platform_sessions(client):
    ac, _seed = client
    mgr = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    r = await ac.get("/api/v1/platform/users/sessions", headers=mgr)
    assert r.status_code == 403


def test_platform_users_ui_invite_and_sessions():
    page = (ROOT / "frontend/app/platform/users/page.tsx").read_text(encoding="utf-8")
    assert "Invite by email" in page or "optional" in page.lower()
    assert "/platform/users/sessions" in page
    assert "Revoke" in page
