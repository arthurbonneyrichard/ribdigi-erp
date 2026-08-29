"""ExpenseCreate / Update / recurring / AI draft payee OpenAPI honesty (BR-9.2 / BR-9.5)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import (
    AiDocumentExpenseCreate,
    ExpenseCreate,
    ExpenseUpdate,
    RecurringExpenseCreate,
    RecurringExpenseUpdate,
)
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_expense_payee_schema():
    omit = ExpenseCreate.model_validate({"amount": 10})
    assert omit.payee is None
    ok = ExpenseCreate.model_validate({"amount": 10, "payee": "  Acme Supplies  "})
    assert ok.payee == "Acme Supplies"
    for bad in ("", " ", "!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            ExpenseCreate.model_validate({"amount": 10, "payee": bad})

    patch_omit = ExpenseUpdate.model_validate({})
    assert patch_omit.payee is None
    patch_ok = ExpenseUpdate.model_validate({"payee": " Renamed Vendor "})
    assert patch_ok.payee == "Renamed Vendor"
    with pytest.raises(ValidationError):
        ExpenseUpdate.model_validate({"payee": "!!!"})
    with pytest.raises(ValidationError):
        ExpenseUpdate.model_validate({"payee": "  "})

    rec_ok = RecurringExpenseCreate.model_validate({"amount": 20, "payee": "  Landlord  "})
    assert rec_ok.payee == "Landlord"
    with pytest.raises(ValidationError):
        RecurringExpenseCreate.model_validate({"amount": 20, "payee": "!!!"})
    with pytest.raises(ValidationError):
        RecurringExpenseUpdate.model_validate({"payee": ""})
    clear_ok = RecurringExpenseUpdate.model_validate({"payee": None, "clear_payee": True})
    assert clear_ok.payee is None and clear_ok.clear_payee is True

    ai_ok = AiDocumentExpenseCreate.model_validate({"amount": 5, "payee": "  OCR Vendor  "})
    assert ai_ok.payee == "OCR Vendor"
    with pytest.raises(ValidationError):
        AiDocumentExpenseCreate.model_validate({"amount": 5, "payee": "http://evil"})


def test_expense_payee_ui_and_docs():
    page = (ROOT / "frontend/app/expenses/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Expense payee"' in page
    assert "payee.trim() || null" in page
    assert 'aria-label="Recurring payee"' in page
    assert "recPayee.trim() || null" in page
    assert 'aria-label="Edit payee"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Expense payee OpenAPI" in agents
    assert "ExpensePayeeValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "ExpensePayeeValue" in docs
    assert "Expense payee" in docs


@pytest.mark.asyncio
async def test_expense_payee_api_blank_invalid_422(client, seeded):
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
                "payee": bad,
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
    assert omit.json()["data"].get("payee") in (None, "")

    ok = await ac.post(
        "/api/v1/expenses",
        headers=admin,
        json={
            "amount": 5000,
            "category_id": category_id,
            "payee": f"  Tip148 Payee {suffix}  ",
            "description": f"Tip148 desc {suffix}",
            "payment_method": "cash",
        },
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["payee"] == f"Tip148 Payee {suffix}"
    eid = ok.json()["data"]["id"]
    if ok.json()["data"].get("status") == "approved":
        pending = await ac.post(
            "/api/v1/expenses",
            headers=admin,
            json={
                "amount": 9000,
                "category_id": category_id,
                "payee": f"  Tip148 Pending {suffix}  ",
                "description": f"Tip148 pending {suffix}",
                "payment_method": "cash",
            },
        )
        assert pending.status_code == 200, pending.text
        eid = pending.json()["data"]["id"]
        assert pending.json()["data"]["payee"] == f"Tip148 Pending {suffix}"

    keep = await ac.patch(
        f"/api/v1/expenses/{eid}",
        headers=admin,
        json={"description": f"Tip148 keep {suffix}"},
    )
    assert keep.status_code == 200, keep.text
    assert "Tip148" in (keep.json()["data"].get("payee") or "")

    for bad in ("", "!!!", "http://evil"):
        bad_patch = await ac.patch(
            f"/api/v1/expenses/{eid}",
            headers=admin,
            json={"payee": bad},
        )
        assert bad_patch.status_code == 422, (bad, bad_patch.text)

    renamed = await ac.patch(
        f"/api/v1/expenses/{eid}",
        headers=admin,
        json={"payee": f"  Tip148 Renamed {suffix}  "},
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["data"]["payee"] == f"Tip148 Renamed {suffix}"
