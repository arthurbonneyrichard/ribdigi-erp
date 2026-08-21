"""WebAuthnRegisterVerify.name ∈ PasskeyNameValue OpenAPI (BR-19 / WebAuthn)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import PasskeyNameValue, WebAuthnRegisterVerify
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_name = TypeAdapter(PasskeyNameValue)


def test_passkey_name_value_schema():
    assert _name.validate_python("  Laptop Key  ") == "Laptop Key"
    assert _name.validate_python("YubiKey-5") == "YubiKey-5"
    for bad in ("", " ", "!!!", "http://evil", "@@", "   "):
        with pytest.raises(ValidationError):
            _name.validate_python(bad)

    omit = WebAuthnRegisterVerify.model_validate({"credential": {"id": "x"}})
    assert omit.name is None
    ok = WebAuthnRegisterVerify.model_validate(
        {"credential": {"id": "x"}, "name": "  Tip-236 Key  "}
    )
    assert ok.name == "Tip-236 Key"
    with pytest.raises(ValidationError):
        WebAuthnRegisterVerify.model_validate(
            {"credential": {"id": "x"}, "name": "!!!"}
        )
    with pytest.raises(ValidationError):
        WebAuthnRegisterVerify.model_validate(
            {"credential": {"id": "x"}, "name": ""}
        )
    with pytest.raises(ValidationError):
        WebAuthnRegisterVerify.model_validate(
            {"credential": {"id": "x"}, "name": "http://evil.example"}
        )


def test_passkey_name_ui_and_docs():
    page = (ROOT / "frontend/app/security/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Passkey name"' in page
    assert 'aria-label="Add passkey"' in page
    assert "passkeyName.trim() ? passkeyName.trim() : null" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Passkey name OpenAPI" in agents
    assert "PasskeyNameValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "PasskeyNameValue" in docs
    assert "Passkey name" in docs


@pytest.mark.asyncio
async def test_passkey_name_api_blank_invalid_422(client):
    ac, _seed = client
    headers = await auth_headers(
        ac, email="admin@alpha.example.com", tenant_slug="alpha"
    )

    for bad in ("", "!!!", "http://evil.example/p", "@@"):
        r = await ac.post(
            "/api/v1/auth/webauthn/register/verify",
            headers=headers,
            json={"credential": {"id": "not-a-real-cred"}, "name": bad},
        )
        assert r.status_code == 422, (bad, r.text)

    # omit name → schema OK; registration fails later on bogus credential (not 422)
    omit = await ac.post(
        "/api/v1/auth/webauthn/register/verify",
        headers=headers,
        json={"credential": {"id": "not-a-real-cred"}},
    )
    assert omit.status_code != 422, omit.text

    hello = await ac.post(
        "/api/v1/auth/webauthn/register/verify",
        headers=headers,
        json={
            "credential": {"id": "not-a-real-cred"},
            "name": "  Tip236 Hello Key  ",
        },
    )
    assert hello.status_code != 422, hello.text
