"""ExpenseCreate.store_id ∈ UuidIdValue OpenAPI honesty (BR-9.2)."""

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


def test_expense_create_store_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    omit = ExpenseCreate.model_validate({"amount": 10, "category": "Misc"})
    assert omit.store_id is None
    ok = ExpenseCreate.model_validate({"amount": 10, "store_id": f"  {_VALID}  "})
    assert ok.store_id == _VALID.lower()
    nullish = ExpenseCreate.model_validate({"amount": 10, "store_id": None})
    assert nullish.store_id is None
    for bad in ("", " ", "!!!", "http://evil", "not-a-uuid", "st_001", "a b"):
        with pytest.raises(ValidationError):
            ExpenseCreate.model_validate({"amount": 10, "store_id": bad})


def test_expense_create_store_id_ui_and_docs():
    page = (ROOT / "frontend/app/expenses/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Expense store"' in page
    assert "store_id: storeId.trim() || null" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Expense create store_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Expense store" in docs
    assert "POST /expenses" in docs


@pytest.mark.asyncio
async def test_expense_create_store_id_api_blank_invalid_422(client, seeded):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "st_001"):
        resp = await ac.post(
            "/api/v1/expenses",
            headers=headers,
            json={
                "amount": 12.5,
                "category": "Misc",
                "description": "Tip 304 store",
                "store_id": bad,
            },
        )
        assert resp.status_code == 422, (bad, resp.text)

    omit = await ac.post(
        "/api/v1/expenses",
        headers=headers,
        json={
            "amount": 12.5,
            "category": "Misc",
            "description": "Tip 304 omit store",
        },
    )
    assert omit.status_code == 200, omit.text

    missing = await ac.post(
        "/api/v1/expenses",
        headers=headers,
        json={
            "amount": 12.5,
            "category": "Misc",
            "description": "Tip 304 missing store",
            "store_id": f"  {str(uuid4()).upper()}  ",
        },
    )
    assert missing.status_code in (400, 404), missing.text
    assert missing.status_code != 422
