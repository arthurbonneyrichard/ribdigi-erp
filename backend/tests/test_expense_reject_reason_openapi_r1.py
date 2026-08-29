"""ExpenseReject.reason OpenAPI honesty (BR-9.3)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas import ExpenseReject
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_expense_reject_reason_schema():
    ok = ExpenseReject.model_validate({"reason": "  Missing receipt  "})
    assert ok.reason == "Missing receipt"
    for bad in ("", " ", "!!!", "!!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            ExpenseReject.model_validate({"reason": bad})
    with pytest.raises(ValidationError):
        ExpenseReject.model_validate({})


def test_expense_reject_reason_ui_and_docs():
    page = (ROOT / "frontend/app/expenses/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Expense reject reason"' in page
    assert "rejectReason" in page
    assert "JSON.stringify({ reason })" in page
    assert 'aria-label={`Reject expense ${r.id}`}' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "ExpenseRejectReasonValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "ExpenseRejectReasonValue" in docs


@pytest.mark.asyncio
async def test_expense_reject_reason_api_blank_invalid_422(client):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    cats = await ac.get("/api/v1/expenses/categories", headers=headers)
    assert cats.status_code == 200, cats.text
    cat_id = cats.json()["data"][0]["id"]
    suffix = uuid4().hex[:8]
    tag = f"TIP191 reject {suffix}"

    created = await ac.post(
        "/api/v1/expenses",
        headers=headers,
        json={
            "category_id": cat_id,
            "amount": 250,
            "description": f"Reject tip191 {suffix}",
            "payee": "Tip191 Vendor",
            "payment_method": "cash",
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()["data"]
    assert body["status"] == "pending", body
    eid = body["id"]

    for bad in ("", "!!!", "http://evil", "   "):
        resp = await ac.post(
            f"/api/v1/expenses/{eid}/reject",
            headers=headers,
            json={"reason": bad},
        )
        assert resp.status_code == 422, (bad, resp.text)

    ok = await ac.post(
        f"/api/v1/expenses/{eid}/reject",
        headers=headers,
        json={"reason": tag},
    )
    assert ok.status_code == 200, ok.text
    rejected = ok.json()["data"]
    assert rejected["status"] == "rejected"
    assert rejected["rejection_reason"] == tag
