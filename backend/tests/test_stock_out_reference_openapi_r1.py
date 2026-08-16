"""Stock-out reference_type OpenAPI Literal (BR-5.2)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas import StockOut

ROOT = Path(__file__).resolve().parents[2]


def test_stock_out_reference_type_literal_schema():
    ok = StockOut.model_validate(
        {"product_id": "p", "quantity": 1, "reference_type": "sale"}
    )
    assert ok.reference_type == "sale"
    with pytest.raises(ValidationError):
        StockOut.model_validate({"product_id": "p", "quantity": 1})
    with pytest.raises(ValidationError):
        StockOut.model_validate(
            {"product_id": "p", "quantity": 1, "reference_type": "  "}
        )
    with pytest.raises(ValidationError):
        StockOut.model_validate(
            {"product_id": "p", "quantity": 1, "reference_type": "sales"}
        )


def test_stock_out_ui_and_docs_mention_literal():
    inv = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert "Select reference type" in inv
    api = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "StockOut" in api or "omit/blank/invalid → **422**" in api
    assert "reference_type" in api
