"""Coded reason OpenAPI Literals (PR/SR create + stock adjust)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas import PurchaseReturnCreate, SalesReturnCreate, StockAdjust

ROOT = Path(__file__).resolve().parents[2]


def test_stock_adjust_reason_literal():
    ok = StockAdjust.model_validate({"quantity": -1, "reason": "damage"})
    assert ok.reason == "damage"
    with pytest.raises(ValidationError):
        StockAdjust.model_validate({"quantity": -1})
    with pytest.raises(ValidationError):
        StockAdjust.model_validate({"quantity": -1, "reason": ""})
    with pytest.raises(ValidationError):
        StockAdjust.model_validate({"quantity": -1, "reason": "   "})
    with pytest.raises(ValidationError):
        StockAdjust.model_validate({"quantity": -1, "reason": "adjustment"})


def test_purchase_return_reason_literal():
    base = {
        "goods_receipt_id": "g1",
        "items": [{"goods_receipt_item_id": "i1", "quantity": 1}],
    }
    ok = PurchaseReturnCreate.model_validate({**base, "reason": "damaged"})
    assert ok.reason == "damaged"
    with pytest.raises(ValidationError):
        PurchaseReturnCreate.model_validate(base)
    with pytest.raises(ValidationError):
        PurchaseReturnCreate.model_validate({**base, "reason": "   "})
    with pytest.raises(ValidationError):
        PurchaseReturnCreate.model_validate({**base, "reason": "not_a_reason"})


def test_sales_return_reason_literal():
    base = {
        "sales_invoice_id": "inv1",
        "items": [{"product_id": "p1", "quantity": 1, "condition": "discard"}],
    }
    ok = SalesReturnCreate.model_validate({**base, "reason": "defective"})
    assert ok.reason == "defective"
    with pytest.raises(ValidationError):
        SalesReturnCreate.model_validate(base)
    with pytest.raises(ValidationError):
        SalesReturnCreate.model_validate({**base, "reason": ""})
    with pytest.raises(ValidationError):
        SalesReturnCreate.model_validate({**base, "reason": "damaged_typo"})


def test_docs_mention_literal_422():
    api = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Literal" in api or "omit/blank/invalid → **422**" in api or "omit/blank/invalid → 422" in api
