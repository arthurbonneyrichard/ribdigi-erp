"""ExpenseDecision.comment OpenAPI honesty (BR-9.3)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import ExpenseDecision
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_expense_approve_comment_schema():
    omit = ExpenseDecision.model_validate({})
    assert omit.comment is None
    nullish = ExpenseDecision.model_validate({"comment": None})
    assert nullish.comment is None
    ok = ExpenseDecision.model_validate({"comment": "  Receipt verified  "})
    assert ok.comment == "Receipt verified"
    for bad in ("", " ", "!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            ExpenseDecision.model_validate({"comment": bad})


def test_expense_approve_comment_ui_and_docs():
    page = (ROOT / "frontend/app/expenses/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Expense approve comment"' in page
    assert "comment ? { comment } : {}" in page or (
        "comment ?" in page and "{ comment }" in page
    )
    assert 'aria-label="Approve expense"' in page
    assert "comment: 'Approved'" not in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Expense approve comment OpenAPI" in agents
    assert "ExpenseApproveCommentValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "ExpenseApproveCommentValue" in docs
    assert "Expense approve comment" in docs


@pytest.mark.asyncio
async def test_expense_approve_comment_api_blank_invalid_422(client):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    headers = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:8]
    tag = f"Tip179 comment {suffix}"

    cats = await ac.get("/api/v1/expenses/categories", headers=headers)
    assert cats.status_code == 200, cats.text
    cat_id = cats.json()["data"][0]["id"]

    created = await ac.post(
        "/api/v1/expenses",
        headers=headers,
        json={
            "category_id": cat_id,
            "amount": 275,
            "description": f"Approve comment OpenAPI {suffix}",
            "payee": f"Vendor Tip179 {suffix}",
            "payment_method": "cash",
        },
    )
    assert created.status_code == 200, created.text
    eid = created.json()["data"]["id"]

    for bad in ("", "!!!", "http://evil"):
        resp = await ac.post(
            f"/api/v1/expenses/{eid}/approve",
            headers=headers,
            json={"comment": bad},
        )
        assert resp.status_code == 422, (bad, resp.text)

    omit = await ac.post(f"/api/v1/expenses/{eid}/approve", headers=headers, json={})
    # May approve on empty comment; if already approved create fresh for typed path
    if omit.status_code == 200:
        assert omit.json()["data"].get("approval_comment") != "Approved"
        created2 = await ac.post(
            "/api/v1/expenses",
            headers=headers,
            json={
                "category_id": cat_id,
                "amount": 280,
                "description": f"Approve comment typed {suffix}",
                "payee": f"Vendor Tip179b {suffix}",
                "payment_method": "cash",
            },
        )
        assert created2.status_code == 200, created2.text
        eid = created2.json()["data"]["id"]

    ok = await ac.post(
        f"/api/v1/expenses/{eid}/approve",
        headers=headers,
        json={"comment": f"  {tag}  "},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"].get("approval_comment") == tag
