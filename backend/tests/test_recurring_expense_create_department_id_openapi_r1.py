"""RecurringExpenseCreate.department_id ∈ UuidIdValue OpenAPI honesty (BR-9.5)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import RecurringExpenseCreate, UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"


def test_recurring_expense_create_department_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    omit = RecurringExpenseCreate.model_validate({"amount": 10, "category": "Misc"})
    assert omit.department_id is None
    ok = RecurringExpenseCreate.model_validate(
        {"amount": 10, "department_id": f"  {_VALID}  "}
    )
    assert ok.department_id == _VALID.lower()
    nullish = RecurringExpenseCreate.model_validate(
        {"amount": 10, "department_id": None}
    )
    assert nullish.department_id is None
    for bad in ("", " ", "!!!", "http://evil", "not-a-uuid", "dept_001", "a b"):
        with pytest.raises(ValidationError):
            RecurringExpenseCreate.model_validate({"amount": 10, "department_id": bad})


def test_recurring_expense_create_department_id_ui_and_docs():
    page = (ROOT / "frontend/app/expenses/page.tsx").read_text(encoding="utf-8")
    assert "Recurring expense department" in page
    assert "department_id: recDepartmentId.trim() || null" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Recurring expense create department_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Recurring expense department" in docs
    assert "POST /expenses/recurring" in docs


@pytest.mark.asyncio
async def test_recurring_expense_create_department_id_api_blank_invalid_422(client, seeded):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    suffix = uuid4().hex[:8]

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "dept_001"):
        resp = await ac.post(
            "/api/v1/expenses/recurring",
            headers=headers,
            json={
                "amount": 1600,
                "category": "Misc",
                "description": f"Tip324 bad department {suffix}",
                "department_id": bad,
            },
        )
        assert resp.status_code == 422, (bad, resp.text)

    omit = await ac.post(
        "/api/v1/expenses/recurring",
        headers=headers,
        json={
            "amount": 1600,
            "category": "Misc",
            "description": f"Tip324 omit department {suffix}",
        },
    )
    assert omit.status_code == 200, omit.text

    missing = await ac.post(
        "/api/v1/expenses/recurring",
        headers=headers,
        json={
            "amount": 1600,
            "category": "Misc",
            "description": f"Tip324 missing department {suffix}",
            "department_id": f"  {str(uuid4()).upper()}  ",
        },
    )
    assert missing.status_code in (400, 404), missing.text
    assert missing.status_code != 422
