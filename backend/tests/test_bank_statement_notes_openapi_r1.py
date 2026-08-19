"""BankStatementCreateBody.notes OpenAPI honesty (BR-10.3)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas import BankStatementCreateBody
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_bank_statement_notes_schema():
    omit = BankStatementCreateBody.model_validate({"account_id": "a"})
    assert omit.notes is None
    nullish = BankStatementCreateBody.model_validate(
        {"account_id": "a", "notes": None}
    )
    assert nullish.notes is None
    ok = BankStatementCreateBody.model_validate(
        {"account_id": "a", "notes": "  Month-end feed  "}
    )
    assert ok.notes == "Month-end feed"
    for bad in ("", " ", "!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            BankStatementCreateBody.model_validate(
                {"account_id": "a", "notes": bad}
            )


def test_bank_statement_notes_ui_and_docs():
    page = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Statement notes"' in page
    assert "stmtNotes.trim() || null" in page
    assert 'aria-label="Create bank statement"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Bank statement notes OpenAPI" in agents
    assert "BankStatementNotesValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "BankStatementNotesValue" in docs
    assert "Statement notes" in docs or "`notes` ∈ `BankStatementNotesValue`" in docs


@pytest.mark.asyncio
async def test_bank_statement_notes_api_blank_invalid_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    suffix = uuid4().hex[:8]

    accounts = await ac.get("/api/v1/accounting/liquid-accounts", headers=headers)
    assert accounts.status_code == 200, accounts.text
    acct = (accounts.json()["data"] or [None])[0]
    assert acct

    for bad in ("", "!!!", "http://evil"):
        resp = await ac.post(
            "/api/v1/accounting/bank-statements",
            headers=headers,
            json={
                "account_id": acct["id"],
                "opening_balance": 0,
                "closing_balance": 2,
                "notes": bad,
                "lines": [{"amount": 2, "description": "ok line"}],
            },
        )
        assert resp.status_code == 422, (bad, resp.text)

    omit = await ac.post(
        "/api/v1/accounting/bank-statements",
        headers=headers,
        json={
            "account_id": acct["id"],
            "opening_balance": 0,
            "closing_balance": 3,
            "lines": [{"amount": 3, "description": "omit notes line"}],
        },
    )
    assert omit.status_code == 200, omit.text
    assert omit.json()["data"].get("notes") in (None, "")

    tag = f"Tip166 notes {suffix}"
    ok = await ac.post(
        "/api/v1/accounting/bank-statements",
        headers=headers,
        json={
            "account_id": acct["id"],
            "opening_balance": 0,
            "closing_balance": 4,
            "notes": f"  {tag}  ",
            "lines": [{"amount": 4, "description": "keep notes line"}],
        },
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"].get("notes") == tag, ok.json()
