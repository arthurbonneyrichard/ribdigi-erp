"""BR-19.1: email verification required before login."""

from __future__ import annotations

import pytest

from app import models as m
from app.security import hash_password
from app.rbac import permissions_for_role
from tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_login_blocked_until_email_verified(client, db_session):
    ac, seed = client
    tenant = seed["t1"]

    user = m.User(
        tenant_id=tenant.id,
        email="unverified@alpha.example.com",
        full_name="Unverified User",
        password_hash=hash_password("SecurePass123!"),
        role="cashier",
        email_verified=False,
        permissions=permissions_for_role("cashier"),
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()

    blocked = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": "unverified@alpha.example.com",
            "password": "SecurePass123!",
            "tenant_id": "alpha",
        },
    )
    assert blocked.status_code == 403, blocked.text
    detail = blocked.json()["detail"]
    assert detail["code"] == "EMAIL_NOT_VERIFIED"

    # Wrong password still 401 (no verification leak on bad password)
    bad = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": "unverified@alpha.example.com",
            "password": "WrongPass123!",
            "tenant_id": "alpha",
        },
    )
    assert bad.status_code == 401, bad.text

    resend = await ac.post(
        "/api/v1/auth/resend-verification",
        json={"email": "unverified@alpha.example.com", "tenant_id": "alpha"},
    )
    assert resend.status_code == 200, resend.text
    token = resend.json()["data"].get("email_verification_token")
    assert token

    verified = await ac.post("/api/v1/auth/verify-email", json={"token": token})
    assert verified.status_code == 200, verified.text
    assert verified.json()["data"]["verified"] is True

    ok = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": "unverified@alpha.example.com",
            "password": "SecurePass123!",
            "tenant_id": "alpha",
        },
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["access_token"]
    assert ok.json()["data"]["user"]["email_verified"] is True


@pytest.mark.asyncio
async def test_resend_verification_tenant_isolation(client):
    ac, seed = client
    # Alpha user email must not trigger beta-tenant resend token for wrong tenant
    r = await ac.post(
        "/api/v1/auth/resend-verification",
        json={"email": "cashier@alpha.example.com", "tenant_id": "beta"},
    )
    assert r.status_code == 200, r.text
    # Cashier is already verified on alpha; on beta no such user → no token
    assert "email_verification_token" not in (r.json().get("data") or {})


@pytest.mark.asyncio
async def test_verified_seed_users_still_login(client):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    assert "Authorization" in headers
