"""Company email settings from_name OpenAPI honesty (BR-20.3)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import EmailSettingsUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_email_settings_from_name_schema():
    omit = EmailSettingsUpdate.model_validate({})
    assert omit.from_name is None
    ok = EmailSettingsUpdate.model_validate({"from_name": "  Acme ERP  "})
    assert ok.from_name == "Acme ERP"
    for bad in ("", " ", "!!!", "---", "http://mail.example", "ops@example.com"):
        with pytest.raises(ValidationError):
            EmailSettingsUpdate.model_validate({"from_name": bad})


def test_email_settings_from_name_ui_and_docs():
    page = (ROOT / "frontend/app/company/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Company from name"' in page
    assert "trimmedFromName" in page
    assert 'aria-label="Save email settings"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Company SMTP from_name OpenAPI" in agents
    assert "SmtpFromNameValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "SmtpFromNameValue" in docs
    assert "Company from name" in docs


@pytest.mark.asyncio
async def test_email_settings_from_name_api_blank_invalid_422(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )

    blank = await ac.patch(
        "/api/v1/settings/email",
        headers=admin,
        json={"from_name": ""},
    )
    assert blank.status_code == 422, blank.text

    garbage = await ac.patch(
        "/api/v1/settings/email",
        headers=admin,
        json={"from_name": "!!!"},
    )
    assert garbage.status_code == 422, garbage.text

    urlish = await ac.patch(
        "/api/v1/settings/email",
        headers=admin,
        json={"from_name": "http://mail.example"},
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
    assert ok.json()["data"]["from_name"] == "Alpha ERP"

    omit = await ac.patch(
        "/api/v1/settings/email",
        headers=admin,
        json={"use_tls": True},
    )
    assert omit.status_code == 200, omit.text
    assert omit.json()["data"]["from_name"] == "Alpha ERP"

    rename = await ac.patch(
        "/api/v1/settings/email",
        headers=admin,
        json={"from_name": "  Alpha ERP Mail  "},
    )
    assert rename.status_code == 200, rename.text
    assert rename.json()["data"]["from_name"] == "Alpha ERP Mail"
