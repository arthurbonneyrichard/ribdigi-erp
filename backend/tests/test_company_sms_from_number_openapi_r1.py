"""Company SMS from_number / SmsTestRequest.to OpenAPI honesty (BR-15.2)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import E164PhoneValue, SmsSettingsUpdate, SmsTestRequest
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_e164_phone_schema():
    adapter = TypeAdapter(E164PhoneValue)
    assert adapter.validate_python(" +233241111111 ") == "+233241111111"
    assert adapter.validate_python("00233241111111") == "+233241111111"
    for bad in ("", " ", "not-a-phone", "123", "241111111", "+123"):
        with pytest.raises(ValidationError):
            adapter.validate_python(bad)


def test_sms_settings_from_number_schema():
    ok = SmsSettingsUpdate.model_validate({"from_number": " +15551234567 "})
    assert ok.from_number == "+15551234567"
    omit = SmsSettingsUpdate.model_validate({})
    assert omit.from_number is None
    with pytest.raises(ValidationError):
        SmsSettingsUpdate.model_validate({"from_number": ""})
    with pytest.raises(ValidationError):
        SmsSettingsUpdate.model_validate({"from_number": "not-a-phone"})
    with pytest.raises(ValidationError):
        SmsSettingsUpdate.model_validate({"from_number": "123"})
    with pytest.raises(ValidationError):
        SmsSettingsUpdate.model_validate({"from_number": "+15551234567", "bogus": True})

    with pytest.raises(ValidationError):
        SmsTestRequest.model_validate({"to": ""})
    with pytest.raises(ValidationError):
        SmsTestRequest.model_validate({"to": "abc"})
    test_ok = SmsTestRequest.model_validate({"to": "+233200000001"})
    assert test_ok.to == "+233200000001"


def test_sms_from_number_ui_and_docs():
    page = (ROOT / "frontend/app/company/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Company SMS from number"' in page
    assert 'aria-label="Save SMS settings"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Company SMS from_number OpenAPI" in agents
    assert "E164PhoneValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "SmsSettingsUpdate" in docs
    assert "E164PhoneValue" in docs


@pytest.mark.asyncio
async def test_sms_from_number_api_blank_invalid_422(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )

    blank = await ac.patch(
        "/api/v1/settings/sms",
        headers=admin,
        json={"from_number": ""},
    )
    assert blank.status_code == 422, blank.text

    garbage = await ac.patch(
        "/api/v1/settings/sms",
        headers=admin,
        json={"from_number": "not-a-phone"},
    )
    assert garbage.status_code == 422, garbage.text

    short = await ac.patch(
        "/api/v1/settings/sms",
        headers=admin,
        json={"from_number": "123"},
    )
    assert short.status_code == 422, short.text

    no_plus = await ac.patch(
        "/api/v1/settings/sms",
        headers=admin,
        json={"from_number": "233241111111"},
    )
    assert no_plus.status_code == 422, no_plus.text

    extra = await ac.patch(
        "/api/v1/settings/sms",
        headers=admin,
        json={"from_number": "+233241111111", "unknown": 1},
    )
    assert extra.status_code == 422, extra.text

    ok = await ac.patch(
        "/api/v1/settings/sms",
        headers=admin,
        json={
            "account_sid": "ACtip73",
            "auth_token": "Tip73Token!",
            "from_number": "+233241111222",
        },
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["from_number"] == "+233241111222"

    omit = await ac.patch(
        "/api/v1/settings/sms",
        headers=admin,
        json={"account_sid": "ACtip73b"},
    )
    assert omit.status_code == 200, omit.text
    assert omit.json()["data"]["from_number"] == "+233241111222"

    test_bad = await ac.post(
        "/api/v1/settings/sms/test",
        headers=admin,
        json={"to": "not-a-phone"},
    )
    assert test_bad.status_code == 422, test_bad.text
