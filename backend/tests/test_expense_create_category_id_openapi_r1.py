"""ExpenseCreate.category_id ∈ UuidIdValue OpenAPI honesty (BR-9.2)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import ExpenseCreate, UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"


def test_expense_create_category_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    omit = ExpenseCreate.model_validate({"amount": 10, "category": "Misc"})
    assert omit.category_id is None
    ok = ExpenseCreate.model_validate(
        {"amount": 10, "category_id": f"  {_VALID}  "}
    )
    assert ok.category_id == _VALID.lower()
    nullish = ExpenseCreate.model_validate({"amount": 10, "category_id": None})
    assert nullish.category_id is None
    for bad in ("", " ", "!!!", "http://evil", "not-a-uuid", "exp_cat_001", "a b"):
        with pytest.raises(ValidationError):
            ExpenseCreate.model_validate({"amount": 10, "category_id": bad})


def test_expense_create_category_id_ui_and_docs():
    page = (ROOT / "frontend/app/expenses/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Expense spend category"' in page
    assert "category_id: categoryId.trim() || null" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Expense create category_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "UuidIdValue" in docs
    assert "Expense spend category" in docs


@pytest.mark.asyncio
async def test_expense_create_category_id_api_blank_invalid_422(client, seeded):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    cats = await ac.get("/api/v1/expenses/categories", headers=headers)
    assert cats.status_code == 200, cats.text
    rows = cats.json().get("data") or []
    active = next((c for c in rows if c.get("is_active") is not False), rows[0] if rows else None)
    assert active, "seeded expense category required"
    cat_id = active["id"]

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "exp_cat_001"):
        resp = await ac.post(
            "/api/v1/expenses",
            headers=headers,
            json={"amount": 12.5, "category_id": bad, "description": "Tip270 bad cat"},
        )
        assert resp.status_code == 422, (bad, resp.text)

    ok = await ac.post(
        "/api/v1/expenses",
        headers=headers,
        json={
            "amount": 12.5,
            "category_id": f"  {str(cat_id).upper()}  ",
            "description": "Tip270 with category",
        },
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["category_id"] == str(cat_id).lower()

    missing = await ac.post(
        "/api/v1/expenses",
        headers=headers,
        json={
            "amount": 12.5,
            "category_id": str(uuid4()),
            "description": "Tip270 missing category",
        },
    )
    assert missing.status_code in (400, 404), missing.text
