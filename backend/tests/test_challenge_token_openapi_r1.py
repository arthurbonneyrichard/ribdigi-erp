"""TwoFactorVerify / WebAuthn login challenge_token ∈ ChallengeTokenValue (BR-19)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import (
    ChallengeTokenValue,
    TwoFactorVerify,
    WebAuthnLoginOptions,
    WebAuthnLoginVerify,
)
from app.totp import create_challenge_token

ROOT = Path(__file__).resolve().parents[2]
_token = TypeAdapter(ChallengeTokenValue)


def test_challenge_token_value_schema():
    assert _token.validate_python("  Tip257.eyJhbGciOiJIUzI1NiIs  ") == "Tip257.eyJhbGciOiJIUzI1NiIs"
    assert _token.validate_python("a" * 2048) == "a" * 2048
    for bad in ("", " ", "!!!", "http://evil", "a@b", "tok en", "a" * 2049):
        with pytest.raises(ValidationError):
            _token.validate_python(bad)

    ok = TwoFactorVerify.model_validate(
        {"challenge_token": "  tip257-challenge-ok  ", "code": "123456"}
    )
    assert ok.challenge_token == "tip257-challenge-ok"
    assert (
        WebAuthnLoginOptions.model_validate(
            {"challenge_token": "  tip257-wa-opt  "}
        ).challenge_token
        == "tip257-wa-opt"
    )
    assert (
        WebAuthnLoginVerify.model_validate(
            {"challenge_token": "  tip257-wa-ver  ", "credential": {"id": "x"}}
        ).challenge_token
        == "tip257-wa-ver"
    )
    for bad in ("", "!!!", "http://evil", "a@b", "tok en"):
        with pytest.raises(ValidationError):
            TwoFactorVerify.model_validate({"challenge_token": bad, "code": "123456"})
        with pytest.raises(ValidationError):
            WebAuthnLoginOptions.model_validate({"challenge_token": bad})
    with pytest.raises(ValidationError):
        TwoFactorVerify.model_validate({"code": "123456"})


def test_challenge_token_ui_and_docs():
    page = (ROOT / "frontend/app/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="2FA challenge token"' in page
    assert "trimmedChallenge" in page
    assert page.count('aria-label="2FA challenge token"') == 1
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "2FA challenge token OpenAPI" in agents
    assert "ChallengeTokenValue" in agents
    assert agents.count("2FA challenge token OpenAPI") == 1
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "ChallengeTokenValue" in docs
    assert "2FA challenge token" in docs


@pytest.mark.asyncio
async def test_challenge_token_api_blank_invalid_422(client):
    ac, _seed = client

    for bad in ("", "!!!", "http://evil", "a@b", "tok en"):
        resp = await ac.post(
            "/api/v1/auth/2fa/verify",
            json={"challenge_token": bad, "code": "123456"},
        )
        assert resp.status_code == 422, (bad, resp.text)
        opt = await ac.post(
            "/api/v1/auth/webauthn/login/options",
            json={"challenge_token": bad},
        )
        assert opt.status_code == 422, (bad, opt.text)

    # well-shaped challenge → not schema 422 (may fail 401 if JWT invalid/expired)
    shaped = await ac.post(
        "/api/v1/auth/2fa/verify",
        json={
            "challenge_token": "  Tip257.not-a-real-jwt-but-shaped  ",
            "code": "123456",
        },
    )
    assert shaped.status_code != 422, shaped.text

    live = create_challenge_token(
        user_id="00000000-0000-0000-0000-000000000001",
        tenant_id="00000000-0000-0000-0000-000000000002",
        role="cashier",
    )
    live_resp = await ac.post(
        "/api/v1/auth/2fa/verify",
        json={"challenge_token": f"  {live}  ", "code": "123456"},
    )
    assert live_resp.status_code != 422, live_resp.text
