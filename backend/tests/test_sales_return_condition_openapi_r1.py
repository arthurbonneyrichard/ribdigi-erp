"""Sales return items[].condition OpenAPI Literal (BR-7.5)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas import SalesReturnItemCreate

ROOT = Path(__file__).resolve().parents[2]


def test_sales_return_condition_literal_schema():
    ok = SalesReturnItemCreate.model_validate(
        {"product_id": "p", "quantity": 1, "condition": "discard"}
    )
    assert ok.condition == "discard"
    with pytest.raises(ValidationError):
        SalesReturnItemCreate.model_validate({"product_id": "p", "quantity": 1})
    with pytest.raises(ValidationError):
        SalesReturnItemCreate.model_validate(
            {"product_id": "p", "quantity": 1, "condition": ""}
        )
    with pytest.raises(ValidationError):
        SalesReturnItemCreate.model_validate(
            {"product_id": "p", "quantity": 1, "condition": "broken"}
        )


def test_sales_return_condition_ui_and_docs():
    sales = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert "Select condition" in sales
    api = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "condition" in api and "422" in api
    assert "Literal" in api or "omit/blank/invalid → **422**" in api
