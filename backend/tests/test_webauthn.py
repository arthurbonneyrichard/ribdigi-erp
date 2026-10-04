"""WebAuthn / passkey registration and login (crypto verify mocked)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.totp import create_challenge_token, path_allowed_during_enrollment
from tests.conftest import auth_headers


def test_enrollment_allows_webauthn_paths():
    assert path_allowed_during_enrollment("/api/v1/auth/webauthn/register/options") is True
    assert path_allowed_during_enrollment("/api/v1/auth/webauthn/register/verify") is True
    assert path_allowed_during_enrollment("/api/v1/auth/webauthn/credentials") is True
    assert path_allowed_during_enrollment("/api/v1/auth/webauthn/credentials/abc") is True


def test_challenge_token_is_mfa(monkeypatch):
    monkeypatch.setattr("app.totp.settings.JWT_SECRET_KEY", "unit-test-secret-key-32chars!!")
    token = create_challenge_token(user_id="u1", tenant_id="t1", role="cashier")
    from app.totp import decode_challenge_token

    data = decode_challenge_token(token)
    assert data["type"] == "mfa_challenge"


@pytest.mark.asyncio
async def test_webauthn_register_list_login_delete(client, monkeypatch):
    monkeypatch.setattr("app.webauthn_svc.settings.WEBAUTHN_RP_ID", "localhost")
    monkeypatch.setattr("app.webauthn_svc.settings.WEBAUTHN_ORIGIN", "http://localhost:3000")
    monkeypatch.setattr("app.config.settings.WEBAUTHN_RP_ID", "localhost")
    monkeypatch.setattr("app.config.settings.WEBAUTHN_ORIGIN", "http://localhost:3000")
    monkeypatch.setattr("app.config.settings.LOGIN_2FA_ENABLED", True)

    ac, seeded = client
    headers = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")

    opt = await ac.post("/api/v1/auth/webauthn/register/options", headers=headers, json={})
    assert opt.status_code == 200, opt.text
    options = opt.json()["data"]
    assert "challenge" in options
    assert options.get("rp", {}).get("id") == "localhost"

    fake_cred_id = b"\x11" * 32
    fake_pubkey = b"\x22" * 77
    fake_verification = SimpleNamespace(
        credential_id=fake_cred_id,
        credential_public_key=fake_pubkey,
        sign_count=0,
        credential_device_type="platform",
        credential_backed_up=True,
    )

    with patch("webauthn.verify_registration_response", return_value=fake_verification):
        verify = await ac.post(
            "/api/v1/auth/webauthn/register/verify",
            headers=headers,
            json={
                "name": "Laptop",
                "credential": {
                    "id": "ignored-by-mock",
                    "rawId": "ignored",
                    "type": "public-key",
                    "response": {
                        "clientDataJSON": "x",
                        "attestationObject": "y",
                        "transports": ["internal"],
                    },
                },
            },
        )
    assert verify.status_code == 200, verify.text
    cred = verify.json()["data"]
    assert cred["name"] == "Laptop"
    cred_pk = cred["id"]

    listed = await ac.get("/api/v1/auth/webauthn/credentials", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()["data"]) == 1

    status = await ac.get("/api/v1/auth/2fa/status", headers=headers)
    assert status.status_code == 200
    body = status.json()["data"]
    assert body["webauthn_enabled"] is True
    assert body["webauthn_count"] == 1
    assert "webauthn" in body["methods"]

    # Login should challenge for passkey
    login = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": "cashier@alpha.example.com",
            "password": "SecurePass123!",
            "tenant_id": "alpha",
        },
    )
    assert login.status_code == 200, login.text
    challenge = login.json()["data"]
    assert challenge["requires_2fa"] is True
    assert challenge["methods"] == ["webauthn"]
    challenge_token = challenge["challenge_token"]

    auth_opt = await ac.post(
        "/api/v1/auth/webauthn/login/options",
        json={"challenge_token": challenge_token},
    )
    assert auth_opt.status_code == 200, auth_opt.text
    assert "challenge" in auth_opt.json()["data"]

    from webauthn.helpers import bytes_to_base64url

    cred_id_b64 = bytes_to_base64url(fake_cred_id)
    fake_auth = SimpleNamespace(new_sign_count=3)

    with patch("webauthn.verify_authentication_response", return_value=fake_auth):
        done = await ac.post(
            "/api/v1/auth/webauthn/login/verify",
            json={
                "challenge_token": challenge_token,
                "credential": {
                    "id": cred_id_b64,
                    "rawId": cred_id_b64,
                    "type": "public-key",
                    "response": {
                        "clientDataJSON": "x",
                        "authenticatorData": "y",
                        "signature": "z",
                    },
                },
            },
        )
    assert done.status_code == 200, done.text
    tokens = done.json()["data"]
    assert tokens["access_token"]
    assert tokens["user"]["webauthn_enabled"] is True

    headers2 = {
        "Authorization": f"Bearer {tokens['access_token']}",
        "X-Tenant-ID": tokens["user"]["tenant_id"],
    }
    deleted = await ac.delete(f"/api/v1/auth/webauthn/credentials/{cred_pk}", headers=headers2)
    assert deleted.status_code == 200, deleted.text

    empty = await ac.get("/api/v1/auth/webauthn/credentials", headers=headers2)
    assert empty.json()["data"] == []


@pytest.mark.asyncio
async def test_login_options_requires_registered_passkey(client):
    ac, seeded = client
    # Manager has no passkeys — challenge token still needed but options should 400
    from app.totp import create_challenge_token

    token = create_challenge_token(
        user_id=seeded["mgr1"].id, tenant_id=seeded["t1"].id, role="store_manager"
    )
    r = await ac.post(
        "/api/v1/auth/webauthn/login/options",
        json={"challenge_token": token},
    )
    assert r.status_code == 400
