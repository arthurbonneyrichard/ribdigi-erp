"""ExpenseUpdate.branch_id ∈ UuidIdValue OpenAPI honesty (BR-9.2)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import ExpenseUpdate, UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"


def test_expense_update_branch_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    omit = ExpenseUpdate.model_validate({})
    assert omit.branch_id is None
    ok = ExpenseUpdate.model_validate({"branch_id": f"  {_VALID}  "})
    assert ok.branch_id == _VALID.lower()
    nullish = ExpenseUpdate.model_validate({"branch_id": None})
    assert nullish.branch_id is None
    for bad in ("", " ", "!!!", "http://evil", "not-a-uuid", "br_001", "a b"):
        with pytest.raises(ValidationError):
            ExpenseUpdate.model_validate({"branch_id": bad})


def test_expense_update_branch_id_ui_and_docs():
    page = (ROOT / "frontend/app/expenses/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Edit expense branch"' in page
    assert "body.branch_id = branchTrim" in page
    assert "body.clear_branch = true" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Expense update branch_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Edit expense branch" in docs
    assert "PATCH /expenses/{expense_id}" in docs


@pytest.mark.asyncio
async def test_expense_update_branch_id_api_blank_invalid_422(client, seeded):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    created = await ac.post(
        "/api/v1/expenses",
        headers=headers,
        json={
            "amount": 5000,
            "category": "Misc",
            "description": "Tip 315 edit branch seed",
        },
    )
    assert created.status_code == 200, created.text
    data = created.json()["data"]
    exp_id = data["id"]
    assert data.get("status") == "pending", data

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "br_001"):
        resp = await ac.patch(
            f"/api/v1/expenses/{exp_id}",
            headers=headers,
            json={"branch_id": bad},
        )
        assert resp.status_code == 422, (bad, resp.text)

    omit = await ac.patch(
        f"/api/v1/expenses/{exp_id}",
        headers=headers,
        json={"description": "Tip 315 omit branch"},
    )
    assert omit.status_code == 200, omit.text

    missing = await ac.patch(
        f"/api/v1/expenses/{exp_id}",
        headers=headers,
        json={"branch_id": f"  {str(uuid4()).upper()}  "},
    )
    assert missing.status_code in (400, 404), missing.text
    assert missing.status_code != 422
