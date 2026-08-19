"""Authenticated change-password (Stage 1 A2)."""

from __future__ import annotations

import pytest

from tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_change_password_requires_auth_and_current(client):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    unauth = await ac.post(
        "/api/v1/auth/change-password",
        json={"current_password": "SecurePass123!", "new_password": "NewerPass123!"},
    )
    assert unauth.status_code in {401, 403}

    bad = await ac.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={"current_password": "WrongPass123!", "new_password": "NewerPass123!"},
    )
    assert bad.status_code == 400, bad.text

    weak = await ac.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={"current_password": "SecurePass123!", "new_password": "short"},
    )
    assert weak.status_code == 400, weak.text

    ok = await ac.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={"current_password": "SecurePass123!", "new_password": "NewerPass123!"},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["changed"] is True

    # Old password no longer works
    old_login = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": "mgr@alpha.example.com",
            "password": "SecurePass123!",
            "tenant_id": "alpha",
        },
    )
    assert old_login.status_code == 401, old_login.text

    new_login = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": "mgr@alpha.example.com",
            "password": "NewerPass123!",
            "tenant_id": "alpha",
        },
    )
    assert new_login.status_code == 200, new_login.text

    # Restore for other tests in same DB session suite independence — each test gets fresh DB via fixture
