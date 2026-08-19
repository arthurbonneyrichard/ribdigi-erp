"""BankStatementLineCreate.external_ref OpenAPI honesty (BR-10.3)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas import BankStatementLineCreate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_bank_statement_line_external_ref_schema():
    omit = BankStatementLineCreate.model_validate({"amount": 1})
    assert omit.external_ref is None
    nullish = BankStatementLineCreate.model_validate(
        {"amount": 1, "external_ref": None}
    )
    assert nullish.external_ref is None
    ok = BankStatementLineCreate.model_validate(
        {"amount": 1, "external_ref": "  FITID-9  "}
    )
    assert ok.external_ref == "FITID-9"
    for bad in ("", " ", "!!!", "http://evil", "@@", "x" * 121):
        with pytest.raises(ValidationError):
            BankStatementLineCreate.model_validate(
                {"amount": 1, "external_ref": bad}
            )


def test_bank_statement_line_external_ref_ui_and_docs():
    page = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Statement line external ref"' in page
    assert "lineExternalRef.trim() || null" in page
    assert 'aria-label="Create bank statement"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Bank statement line external_ref OpenAPI" in agents
    assert "BankStatementLineExternalRefValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "BankStatementLineExternalRefValue" in docs
    assert "external ref" in docs.lower()


@pytest.mark.asyncio
async def test_bank_statement_line_external_ref_api_blank_invalid_422(client):
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
                "lines": [
                    {
                        "amount": 2,
                        "description": "ok line",
                        "external_ref": bad,
                    }
                ],
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
            "lines": [{"amount": 3, "description": "omit xref line"}],
        },
    )
    assert omit.status_code == 200, omit.text
    assert omit.json()["data"]["lines"][0].get("external_ref") in (None, "")

    tag = f"TIP168-XREF-{suffix}"
    ok = await ac.post(
        "/api/v1/accounting/bank-statements",
        headers=headers,
        json={
            "account_id": acct["id"],
            "opening_balance": 0,
            "closing_balance": 4,
            "lines": [
                {
                    "amount": 4,
                    "description": "keep xref line",
                    "external_ref": f"  {tag}  ",
                }
            ],
        },
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["lines"][0].get("external_ref") == tag, ok.json()
