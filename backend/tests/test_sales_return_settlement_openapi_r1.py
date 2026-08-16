"""Sales return settlement_method OpenAPI Literal (BR-7.5)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas import SalesReturnPost

ROOT = Path(__file__).resolve().parents[2]


def test_sales_return_settlement_method_literal_schema():
    bare = SalesReturnPost.model_validate({})
    assert bare.settlement_method is None
    assert bare.payment_method == "cash"

    ok = SalesReturnPost.model_validate({"settlement_method": "ADJUST"})
    assert ok.settlement_method == "adjust"
    refund = SalesReturnPost.model_validate({"settlement_method": "refund"})
    assert refund.settlement_method == "refund"

    with pytest.raises(ValidationError):
        SalesReturnPost.model_validate({"settlement_method": ""})
    with pytest.raises(ValidationError):
        SalesReturnPost.model_validate({"settlement_method": "   "})
    with pytest.raises(ValidationError):
        SalesReturnPost.model_validate({"settlement_method": "credit"})
    with pytest.raises(ValidationError):
        SalesReturnPost.model_validate({"settlement_method": "bogus"})


def test_sales_return_settlement_ui_and_docs():
    sales = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert "settlement_method: 'adjust'" in sales
    assert "settlement_method: 'refund'" in sales
    assert "Post credit" in sales
    assert "Post + refund" in sales
    api = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "settlement_method" in api
    assert 'Literal["adjust","refund"]' in api
    assert "422" in api
