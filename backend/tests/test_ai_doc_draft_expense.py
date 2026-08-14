"""AI Document Assistant — Create draft expense from OCR extract (BR-21.8)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_ai_doc_draft_expense_ui_wired():
    ai = (ROOT / "frontend/app/ai/page.tsx").read_text(encoding="utf-8")
    assert "createDraftExpenseFromDoc" in ai
    assert "Create draft expense" in ai
    assert "/ai/documents/create-expense" in ai
    assert "lastDocExtract" in ai


@pytest.mark.asyncio
async def test_create_expense_from_extract_and_rejects_bad_amount(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )

    bad = await ac.post(
        "/api/v1/ai/documents/create-expense",
        headers=admin,
        json={"amount": 0, "payee": "Nope"},
    )
    assert bad.status_code == 422, bad.text

    created = await ac.post(
        "/api/v1/ai/documents/create-expense",
        headers=admin,
        json={
            "amount": 42.5,
            "payee": "OCR Cafe",
            "description": "Lunch receipt",
            "reference": "OCR-RCP-42",
            "expense_date": "2026-08-01",
            "payment_method": "cash",
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()["data"]
    exp = body["expense"]
    assert float(exp["amount"]) == 42.5
    assert exp["payee"] == "OCR Cafe"
    assert exp["reference"] == "OCR-RCP-42"
    assert exp["status"] in {"pending", "approved"}
    assert body["method"] == "rule_based_ocr_apply"

    listed = await ac.get("/api/v1/expenses", headers=admin)
    assert listed.status_code == 200
    ids = {e["id"] for e in listed.json()["data"]}
    assert exp["id"] in ids
