"""Company SMS account_sid OpenAPI honesty (BR-15.2)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import SmsSettingsUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_sms_settings_account_sid_schema():
    omit = SmsSettingsUpdate.model_validate({})
    assert omit.account_sid is None
    ok = SmsSettingsUpdate.model_validate({"account_sid": "  ACtip73  "})
    assert ok.account_sid == "ACtip73"
    short = SmsSettingsUpdate.model_validate({"account_sid": "ACtenant"})
    assert short.account_sid == "ACtenant"
    for bad in ("", " ", "!!!", "---", "http://twilio.example", "AC with spaces", "AC@sid"):
        with pytest.raises(ValidationError):
            SmsSettingsUpdate.model_validate({"account_sid": bad})


def test_sms_settings_account_sid_ui_and_docs():
    page = (ROOT / "frontend/app/company/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Company SMS account SID"' in page
    assert "trimmedSid" in page
    assert 'aria-label="Save SMS settings"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Company SMS account_sid OpenAPI" in agents
    assert "TwilioAccountSidValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "TwilioAccountSidValue" in docs
    assert "Company SMS account SID" in docs


@pytest.mark.asyncio
async def test_sms_settings_account_sid_api_blank_invalid_422(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )

    blank = await ac.patch(
        "/api/v1/settings/sms",
        headers=admin,
        json={"account_sid": ""},
    )
    assert blank.status_code == 422, blank.text

    garbage = await ac.patch(
        "/api/v1/settings/sms",
        headers=admin,
        json={"account_sid": "!!!"},
    )
    assert garbage.status_code == 422, garbage.text

    urlish = await ac.patch(
        "/api/v1/settings/sms",
        headers=admin,
        json={"account_sid": "http://twilio.example"},
    )
    assert urlish.status_code == 422, urlish.text

    spaced = await ac.patch(
        "/api/v1/settings/sms",
        headers=admin,
        json={"account_sid": "AC with spaces"},
    )
    assert spaced.status_code == 422, spaced.text

    ok = await ac.patch(
        "/api/v1/settings/sms",
        headers=admin,
        json={
            "account_sid": "ACtip94",
            "auth_token": "Tip94Token!",
            "from_number": "+233241111333",
        },
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["account_sid"] == "ACtip94"

    omit = await ac.patch(
        "/api/v1/settings/sms",
        headers=admin,
        json={"from_number": "+233241111444"},
    )
    assert omit.status_code == 200, omit.text
    assert omit.json()["data"]["account_sid"] == "ACtip94"
    assert omit.json()["data"]["from_number"] == "+233241111444"
