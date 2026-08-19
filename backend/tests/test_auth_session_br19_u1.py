"""Stage 19 U1: Auth & session BR-19 fidelity sync."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pyotp
import pytest
from sqlalchemy import select

from app import models as m
from app.config import settings
from app.rbac import permissions_for_role
from app.security import hash_password, issue_one_time_token
from app.totp import role_requires_2fa
from tests.conftest import auth_headers

pytestmark = pytest.mark.security

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.asyncio
async def test_login_bcrypt_password_policy_and_jwt_expiry(client, db_session):
    ac, seed = client
    login = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": "mgr@alpha.example.com",
            "password": "SecurePass123!",
            "tenant_id": "alpha",
        },
    )
    assert login.status_code == 200, login.text
    data = login.json()["data"]
    assert data["expires_in"] == settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    assert data["token_type"] == "Bearer"

    user = (
        await db_session.execute(select(m.User).where(m.User.id == seed["mgr1"].id))
    ).scalar_one()
    assert user.password_hash.startswith("$2b$") or user.password_hash.startswith("$2a$")

    headers = {
        "Authorization": f"Bearer {data['access_token']}",
        "X-Tenant-ID": seed["t1"].id,
    }
    weak = await ac.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={"current_password": "SecurePass123!", "new_password": "short"},
    )
    assert weak.status_code == 400, weak.text


@pytest.mark.asyncio
async def test_lockout_five_sets_30m_cooldown(client, db_session):
    ac, seed = client
    user = m.User(
        tenant_id=seed["t1"].id,
        email="u1-lockout@alpha.example.com",
        full_name="U1 Lockout",
        password_hash=hash_password("SecurePass123!"),
        role="cashier",
        email_verified=True,
        permissions=permissions_for_role("cashier"),
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()

    for _ in range(5):
        r = await ac.post(
            "/api/v1/auth/login",
            json={
                "email": "u1-lockout@alpha.example.com",
                "password": "WrongPassword!!!",
                "tenant_id": "alpha",
            },
        )
        assert r.status_code in {401, 423}

    locked = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": "u1-lockout@alpha.example.com",
            "password": "SecurePass123!",
            "tenant_id": "alpha",
        },
    )
    assert locked.status_code == 423

    db_session.expire_all()
    row = (
        await db_session.execute(select(m.User).where(m.User.email == "u1-lockout@alpha.example.com"))
    ).scalar_one()
    assert row.locked_until is not None
    delta = row.locked_until - datetime.utcnow()
    assert timedelta(minutes=25) <= delta <= timedelta(minutes=35)


@pytest.mark.asyncio
async def test_email_verify_gate_and_password_reset_spot(client, db_session):
    ac, seed = client
    user = m.User(
        tenant_id=seed["t1"].id,
        email="u1-unverified@alpha.example.com",
        full_name="U1 Unverified",
        password_hash=hash_password("SecurePass123!"),
        role="cashier",
        email_verified=False,
        permissions=permissions_for_role("cashier"),
        is_active=True,
    )
    reset_user = m.User(
        tenant_id=seed["t1"].id,
        email="u1-reset@alpha.example.com",
        full_name="U1 Reset",
        password_hash=hash_password("SecurePass123!"),
        role="cashier",
        email_verified=True,
        permissions=permissions_for_role("cashier"),
        is_active=True,
    )
    db_session.add_all([user, reset_user])
    await db_session.commit()

    blocked = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": "u1-unverified@alpha.example.com",
            "password": "SecurePass123!",
            "tenant_id": "alpha",
        },
    )
    assert blocked.status_code == 403
    assert blocked.json()["detail"]["code"] == "EMAIL_NOT_VERIFIED"

    _raw, _hash, expires = issue_one_time_token()
    assert timedelta(minutes=55) <= (expires - datetime.utcnow()) <= timedelta(minutes=65)

    req = await ac.post(
        "/api/v1/auth/password-reset-request",
        json={"email": "u1-reset@alpha.example.com", "tenant_id": "alpha"},
    )
    assert req.status_code == 200, req.text
    token = req.json()["data"].get("reset_token")
    assert token
    confirm = await ac.post(
        "/api/v1/auth/password-reset",
        json={"token": token, "new_password": "U1ResetPass123!"},
    )
    assert confirm.status_code == 200, confirm.text


@pytest.mark.asyncio
async def test_totp_setup_qr_confirm_backup_and_role_gate(client):
    ac, seed = client
    headers = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    setup = await ac.post("/api/v1/auth/2fa/setup", headers=headers)
    assert setup.status_code == 200, setup.text
    body = setup.json()["data"]
    assert body.get("secret")
    assert str(body.get("otpauth_url", "")).startswith("otpauth://")
    assert body.get("qr_png_base64")

    code = pyotp.TOTP(body["secret"]).now()
    confirm = await ac.post(
        "/api/v1/auth/2fa/confirm",
        headers=headers,
        json={"code": code},
    )
    assert confirm.status_code == 200, confirm.text
    assert confirm.json()["data"]["enabled"] is True
    assert len(confirm.json()["data"]["backup_codes"]) >= 1

    assert role_requires_2fa("company_admin") is True
    assert role_requires_2fa("cashier") is False
    admin_login = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": "admin@alpha.example.com",
            "password": "SecurePass123!",
            "tenant_id": "alpha",
        },
    )
    assert admin_login.status_code == 200, admin_login.text
    assert admin_login.json()["data"]["must_enroll_2fa"] is True


@pytest.mark.asyncio
async def test_sessions_idle_remote_revoke_and_refresh_rotation(client):
    """BR-19.3: refresh rotation, remote revoke, idle logout."""
    ac, seed = client

    # Refresh rotation — reuse of old refresh token fails
    login_a = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": "mgr@alpha.example.com",
            "password": "SecurePass123!",
            "tenant_id": "alpha",
        },
    )
    assert login_a.status_code == 200, login_a.text
    refresh_a = login_a.json()["data"]["refresh_token"]
    rotated = await ac.post("/api/v1/auth/refresh", json={"refresh_token": refresh_a})
    assert rotated.status_code == 200, rotated.text
    new_refresh = rotated.json()["data"]["refresh_token"]
    assert new_refresh != refresh_a
    reuse = await ac.post("/api/v1/auth/refresh", json={"refresh_token": refresh_a})
    assert reuse.status_code == 401

    # Second device — remote revoke of the first session invalidates its refresh
    login_b = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": "mgr@alpha.example.com",
            "password": "SecurePass123!",
            "tenant_id": "alpha",
        },
    )
    assert login_b.status_code == 200, login_b.text
    h2 = {
        "Authorization": f"Bearer {login_b.json()['data']['access_token']}",
        "X-Tenant-ID": seed["t1"].id,
    }
    sessions2 = await ac.get("/api/v1/auth/sessions", headers=h2)
    assert sessions2.status_code == 200, sessions2.text
    items = sessions2.json()["data"]
    assert len(items) >= 2
    assert any(s.get("current") for s in items)
    other = next(s for s in items if not s.get("current"))
    revoked = await ac.delete(f"/api/v1/auth/sessions/{other['id']}", headers=h2)
    assert revoked.status_code == 200, revoked.text
    revoked_refresh = await ac.post("/api/v1/auth/refresh", json={"refresh_token": new_refresh})
    assert revoked_refresh.status_code == 401

    # Idle logout ends the current session
    idle = await ac.post("/api/v1/auth/idle-logout", headers=h2, json={})
    assert idle.status_code == 200, idle.text
    after = await ac.get("/api/v1/me", headers=h2)
    assert after.status_code == 401


def test_br_19_and_plan_synced():
    br = (ROOT / "docs" / "BUSINESS_REQUIREMENTS_DOCUMENT.md").read_text(encoding="utf-8")
    s191 = br.split("#### BR-19.1 Authentication")[1].split("#### BR-19.2")[0]
    assert "[x] Email/password login with bcrypt hashing" in s191
    assert "[x] Password complexity requirements" in s191
    assert "[x] Account lockout after 5 failed attempts" in s191
    assert "[x] Email verification before first login" in s191
    assert "[x] Password reset via secure token link" in s191
    assert "Stage 19 U1" in s191

    s192 = br.split("#### BR-19.2 Two-Factor Authentication")[1].split("#### BR-19.3")[0]
    assert "[x] Optional TOTP-based 2FA" in s192
    assert "[x] QR code setup for 2FA" in s192
    assert "[x] Backup recovery codes" in s192
    assert "[x] Enforce 2FA for Super Admin and Company Admin roles" in s192
    assert "Stage 19 U1" in s192

    s193 = br.split("#### BR-19.3 Session Management")[1].split("#### BR-20.1")[0].split("### 4.20")[0]
    assert "[x] JWT token with configurable expiry" in s193
    assert "[x] Refresh token rotation" in s193
    assert "[x] View active sessions per user" in s193
    assert "[x] Remote session termination" in s193
    assert "[x] Auto-logout on inactivity" in s193
    assert "Stage 19 U1" in s193

    plan = (ROOT / "docs" / "STAGE_19_PLAN.md").read_text(encoding="utf-8")
    u1_line = [ln for ln in plan.splitlines() if "| **U1**" in ln][0]
    assert "COMPLETE" in u1_line
    assert "test_auth_session_br19_u1.py" in plan
