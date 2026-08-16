"""Recurring expense frequency OpenAPI Literal (BR-9.5)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas import RecurringExpenseCreate, RecurringExpenseUpdate

ROOT = Path(__file__).resolve().parents[2]


def test_recurring_frequency_literal_create():
    ok = RecurringExpenseCreate.model_validate(
        {"amount": 10, "frequency": "weekly"}
    )
    assert ok.frequency == "weekly"
    defaulted = RecurringExpenseCreate.model_validate({"amount": 10})
    assert defaulted.frequency == "monthly"
    with pytest.raises(ValidationError):
        RecurringExpenseCreate.model_validate({"amount": 10, "frequency": ""})
    with pytest.raises(ValidationError):
        RecurringExpenseCreate.model_validate({"amount": 10, "frequency": "   "})
    with pytest.raises(ValidationError):
        RecurringExpenseCreate.model_validate({"amount": 10, "frequency": "biweekly"})


def test_recurring_frequency_literal_update():
    ok = RecurringExpenseUpdate.model_validate({"frequency": "yearly"})
    assert ok.frequency == "yearly"
    with pytest.raises(ValidationError):
        RecurringExpenseUpdate.model_validate({"frequency": "biweekly"})
    with pytest.raises(ValidationError):
        RecurringExpenseUpdate.model_validate({"frequency": ""})


def test_recurring_frequency_ui_and_docs():
    expenses = (ROOT / "frontend/app/expenses/page.tsx").read_text(encoding="utf-8")
    assert "recFrequency" in expenses
    assert "weekly" in expenses and "yearly" in expenses
    api = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "frequency" in api
    assert "Literal" in api or "omit/blank/invalid → **422**" in api
