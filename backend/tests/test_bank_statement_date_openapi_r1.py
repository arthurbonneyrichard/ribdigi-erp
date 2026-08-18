"""Bank statement statement_date + line txn_date OpenAPI honesty (BR-10.3)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import BankStatementCreateBody, BankStatementLineCreate, IsoDateQueryValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_iso_date_query_schema_for_bank_statement_dates():
    adapter = TypeAdapter(IsoDateQueryValue)
    assert adapter.validate_python(" 2026-08-17 ") == "2026-08-17"
    for bad in ("", " ", "not-a-date", "01/02/2024", "2026-13-01"):
        with pytest.raises(ValidationError):
            adapter.validate_python(bad)


def test_bank_statement_date_schema_rejects_invalid():
    with pytest.raises(ValidationError):
        BankStatementCreateBody.model_validate(
            {"account_id": "a", "statement_date": "not-a-date"}
        )
    with pytest.raises(ValidationError):
        BankStatementCreateBody.model_validate({"account_id": "a", "statement_date": ""})
    with pytest.raises(ValidationError):
        BankStatementCreateBody.model_validate(
            {"account_id": "a", "statement_date": "01/02/2024"}
        )
    with pytest.raises(ValidationError):
        BankStatementLineCreate.model_validate(
            {"amount": 10, "txn_date": "not-a-date"}
        )
    with pytest.raises(ValidationError):
        BankStatementLineCreate.model_validate({"amount": 10, "txn_date": ""})

    ok = BankStatementCreateBody.model_validate(
        {
            "account_id": "a",
            "statement_date": " 2020-01-01 ",
            "lines": [{"amount": 10, "txn_date": " 2020-01-02 "}],
        }
    )
    assert ok.statement_date == "2020-01-01"
    assert ok.lines[0].txn_date == "2020-01-02"

    omit = BankStatementCreateBody.model_validate({"account_id": "a"})
    assert omit.statement_date is None


def test_bank_statement_date_ui_and_docs():
    page = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Statement date"' in page
    assert 'aria-label="Statement line txn date"' in page
    assert "stmtDate" in page
    assert "lineTxnDate" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Bank statement date OpenAPI" in agents
    assert "IsoDateQueryValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "IsoDateQueryValue" in docs
    assert "bank-statements/import" in docs


@pytest.mark.asyncio
async def test_bank_statement_date_api_blank_invalid_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    accounts = await ac.get("/api/v1/accounting/liquid-accounts", headers=headers)
    assert accounts.status_code == 200, accounts.text
    acct = (accounts.json()["data"] or [None])[0]
    assert acct
    account_id = acct["id"]

    for bad in ("", "not-a-date", "01/02/2024"):
        bad_stmt = await ac.post(
            "/api/v1/accounting/bank-statements",
            headers=headers,
            json={
                "account_id": account_id,
                "statement_date": bad,
                "opening_balance": 0,
                "closing_balance": 10,
                "lines": [
                    {"txn_date": "2020-01-01", "amount": 10, "description": "ok"}
                ],
            },
        )
        assert bad_stmt.status_code == 422, (bad, bad_stmt.text)

        bad_line = await ac.post(
            "/api/v1/accounting/bank-statements",
            headers=headers,
            json={
                "account_id": account_id,
                "statement_date": "2020-01-01",
                "opening_balance": 0,
                "closing_balance": 10,
                "lines": [{"txn_date": bad, "amount": 10, "description": "bad"}],
            },
        )
        assert bad_line.status_code == 422, (bad, bad_line.text)

    created = await ac.post(
        "/api/v1/accounting/bank-statements",
        headers=headers,
        json={
            "account_id": account_id,
            "statement_date": "2020-01-01",
            "opening_balance": 0,
            "closing_balance": 25,
            "notes": "bank statement date tip",
            "lines": [
                {
                    "txn_date": "2020-01-01",
                    "amount": 25,
                    "description": "bank statement date tip",
                }
            ],
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()["data"]
    assert str(body.get("statement_date", "")).startswith("2020-01-01")

    omit = await ac.post(
        "/api/v1/accounting/bank-statements",
        headers=headers,
        json={
            "account_id": account_id,
            "opening_balance": 0,
            "closing_balance": 5,
            "lines": [{"amount": 5, "description": "omit dates"}],
        },
    )
    assert omit.status_code == 200, omit.text

    # Import Query statement_date honesty
    files = {"file": ("probe.csv", b"Date,Amount,Description\n2020-01-01,10,test\n", "text/csv")}
    bad_imp = await ac.post(
        f"/api/v1/accounting/bank-statements/import?account_id={account_id}&statement_date=not-a-date",
        headers=headers,
        files=files,
    )
    assert bad_imp.status_code == 422, bad_imp.text

    blank_imp = await ac.post(
        f"/api/v1/accounting/bank-statements/import?account_id={account_id}&statement_date=",
        headers=headers,
        files=files,
    )
    assert blank_imp.status_code == 422, blank_imp.text

    ok_imp = await ac.post(
        f"/api/v1/accounting/bank-statements/import?account_id={account_id}&statement_date=2020-01-01",
        headers=headers,
        files=files,
    )
    assert ok_imp.status_code == 200, ok_imp.text
