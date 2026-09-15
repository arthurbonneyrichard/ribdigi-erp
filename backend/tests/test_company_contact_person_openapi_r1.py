"""TenantProfileUpdate.contact_person OpenAPI honesty (Company contact person)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import TenantProfileUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_tenant_profile_contact_person_schema():
    omit = TenantProfileUpdate.model_validate({})
    assert omit.contact_person is None
    ok = TenantProfileUpdate.model_validate({"contact_person": "  Ama Mensah  "})
    assert ok.contact_person == "Ama Mensah"
    for bad in ("", " ", "!!!", "---", "http://person.example", "ops@example.com"):
        with pytest.raises(ValidationError):
            TenantProfileUpdate.model_validate({"contact_person": bad})


def test_company_contact_person_ui_and_docs():
    page = (ROOT / "frontend/app/company/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Company contact person"' in page
    assert "Omit blank contact" in page or "ContactPersonValue" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Company contact_person OpenAPI" in agents
    assert "ContactPersonValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "ContactPersonValue" in docs
    assert "Company contact person" in docs


@pytest.mark.asyncio
async def test_company_contact_person_api_blank_invalid_422(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )

    blank = await ac.patch(
        "/api/v1/tenants/me",
        headers=admin,
        json={"contact_person": ""},
    )
    assert blank.status_code == 422, blank.text

    garbage = await ac.patch(
        "/api/v1/tenants/me",
        headers=admin,
        json={"contact_person": "!!!"},
    )
    assert garbage.status_code == 422, garbage.text

    urlish = await ac.patch(
        "/api/v1/tenants/me",
        headers=admin,
        json={"contact_person": "http://person.example"},
    )
    assert urlish.status_code == 422, urlish.text

    ok = await ac.patch(
        "/api/v1/tenants/me",
        headers=admin,
        json={"contact_person": "Ama Mensah"},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["contact_person"] == "Ama Mensah"

    keep = await ac.patch(
        "/api/v1/tenants/me",
        headers=admin,
        json={"company_name": seed["t1"].company_name},
    )
    assert keep.status_code == 200, keep.text
    assert keep.json()["data"]["contact_person"] == "Ama Mensah"
