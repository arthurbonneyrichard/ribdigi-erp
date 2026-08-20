"""Expense Reject reason honesty (BR-9.3) — FE/API required reason."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_expense_reject_reason_ui_wired():
    expenses = (ROOT / "frontend/app/expenses/page.tsx").read_text(encoding="utf-8")
    assert "rejectReason" in expenses
    assert "Enter a reject reason before rejecting an expense" in expenses
    assert "Required before Reject" in expenses
    assert 'aria-label="Expense reject reason"' in expenses
    assert "rejection_reason" in expenses
    assert "|| 'Rejected'" not in expenses
    assert 'reason: rejectReason || "Rejected"' not in expenses
    assert "reason: rejectReason || 'Rejected'" not in expenses
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "ExpenseRejectReasonValue" in agents


@pytest.mark.asyncio
async def test_expense_reject_requires_and_persists_reason(client):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    headers = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )

    cats = await ac.get("/api/v1/expenses/categories", headers=headers)
    assert cats.status_code == 200, cats.text
    cat_id = cats.json()["data"][0]["id"]

    # Amount above default threshold so status stays pending
    created = await ac.post(
        "/api/v1/expenses",
        headers=headers,
        json={
            "category_id": cat_id,
            "amount": 250,
            "description": "Reject reason hello-world",
            "payee": "Vendor HW",
            "payment_method": "cash",
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()["data"]
    assert body["status"] == "pending", body
    eid = body["id"]

    missing = await ac.post(f"/api/v1/expenses/{eid}/reject", headers=headers, json={})
    assert missing.status_code == 422, missing.text

    blank = await ac.post(
        f"/api/v1/expenses/{eid}/reject",
        headers=headers,
        json={"reason": "  "},
    )
    # OpenAPI honesty: strip + ExpenseRejectReasonValue → 422 (was service 400).
    assert blank.status_code == 422, blank.text

    garbage = await ac.post(
        f"/api/v1/expenses/{eid}/reject",
        headers=headers,
        json={"reason": "!!!!"},
    )
    assert garbage.status_code == 422, garbage.text

    ok = await ac.post(
        f"/api/v1/expenses/{eid}/reject",
        headers=headers,
        json={"reason": "Receipt missing — API hello-world"},
    )
    assert ok.status_code == 200, ok.text
    rejected = ok.json()["data"]
    assert rejected["status"] == "rejected"
    assert rejected["rejection_reason"] == "Receipt missing — API hello-world"
