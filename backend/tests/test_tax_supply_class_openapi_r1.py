"""Product tax_supply_class OpenAPI Literal (BR-5.1 / BR-12.1)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.schemas import ProductCreate, ProductUpdate
from app.tax import normalize_supply_class

ROOT = Path(__file__).resolve().parents[2]


def test_tax_supply_class_literal_schema():
    ok = ProductCreate.model_validate(
        {"name": "Export", "tax_supply_class": "zero_rated"}
    )
    assert ok.tax_supply_class == "zero_rated"
    defaulted = ProductCreate.model_validate({"name": "Widget"})
    assert defaulted.tax_supply_class == "standard"

    with pytest.raises(ValidationError):
        ProductCreate.model_validate({"name": "x", "tax_supply_class": ""})
    with pytest.raises(ValidationError):
        ProductCreate.model_validate({"name": "x", "tax_supply_class": "   "})
    with pytest.raises(ValidationError):
        ProductCreate.model_validate({"name": "x", "tax_supply_class": "taxable"})

    bare = ProductUpdate.model_validate({})
    assert bare.tax_supply_class is None
    with pytest.raises(ValidationError):
        ProductUpdate.model_validate({"tax_supply_class": ""})
    with pytest.raises(ValidationError):
        ProductUpdate.model_validate({"tax_supply_class": "gst"})


def test_normalize_supply_class_strict_rejects_garbage():
    assert normalize_supply_class("zero-rated") == "zero_rated"
    assert normalize_supply_class(None, tax_exempt=True) == "exempt"
    assert normalize_supply_class("bogus") == "standard"
    with pytest.raises(HTTPException) as ei:
        normalize_supply_class("bogus", strict=True)
    assert ei.value.status_code == 400
    with pytest.raises(HTTPException):
        normalize_supply_class("", strict=True)


def test_tax_supply_class_ui_and_docs():
    inventory = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert "productSupplyClass" in inventory
    assert 'value="zero_rated"' in inventory
    assert 'value="exempt"' in inventory
    assert "editSupplyClass" in inventory
    api = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "tax_supply_class" in api
    assert "Literal" in api
    assert "422" in api
