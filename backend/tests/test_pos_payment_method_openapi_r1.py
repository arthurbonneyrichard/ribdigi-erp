"""POS payment_method OpenAPI Literal (BR-8.1)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.pos import normalize_payment_method
from app.schemas import PosPaymentLine, PosSaleCreate

ROOT = Path(__file__).resolve().parents[2]


def test_pos_payment_method_literal_schema():
    ok = PosSaleCreate.model_validate(
        {
            "payment_method": "digital_wallet",
            "items": [{"product_id": "p1", "quantity": 1, "unit_price": 1}],
        }
    )
    assert ok.payment_method == "wallet"
    defaulted = PosSaleCreate.model_validate(
        {"items": [{"product_id": "p1", "quantity": 1, "unit_price": 1}]}
    )
    assert defaulted.payment_method == "cash"
    split = PosSaleCreate.model_validate(
        {
            "payment_method": "split",
            "payments": [
                {"payment_method": "cash", "amount": 1},
                {"payment_method": "card", "amount": 1},
            ],
            "items": [{"product_id": "p1", "quantity": 1, "unit_price": 1}],
        }
    )
    assert split.payment_method == "split"

    with pytest.raises(ValidationError):
        PosSaleCreate.model_validate(
            {
                "payment_method": "",
                "items": [{"product_id": "p1", "quantity": 1, "unit_price": 1}],
            }
        )
    with pytest.raises(ValidationError):
        PosSaleCreate.model_validate(
            {
                "payment_method": "bitcoin",
                "items": [{"product_id": "p1", "quantity": 1, "unit_price": 1}],
            }
        )
    with pytest.raises(ValidationError):
        PosPaymentLine.model_validate({"payment_method": "split", "amount": 1})
    with pytest.raises(ValidationError):
        PosPaymentLine.model_validate({"payment_method": "", "amount": 1})


def test_normalize_payment_method_strict_rejects_unknown():
    assert normalize_payment_method("MoMo") == "wallet"
    assert normalize_payment_method(None) == "cash"
    with pytest.raises(HTTPException) as ei:
        normalize_payment_method("weird")
    assert ei.value.status_code == 400
    with pytest.raises(HTTPException):
        normalize_payment_method("")
    assert normalize_payment_method("weird", strict=False) == "other"


def test_pos_payment_method_ui_and_docs():
    pos = (ROOT / "frontend/app/pos/page.tsx").read_text(encoding="utf-8")
    assert "paymentMethod" in pos
    assert 'value="wallet"' in pos
    assert 'value="credit"' in pos
    api = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "payment_method" in api
    assert "Literal" in api
    assert "422" in api
