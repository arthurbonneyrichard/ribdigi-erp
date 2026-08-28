"""ExpenseCategoryUpdate.account_id ∈ UuidIdValue OpenAPI honesty (BR-9.1)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import ExpenseCategoryUpdate, UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"


def test_expense_category_update_account_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    omit = ExpenseCategoryUpdate.model_validate({})
    assert omit.account_id is None
    ok = ExpenseCategoryUpdate.model_validate({"account_id": f"  {_VALID}  "})
    assert ok.account_id == _VALID.lower()
    for bad in ("", "!!!", "http://evil", "not-a-uuid", "acct_001"):
        with pytest.raises(ValidationError):
            ExpenseCategoryUpdate.model_validate({"account_id": bad})


def test_expense_category_update_account_id_ui_and_docs():
    page = (ROOT / "frontend/app/expenses/page.tsx").read_text(encoding="utf-8")
    assert "Edit expense category GL account" in page
    assert "accountId) payload.account_id = accountId" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Expense category update account_id OpenAPI" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Edit expense category GL account" in docs


@pytest.mark.asyncio
async def test_expense_category_update_account_id_api_blank_invalid_422(client, seeded):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    suffix = uuid4().hex[:8]
    created = await ac.post(
        "/api/v1/expenses/categories",
        headers=headers,
        json={"code": f"T402{suffix[:4]}".upper(), "name": f"Tip402 Cat {suffix}"},
    )
    assert created.status_code == 200, created.text
    cat_id = created.json()["data"]["id"]

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "acct_001"):
        resp = await ac.patch(
            f"/api/v1/expenses/categories/{cat_id}",
            headers=headers,
            json={"account_id": bad},
        )
        assert resp.status_code == 422, (bad, resp.text)

    missing = await ac.patch(
        f"/api/v1/expenses/categories/{cat_id}",
        headers=headers,
        json={"account_id": f"  {str(uuid4()).upper()}  "},
    )
    assert missing.status_code in (400, 404), missing.text
    assert missing.status_code != 422
