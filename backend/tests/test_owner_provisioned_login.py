"""Accounts created by a signed-in platform owner can sign in immediately."""

from __future__ import annotations

import pyotp
import pytest

from tests.conftest import auth_headers


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


def _tenant_body(slug: str, email: str) -> dict:
    return {
        "company_name": f"Company {slug}",
        "slug": slug,
        "industry": "retail",
        "currency": "GHS",
        "admin_email": email,
        "admin_password": "SecurePass123!",
    }


async def _login(ac, *, email: str, slug: str):
    return await ac.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SecurePass123!", "tenant_id": slug},
    )


@pytest.mark.asyncio
async def test_unauthenticated_tenant_create_is_rejected(client):
    ac, _seed = client
    created = await ac.post("/api/v1/tenants", json=_tenant_body("public-co", "admin@public-co.example"))
    assert created.status_code == 401, created.text


@pytest.mark.asyncio
async def test_platform_console_admin_must_verify_email(client):
    ac, seed = client
    headers = await _super(ac, seed)
    created = await ac.post(
        "/api/v1/tenants",
        headers=headers,
        json=_tenant_body("owner-co", "admin@owner-co.example"),
    )
    assert created.status_code == 200, created.text
    assert created.json()["data"]["admin_email_verified"] is False
    assert "email" in created.json()["data"]

    blocked = await _login(ac, email="admin@owner-co.example", slug="owner-co")
    assert blocked.status_code == 403, blocked.text

    opened = await ac.post("/api/v1/tenants/owner-co/verify-admin", headers=headers)
    assert opened.status_code == 200, opened.text
    login = await _login(ac, email="admin@owner-co.example", slug="owner-co")
    assert login.status_code == 200, login.text


@pytest.mark.asyncio
async def test_company_token_cannot_create_tenant(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    created = await ac.post(
        "/api/v1/tenants",
        headers=headers,
        json=_tenant_body("shop-co", "admin@shop-co.example"),
    )
    assert created.status_code == 403, created.text


@pytest.mark.asyncio
async def test_verify_admin_unlocks_existing_company(client):
    ac, seed = client
    headers = await _super(ac, seed)
    created = await ac.post(
        "/api/v1/tenants",
        headers=headers,
        json=_tenant_body("old-co", "admin@old-co.example"),
    )
    assert created.status_code == 200, created.text
    blocked = await _login(ac, email="admin@old-co.example", slug="old-co")
    assert blocked.status_code == 403

    opened = await ac.post("/api/v1/tenants/old-co/verify-admin", headers=headers)
    assert opened.status_code == 200, opened.text
    assert opened.json()["data"]["newly_verified"] == 1

    login = await _login(ac, email="admin@old-co.example", slug="old-co")
    assert login.status_code == 200, login.text


@pytest.mark.asyncio
async def test_admin_created_user_can_sign_in(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    created = await ac.post(
        "/api/v1/users",
        headers=headers,
        json={
            "email": "newclerk@alpha.example.com",
            "full_name": "New Clerk",
            "password": "SecurePass123!",
            "role": "cashier",
        },
    )
    assert created.status_code == 200, created.text
    assert created.json()["data"]["user"]["email_verified"] is True

    login = await _login(ac, email="newclerk@alpha.example.com", slug="alpha")
    assert login.status_code == 200, login.text


@pytest.mark.asyncio
async def test_confirm_email_unlocks_existing_user(client, db_session):
    ac, seed = client
    user = seed["u1"]
    user.email_verified = False
    await db_session.commit()

    blocked = await _login(ac, email="cashier@alpha.example.com", slug="alpha")
    assert blocked.status_code == 403, blocked.text

    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    opened = await ac.post(f"/api/v1/users/{user.id}/confirm-email", headers=headers)
    assert opened.status_code == 200, opened.text

    login = await _login(ac, email="cashier@alpha.example.com", slug="alpha")
    assert login.status_code == 200, login.text
