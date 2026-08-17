"""Company / tenant create currency ISO OpenAPI honesty (BR-2.6)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas import TenantCreate, TenantProfileUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_company_currency_schema():
    created = TenantCreate.model_validate(
        {
            "company_name": "Acme",
            "slug": "acme-cur",
            "admin_email": "a@example.com",
            "admin_password": "SecurePass123!",
            "currency": "usd",
        }
    )
    assert created.currency == "USD"

    defaulted = TenantCreate.model_validate(
        {
            "company_name": "Acme",
            "slug": "acme-cur2",
            "admin_email": "b@example.com",
            "admin_password": "SecurePass123!",
        }
    )
    assert defaulted.currency == "GHS"

    with pytest.raises(ValidationError):
        TenantCreate.model_validate(
            {
                "company_name": "Acme",
                "slug": "acme-bad",
                "admin_email": "c@example.com",
                "admin_password": "SecurePass123!",
                "currency": "",
            }
        )
    with pytest.raises(ValidationError):
        TenantCreate.model_validate(
            {
                "company_name": "Acme",
                "slug": "acme-bad2",
                "admin_email": "d@example.com",
                "admin_password": "SecurePass123!",
                "currency": "EURO",
            }
        )

    bare = TenantProfileUpdate.model_validate({})
    assert bare.currency is None
    ok = TenantProfileUpdate.model_validate({"currency": "  eur "})
    assert ok.currency == "EUR"
    with pytest.raises(ValidationError):
        TenantProfileUpdate.model_validate({"currency": ""})
    with pytest.raises(ValidationError):
        TenantProfileUpdate.model_validate({"currency": "US"})
    with pytest.raises(ValidationError):
        TenantProfileUpdate.model_validate({"currency": "XXXX"})


def test_company_currency_ui_and_docs():
    page = (ROOT / "frontend/app/company/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Company currency"' in page
    assert "'GHS'" in page and "'USD'" in page
    assert "Currency: {c}" in page
    assert 'placeholder="Currency"' not in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Company currency OpenAPI" in agents
    assert "CurrencyCodeValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "CurrencyCodeValue" in docs
    assert "Company **Currency** select" in docs


@pytest.mark.asyncio
async def test_company_currency_api_blank_invalid_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    blank = await ac.patch(
        "/api/v1/tenants/me",
        headers=headers,
        json={"currency": ""},
    )
    assert blank.status_code == 422, blank.text

    bad = await ac.patch(
        "/api/v1/tenants/me",
        headers=headers,
        json={"currency": "EURO"},
    )
    assert bad.status_code == 422, bad.text

    ok = await ac.patch(
        "/api/v1/tenants/me",
        headers=headers,
        json={"currency": "ghs"},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"].get("currency") == "GHS"

    # Restore a known base for other tests that assume GHS
    restore = await ac.patch(
        "/api/v1/tenants/me",
        headers=headers,
        json={"currency": "GHS"},
    )
    assert restore.status_code == 200, restore.text
