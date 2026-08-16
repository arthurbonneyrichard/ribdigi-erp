"""Company regional / tax format OpenAPI Literals (BR-20.2)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas import TenantProfileUpdate

ROOT = Path(__file__).resolve().parents[2]


def test_company_format_literal_schema():
    bare = TenantProfileUpdate.model_validate({})
    assert bare.tax_filing_period is None
    assert bare.date_format is None
    assert bare.decimal_separator is None
    assert bare.thousand_separator is None
    assert bare.time_format is None

    ok = TenantProfileUpdate.model_validate(
        {
            "tax_filing_period": "QUARTERLY",
            "date_format": " YYYY-MM-DD ",
            "decimal_separator": ",",
            "thousand_separator": "none",
            "time_format": "12H",
        }
    )
    assert ok.tax_filing_period == "quarterly"
    assert ok.date_format == "YYYY-MM-DD"
    assert ok.decimal_separator == ","
    assert ok.thousand_separator == ""
    assert ok.time_format == "12h"

    space = TenantProfileUpdate.model_validate({"thousand_separator": " "})
    assert space.thousand_separator == " "

    with pytest.raises(ValidationError):
        TenantProfileUpdate.model_validate({"tax_filing_period": ""})
    with pytest.raises(ValidationError):
        TenantProfileUpdate.model_validate({"tax_filing_period": "yearly"})
    with pytest.raises(ValidationError):
        TenantProfileUpdate.model_validate({"date_format": ""})
    with pytest.raises(ValidationError):
        TenantProfileUpdate.model_validate({"date_format": "YY/MM/DD"})
    with pytest.raises(ValidationError):
        TenantProfileUpdate.model_validate({"decimal_separator": ""})
    with pytest.raises(ValidationError):
        TenantProfileUpdate.model_validate({"decimal_separator": ";"})
    with pytest.raises(ValidationError):
        TenantProfileUpdate.model_validate({"thousand_separator": "apostrophe"})
    with pytest.raises(ValidationError):
        TenantProfileUpdate.model_validate({"time_format": ""})
    with pytest.raises(ValidationError):
        TenantProfileUpdate.model_validate({"time_format": "36h"})


def test_company_format_ui_and_docs():
    company = (ROOT / "frontend/app/company/page.tsx").read_text(encoding="utf-8")
    assert "tax_filing_period" in company
    assert 'value="monthly"' in company and 'value="quarterly"' in company
    assert "DD/MM/YYYY" in company and "MM/DD/YYYY" in company and "YYYY-MM-DD" in company
    assert "decimal_separator" in company and "thousand_separator" in company
    assert 'value="24h"' in company and 'value="12h"' in company
    api = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "tax_filing_period" in api
    assert "date_format" in api
    assert "422" in api
    assert "BR-20.2" in api
