"""TwoFactorDisable.password ∈ TwoFactorDisablePasswordValue OpenAPI honesty (BR-19)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import TwoFactorDisable, TwoFactorDisablePasswordValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_password = TypeAdapter(TwoFactorDisablePasswordValue)


def test_two_factor_disable_password_value_schema():
    assert _password.validate_python("  Tip253Pass!  ") == "Tip253Pass!"
    assert _password.validate_python("a" * 128) == "a" * 128
    for bad in ("", " ", "!!!", "http://evil", "a@b", "pass word", "a" * 129):
        with pytest.raises(ValidationError):
            _password.validate_python(bad)

    ok = TwoFactorDisable.model_validate(
        {"password": "  SecurePass123!  ", "code": "123456"}
    )
    assert ok.password == "SecurePass123!"
    assert ok.code == "123456"
    for bad in ("", "!!!", "http://evil", "a@b", "pass word"):
        with pytest.raises(ValidationError):
            TwoFactorDisable.model_validate({"password": bad, "code": "123456"})
    with pytest.raises(ValidationError):
        TwoFactorDisable.model_validate({"code": "123456"})


def test_two_factor_disable_password_ui_and_docs():
    page = (ROOT / "frontend/app/security/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Disable 2FA password"' in page
    assert "trimmedPassword" in page
    assert 'aria-label="Disable 2FA"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "2FA disable password OpenAPI" in agents
    assert "TwoFactorDisablePasswordValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "TwoFactorDisablePasswordValue" in docs
    assert "Disable 2FA password" in docs


@pytest.mark.asyncio
async def test_two_factor_disable_password_api_blank_invalid_422(client):
    ac, _seed = client
    headers = await auth_headers(
        ac, email="admin@alpha.example.com", tenant_slug="alpha"
    )

    for bad in ("", "!!!", "http://evil", "a@b", "pass word"):
        resp = await ac.post(
            "/api/v1/auth/2fa/disable",
            headers=headers,
            json={"password": bad, "code": "123456"},
        )
        assert resp.status_code == 422, (bad, resp.text)

    # well-shaped password → not schema 422 (may fail 400/401 if 2FA off / wrong code)
    shaped = await ac.post(
        "/api/v1/auth/2fa/disable",
        headers=headers,
        json={"password": "  SecurePass123!  ", "code": "123456"},
    )
    assert shaped.status_code != 422, shaped.text
