"""Expense / recurring payment_method OpenAPI Literal (BR-9.2 / BR-9.5)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.expenses import (
    EXPENSE_PAYMENT_METHODS,
    coerce_expense_payment_method_value,
    normalize_expense_payment_method,
)
from app.schemas import (
    AiDocumentExpenseCreate,
    ExpenseCreate,
    ExpenseUpdate,
    RecurringExpenseCreate,
    RecurringExpenseUpdate,
)

ROOT = Path(__file__).resolve().parents[2]


def test_expense_payment_method_literal_schema():
    ok = ExpenseCreate.model_validate({"amount": 12.5, "payment_method": "Check"})
    assert ok.payment_method == "cheque"
    defaulted = ExpenseCreate.model_validate({"amount": 1})
    assert defaulted.payment_method == "cash"
    card = ExpenseCreate.model_validate({"amount": 1, "payment_method": "credit_card"})
    assert card.payment_method == "card"

    with pytest.raises(ValidationError):
        ExpenseCreate.model_validate({"amount": 1, "payment_method": ""})
    with pytest.raises(ValidationError):
        ExpenseCreate.model_validate({"amount": 1, "payment_method": "   "})
    with pytest.raises(ValidationError):
        ExpenseCreate.model_validate({"amount": 1, "payment_method": "crypto"})

    bare = ExpenseUpdate.model_validate({})
    assert bare.payment_method is None
    with pytest.raises(ValidationError):
        ExpenseUpdate.model_validate({"payment_method": ""})
    with pytest.raises(ValidationError):
        ExpenseUpdate.model_validate({"payment_method": "wallet"})

    ai = AiDocumentExpenseCreate.model_validate({"amount": 9, "payment_method": "BANK"})
    assert ai.payment_method == "bank_transfer"

    rec = RecurringExpenseCreate.model_validate({"amount": 5})
    assert rec.payment_method == "bank_transfer"
    with pytest.raises(ValidationError):
        RecurringExpenseCreate.model_validate({"amount": 5, "payment_method": "bogus"})
    with pytest.raises(ValidationError):
        RecurringExpenseUpdate.model_validate({"payment_method": ""})


def test_normalize_expense_payment_method_defense():
    assert coerce_expense_payment_method_value("  Debit Card ") == "card"
    assert coerce_expense_payment_method_value("") == ""
    assert normalize_expense_payment_method(None) == "cash"
    assert normalize_expense_payment_method(None, default="bank_transfer") == "bank_transfer"
    assert normalize_expense_payment_method("cheque") == "cheque"
    for item in sorted(EXPENSE_PAYMENT_METHODS):
        assert normalize_expense_payment_method(item) == item
    with pytest.raises(HTTPException) as ei:
        normalize_expense_payment_method("crypto")
    assert ei.value.status_code == 400
    with pytest.raises(HTTPException):
        normalize_expense_payment_method("")


def test_expense_payment_method_ui_and_docs():
    expenses = (ROOT / "frontend/app/expenses/page.tsx").read_text(encoding="utf-8")
    assert 'value="cash"' in expenses
    assert 'value="bank_transfer"' in expenses
    assert 'value="card"' in expenses
    assert 'value="cheque"' in expenses
    assert "paymentMethod" in expenses
    api = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "payment_method" in api
    assert 'Literal["cash","bank_transfer","card","cheque"]' in api
    assert "422" in api
