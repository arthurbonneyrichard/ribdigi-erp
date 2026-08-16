"""Tax pricing_mode / tax_type OpenAPI Literals (BR-12.1)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas import TaxCalculateRequest, TaxCreate, TaxUpdate

ROOT = Path(__file__).resolve().parents[2]


def test_tax_pricing_mode_and_type_literal_schema():
    ok = TaxCreate.model_validate(
        {"name": "VAT", "rate": 12.5, "tax_type": "gst", "pricing_mode": "inclusive"}
    )
    assert ok.tax_type == "gst"
    assert ok.pricing_mode == "inclusive"
    defaulted = TaxCreate.model_validate({"name": "Std", "rate": 10})
    assert defaulted.tax_type == "vat"
    assert defaulted.pricing_mode == "exclusive"

    with pytest.raises(ValidationError):
        TaxCreate.model_validate({"name": "x", "rate": 1, "pricing_mode": ""})
    with pytest.raises(ValidationError):
        TaxCreate.model_validate({"name": "x", "rate": 1, "pricing_mode": "gross"})
    with pytest.raises(ValidationError):
        TaxCreate.model_validate({"name": "x", "rate": 1, "tax_type": ""})
    with pytest.raises(ValidationError):
        TaxCreate.model_validate({"name": "x", "rate": 1, "tax_type": "VAT"})
    with pytest.raises(ValidationError):
        TaxCreate.model_validate({"name": "x", "rate": 1, "tax_type": "hst"})

    bare = TaxUpdate.model_validate({})
    assert bare.pricing_mode is None and bare.tax_type is None
    with pytest.raises(ValidationError):
        TaxUpdate.model_validate({"pricing_mode": ""})
    with pytest.raises(ValidationError):
        TaxUpdate.model_validate({"tax_type": "plaid"})

    calc = TaxCalculateRequest.model_validate({"amount": 100})
    assert calc.pricing_mode is None
    with pytest.raises(ValidationError):
        TaxCalculateRequest.model_validate({"amount": 100, "pricing_mode": ""})
    with pytest.raises(ValidationError):
        TaxCalculateRequest.model_validate({"amount": 100, "pricing_mode": "gross"})


def test_tax_pricing_mode_ui_and_docs():
    tax = (ROOT / "frontend/app/tax/page.tsx").read_text(encoding="utf-8")
    assert "pricingMode" in tax
    assert 'value="exclusive"' in tax
    assert 'value="inclusive"' in tax
    assert 'value="custom"' in tax
    assert 'value="vat"' in tax
    api = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "pricing_mode" in api
    assert "Literal" in api
    assert "422" in api
