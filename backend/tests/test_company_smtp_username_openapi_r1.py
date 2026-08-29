"""Company email settings SMTP username OpenAPI honesty (BR-20.3)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import EmailSettingsUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_email_settings_smtp_username_schema():
    omit = EmailSettingsUpdate.model_validate({})
    assert omit.username is None
    ok = EmailSettingsUpdate.model_validate({"username": "  smtp-user  "})
    assert ok.username == "smtp-user"
    emailish = EmailSettingsUpdate.model_validate(
        {"username": "  ops@smtp.example.com  "}
    )
    assert emailish.username == "ops@smtp.example.com"
    for bad in ("", " ", "!!!", "---", "http://smtp.example.com", "ftp://x"):
        with pytest.raises(ValidationError):
            EmailSettingsUpdate.model_validate({"username": bad})


def test_email_settings_smtp_username_ui_and_docs():
    page = (ROOT / "frontend/app/company/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Company SMTP username"' in page
    assert "trimmedUser" in page
    assert 'aria-label="Save email settings"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Company SMTP username OpenAPI" in agents
    assert "SmtpUsernameValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "SmtpUsernameValue" in docs
    assert "Company SMTP username" in docs


@pytest.mark.asyncio
async def test_email_settings_smtp_username_api_blank_invalid_422(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )

    blank = await ac.patch(
        "/api/v1/settings/email",
        headers=admin,
        json={"username": ""},
    )
    assert blank.status_code == 422, blank.text

    garbage = await ac.patch(
        "/api/v1/settings/email",
        headers=admin,
        json={"username": "!!!"},
    )
    assert garbage.status_code == 422, garbage.text

    urlish = await ac.patch(
        "/api/v1/settings/email",
        headers=admin,
        json={"username": "http://smtp.example.com"},
    )
    assert urlish.status_code == 422, urlish.text

    ok = await ac.patch(
        "/api/v1/settings/email",
        headers=admin,
        json={
            "host": "smtp.example.com",
            "port": 587,
            "username": "alpha",
            "from_email": "noreply@example.com",
            "from_name": "Alpha ERP",
            "use_tls": True,
            "use_ssl": False,
        },
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["username"] == "alpha"

    emailish = await ac.patch(
        "/api/v1/settings/email",
        headers=admin,
        json={"username": "ops@smtp.example.com"},
    )
    assert emailish.status_code == 200, emailish.text
    assert emailish.json()["data"]["username"] == "ops@smtp.example.com"

    omit = await ac.patch(
        "/api/v1/settings/email",
        headers=admin,
        json={"use_tls": True},
    )
    assert omit.status_code == 200, omit.text
    assert omit.json()["data"]["username"] == "ops@smtp.example.com"
