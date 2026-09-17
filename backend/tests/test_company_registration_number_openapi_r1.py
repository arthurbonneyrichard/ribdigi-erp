"""TenantProfileUpdate.registration_number OpenAPI honesty (Company registration)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import TenantProfileUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_tenant_profile_registration_number_schema():
    omit = TenantProfileUpdate.model_validate({})
    assert omit.registration_number is None
    ok = TenantProfileUpdate.model_validate(
        {"registration_number": "  CS123456789  "}
    )
    assert ok.registration_number == "CS123456789"
    spaced = TenantProfileUpdate.model_validate(
        {"registration_number": "CS-123 456"}
    )
    assert spaced.registration_number == "CS-123 456"
    for bad in ("", " ", "!!!", "---", "http://reg.example", "reg@x", "!!bad!!"):
        with pytest.raises(ValidationError):
            TenantProfileUpdate.model_validate({"registration_number": bad})


def test_company_registration_number_ui_and_docs():
    page = (ROOT / "frontend/app/company/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Company registration number"' in page
    assert "Omit blank registration" in page or "RegistrationNumberValue" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Company registration_number OpenAPI" in agents
    assert "RegistrationNumberValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "RegistrationNumberValue" in docs
    assert "Company registration number" in docs


@pytest.mark.asyncio
async def test_company_registration_number_api_blank_invalid_422(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )

    blank = await ac.patch(
        "/api/v1/tenants/me",
        headers=admin,
        json={"registration_number": ""},
    )
    assert blank.status_code == 422, blank.text

    garbage = await ac.patch(
        "/api/v1/tenants/me",
        headers=admin,
        json={"registration_number": "!!!"},
    )
    assert garbage.status_code == 422, garbage.text

    urlish = await ac.patch(
        "/api/v1/tenants/me",
        headers=admin,
        json={"registration_number": "http://reg.example"},
    )
    assert urlish.status_code == 422, urlish.text

    ok = await ac.patch(
        "/api/v1/tenants/me",
        headers=admin,
        json={"registration_number": "CS123456789"},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["registration_number"] == "CS123456789"

    keep = await ac.patch(
        "/api/v1/tenants/me",
        headers=admin,
        json={"company_name": seed["t1"].company_name},
    )
    assert keep.status_code == 200, keep.text
    assert keep.json()["data"]["registration_number"] == "CS123456789"
