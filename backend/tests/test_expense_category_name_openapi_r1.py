"""ExpenseCategoryCreate / ExpenseCategoryUpdate.name OpenAPI honesty (BR-9.1)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import ExpenseCategoryCreate, ExpenseCategoryUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_expense_category_name_schema():
    ok = ExpenseCategoryCreate.model_validate({"code": "MISC", "name": "  Office Supplies  "})
    assert ok.name == "Office Supplies"
    for bad in ("", " ", "!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            ExpenseCategoryCreate.model_validate({"code": "X", "name": bad})

    patch_omit = ExpenseCategoryUpdate.model_validate({})
    assert patch_omit.name is None
    patch_ok = ExpenseCategoryUpdate.model_validate({"name": " Renamed Category "})
    assert patch_ok.name == "Renamed Category"
    with pytest.raises(ValidationError):
        ExpenseCategoryUpdate.model_validate({"name": "!!!"})
    with pytest.raises(ValidationError):
        ExpenseCategoryUpdate.model_validate({"name": "  "})


def test_expense_category_name_ui_and_docs():
    expenses = (ROOT / "frontend/app/expenses/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Expense category name"' in expenses
    assert "newCatName.trim()" in expenses
    assert 'aria-label="Add expense category"' in expenses
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Expense category name OpenAPI" in agents
    assert "ExpenseCategoryNameValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "ExpenseCategoryNameValue" in docs
    assert "Expense category name" in docs


@pytest.mark.asyncio
async def test_expense_category_name_api_blank_invalid_422(client):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    headers = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:8]
    cat_code = f"T136{suffix[:4]}".upper()

    for bad in ("", "!!!", "http://evil"):
        r = await ac.post(
            "/api/v1/expenses/categories",
            headers=headers,
            json={"code": cat_code, "name": bad, "budget_amount": 0},
        )
        assert r.status_code == 422, (bad, r.text)

    ok = await ac.post(
        "/api/v1/expenses/categories",
        headers=headers,
        json={"code": cat_code, "name": f"  Tip136 Cat {suffix}  ", "budget_amount": 100},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["name"] == f"Tip136 Cat {suffix}"
    cat_id = ok.json()["data"]["id"]

    omit = await ac.patch(
        f"/api/v1/expenses/categories/{cat_id}",
        headers=headers,
        json={"budget_amount": 150},
    )
    assert omit.status_code == 200, omit.text
    assert omit.json()["data"]["name"] == f"Tip136 Cat {suffix}"

    for bad in ("", "!!!", "http://evil"):
        bad_patch = await ac.patch(
            f"/api/v1/expenses/categories/{cat_id}",
            headers=headers,
            json={"name": bad},
        )
        assert bad_patch.status_code == 422, (bad, bad_patch.text)

    renamed = await ac.patch(
        f"/api/v1/expenses/categories/{cat_id}",
        headers=headers,
        json={"name": f"  Tip136 Renamed {suffix}  "},
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["data"]["name"] == f"Tip136 Renamed {suffix}"
