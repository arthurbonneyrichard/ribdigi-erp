"""ExpenseCreate / ExpenseUpdate.expense_date OpenAPI honesty."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import ExpenseCreate, ExpenseUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_expense_date_schema():
    omit = ExpenseCreate.model_validate({"amount": 10})
    assert omit.expense_date is None
    ok = ExpenseCreate.model_validate({"amount": 10, "expense_date": " 2026-08-01 "})
    assert ok.expense_date == "2026-08-01"
    for bad in ("", " ", "not-a-date", "01/02/2024", "2026-13-01"):
        with pytest.raises(ValidationError):
            ExpenseCreate.model_validate({"amount": 10, "expense_date": bad})

    patch_omit = ExpenseUpdate.model_validate({})
    assert patch_omit.expense_date is None
    patch_ok = ExpenseUpdate.model_validate({"expense_date": "2026-08-10"})
    assert patch_ok.expense_date == "2026-08-10"
    with pytest.raises(ValidationError):
        ExpenseUpdate.model_validate({"expense_date": ""})
    with pytest.raises(ValidationError):
        ExpenseUpdate.model_validate({"expense_date": "not-a-date"})


def test_expense_date_ui_and_docs():
    page = (ROOT / "frontend/app/expenses/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Expense date"' in page
    assert 'aria-label="Expense OCR date"' in page
    assert "IsoDateQueryValue" in page or "expenseDate.trim() || null" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Expense expense_date OpenAPI" in agents
    assert "IsoDateQueryValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Expense date" in docs
    assert "Expense OCR date" in docs
    assert "IsoDateQueryValue" in docs


@pytest.mark.asyncio
async def test_expense_date_api_blank_invalid_422(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )

    cats = await ac.get("/api/v1/expenses/categories", headers=admin)
    assert cats.status_code == 200, cats.text
    cat_rows = cats.json().get("data") or []
    category = next((c for c in cat_rows if c.get("code") == "MISC"), cat_rows[0])
    category_id = category["id"]

    for bad in ("", "not-a-date", "01/02/2024"):
        resp = await ac.post(
            "/api/v1/expenses",
            headers=admin,
            json={
                "amount": 12.5,
                "category_id": category_id,
                "description": f"Bad date {uuid4().hex[:6]}",
                "expense_date": bad,
            },
        )
        assert resp.status_code == 422, (bad, resp.text)

    ok = await ac.post(
        "/api/v1/expenses",
        headers=admin,
        json={
            "amount": 12.5,
            "category_id": category_id,
            "description": f"Ok date {uuid4().hex[:6]}",
            "expense_date": "2026-08-01",
        },
    )
    assert ok.status_code == 200, ok.text
    expense = ok.json()["data"]
    assert str(expense["expense_date"]).startswith("2026-08-01")
    expense_id = expense["id"]

    # Pending expenses can be patched; if auto-approved under threshold, create another.
    if expense.get("status") == "approved":
        pending = await ac.post(
            "/api/v1/expenses",
            headers=admin,
            json={
                "amount": 5000,
                "category_id": category_id,
                "description": f"Pending date {uuid4().hex[:6]}",
                "expense_date": "2026-08-02",
            },
        )
        assert pending.status_code == 200, pending.text
        expense_id = pending.json()["data"]["id"]

    patch_bad = await ac.patch(
        f"/api/v1/expenses/{expense_id}",
        headers=admin,
        json={"expense_date": "!!!"},
    )
    assert patch_bad.status_code == 422, patch_bad.text

    patch_blank = await ac.patch(
        f"/api/v1/expenses/{expense_id}",
        headers=admin,
        json={"expense_date": ""},
    )
    assert patch_blank.status_code == 422, patch_blank.text

    patch_ok = await ac.patch(
        f"/api/v1/expenses/{expense_id}",
        headers=admin,
        json={"expense_date": "2026-08-15", "description": "date updated"},
    )
    assert patch_ok.status_code == 200, patch_ok.text
    assert str(patch_ok.json()["data"]["expense_date"]).startswith("2026-08-15")
