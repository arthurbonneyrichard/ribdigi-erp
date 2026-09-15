"""Company email settings SMTP host OpenAPI honesty (BR-20.3)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import EmailSettingsUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_email_settings_smtp_host_schema():
    omit = EmailSettingsUpdate.model_validate({})
    assert omit.host is None
    ok = EmailSettingsUpdate.model_validate({"host": "  SMTP.Example.COM  "})
    assert ok.host == "smtp.example.com"
    local = EmailSettingsUpdate.model_validate({"host": "localhost"})
    assert local.host == "localhost"
    ip = EmailSettingsUpdate.model_validate({"host": "127.0.0.1"})
    assert ip.host == "127.0.0.1"
    for bad in (
        "",
        " ",
        "not a host",
        "http://smtp.example.com",
        "smtp://smtp.example.com",
        "user@smtp.example.com",
        "...",
        "-bad-.com",
    ):
        with pytest.raises(ValidationError):
            EmailSettingsUpdate.model_validate({"host": bad})


def test_email_settings_smtp_host_ui_and_docs():
    page = (ROOT / "frontend/app/company/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Company SMTP host"' in page
    assert "Omit blank host" in page or "trimmedHost" in page
    assert 'aria-label="Save email settings"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Company SMTP host OpenAPI" in agents
    assert "SmtpHostValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "SmtpHostValue" in docs
    assert "Company SMTP host" in docs


@pytest.mark.asyncio
async def test_email_settings_smtp_host_api_blank_invalid_422(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )

    blank = await ac.patch(
        "/api/v1/settings/email",
        headers=admin,
        json={"host": ""},
    )
    assert blank.status_code == 422, blank.text

    garbage = await ac.patch(
        "/api/v1/settings/email",
        headers=admin,
        json={"host": "not a host"},
    )
    assert garbage.status_code == 422, garbage.text

    urlish = await ac.patch(
        "/api/v1/settings/email",
        headers=admin,
        json={"host": "http://smtp.example.com"},
    )
    assert urlish.status_code == 422, urlish.text

    ok = await ac.patch(
        "/api/v1/settings/email",
        headers=admin,
        json={
            "host": "smtp.example.com",
            "port": 587,
            "from_email": "noreply@example.com",
            "from_name": "Alpha ERP",
            "use_tls": True,
            "use_ssl": False,
        },
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["host"] == "smtp.example.com"

    omit = await ac.patch(
        "/api/v1/settings/email",
        headers=admin,
        json={"from_name": "Alpha ERP Host Keep"},
    )
    assert omit.status_code == 200, omit.text
    assert omit.json()["data"]["host"] == "smtp.example.com"
    assert omit.json()["data"]["from_name"] == "Alpha ERP Host Keep"
