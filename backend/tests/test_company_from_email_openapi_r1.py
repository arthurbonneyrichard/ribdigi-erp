"""Company email settings from_email OpenAPI honesty (BR-20.3)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import EmailSettingsUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_email_settings_from_email_schema():
    ok = EmailSettingsUpdate.model_validate({"from_email": "  ops@example.com  "})
    assert str(ok.from_email) == "ops@example.com"
    omit = EmailSettingsUpdate.model_validate({})
    assert omit.from_email is None
    with pytest.raises(ValidationError):
        EmailSettingsUpdate.model_validate({"from_email": ""})
    with pytest.raises(ValidationError):
        EmailSettingsUpdate.model_validate({"from_email": "not-an-email"})
    with pytest.raises(ValidationError):
        EmailSettingsUpdate.model_validate({"from_email": "ok@example.com", "bogus": True})


def test_email_settings_from_email_ui_and_docs():
    page = (ROOT / "frontend/app/company/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Company from email"' in page
    assert 'aria-label="Save email settings"' in page
    assert 'type="email"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Company from_email OpenAPI" in agents
    assert "EmailStr" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "EmailSettingsUpdate" in docs
    assert "from_email" in docs
    assert "EmailStr" in docs


@pytest.mark.asyncio
async def test_email_settings_from_email_api_blank_invalid_422(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )

    blank = await ac.patch(
        "/api/v1/settings/email",
        headers=admin,
        json={"from_email": ""},
    )
    assert blank.status_code == 422, blank.text

    garbage = await ac.patch(
        "/api/v1/settings/email",
        headers=admin,
        json={"from_email": "not-an-email"},
    )
    assert garbage.status_code == 422, garbage.text

    extra = await ac.patch(
        "/api/v1/settings/email",
        headers=admin,
        json={"from_email": "ok@example.com", "unknown": 1},
    )
    assert extra.status_code == 422, extra.text

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
    assert ok.json()["data"]["from_email"] == "noreply@example.com"

    omit = await ac.patch(
        "/api/v1/settings/email",
        headers=admin,
        json={"from_name": "Alpha ERP Updated"},
    )
    assert omit.status_code == 200, omit.text
    assert omit.json()["data"]["from_email"] == "noreply@example.com"
    assert omit.json()["data"]["from_name"] == "Alpha ERP Updated"
