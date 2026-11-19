"""Passwordless (fingerprint / passkey) admin sign-in: challenge rules, verifier settings, fallbacks.

Crypto verification is mocked; what is checked is everything around it: who gets a challenge, that user
verification is required, that RP id / origin reach the verifier, that challenges are single-use and expire,
and that password sign-in is untouched.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from webauthn.helpers import bytes_to_base64url

from tests.conftest import auth_headers

START = "/api/v1/auth/webauthn/passwordless/start"
VERIFY = "/api/v1/auth/webauthn/login/verify"
ADMIN = {"email": "admin@alpha.example.com", "tenant_id": "alpha"}


async def _register_admin_passkey(ac, monkeypatch):
    monkeypatch.setattr("app.webauthn_svc.settings.WEBAUTHN_RP_ID", "localhost")
    monkeypatch.setattr("app.webauthn_svc.settings.WEBAUTHN_ORIGIN", "http://localhost:3000")
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    opt = await ac.post(
        "/api/v1/auth/webauthn/register/options?platform=true", headers=headers, json={}
    )
    assert opt.status_code == 200, opt.text
    raw_id = b"\x33" * 32
    fake = SimpleNamespace(
        credential_id=raw_id,
        credential_public_key=b"\x44" * 77,
        sign_count=0,
        credential_device_type="platform",
        credential_backed_up=True,
    )
    with patch("webauthn.verify_registration_response", return_value=fake):
        r = await ac.post(
            "/api/v1/auth/webauthn/register/verify",
            headers=headers,
            json={
                "name": None,
                "credential": {
                    "id": "x",
                    "rawId": "x",
                    "type": "public-key",
                    "response": {
                        "clientDataJSON": "x",
                        "attestationObject": "y",
                        "transports": ["internal"],
                    },
                },
            },
        )
    assert r.status_code == 200, r.text
    return bytes_to_base64url(raw_id)


def _assertion(cred_id: str) -> dict:
    return {
        "id": cred_id,
        "rawId": cred_id,
        "type": "public-key",
        "response": {"clientDataJSON": "x", "authenticatorData": "y", "signature": "z"},
    }


async def _start(ac) -> str:
    r = await ac.post(START, json=ADMIN)
    assert r.status_code == 200, r.text
    return r.json()["data"]["challenge_token"]


@pytest.mark.asyncio
async def test_start_is_generic_for_unknown_no_passkey_and_non_admin(client):
    ac, _ = client
    bodies = (
        {"email": "nobody@alpha.example.com", "tenant_id": "alpha"},
        {"email": "admin@alpha.example.com", "tenant_id": "no-such-company"},
        ADMIN,  # admin without a passkey
        {"email": "cashier@alpha.example.com", "tenant_id": "alpha"},  # not an admin role
    )
    texts = set()
    for body in bodies:
        r = await ac.post(START, json=body)
        assert r.status_code == 401, r.text
        texts.add(r.text)
    assert len(texts) == 1  # same answer every time: nothing to enumerate


@pytest.mark.asyncio
async def test_login_requires_user_verification_and_issues_one_session(client, monkeypatch):
    ac, _ = client
    cred_id = await _register_admin_passkey(ac, monkeypatch)
    start = await ac.post(START, json=ADMIN)
    assert start.status_code == 200, start.text
    data = start.json()["data"]
    assert data["options"]["userVerification"] == "required"
    assert data["options"]["rpId"] == "localhost"
    assert data["options"]["allowCredentials"]
    token = data["challenge_token"]

    seen: dict = {}

    def fake_verify(**kwargs):
        seen.update(kwargs)
        return SimpleNamespace(new_sign_count=5)

    with patch("webauthn.verify_authentication_response", side_effect=fake_verify):
        done = await ac.post(VERIFY, json={"challenge_token": token, "credential": _assertion(cred_id)})
    assert done.status_code == 200, done.text
    assert done.json()["data"]["access_token"]
    assert seen["require_user_verification"] is True
    assert seen["expected_rp_id"] == "localhost"
    assert seen["expected_origin"] == "http://localhost:3000"

    # Single use: replaying the same challenge is refused and issues nothing.
    with patch("webauthn.verify_authentication_response", return_value=SimpleNamespace(new_sign_count=6)):
        again = await ac.post(VERIFY, json={"challenge_token": token, "credential": _assertion(cred_id)})
    assert again.status_code in (400, 401)
    assert "access_token" not in again.text


@pytest.mark.asyncio
async def test_bad_signature_origin_rp_and_unknown_credential_are_refused(client, monkeypatch):
    ac, _ = client
    cred_id = await _register_admin_passkey(ac, monkeypatch)
    for msg in ("Invalid signature", "Unexpected client data origin", "Unexpected RP ID hash"):
        token = await _start(ac)
        with patch("webauthn.verify_authentication_response", side_effect=ValueError(msg)):
            r = await ac.post(VERIFY, json={"challenge_token": token, "credential": _assertion(cred_id)})
        assert r.status_code == 401, r.text
        assert "access_token" not in r.text

    token = await _start(ac)
    r = await ac.post(VERIFY, json={"challenge_token": token, "credential": _assertion("QUJD" * 8)})
    assert r.status_code == 400  # a passkey this account never registered


@pytest.mark.asyncio
async def test_expired_challenge_is_refused(client, monkeypatch):
    ac, _ = client
    cred_id = await _register_admin_passkey(ac, monkeypatch)
    monkeypatch.setattr("app.webauthn_svc.CHALLENGE_TTL_MINUTES", -1)  # stored already expired
    token = await _start(ac)
    with patch("webauthn.verify_authentication_response", return_value=SimpleNamespace(new_sign_count=1)):
        r = await ac.post(VERIFY, json={"challenge_token": token, "credential": _assertion(cred_id)})
    assert r.status_code == 400
    assert "expired" in r.text.lower()


@pytest.mark.asyncio
async def test_password_login_still_works_when_the_user_has_a_passkey(client, monkeypatch):
    ac, _ = client
    await _register_admin_passkey(ac, monkeypatch)
    monkeypatch.setattr("app.config.settings.LOGIN_2FA_ENABLED", False)
    r = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": "admin@alpha.example.com",
            "password": "SecurePass123!",
            "tenant_id": "alpha",
            "portal": "admin",
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["access_token"]
