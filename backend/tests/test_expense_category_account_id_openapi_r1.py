"""ExpenseCategoryCreate.account_id ∈ UuidIdValue OpenAPI honesty (BR-9.1)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import ExpenseCategoryCreate, UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"


def test_expense_category_account_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    omit = ExpenseCategoryCreate.model_validate({"code": "MISC", "name": "Misc"})
    assert omit.account_id is None
    ok = ExpenseCategoryCreate.model_validate(
        {"code": "MISC", "name": "Misc", "account_id": f"  {_VALID}  "}
    )
    assert ok.account_id == _VALID.lower()
    nullish = ExpenseCategoryCreate.model_validate(
        {"code": "MISC", "name": "Misc", "account_id": None}
    )
    assert nullish.account_id is None
    for bad in ("", " ", "!!!", "http://evil", "not-a-uuid", "acct_001", "a b"):
        with pytest.raises(ValidationError):
            ExpenseCategoryCreate.model_validate(
                {"code": "MISC", "name": "Misc", "account_id": bad}
            )


def test_expense_category_account_id_ui_and_docs():
    page = (ROOT / "frontend/app/expenses/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Expense category GL account"' in page
    assert "account_id: newCatAccountId.trim() || null" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Expense category account_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "UuidIdValue" in docs
    assert "Expense category GL account" in docs


@pytest.mark.asyncio
async def test_expense_category_account_id_api_blank_invalid_422(client, seeded):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    accounts = await ac.get("/api/v1/accounting/accounts", headers=headers)
    assert accounts.status_code == 200, accounts.text
    rows = accounts.json().get("data") or []
    expense_acct = next(
        (a for a in rows if str(a.get("account_type", "")).lower() == "expense"),
        rows[0] if rows else None,
    )
    assert expense_acct, "seeded COA required"
    acct_id = expense_acct["id"]

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "acct_001"):
        resp = await ac.post(
            "/api/v1/expenses/categories",
            headers=headers,
            json={
                "code": f"T{uuid4().hex[:6].upper()}",
                "name": "Tip267 category",
                "account_id": bad,
            },
        )
        assert resp.status_code == 422, (bad, resp.text)

    code = f"T{uuid4().hex[:6].upper()}"
    ok = await ac.post(
        "/api/v1/expenses/categories",
        headers=headers,
        json={
            "code": code,
            "name": "Tip267 with GL",
            "account_id": f"  {str(acct_id).upper()}  ",
        },
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["account_id"] == str(acct_id).lower()

    missing = await ac.post(
        "/api/v1/expenses/categories",
        headers=headers,
        json={
            "code": f"T{uuid4().hex[:6].upper()}",
            "name": "Tip267 missing GL",
            "account_id": str(uuid4()),
        },
    )
    assert missing.status_code in (400, 404), missing.text
