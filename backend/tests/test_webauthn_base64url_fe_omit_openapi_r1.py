"""OpenAPI honesty tips #576–#580: WebAuthn Base64UrlValue + FE omit/trim."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import (
    Base64UrlValue,
    WebAuthnAssertionResponse,
    WebAuthnAttestationResponse,
    WebAuthnAuthenticationCredential,
    WebAuthnLoginVerify,
    WebAuthnRegisterVerify,
    WebAuthnRegistrationCredential,
)
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_b64 = TypeAdapter(Base64UrlValue)

_REG_CRED = {
    "id": "cred-id",
    "rawId": "cred-id",
    "type": "public-key",
    "response": {
        "clientDataJSON": "eyJ0eXBlIjoid2ViYXV0aG4uY3JlYXRlIn0",
        "attestationObject": "o2NmbXRkbm9uZWdhdHRTdG10oGhhdXRoRGF0YQ",
    },
}
_ASSERT_CRED = {
    "id": "cred-id",
    "rawId": "cred-id",
    "type": "public-key",
    "response": {
        "clientDataJSON": "eyJ0eXBlIjoid2ViYXV0aG4uZ2V0In0",
        "authenticatorData": "authenticator-data",
        "signature": "signature-bytes",
        "userHandle": None,
    },
}

_BAD_B64 = (
    "",
    " ",
    "!!!",
    "http://evil.example/x",
    "abc+def",
    "abc/def",
    "ab cd",
    "user@host",
)


def test_base64url_value_schema():
    assert _b64.validate_python("  eyJ0eXBlIg  ") == "eyJ0eXBlIg"
    assert _b64.validate_python("abc-_XYZ09") == "abc-_XYZ09"
    assert _b64.validate_python("YWJjZA==") == "YWJjZA=="
    assert _b64.validate_python("  padded==  ") == "padded=="
    for bad in _BAD_B64:
        with pytest.raises(ValidationError):
            _b64.validate_python(bad)

    WebAuthnAttestationResponse.model_validate(
        {
            "clientDataJSON": "eyJ0eXBlIjoid2ViYXV0aG4uY3JlYXRlIn0",
            "attestationObject": "o2NmbXRkbm9uZWdhdHRTdG10oGhhdXRoRGF0YQ",
        }
    )
    for field in ("clientDataJSON", "attestationObject"):
        for bad in ("", "!!!", "a+b", "http://x"):
            body = {
                "clientDataJSON": "x",
                "attestationObject": "y",
                field: bad,
            }
            with pytest.raises(ValidationError):
                WebAuthnAttestationResponse.model_validate(body)

    WebAuthnAssertionResponse.model_validate(
        {
            "clientDataJSON": "eyJ0eXBlIjoid2ViYXV0aG4uZ2V0In0",
            "authenticatorData": "authenticator-data",
            "signature": "signature-bytes",
        }
    )
    for field in ("clientDataJSON", "authenticatorData", "signature"):
        for bad in ("", "!!!", "a/b", "http://x"):
            body = {
                "clientDataJSON": "x",
                "authenticatorData": "y",
                "signature": "z",
                field: bad,
            }
            with pytest.raises(ValidationError):
                WebAuthnAssertionResponse.model_validate(body)

    ok_uh = WebAuthnAssertionResponse.model_validate(
        {
            "clientDataJSON": "x",
            "authenticatorData": "y",
            "signature": "z",
            "userHandle": "dXNlci1oYW5kbGU",
        }
    )
    assert ok_uh.userHandle == "dXNlci1oYW5kbGU"
    omit_uh = WebAuthnAssertionResponse.model_validate(
        {
            "clientDataJSON": "x",
            "authenticatorData": "y",
            "signature": "z",
        }
    )
    assert omit_uh.userHandle is None
    for bad in ("", "!!!", "a+b"):
        with pytest.raises(ValidationError):
            WebAuthnAssertionResponse.model_validate(
                {
                    "clientDataJSON": "x",
                    "authenticatorData": "y",
                    "signature": "z",
                    "userHandle": bad,
                }
            )

    WebAuthnRegistrationCredential.model_validate(_REG_CRED)
    for field in ("id", "rawId"):
        with pytest.raises(ValidationError):
            WebAuthnRegistrationCredential.model_validate(
                {**_REG_CRED, field: "!!!"}
            )
        with pytest.raises(ValidationError):
            WebAuthnRegistrationCredential.model_validate(
                {**_REG_CRED, field: "a+b/c"}
            )

    WebAuthnAuthenticationCredential.model_validate(_ASSERT_CRED)
    with pytest.raises(ValidationError):
        WebAuthnAuthenticationCredential.model_validate(
            {**_ASSERT_CRED, "id": "http://evil"}
        )


def test_webauthn_base64url_fe_omit_ui_and_docs():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for title in (
        "WebAuthn Base64UrlValue OpenAPI",
        "WebAuthn assertion Base64Url OpenAPI",
        "WebAuthn credential id/rawId OpenAPI",
        "WebAuthn userHandle Base64Url OpenAPI",
        "Profile phone Save omit OpenAPI",
        "POS customer_name trim OpenAPI",
    ):
        assert title in agents, title
    assert "Base64UrlValue" in agents

    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Base64UrlValue" in docs
    assert "Save omits blank `phone`" in docs or "omits blank `phone`" in docs
    assert "name.trim() || null" in docs

    company = (ROOT / "frontend/app/company/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Profile phone for SMS test"' in company
    assert "const trimmedPhone = profilePhone.trim();" in company
    assert "if (trimmedPhone) body.phone = trimmedPhone;" in company
    assert "if (trimmedName) body.full_name = trimmedName;" in company

    pos = (ROOT / "frontend/app/pos/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="POS customer name"' in pos
    assert "customer_name: name.trim() || null" in pos

    sec = (ROOT / "frontend/app/security/page.tsx").read_text(encoding="utf-8")
    assert "bufferToBase64url" in sec or "credentialToJson" in sec


@pytest.mark.asyncio
async def test_webauthn_base64url_api_422(client):
    ac, _seed = client
    headers = await auth_headers(
        ac, email="admin@alpha.example.com", tenant_slug="alpha"
    )

    for field in ("clientDataJSON", "attestationObject"):
        bad_cred = {
            **_REG_CRED,
            "response": {**_REG_CRED["response"], field: "!!!"},
        }
        r = await ac.post(
            "/api/v1/auth/webauthn/register/verify",
            headers=headers,
            json={"credential": bad_cred},
        )
        assert r.status_code == 422, (field, r.text)

    for field in ("id", "rawId"):
        r = await ac.post(
            "/api/v1/auth/webauthn/register/verify",
            headers=headers,
            json={"credential": {**_REG_CRED, field: "a+b/c=="}},
        )
        assert r.status_code == 422, (field, r.text)

    # challenge_token must pass ChallengeTokenValue; use a plausible token shape
    challenge = "a." + ("b" * 20) + ".c"
    for field in ("clientDataJSON", "authenticatorData", "signature"):
        bad_assert = {
            **_ASSERT_CRED,
            "response": {**_ASSERT_CRED["response"], field: "http://evil"},
        }
        r = await ac.post(
            "/api/v1/auth/webauthn/login/verify",
            headers=headers,
            json={"challenge_token": challenge, "credential": bad_assert},
        )
        assert r.status_code == 422, (field, r.text)

    bad_uh = {
        **_ASSERT_CRED,
        "response": {**_ASSERT_CRED["response"], "userHandle": "!!!"},
    }
    r = await ac.post(
        "/api/v1/auth/webauthn/login/verify",
        headers=headers,
        json={"challenge_token": challenge, "credential": bad_uh},
    )
    assert r.status_code == 422, r.text

    # Schema-level sanity: register/login verify models accept good fixtures
    WebAuthnRegisterVerify.model_validate({"credential": _REG_CRED})
    WebAuthnLoginVerify.model_validate(
        {"challenge_token": challenge, "credential": _ASSERT_CRED}
    )
