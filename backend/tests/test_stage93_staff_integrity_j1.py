"""Stage 93 J1 — Staff delivery & integrity."""

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


async def _platform_headers(ac, db_engine, email="staff-j1@ribdigi.example.com"):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        await ensure_platform_tenant(db)
        secret = pyotp.random_base32()
        user = m.User(
            tenant_id=PLATFORM_TENANT_ID,
            email=email,
            full_name="Staff J1",
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
async def test_invite_delivery_on_users_and_verify_timestamp(client, db_engine):
    ac, _seed = client
    headers = await _platform_headers(ac, db_engine)

    created = await ac.post(
        "/api/v1/platform/users",
        headers=headers,
        json={
            "email": "invitee-j1@ribdigi.example.com",
            "full_name": "Invitee J1",
            "role": "platform_admin",
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert "email_delivery" in body["data"]
    assert body["data"]["email_delivery"].get("fabricated_success") is False
    assert "Invite email" in body["message"]

    users = await ac.get("/api/v1/platform/users", headers=headers)
    assert users.status_code == 200, users.text
    invitee = next(
        u for u in users.json()["data"] if u.get("email") == "invitee-j1@ribdigi.example.com"
    )
    assert invitee.get("last_invite_delivery") is not None
    assert "sent" in invitee["last_invite_delivery"]

    verify = await ac.get("/api/v1/platform/audit/verify", headers=headers)
    assert verify.status_code == 200, verify.text
    assert verify.json()["data"].get("verified_at")


def test_users_audit_ui_j1():
    users = (ROOT / "frontend/app/platform/users/page.tsx").read_text(encoding="utf-8")
    assert "last_invite_delivery" in users
    assert "Invite email" in users or "email_delivery" in users
    audit = (ROOT / "frontend/app/platform/audit/page.tsx").read_text(encoding="utf-8")
    assert "verified_at" in audit
    assert "broken_created_at" in audit
