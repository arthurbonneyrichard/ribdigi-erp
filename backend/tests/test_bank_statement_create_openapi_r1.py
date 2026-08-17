"""POST /accounting/bank-statements typed BankStatementCreateBody OpenAPI (BR-10.3)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas import BankStatementCreateBody, BankStatementLineCreate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_bank_statement_create_schema_forbid_and_bounds():
    ok = BankStatementCreateBody.model_validate(
        {
            "account_id": "  acct-1  ",
            "opening_balance": 10,
            "closing_balance": 25,
            "notes": "  hello  ",
            "lines": [
                {
                    "amount": 15,
                    "txn_date": " 2026-08-17 ",
                    "description": "  Line  ",
                    "external_ref": "  xref  ",
                }
            ],
        }
    )
    assert ok.account_id == "acct-1"
    assert ok.notes == "hello"
    assert ok.lines[0].description == "Line"
    assert ok.lines[0].external_ref == "xref"
    assert ok.lines[0].txn_date == "2026-08-17"

    empty_lines = BankStatementCreateBody.model_validate({"account_id": "a"})
    assert empty_lines.lines == []
    assert empty_lines.opening_balance == 0

    with pytest.raises(ValidationError):
        BankStatementCreateBody.model_validate({})
    with pytest.raises(ValidationError):
        BankStatementCreateBody.model_validate({"account_id": ""})
    with pytest.raises(ValidationError):
        BankStatementCreateBody.model_validate({"account_id": "   "})
    with pytest.raises(ValidationError):
        BankStatementCreateBody.model_validate({"account_id": "a", "extra": 1})
    with pytest.raises(ValidationError):
        BankStatementCreateBody.model_validate(
            {"account_id": "a", "lines": [{"amount": 0}]}
        )
    with pytest.raises(ValidationError):
        BankStatementLineCreate.model_validate({"amount": 1, "unknown": True})


def test_bank_statement_create_ui_and_docs():
    page = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Reconcile liquid account"' in page
    assert 'aria-label="Statement opening balance"' in page
    assert 'aria-label="Statement closing balance"' in page
    assert 'aria-label="Statement line amount"' in page
    assert 'aria-label="Statement line description"' in page
    assert 'aria-label="Create bank statement"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Bank statement create body OpenAPI" in agents
    assert "BankStatementCreateBody" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "BankStatementCreateBody" in docs
    assert "BankStatementLineCreate" in docs
    assert "extra=forbid" in docs


@pytest.mark.asyncio
async def test_bank_statement_create_api_unknown_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    accounts = await ac.get("/api/v1/accounting/liquid-accounts", headers=headers)
    assert accounts.status_code == 200, accounts.text
    acct = (accounts.json()["data"] or [None])[0]
    assert acct

    unknown = await ac.post(
        "/api/v1/accounting/bank-statements",
        headers=headers,
        json={"account_id": acct["id"], "foo": 1},
    )
    assert unknown.status_code == 422, unknown.text

    blank = await ac.post(
        "/api/v1/accounting/bank-statements",
        headers=headers,
        json={"account_id": ""},
    )
    assert blank.status_code == 422, blank.text

    omit = await ac.post("/api/v1/accounting/bank-statements", headers=headers, json={})
    assert omit.status_code == 422, omit.text

    zero_line = await ac.post(
        "/api/v1/accounting/bank-statements",
        headers=headers,
        json={
            "account_id": acct["id"],
            "lines": [{"amount": 0, "description": "zero"}],
        },
    )
    assert zero_line.status_code == 422, zero_line.text

    created = await ac.post(
        "/api/v1/accounting/bank-statements",
        headers=headers,
        json={
            "account_id": acct["id"],
            "statement_date": "2026-08-17",
            "opening_balance": 100,
            "closing_balance": 115,
            "notes": "BankStatementCreateBody hello-world",
            "lines": [
                {
                    "txn_date": "2026-08-17",
                    "amount": 15,
                    "description": "BankStatementCreateBody hello-world",
                }
            ],
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()["data"]
    assert body["notes"] == "BankStatementCreateBody hello-world"
    assert body["status"] == "in_progress"
    assert body["line_count"] == 1
    assert abs(float(body["opening_balance"]) - 100) < 1e-9
