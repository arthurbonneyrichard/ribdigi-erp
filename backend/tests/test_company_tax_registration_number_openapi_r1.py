"""TenantProfileUpdate.tax_registration_number OpenAPI honesty (Company TIN/VAT)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import TenantProfileUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_tenant_profile_tax_registration_number_schema():
    omit = TenantProfileUpdate.model_validate({})
    assert omit.tax_registration_number is None
    ok = TenantProfileUpdate.model_validate(
        {"tax_registration_number": "  C0001234567  "}
    )
    assert ok.tax_registration_number == "C0001234567"
    spaced = TenantProfileUpdate.model_validate(
        {"tax_registration_number": "C00-123 456"}
    )
    assert spaced.tax_registration_number == "C00-123 456"
    for bad in ("", " ", "!!!", "---", "http://tin.example", "tin@x", "!!bad!!"):
        with pytest.raises(ValidationError):
            TenantProfileUpdate.model_validate({"tax_registration_number": bad})


def test_company_tax_registration_number_ui_and_docs():
    page = (ROOT / "frontend/app/company/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="TIN / VAT registration number"' in page
    assert "TaxRegistrationNumberValue" in page or "Omit blank TIN" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Company tax_registration_number OpenAPI" in agents
    assert "TaxRegistrationNumberValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "TaxRegistrationNumberValue" in docs
    assert "TIN / VAT registration number" in docs


@pytest.mark.asyncio
async def test_company_tax_registration_number_api_blank_invalid_422(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )

    blank = await ac.patch(
        "/api/v1/tenants/me",
        headers=admin,
        json={"tax_registration_number": ""},
    )
    assert blank.status_code == 422, blank.text

    garbage = await ac.patch(
        "/api/v1/tenants/me",
        headers=admin,
        json={"tax_registration_number": "!!!"},
    )
    assert garbage.status_code == 422, garbage.text

    urlish = await ac.patch(
        "/api/v1/tenants/me",
        headers=admin,
        json={"tax_registration_number": "http://tin.example"},
    )
    assert urlish.status_code == 422, urlish.text

    ok = await ac.patch(
        "/api/v1/tenants/me",
        headers=admin,
        json={"tax_registration_number": "C0001234567"},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["tax_registration_number"] == "C0001234567"

    keep = await ac.patch(
        "/api/v1/tenants/me",
        headers=admin,
        json={"company_name": seed["t1"].company_name},
    )
    assert keep.status_code == 200, keep.text
    assert keep.json()["data"]["tax_registration_number"] == "C0001234567"
