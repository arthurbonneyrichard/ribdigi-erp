"""BankStatementLineCreate.description OpenAPI honesty (BR-10.3)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas import BankStatementCreateBody, BankStatementLineCreate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_bank_statement_line_description_schema():
    omit = BankStatementLineCreate.model_validate({"amount": 10})
    assert omit.description is None
    nullish = BankStatementLineCreate.model_validate(
        {"amount": 10, "description": None}
    )
    assert nullish.description is None
    ok = BankStatementLineCreate.model_validate(
        {"amount": 10, "description": "  Deposit ACH  "}
    )
    assert ok.description == "Deposit ACH"
    for bad in ("", " ", "!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            BankStatementLineCreate.model_validate(
                {"amount": 10, "description": bad}
            )
    # Nested create body rejects garbage line description.
    with pytest.raises(ValidationError):
        BankStatementCreateBody.model_validate(
            {
                "account_id": "a",
                "lines": [{"amount": 10, "description": "!!!!"}],
            }
        )


def test_bank_statement_line_description_ui_and_docs():
    page = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Statement line description"' in page
    assert "const desc = lineDesc.trim() || null" in page
    assert "description: desc" in page
    assert 'aria-label="Create bank statement"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Bank statement line description OpenAPI" in agents
    assert "BankStatementLineDescriptionValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "BankStatementLineDescriptionValue" in docs
    assert "Statement line description" in docs or "line `description`" in docs


@pytest.mark.asyncio
async def test_bank_statement_line_description_api_blank_invalid_422(client):
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
                "closing_balance": 5,
                "lines": [{"amount": 5, "description": bad}],
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
            "lines": [{"amount": 3}],
        },
    )
    assert omit.status_code == 200, omit.text
    omit_lines = omit.json()["data"].get("lines") or []
    assert omit_lines, omit.json()
    assert omit_lines[0].get("description") in (None, "")

    tag = f"Tip165 desc {suffix}"
    ok = await ac.post(
        "/api/v1/accounting/bank-statements",
        headers=headers,
        json={
            "account_id": acct["id"],
            "opening_balance": 0,
            "closing_balance": 7,
            "lines": [{"amount": 7, "description": f"  {tag}  "}],
        },
    )
    assert ok.status_code == 200, ok.text
    lines = ok.json()["data"].get("lines") or []
    assert lines and lines[0].get("description") == tag, ok.json()
