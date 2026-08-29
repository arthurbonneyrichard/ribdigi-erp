"""TenantProfileUpdate.tax_jurisdiction OpenAPI (Company Tax jurisdiction select)."""

from __future__ import annotations

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

    for code in tax_filings_svc.SUPPORTED:
        assert (
            TenantProfileUpdate.model_validate({"tax_jurisdiction": code}).tax_jurisdiction
            == code
        )

    with pytest.raises(ValidationError):
        TenantProfileUpdate.model_validate({"tax_jurisdiction": ""})
    with pytest.raises(ValidationError):
        TenantProfileUpdate.model_validate({"tax_jurisdiction": "   "})
    with pytest.raises(ValidationError):
        TenantProfileUpdate.model_validate({"tax_jurisdiction": "NG"})
    with pytest.raises(ValidationError):
        TenantProfileUpdate.model_validate({"tax_jurisdiction": "US"})
    with pytest.raises(ValidationError):
        TenantProfileUpdate.model_validate({"tax_jurisdiction": "garbage"})


def test_company_tax_jurisdiction_ui_and_docs():
    page = (ROOT / "frontend/app/company/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Tax jurisdiction"' in page
    assert 'aria-label="Save company profile"' in page
    assert 'value="GH"' in page
    assert "Tax jurisdiction: GH" in page
    assert "placeholder=\"Tax jurisdiction" not in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Company tax_jurisdiction OpenAPI" in agents
    assert "TaxFilingJurisdictionValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "tax_jurisdiction" in docs
    assert "TaxFilingJurisdictionValue" in docs or "tax_filings.SUPPORTED" in docs
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
        json={"tax_jurisdiction": "NG"},
    )
    assert bad.status_code == 422, bad.text

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