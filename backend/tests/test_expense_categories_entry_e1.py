"""Stage 22 E1: Expense categories & entry fidelity (BR-9.1–9.2)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from app.expenses import DEFAULT_CATEGORIES
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_expense_categories_budgets_and_entry_fields(client):
    """BR-9.1–9.2: predefined/custom categories, budgets, full expense entry fields."""
    ac, seed = client
    headers = await _super(ac, seed)

    listed = await ac.get("/api/v1/expenses/categories", headers=headers)
    assert listed.status_code == 200, listed.text
    by_code = {c["code"]: c for c in listed.json()["data"]}
    for code, name in DEFAULT_CATEGORIES:
        assert code in by_code, code
        assert by_code[code]["name"] == name

    custom = await ac.post(
        "/api/v1/expenses/categories",
        headers=headers,
        json={"code": "e1trv", "name": "E1 Travel", "budget_amount": 500},
    )
    assert custom.status_code == 200, custom.text
    cat = custom.json()["data"]
    cat_id = cat["id"]
    assert cat["code"] == "E1TRV"
    assert cat["name"] == "E1 Travel"
    assert float(cat["budget_amount"]) == pytest.approx(500)

    patched = await ac.patch(
        f"/api/v1/expenses/categories/{cat_id}",
        headers=headers,
        json={"budget_amount": 750},
    )
    assert patched.status_code == 200, patched.text
    assert float(patched.json()["data"]["budget_amount"]) == pytest.approx(750)

    # Full BR-9.2 entry fields (under auto-approve threshold)
    created = await ac.post(
        "/api/v1/expenses",
        headers=headers,
        json={
            "category_id": cat_id,
            "amount": 80,
            "expense_date": "2026-08-10T12:00:00",
            "payment_method": "bank_transfer",
            "reference": "E1-REF-001",
            "payee": "City Transit",
            "description": "Airport transfer for client visit",
        },
    )
    assert created.status_code == 200, created.text
    expense = created.json()["data"]
    expense_id = expense["id"]
    assert expense["category_id"] == cat_id
    assert float(expense["amount"]) == pytest.approx(80)
    assert expense["payment_method"] == "bank_transfer"
    assert expense["reference"] == "E1-REF-001"
    assert expense["payee"] == "City Transit"
    assert expense["description"] == "Airport transfer for client visit"
    assert expense.get("expense_date")

    got = await ac.get(f"/api/v1/expenses/{expense_id}", headers=headers)
    assert got.status_code == 200, got.text
    gdata = got.json()["data"]
    assert gdata["payee"] == "City Transit"
    assert gdata["reference"] == "E1-REF-001"
    assert gdata["description"] == "Airport transfer for client visit"

    # Patch entry notes/payee while editable (approved auto under threshold may still allow
    # description/payee depending on status — prefer pending path for patch)
    pending = await ac.post(
        "/api/v1/expenses",
        headers=headers,
        json={
            "category_id": cat_id,
            "amount": 400,
            "payment_method": "cash",
            "reference": "E1-PEND",
            "payee": "Hotel Co",
            "description": "Pending lodging",
        },
    )
    assert pending.status_code == 200, pending.text
    assert pending.json()["data"]["status"] == "pending"
    pid = pending.json()["data"]["id"]

    updated = await ac.patch(
        f"/api/v1/expenses/{pid}",
        headers=headers,
        json={
            "payee": "Hotel Co Ltd",
            "reference": "E1-PEND-A",
            "description": "Adjusted lodging note",
            "payment_method": "bank_transfer",
        },
    )
    assert updated.status_code == 200, updated.text
    udata = updated.json()["data"]
    assert udata["payee"] == "Hotel Co Ltd"
    assert udata["reference"] == "E1-PEND-A"
    assert udata["description"] == "Adjusted lodging note"
    assert udata["payment_method"] == "bank_transfer"

    budgets = await ac.get("/api/v1/expenses/budgets", headers=headers)
    assert budgets.status_code == 200, budgets.text
    body = budgets.json()["data"]
    assert "categories" in body and "totals" in body
    row = next(c for c in body["categories"] if c["id"] == cat_id)
    assert float(row["budget_amount"]) == pytest.approx(750)
    assert float(row["spent"]) + float(row["pending"]) >= 80


def test_br_9_1_9_2_and_plan_synced():
    br = (ROOT / "docs" / "BUSINESS_REQUIREMENTS_DOCUMENT.md").read_text(encoding="utf-8")
    s91 = br.split("#### BR-9.1 Expense Categories")[1].split("#### BR-9.2")[0]
    assert "[x] Predefined categories" in s91
    assert "[x] Custom category creation" in s91
    assert "[x] Category-based budget allocation" in s91
    assert "Stage 22 E1" in s91
    assert "test_expense_categories_entry_e1.py" in s91

    s92 = br.split("#### BR-9.2 Expense Entry")[1].split("#### BR-9.3")[0]
    assert "[x] Expense date, category, amount, payment method, reference number" in s92
    assert "[x] Payee name" in s92
    assert "[x] Description/notes" in s92
    assert "[x] Assign to store/department" in s92
    assert "[x] Link to chart of accounts" in s92
    assert "Stage 22 E1" in s92
    assert "Stage 14" in s92

    plan = (ROOT / "docs" / "STAGE_22_PLAN.md").read_text(encoding="utf-8")
    e1_line = [ln for ln in plan.splitlines() if "| **E1**" in ln][0]
    assert "COMPLETE" in e1_line
    assert "test_expense_categories_entry_e1.py" in plan
