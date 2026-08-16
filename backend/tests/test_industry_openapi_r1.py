"""Tenant industry OpenAPI Literal (BR-1.2)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas import TenantCreate, TenantProfileUpdate
from app.tenants import VALID_INDUSTRIES, coerce_industry_value, normalize_industry

ROOT = Path(__file__).resolve().parents[2]


def test_industry_literal_schema():
    ok = TenantCreate.model_validate(
        {
            "company_name": "Acme",
            "slug": "acme-lit",
            "industry": "Wholesale",
            "admin_email": "a@example.com",
            "admin_password": "SecurePass123!",
        }
    )
    assert ok.industry == "wholesale"
    defaulted = TenantCreate.model_validate(
        {
            "company_name": "Beta",
            "slug": "beta-lit",
            "admin_email": "b@example.com",
            "admin_password": "SecurePass123!",
        }
    )
    assert defaulted.industry == "retail"

    with pytest.raises(ValidationError):
        TenantCreate.model_validate(
            {
                "company_name": "x",
                "slug": "x",
                "industry": "",
                "admin_email": "x@example.com",
                "admin_password": "SecurePass123!",
            }
        )
    with pytest.raises(ValidationError):
        TenantCreate.model_validate(
            {
                "company_name": "x",
                "slug": "x",
                "industry": "   ",
                "admin_email": "x@example.com",
                "admin_password": "SecurePass123!",
            }
        )
    with pytest.raises(ValidationError):
        TenantCreate.model_validate(
            {
                "company_name": "x",
                "slug": "x",
                "industry": "spaceships",
                "admin_email": "x@example.com",
                "admin_password": "SecurePass123!",
            }
        )

    bare = TenantProfileUpdate.model_validate({})
    assert bare.industry is None
    with pytest.raises(ValidationError):
        TenantProfileUpdate.model_validate({"industry": ""})
    with pytest.raises(ValidationError):
        TenantProfileUpdate.model_validate({"industry": "bogus"})
    patched = TenantProfileUpdate.model_validate({"industry": "PHARMACY"})
    assert patched.industry == "pharmacy"


def test_coerce_and_normalize_industry_defense():
    assert coerce_industry_value("  Mart ") == "mart"
    assert coerce_industry_value("") == ""
    assert coerce_industry_value(None) is None
    assert normalize_industry("Retail") == "retail"
    for item in sorted(VALID_INDUSTRIES):
        assert normalize_industry(item) == item


def test_industry_ui_and_docs():
    company = (ROOT / "frontend/app/company/page.tsx").read_text(encoding="utf-8")
    assert "tenant.industry" in company
    for value in (
        "retail",
        "mart",
        "pharmacy",
        "restaurant",
        "bakery",
        "wholesale",
        "manufacturing",
    ):
        assert f"'{value}'" in company or f'"{value}"' in company
    api = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "industry" in api
    assert "Literal" in api
    assert "422" in api
