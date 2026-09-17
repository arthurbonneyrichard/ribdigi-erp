"""TenantCreate / TenantProfileUpdate.company_name OpenAPI honesty (trading name)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import TenantCreate, TenantProfileUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_tenant_company_name_schema():
    omit = TenantProfileUpdate.model_validate({})
    assert omit.company_name is None
    ok = TenantProfileUpdate.model_validate({"company_name": "  Acme Trading  "})
    assert ok.company_name == "Acme Trading"
    for bad in ("", " ", "!!!", "---", "X", "http://co.example", "ops@example.com"):
        with pytest.raises(ValidationError):
            TenantProfileUpdate.model_validate({"company_name": bad})

    create_ok = TenantCreate.model_validate(
        {
            "company_name": "  Beta Co  ",
            "slug": "beta-co",
            "admin_email": "admin@beta.example.com",
            "admin_password": "SecurePass123!",
        }
    )
    assert create_ok.company_name == "Beta Co"
    with pytest.raises(ValidationError):
        TenantCreate.model_validate(
            {
                "company_name": "!!!",
                "slug": "bad",
                "admin_email": "a@b.example.com",
                "admin_password": "SecurePass123!",
            }
        )


def test_company_trading_name_ui_and_docs():
    page = (ROOT / "frontend/app/company/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Company trading name"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Company company_name OpenAPI" in agents
    assert "CompanyNameValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "CompanyNameValue" in docs
    assert "Company trading name" in docs


@pytest.mark.asyncio
async def test_company_name_api_blank_invalid_422(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )

    blank = await ac.patch(
        "/api/v1/tenants/me",
        headers=admin,
        json={"company_name": ""},
    )
    assert blank.status_code == 422, blank.text

    short = await ac.patch(
        "/api/v1/tenants/me",
        headers=admin,
        json={"company_name": "X"},
    )
    assert short.status_code == 422, short.text

    garbage = await ac.patch(
        "/api/v1/tenants/me",
        headers=admin,
        json={"company_name": "!!!"},
    )
    assert garbage.status_code == 422, garbage.text

    urlish = await ac.patch(
        "/api/v1/tenants/me",
        headers=admin,
        json={"company_name": "http://co.example"},
    )
    assert urlish.status_code == 422, urlish.text

    ok = await ac.patch(
        "/api/v1/tenants/me",
        headers=admin,
        json={"company_name": "Alpha Trading"},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["company_name"] == "Alpha Trading"

    keep = await ac.patch(
        "/api/v1/tenants/me",
        headers=admin,
        json={"legal_name": "Alpha Holdings Limited"},
    )
    assert keep.status_code == 200, keep.text
    assert keep.json()["data"]["company_name"] == "Alpha Trading"
