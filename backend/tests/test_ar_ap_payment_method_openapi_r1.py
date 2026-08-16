"""AR/AP settlement payment_method OpenAPI Literal (BR-11)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas import (
    CustomerPaymentCreate,
    SalesReturnPost,
    SupplierPaymentCreate,
)

ROOT = Path(__file__).resolve().parents[2]


def test_ar_ap_payment_method_literal_schema():
    ok = CustomerPaymentCreate.model_validate(
        {"customer_id": "c1", "amount": 10, "payment_method": "Check"}
    )
    assert ok.payment_method == "cheque"
    defaulted = CustomerPaymentCreate.model_validate({"customer_id": "c1", "amount": 1})
    assert defaulted.payment_method == "cash"

    with pytest.raises(ValidationError):
        CustomerPaymentCreate.model_validate(
            {"customer_id": "c1", "amount": 1, "payment_method": ""}
        )
    with pytest.raises(ValidationError):
        CustomerPaymentCreate.model_validate(
            {"customer_id": "c1", "amount": 1, "payment_method": "crypto"}
        )

    ap = SupplierPaymentCreate.model_validate({"supplier_id": "s1", "amount": 5})
    assert ap.payment_method == "bank_transfer"
    ap_card = SupplierPaymentCreate.model_validate(
        {"supplier_id": "s1", "amount": 5, "payment_method": "credit_card"}
    )
    assert ap_card.payment_method == "card"
    with pytest.raises(ValidationError):
        SupplierPaymentCreate.model_validate(
            {"supplier_id": "s1", "amount": 5, "payment_method": "   "}
        )
    with pytest.raises(ValidationError):
        SupplierPaymentCreate.model_validate(
            {"supplier_id": "s1", "amount": 5, "payment_method": "wallet"}
        )

    ret = SalesReturnPost.model_validate({})
    assert ret.payment_method == "cash"
    with pytest.raises(ValidationError):
        SalesReturnPost.model_validate({"payment_method": "bogus"})


def test_ar_ap_payment_method_ui_and_docs():
    credit = (ROOT / "frontend/app/credit/page.tsx").read_text(encoding="utf-8")
    assert "payMethod" in credit
    assert 'value="cash"' in credit
    assert 'value="bank_transfer"' in credit
    assert 'value="card"' in credit
    assert 'value="cheque"' in credit
    assert "/customers/" in credit and "/payments" in credit
    assert "/suppliers/" in credit and "/payments" in credit
    api = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert 'Literal["cash","bank_transfer","card","cheque"]' in api
    assert "422" in api
    assert "/customers/{customer_id}/payments" in api
    assert "/suppliers/{supplier_id}/payments" in api
