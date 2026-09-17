"""ExpenseCreate.liquid_account_id ∈ UuidIdValue OpenAPI honesty (BR-9.2)."""

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


def test_expense_create_liquid_account_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    omit = ExpenseCreate.model_validate({"amount": 10, "category": "Misc"})
    assert omit.liquid_account_id is None
    ok = ExpenseCreate.model_validate(
        {"amount": 10, "liquid_account_id": f"  {_VALID}  "}
    )
    assert ok.liquid_account_id == _VALID.lower()
    nullish = ExpenseCreate.model_validate({"amount": 10, "liquid_account_id": None})
    assert nullish.liquid_account_id is None
    for bad in ("", " ", "!!!", "http://evil", "not-a-uuid", "acct_001", "a b"):
        with pytest.raises(ValidationError):
            ExpenseCreate.model_validate({"amount": 10, "liquid_account_id": bad})


def test_expense_create_liquid_account_id_ui_and_docs():
    page = (ROOT / "frontend/app/expenses/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Expense liquid account"' in page
    assert "liquid_account_id: liquidAccountId.trim() || null" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Expense create liquid_account_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Expense liquid account" in docs
    assert "POST /expenses" in docs


@pytest.mark.asyncio
async def test_expense_create_liquid_account_id_api_blank_invalid_422(client, seeded):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "acct_001"):
        resp = await ac.post(
            "/api/v1/expenses",
            headers=headers,
            json={
                "amount": 12.5,
                "category": "Misc",
                "description": "Tip 301 liquid account",
                "liquid_account_id": bad,
            },
        )
        assert resp.status_code == 422, (bad, resp.text)

    omit = await ac.post(
        "/api/v1/expenses",
        headers=headers,
        json={
            "amount": 12.5,
            "category": "Misc",
            "description": "Tip 301 omit liquid",
        },
    )
    assert omit.status_code == 200, omit.text

    missing = await ac.post(
        "/api/v1/expenses",
        headers=headers,
        json={
            "amount": 12.5,
            "category": "Misc",
            "description": "Tip 301 missing liquid",
            "liquid_account_id": f"  {str(uuid4()).upper()}  ",
        },
    )
    assert missing.status_code in (400, 404), missing.text
    assert missing.status_code != 422
