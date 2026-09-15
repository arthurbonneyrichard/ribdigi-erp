"""RecurringExpenseUpdate.branch_id ∈ UuidIdValue OpenAPI honesty (BR-9.5)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import RecurringExpenseUpdate, UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"


def test_recurring_expense_update_branch_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    omit = RecurringExpenseUpdate.model_validate({})
    assert omit.branch_id is None
    ok = RecurringExpenseUpdate.model_validate({"branch_id": f"  {_VALID}  "})
    assert ok.branch_id == _VALID.lower()
    nullish = RecurringExpenseUpdate.model_validate({"branch_id": None})
    assert nullish.branch_id is None
    for bad in ("", " ", "!!!", "http://evil", "not-a-uuid", "br_001", "a b"):
        with pytest.raises(ValidationError):
            RecurringExpenseUpdate.model_validate({"branch_id": bad})


def test_recurring_expense_update_branch_id_ui_and_docs():
    page = (ROOT / "frontend/app/expenses/page.tsx").read_text(encoding="utf-8")
    assert "Edit recurring expense branch" in page
    assert "branch_id: recBranchId.trim() || null" in page
    assert "clear_branch: !recBranchId.trim()" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Recurring expense update branch_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Edit recurring expense branch" in docs
    assert "PATCH /expenses/recurring/{id}" in docs


@pytest.mark.asyncio
async def test_recurring_expense_update_branch_id_api_blank_invalid_422(client, seeded):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    suffix = uuid4().hex[:8]

    created = await ac.post(
        "/api/v1/expenses/recurring",
        headers=headers,
        json={
            "amount": 1700,
            "category": "Misc",
            "description": f"Tip325 recurring {suffix}",
            "frequency": "monthly",
        },
    )
    assert created.status_code == 200, created.text
    rec_id = created.json()["data"]["id"]

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "br_001"):
        resp = await ac.patch(
            f"/api/v1/expenses/recurring/{rec_id}",
            headers=headers,
            json={"branch_id": bad},
        )
        assert resp.status_code == 422, (bad, resp.text)

    omit = await ac.patch(
        f"/api/v1/expenses/recurring/{rec_id}",
        headers=headers,
        json={"description": f"Tip325 omit branch {suffix}"},
    )
    assert omit.status_code == 200, omit.text

    missing = await ac.patch(
        f"/api/v1/expenses/recurring/{rec_id}",
        headers=headers,
        json={"branch_id": f"  {str(uuid4()).upper()}  "},
    )
    assert missing.status_code in (400, 404), missing.text
    assert missing.status_code != 422
