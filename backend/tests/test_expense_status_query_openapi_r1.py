"""GET /expenses status Query OpenAPI Literal + Expenses manage filter (BR-9.2)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import ExpenseStatusFilterValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_expense_status_filter_literal_schema():
    adapter = TypeAdapter(ExpenseStatusFilterValue)
    assert adapter.validate_python("pending") == "pending"
    assert adapter.validate_python("  Approved ") == "approved"
    assert adapter.validate_python("REJECTED") == "rejected"
    with pytest.raises(ValidationError):
        adapter.validate_python("")
    with pytest.raises(ValidationError):
        adapter.validate_python("   ")
    with pytest.raises(ValidationError):
        adapter.validate_python("draft")
    with pytest.raises(ValidationError):
        adapter.validate_python("garbage_xyz")


def test_expense_status_filter_ui_and_docs():
    page = (ROOT / "frontend/app/expenses/page.tsx").read_text(encoding="utf-8")
    assert "expenseManageFilter" in page
    assert "managedExpenses" in page
    assert 'aria-label="Expense status filter"' in page
    assert 'value="pending"' in page
    assert 'value="approved"' in page
    assert 'value="rejected"' in page
    assert "No expenses for this filter" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Expense status Query OpenAPI" in agents
    assert "expenseManageFilter" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "expenseManageFilter" in docs
    assert "pending" in docs and "422" in docs


@pytest.mark.asyncio
async def test_expense_status_filter_api_blank_invalid_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    blank = await ac.get("/api/v1/expenses?status=", headers=headers)
    assert blank.status_code == 422, blank.text

    bad = await ac.get("/api/v1/expenses?status=draft", headers=headers)
    assert bad.status_code == 422, bad.text

    cats = await ac.get("/api/v1/expenses/categories", headers=headers)
    assert cats.status_code == 200, cats.text
    cat_id = (cats.json()["data"] or [{}])[0].get("id")
    assert cat_id

    created = await ac.post(
        "/api/v1/expenses",
        headers=headers,
        json={
            "amount": 25,
            "description": "Status filter probe",
            "category_id": cat_id,
            "payment_method": "cash",
        },
    )
    assert created.status_code == 200, created.text
    expense_id = created.json()["data"]["id"]
    status = created.json()["data"]["status"]
    assert status in {"pending", "approved"}

    filtered = await ac.get(f"/api/v1/expenses?status={status}", headers=headers)
    assert filtered.status_code == 200, filtered.text
    rows = filtered.json()["data"]
    assert any(r["id"] == expense_id for r in rows)
    assert all(r["status"] == status for r in rows)

    other = "rejected" if status != "rejected" else "pending"
    other_rows = await ac.get(f"/api/v1/expenses?status={other}", headers=headers)
    assert other_rows.status_code == 200, other_rows.text
    assert all(r["status"] == other for r in other_rows.json()["data"])
    assert not any(r["id"] == expense_id for r in other_rows.json()["data"])

    cased = await ac.get("/api/v1/expenses?status=Pending", headers=headers)
    assert cased.status_code == 200, cased.text
    assert all(r["status"] == "pending" for r in cased.json()["data"])

    omit = await ac.get("/api/v1/expenses", headers=headers)
    assert omit.status_code == 200, omit.text
