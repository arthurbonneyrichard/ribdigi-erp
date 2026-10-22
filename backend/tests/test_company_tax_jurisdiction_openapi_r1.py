"""TenantProfileUpdate.tax_jurisdiction OpenAPI (Company Tax jurisdiction select)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from app import tax_filings as tax_filings_svc
from app.schemas import TenantProfileUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_company_tax_jurisdiction_literal_schema():
    bare = TenantProfileUpdate.model_validate({})
    assert bare.tax_jurisdiction is None

    ok = TenantProfileUpdate.model_validate({"tax_jurisdiction": "  gh "})
    assert ok.tax_jurisdiction == "GH"

    for code in ("GH", "NG", "KE", "ZA", "TZ", "UG", "RW", "CI", "SN", "EG", "MA", "GB", "US", "AE", "IN", "CN"):
        assert code in tax_filings_svc.TAX_COUNTRY_CODES
        assert (
            TenantProfileUpdate.model_validate({"tax_jurisdiction": code}).tax_jurisdiction
            == code
        )

    with pytest.raises(ValidationError):
        TenantProfileUpdate.model_validate({"tax_jurisdiction": ""})
    with pytest.raises(ValidationError):
        TenantProfileUpdate.model_validate({"tax_jurisdiction": "   "})
    ng = TenantProfileUpdate.model_validate({"tax_jurisdiction": "ng"})
    assert ng.tax_jurisdiction == "NG"
    us = TenantProfileUpdate.model_validate({"tax_jurisdiction": "US"})
    assert us.tax_jurisdiction == "US"
    with pytest.raises(ValidationError):
        TenantProfileUpdate.model_validate({"tax_jurisdiction": "XX"})
    with pytest.raises(ValidationError):
        TenantProfileUpdate.model_validate({"tax_jurisdiction": "garbage"})


def test_company_tax_jurisdiction_ui_and_docs():
    page = (ROOT / "frontend/app/(dashboard)/company/page.tsx").read_text(encoding="utf-8")
    countries = (ROOT / "frontend/lib/taxCountries.ts").read_text(encoding="utf-8")
    assert 'aria-label="Tax jurisdiction"' in page
    assert 'aria-label="Save company profile"' in page
    assert "TAX_COUNTRIES" in page
    assert "Tax jurisdiction:" in page
    assert "Nigeria" in countries or "NG" in countries
    assert "placeholder=\"Tax jurisdiction" not in page
    assert "NG" in countries and "KE" in countries and "ZA" in countries
    assert "TZ" in countries and "UG" in countries and "RW" in countries
    assert "GB" in countries and "US" in countries and "AE" in countries
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Company tax_jurisdiction OpenAPI" in agents
    assert "TenantTaxJurisdictionValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "tax_jurisdiction" in docs
    assert "TenantTaxJurisdictionValue" in docs
    assert "Tax jurisdiction** select" in docs


@pytest.mark.asyncio
async def test_company_tax_jurisdiction_api_blank_invalid_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    blank = await ac.patch(
        "/api/v1/tenants/me",
        headers=headers,
        json={"tax_jurisdiction": ""},
    )
    assert blank.status_code == 422, blank.text

    bad = await ac.patch(
        "/api/v1/tenants/me",
        headers=headers,
        json={"tax_jurisdiction": "XX"},
    )
    assert bad.status_code == 422, bad.text

    ng = await ac.patch(
        "/api/v1/tenants/me",
        headers=headers,
        json={"tax_jurisdiction": "NG"},
    )
    assert ng.status_code == 200, ng.text
    assert ng.json()["data"].get("tax_jurisdiction") == "NG"

    omit = await ac.patch(
        "/api/v1/tenants/me",
        headers=headers,
        json={"company_name": "Alpha Company OpenAPI Juris"},
    )
    assert omit.status_code == 200, omit.text

    ok = await ac.patch(
        "/api/v1/tenants/me",
        headers=headers,
        json={"tax_jurisdiction": "gh"},
    )
    assert ok.status_code == 200, ok.text
    data = ok.json()["data"]
    assert data.get("tax_jurisdiction") == "GH"


def test_company_tax_countries_frontend_matches_backend():
    countries = (ROOT / "frontend/lib/taxCountries.ts").read_text(encoding="utf-8")
    fe = set(re.findall(r"code: '([A-Z]{2})'", countries))
    assert fe == set(tax_filings_svc.TAX_COUNTRY_CODES)
    assert "GH" in fe
    tax_page = (ROOT / "frontend/app/(dashboard)/tax/page.tsx").read_text(encoding="utf-8")
    assert "filing?.jurisdiction === 'GH'" in tax_page


@pytest.mark.asyncio
async def test_company_tax_jurisdiction_non_gh_uses_generic_filing(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    ke = await ac.patch(
        "/api/v1/tenants/me",
        headers=headers,
        json={"tax_jurisdiction": "KE"},
    )
    assert ke.status_code == 200, ke.text
    assert ke.json()["data"].get("tax_jurisdiction") == "KE"

    filing = await ac.get("/api/v1/reports/tax/filing", headers=headers)
    assert filing.status_code == 200, filing.text
    pack = filing.json()["data"]
    assert pack.get("jurisdiction") == "KE"
    assert pack.get("government") is None

    gh_export = await ac.get(
        "/api/v1/reports/export?report_type=tax_filing_gh&format=csv",
        headers=headers,
    )
    assert gh_export.status_code == 400, gh_export.text

    restore = await ac.patch(
        "/api/v1/tenants/me",
        headers=headers,
        json={"tax_jurisdiction": "GH"},
    )
    assert restore.status_code == 200, restore.text
    assert restore.json()["data"].get("tax_jurisdiction") == "GH"