"""TenantProfileUpdate address fields OpenAPI honesty (Company HQ/billing/shipping)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import TenantProfileUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_tenant_profile_address_schema():
    omit = TenantProfileUpdate.model_validate({})
    assert omit.address is None
    assert omit.billing_address is None
    assert omit.shipping_address is None
    ok = TenantProfileUpdate.model_validate(
        {
            "address": "  1 HQ Road, Accra  ",
            "billing_address": "  2 Billing Ave  ",
            "shipping_address": "  3 Warehouse Gate  ",
        }
    )
    assert ok.address == "1 HQ Road, Accra"
    assert ok.billing_address == "2 Billing Ave"
    assert ok.shipping_address == "3 Warehouse Gate"
    for field in ("address", "billing_address", "shipping_address"):
        for bad in ("", " ", "!!!", "---", "http://addr.example", "ops@example.com"):
            with pytest.raises(ValidationError):
                TenantProfileUpdate.model_validate({field: bad})


def test_company_address_ui_and_docs():
    page = (ROOT / "frontend/app/company/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Company headquarters address"' in page
    assert 'aria-label="Company billing address"' in page
    assert 'aria-label="Company shipping address"' in page
    assert "AddressValue" in page or "Omit blank HQ address" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Company address OpenAPI" in agents
    assert "AddressValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "AddressValue" in docs
    assert "Company headquarters address" in docs


@pytest.mark.asyncio
async def test_company_address_api_blank_invalid_422(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )

    for field in ("address", "billing_address", "shipping_address"):
        blank = await ac.patch(
            "/api/v1/tenants/me",
            headers=admin,
            json={field: ""},
        )
        assert blank.status_code == 422, blank.text

        garbage = await ac.patch(
            "/api/v1/tenants/me",
            headers=admin,
            json={field: "!!!"},
        )
        assert garbage.status_code == 422, garbage.text

        urlish = await ac.patch(
            "/api/v1/tenants/me",
            headers=admin,
            json={field: "http://addr.example"},
        )
        assert urlish.status_code == 422, urlish.text

    ok = await ac.patch(
        "/api/v1/tenants/me",
        headers=admin,
        json={
            "address": "1 Headquarters Road, Accra",
            "billing_address": "2 Billing Avenue, Accra",
            "shipping_address": "3 Warehouse Gate, Tema",
        },
    )
    assert ok.status_code == 200, ok.text
    data = ok.json()["data"]
    assert data["address"] == "1 Headquarters Road, Accra"
    assert data["billing_address"] == "2 Billing Avenue, Accra"
    assert data["shipping_address"] == "3 Warehouse Gate, Tema"

    keep = await ac.patch(
        "/api/v1/tenants/me",
        headers=admin,
        json={"company_name": seed["t1"].company_name},
    )
    assert keep.status_code == 200, keep.text
    kept = keep.json()["data"]
    assert kept["address"] == "1 Headquarters Road, Accra"
    assert kept["billing_address"] == "2 Billing Avenue, Accra"
    assert kept["shipping_address"] == "3 Warehouse Gate, Tema"
