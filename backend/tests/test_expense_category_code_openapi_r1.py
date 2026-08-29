"""ExpenseCategoryCreate.code ∈ ExpenseCategoryCodeValue OpenAPI (BR-9.1)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import ExpenseCategoryCodeValue, ExpenseCategoryCreate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_code = TypeAdapter(ExpenseCategoryCodeValue)


def test_expense_category_code_value_schema():
    assert _code.validate_python("  travel  ") == "travel"
    for bad in ("", " ", "!!!", "http://evil", "@@", "a" * 41):
        with pytest.raises(ValidationError):
            _code.validate_python(bad)

    ok = ExpenseCategoryCreate.model_validate({"code": "  TRVL  ", "name": "Travel"})
    assert ok.code == "TRVL"
    with pytest.raises(ValidationError):
        ExpenseCategoryCreate.model_validate({"code": "!!!", "name": "Travel"})
    with pytest.raises(ValidationError):
        ExpenseCategoryCreate.model_validate({"code": "", "name": "Travel"})


def test_expense_category_code_ui_and_docs():
    page = (ROOT / "frontend/app/expenses/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Expense category code"' in page
    assert "code: newCatCode.trim()" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Expense category code OpenAPI" in agents
    assert "ExpenseCategoryCodeValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "ExpenseCategoryCodeValue" in docs
    assert "Expense category code" in docs


@pytest.mark.asyncio
async def test_expense_category_code_api_blank_invalid_422(client):
    ac, seed = client
    totp = pyotp.TOTP(seed["super_totp_secret"]).now()
    headers = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=totp
    )
    suffix = uuid4().hex[:8]

    for bad in ("!!!", "", "http://evil.example/p"):
        r = await ac.post(
            "/api/v1/expenses/categories",
            headers=headers,
            json={"code": bad, "name": f"TIP226 Cat {suffix}"},
        )
        assert r.status_code == 422, (bad, r.text)

    hello = await ac.post(
        "/api/v1/expenses/categories",
        headers=headers,
        json={
            "code": f"  e226{suffix}  ",
            "name": f"TIP226 Cat OK {suffix}",
        },
    )
    assert hello.status_code == 200, hello.text
    assert hello.json()["data"]["code"] == f"e226{suffix}".upper()
