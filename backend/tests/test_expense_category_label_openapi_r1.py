"""expense denormalized category ∈ ExpenseCategoryLabelValue OpenAPI (BR-9.2 / BR-9.5)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import (
    AiDocumentExpenseCreate,
    ExpenseCategoryLabelValue,
    ExpenseCreate,
    ExpenseUpdate,
    RecurringExpenseCreate,
    RecurringExpenseUpdate,
)
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_label = TypeAdapter(ExpenseCategoryLabelValue)


def test_expense_category_label_value_schema():
    assert _label.validate_python("  Travel  ") == "Travel"
    for bad in ("", " ", "!!!", "http://evil", "@@", "a" * 101):
        with pytest.raises(ValidationError):
            _label.validate_python(bad)

    ok = ExpenseCreate.model_validate({"amount": 10, "category": "  Misc  "})
    assert ok.category == "Misc"
    omit = ExpenseCreate.model_validate({"amount": 10})
    assert omit.category is None
    with pytest.raises(ValidationError):
        ExpenseCreate.model_validate({"amount": 10, "category": "!!!"})
    with pytest.raises(ValidationError):
        ExpenseCreate.model_validate({"amount": 10, "category": ""})

    assert RecurringExpenseCreate.model_validate({"amount": 5, "category": " Ops "}).category == "Ops"
    with pytest.raises(ValidationError):
        RecurringExpenseCreate.model_validate({"amount": 5, "category": "http://x"})

    assert AiDocumentExpenseCreate.model_validate({"amount": 3, "category": " AI "}).category == "AI"
    with pytest.raises(ValidationError):
        AiDocumentExpenseCreate.model_validate({"amount": 3, "category": "!!!"})

    patch_ok = ExpenseUpdate.model_validate({"category": " Renamed "})
    assert patch_ok.category == "Renamed"
    with pytest.raises(ValidationError):
        ExpenseUpdate.model_validate({"category": "  "})
    with pytest.raises(ValidationError):
        RecurringExpenseUpdate.model_validate({"category": "!!!"})


def test_expense_category_label_ui_and_docs():
    page = (ROOT / "frontend/app/expenses/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Expense spend category"' in page
    assert 'aria-label="Recurring expense category"' in page
    assert "category_id: categoryId || undefined" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Expense category label OpenAPI" in agents
    assert "ExpenseCategoryLabelValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "ExpenseCategoryLabelValue" in docs
    assert "Expense spend category" in docs


@pytest.mark.asyncio
async def test_expense_category_label_api_blank_invalid_422(client):
    ac, seed = client
    totp = pyotp.TOTP(seed["super_totp_secret"]).now()
    headers = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=totp
    )
    suffix = uuid4().hex[:8]

    for bad in ("!!!", "", "http://evil.example/p"):
        r = await ac.post(
            "/api/v1/expenses",
            headers=headers,
            json={"amount": 12.5, "category": bad, "description": f"TIP228 {suffix}"},
        )
        assert r.status_code == 422, (bad, r.text)

    hello = await ac.post(
        "/api/v1/expenses",
        headers=headers,
        json={
            "amount": 12.5,
            "category": f"  Tip228Cat {suffix}  ",
            "description": f"TIP228 OK {suffix}",
        },
    )
    assert hello.status_code == 200, hello.text
    assert hello.json()["data"]["category"] == f"Tip228Cat {suffix}"
    expense_id = hello.json()["data"]["id"]

    patch_bad = await ac.patch(
        f"/api/v1/expenses/{expense_id}",
        headers=headers,
        json={"category": "!!!"},
    )
    assert patch_bad.status_code == 422, patch_bad.text
