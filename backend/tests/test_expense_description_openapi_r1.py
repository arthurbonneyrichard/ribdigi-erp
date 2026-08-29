"""ExpenseCreate / ExpenseUpdate / recurring description OpenAPI honesty (BR-9.2 / BR-9.5)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import (
    ExpenseCreate,
    ExpenseUpdate,
    RecurringExpenseCreate,
    RecurringExpenseUpdate,
)
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_expense_description_schema():
    omit = ExpenseCreate.model_validate({"amount": 10})
    assert omit.description is None
    nullish = ExpenseCreate.model_validate({"amount": 10, "description": None})
    assert nullish.description is None
    ok = ExpenseCreate.model_validate({"amount": 10, "description": "  Office supplies  "})
    assert ok.description == "Office supplies"
    for bad in ("", " ", "!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            ExpenseCreate.model_validate({"amount": 10, "description": bad})

    patch_omit = ExpenseUpdate.model_validate({})
    assert patch_omit.description is None
    patch_ok = ExpenseUpdate.model_validate({"description": " Renamed "})
    assert patch_ok.description == "Renamed"
    with pytest.raises(ValidationError):
        ExpenseUpdate.model_validate({"description": "!!!"})
    with pytest.raises(ValidationError):
        ExpenseUpdate.model_validate({"description": "  "})

    rec_ok = RecurringExpenseCreate.model_validate(
        {"amount": 20, "description": "  Monthly rent  "}
    )
    assert rec_ok.description == "Monthly rent"
    with pytest.raises(ValidationError):
        RecurringExpenseCreate.model_validate({"amount": 20, "description": "!!!"})
    with pytest.raises(ValidationError):
        RecurringExpenseUpdate.model_validate({"description": ""})


def test_expense_description_ui_and_docs():
    page = (ROOT / "frontend/app/expenses/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Expense description"' in page
    assert "description.trim() || null" in page
    assert 'aria-label="Recurring description"' in page
    assert "recDescription.trim() || null" in page
    assert 'aria-label="Edit description"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Expense description OpenAPI" in agents
    assert "ExpenseDescriptionValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "ExpenseDescriptionValue" in docs
    assert "Expense description" in docs


@pytest.mark.asyncio
async def test_expense_description_api_blank_invalid_422(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:8]

    cats = await ac.get("/api/v1/expenses/categories", headers=admin)
    assert cats.status_code == 200, cats.text
    cat_rows = cats.json().get("data") or []
    category = next((c for c in cat_rows if c.get("code") == "MISC"), cat_rows[0])
    category_id = category["id"]

    for bad in ("", "!!!", "http://evil"):
        resp = await ac.post(
            "/api/v1/expenses",
            headers=admin,
            json={
                "amount": 12.5,
                "category_id": category_id,
                "description": bad,
                "payment_method": "cash",
            },
        )
        assert resp.status_code == 422, (bad, resp.text)

    omit = await ac.post(
        "/api/v1/expenses",
        headers=admin,
        json={"amount": 12.5, "category_id": category_id, "payment_method": "cash"},
    )
    assert omit.status_code == 200, omit.text
    assert (omit.json()["data"].get("description") or "") == ""

    # High amount → likely pending so PATCH is allowed.
    ok = await ac.post(
        "/api/v1/expenses",
        headers=admin,
        json={
            "amount": 5000,
            "category_id": category_id,
            "description": f"  Tip147 Expense {suffix}  ",
            "payment_method": "cash",
        },
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["description"] == f"Tip147 Expense {suffix}"
    eid = ok.json()["data"]["id"]
    if ok.json()["data"].get("status") == "approved":
        pending = await ac.post(
            "/api/v1/expenses",
            headers=admin,
            json={
                "amount": 9000,
                "category_id": category_id,
                "description": f"  Tip147 Pending {suffix}  ",
                "payment_method": "cash",
            },
        )
        assert pending.status_code == 200, pending.text
        eid = pending.json()["data"]["id"]
        assert pending.json()["data"]["description"] == f"Tip147 Pending {suffix}"

    keep = await ac.patch(
        f"/api/v1/expenses/{eid}",
        headers=admin,
        json={"payee": "Vendor"},
    )
    assert keep.status_code == 200, keep.text
    assert "Tip147" in (keep.json()["data"].get("description") or "")

    for bad in ("", "!!!", "http://evil"):
        bad_patch = await ac.patch(
            f"/api/v1/expenses/{eid}",
            headers=admin,
            json={"description": bad},
        )
        assert bad_patch.status_code == 422, (bad, bad_patch.text)

    renamed = await ac.patch(
        f"/api/v1/expenses/{eid}",
        headers=admin,
        json={"description": f"  Tip147 Renamed {suffix}  "},
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["data"]["description"] == f"Tip147 Renamed {suffix}"
