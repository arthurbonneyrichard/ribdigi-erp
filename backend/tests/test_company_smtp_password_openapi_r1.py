"""Company SMTP password ∈ SmtpPasswordValue OpenAPI honesty (BR-20.3)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import EmailSettingsUpdate, SmtpPasswordValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_password = TypeAdapter(SmtpPasswordValue)


def test_smtp_password_value_schema():
    assert _password.validate_python("  Tip245Pass!  ") == "Tip245Pass!"
    assert _password.validate_python("a" * 128) == "a" * 128
    for bad in ("", " ", "!!!", "http://evil", "a@b", "pass word", "a" * 129):
        with pytest.raises(ValidationError):
            _password.validate_python(bad)

    omit = EmailSettingsUpdate.model_validate({})
    assert omit.password is None
    ok = EmailSettingsUpdate.model_validate({"password": "  secretPass1  "})
    assert ok.password == "secretPass1"
    with pytest.raises(ValidationError):
        EmailSettingsUpdate.model_validate({"password": ""})
    with pytest.raises(ValidationError):
        EmailSettingsUpdate.model_validate({"password": "!!!"})
    with pytest.raises(ValidationError):
        EmailSettingsUpdate.model_validate({"password": "http://smtp.example"})


def test_email_settings_password_ui_and_docs():
    page = (ROOT / "frontend/app/company/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Company SMTP password"' in page
    assert "trimmedPassword" in page
    assert 'aria-label="Save email settings"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Company SMTP password OpenAPI" in agents
    assert "SmtpPasswordValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "SmtpPasswordValue" in docs
    assert "Company SMTP password" in docs


@pytest.mark.asyncio
async def test_email_settings_password_api_blank_invalid_422(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )

    for bad in ("", "!!!", "http://smtp.example", "a@b", "pass word"):
        r = await ac.patch(
            "/api/v1/settings/email",
            headers=admin,
            json={"password": bad},
        )
        assert r.status_code == 422, (bad, r.text)

    ok = await ac.patch(
        "/api/v1/settings/email",
        headers=admin,
        json={
            "host": "smtp.tip245.example.com",
            "username": "noreply@tip245.example.com",
            "password": "Tip245Pass!",
            "from_email": "noreply@tip245.example.com",
            "from_name": "Tip245 ERP",
            "port": 587,
            "use_tls": True,
            "use_ssl": False,
        },
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["host"] == "smtp.tip245.example.com"
    assert ok.json()["data"]["has_password"] is True
    # Password never echoed
    assert "password" not in ok.json()["data"]

    omit = await ac.patch(
        "/api/v1/settings/email",
        headers=admin,
        json={"from_name": "Tip245 Keep Password"},
    )
    assert omit.status_code == 200, omit.text
    assert omit.json()["data"]["has_password"] is True
    assert omit.json()["data"]["from_name"] == "Tip245 Keep Password"
