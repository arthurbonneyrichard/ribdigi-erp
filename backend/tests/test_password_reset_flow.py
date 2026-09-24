"""Password reset request + confirm flow (BR-19.1)."""

from __future__ import annotations

import pytest

from app import emailer
from app.security import verify_password


@pytest.mark.asyncio
async def test_password_reset_request_unknown_is_neutral(client):
    ac, seed = client
    r = await ac.post(
        "/api/v1/auth/password-reset-request",
        json={"email": "nobody@example.com", "tenant_id": "alpha"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["success"] is True
    assert "if the account exists" in body["message"].lower()
    assert body["data"]["requested"] is True
    assert "reset_token" not in body["data"]


@pytest.mark.asyncio
async def test_password_reset_request_and_confirm(client, db_session, seeded):
    ac, seed = client
    emailer.clear_dev_outbox()
    email = "mgr@alpha.example.com"

    req = await ac.post(
        "/api/v1/auth/password-reset-request",
        json={"email": email, "tenant_id": "alpha"},
    )
    assert req.status_code == 200, req.text
    data = req.json()["data"]
    assert data["requested"] is True
    assert data.get("email", {}).get("sent") is True
    token = data.get("reset_token")
    assert token, "DEBUG/non-prod should echo reset_token for tests"
    outbox = emailer.get_dev_outbox()
    assert outbox
    assert token in outbox[0]["text_body"]
    assert "reset-password" in outbox[0]["text_body"]

    weak = await ac.post(
        "/api/v1/auth/password-reset",
        json={"token": token, "new_password": "weak"},
    )
    assert weak.status_code == 400, weak.text

    new_password = "NewSecurePass99!"
    ok = await ac.post(
        "/api/v1/auth/password-reset",
        json={"token": token, "new_password": new_password},
    )
    assert ok.status_code == 200, ok.text

    # Token single-use
    again = await ac.post(
        "/api/v1/auth/password-reset",
        json={"token": token, "new_password": "AnotherSecure99!"},
    )
    assert again.status_code == 400, again.text

    login = await ac.post(
        "/api/v1/auth/login",
        json={"email": email, "password": new_password, "tenant_id": "alpha"},
    )
    assert login.status_code == 200, login.text
    assert login.json()["data"]["access_token"]

    # Restore original password for other tests sharing seed user
    from app.security import hash_password

    user = seed["mgr1"]
    user.password_hash = hash_password("SecurePass123!")
    await db_session.commit()
    assert verify_password("SecurePass123!", user.password_hash)
