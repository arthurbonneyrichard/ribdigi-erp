"""LOGIN_2FA_ENABLED skips authenticator challenge at password login."""

from __future__ import annotations

import pyotp
import pytest

from app import totp as totp_svc
from tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_login_skips_2fa_when_disabled(client, monkeypatch):
    monkeypatch.setattr("app.config.settings.LOGIN_2FA_ENABLED", False)

    ac, _seeded = client
    # super@alpha has totp_enabled=True in seed data
    r = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": "super@alpha.example.com",
            "password": "SecurePass123!",
            "tenant_id": "alpha",
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data.get("requires_2fa") is not True
    assert data.get("access_token")
    assert data.get("must_enroll_2fa") is False


@pytest.mark.asyncio
async def test_login_challenges_2fa_when_enabled(client, monkeypatch):
    monkeypatch.setattr("app.config.settings.LOGIN_2FA_ENABLED", True)

    ac, seeded = client
    r = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": "super@alpha.example.com",
            "password": "SecurePass123!",
            "tenant_id": "alpha",
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["requires_2fa"] is True
    assert "totp" in data["methods"]
    assert data.get("challenge_token")

    code = pyotp.TOTP(seeded["super_totp_secret"]).now()
    done = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": "super@alpha.example.com",
            "password": "SecurePass123!",
            "tenant_id": "alpha",
            "totp_code": code,
        },
    )
    assert done.status_code == 200, done.text
    assert done.json()["data"].get("access_token")


@pytest.mark.asyncio
async def test_must_enroll_respects_login_2fa_flag(client, monkeypatch):
    monkeypatch.setattr("app.config.settings.LOGIN_2FA_ENABLED", False)

    ac, _seeded = client
    # company_admin without MFA — would be blocked when LOGIN_2FA_ENABLED=true
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    me = await ac.get("/api/v1/me", headers=headers)
    assert me.status_code == 200, me.text
    assert me.json()["data"].get("must_enroll_2fa") is False


def test_must_enroll_helper(monkeypatch):
    monkeypatch.setattr("app.config.settings.LOGIN_2FA_ENABLED", False)
    monkeypatch.setattr("app.config.settings.TOTP_ENFORCED_ROLES", "company_admin,super_admin")
    assert totp_svc.must_enroll_2fa("company_admin", has_mfa=False) is False
    monkeypatch.setattr("app.config.settings.LOGIN_2FA_ENABLED", True)
    assert totp_svc.must_enroll_2fa("company_admin", has_mfa=False) is True
    assert totp_svc.must_enroll_2fa("company_admin", has_mfa=True) is False
