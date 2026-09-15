"""Company SMS auth_token ∈ TwilioAuthTokenValue OpenAPI honesty (BR-15.2)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import SmsSettingsUpdate, TwilioAuthTokenValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_token = TypeAdapter(TwilioAuthTokenValue)


def test_twilio_auth_token_value_schema():
    assert _token.validate_python("  Tip94Token!  ") == "Tip94Token!"
    assert _token.validate_python("a" * 128) == "a" * 128
    for bad in ("", " ", "!!!", "http://evil", "a@b", "tok en", "a" * 129):
        with pytest.raises(ValidationError):
            _token.validate_python(bad)

    omit = SmsSettingsUpdate.model_validate({})
    assert omit.auth_token is None
    ok = SmsSettingsUpdate.model_validate({"auth_token": "  secretTok1  "})
    assert ok.auth_token == "secretTok1"
    with pytest.raises(ValidationError):
        SmsSettingsUpdate.model_validate({"auth_token": ""})
    with pytest.raises(ValidationError):
        SmsSettingsUpdate.model_validate({"auth_token": "!!!"})
    with pytest.raises(ValidationError):
        SmsSettingsUpdate.model_validate({"auth_token": "http://twilio.example"})


def test_sms_settings_auth_token_ui_and_docs():
    page = (ROOT / "frontend/app/company/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Company SMS auth token"' in page
    assert "trimmedToken" in page
    assert 'aria-label="Save SMS settings"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Company SMS auth_token OpenAPI" in agents
    assert "TwilioAuthTokenValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "TwilioAuthTokenValue" in docs
    assert "Company SMS auth token" in docs


@pytest.mark.asyncio
async def test_sms_settings_auth_token_api_blank_invalid_422(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )

    for bad in ("", "!!!", "http://twilio.example", "a@b", "tok en"):
        r = await ac.patch(
            "/api/v1/settings/sms",
            headers=admin,
            json={"auth_token": bad},
        )
        assert r.status_code == 422, (bad, r.text)

    ok = await ac.patch(
        "/api/v1/settings/sms",
        headers=admin,
        json={
            "account_sid": "ACtip243",
            "auth_token": "Tip243Token!",
            "from_number": "+233241111555",
        },
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["account_sid"] == "ACtip243"
    assert ok.json()["data"]["has_auth_token"] is True
    # Token never echoed
    assert "auth_token" not in ok.json()["data"]

    omit = await ac.patch(
        "/api/v1/settings/sms",
        headers=admin,
        json={"from_number": "+233241111666"},
    )
    assert omit.status_code == 200, omit.text
    assert omit.json()["data"]["has_auth_token"] is True
    assert omit.json()["data"]["from_number"] == "+233241111666"
