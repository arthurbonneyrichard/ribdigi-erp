"""Expense Approve comment honesty (BR-9.3) — no hardcoded Approved."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_expense_approve_comment_ui_wired():
    expenses = (ROOT / "frontend/app/expenses/page.tsx").read_text(encoding="utf-8")
    assert "approveComment" in expenses
    assert "approval_comment" in expenses
    assert "Approve comment" in expenses
    assert "comment: 'Approved'" not in expenses
    assert 'comment: "Approved"' not in expenses
    assert "JSON.stringify(comment ? { comment } : {})" in expenses or (
        "comment ?" in expenses and "{ comment }" in expenses
    )


@pytest.mark.asyncio
async def test_expense_approve_persists_typed_comment(client):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    headers = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )

    cats = await ac.get("/api/v1/expenses/categories", headers=headers)
    assert cats.status_code == 200, cats.text
    cat_id = cats.json()["data"][0]["id"]

    created = await ac.post(
        "/api/v1/expenses",
        headers=headers,
        json={
            "category_id": cat_id,
            "amount": 250,
            "description": "Approve comment hello-world",
            "payee": "Vendor Approve",
            "payment_method": "cash",
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()["data"]
    assert body["status"] == "pending", body
    eid = body["id"]

    # Empty body: no fake "Approved" comment required
    ok_empty = await ac.post(f"/api/v1/expenses/{eid}/approve", headers=headers, json={})
    # super may self-approve; if this expense was already advanced, create a fresh one
    if ok_empty.status_code == 200:
        data = ok_empty.json()["data"]
        # empty comment should not invent "Approved"
        assert data.get("approval_comment") in (None, "")
        assert data.get("approval_comment") != "Approved"
        # create another for typed comment path
        created2 = await ac.post(
            "/api/v1/expenses",
            headers=headers,
            json={
                "category_id": cat_id,
                "amount": 260,
                "description": "Approve comment typed",
                "payee": "Vendor Approve 2",
                "payment_method": "cash",
            },
        )
        assert created2.status_code == 200, created2.text
        eid = created2.json()["data"]["id"]

    ok = await ac.post(
        f"/api/v1/expenses/{eid}/approve",
        headers=headers,
        json={"comment": "OK — receipt verified API hello-world"},
    )
    assert ok.status_code == 200, ok.text
    approved = ok.json()["data"]
    assert approved["status"] in {"approved", "pending"}
    assert approved["approval_comment"] == "OK — receipt verified API hello-world"
    assert approved["approval_comment"] != "Approved"
