"""GET /accounting/bank-statements status Query OpenAPI + Reconcile filter (BR-10.3)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import BankStatementStatusFilterValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_bank_statement_status_filter_literal_schema():
    adapter = TypeAdapter(BankStatementStatusFilterValue)
    assert adapter.validate_python("draft") == "draft"
    assert adapter.validate_python("  In_Progress ") == "in_progress"
    assert adapter.validate_python("RECONCILED") == "reconciled"
    with pytest.raises(ValidationError):
        adapter.validate_python("")
    with pytest.raises(ValidationError):
        adapter.validate_python("   ")
    with pytest.raises(ValidationError):
        adapter.validate_python("open")
    with pytest.raises(ValidationError):
        adapter.validate_python("garbage_xyz")


def test_bank_statement_status_filter_ui_and_docs():
    page = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert "statementManageFilter" in page
    assert "managedStatements" in page
    assert 'aria-label="Bank statement status filter"' in page
    assert 'value="draft"' in page
    assert 'value="in_progress"' in page
    assert 'value="reconciled"' in page
    assert "No statements for this filter" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Bank statement status Query OpenAPI" in agents
    assert "statementManageFilter" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "statementManageFilter" in docs
    assert "in_progress" in docs and "422" in docs


@pytest.mark.asyncio
async def test_bank_statement_status_filter_api_blank_invalid_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    blank = await ac.get("/api/v1/accounting/bank-statements?status=", headers=headers)
    assert blank.status_code == 422, blank.text

    bad = await ac.get("/api/v1/accounting/bank-statements?status=open", headers=headers)
    assert bad.status_code == 422, bad.text

    # Ensure at least one statement exists for positive filter checks.
    stmts = await ac.get("/api/v1/accounting/bank-statements", headers=headers)
    assert stmts.status_code == 200, stmts.text
    rows = stmts.json()["data"] or []
    if not rows:
        accounts = await ac.get("/api/v1/accounting/liquid-accounts", headers=headers)
        assert accounts.status_code == 200, accounts.text
        acct = (accounts.json()["data"] or [None])[0]
        assert acct
        conn = await ac.post(
            "/api/v1/accounting/bank-connections",
            headers=headers,
            json={
                "account_id": acct["id"],
                "provider": "mock",
                "display_name": "Statement status OpenAPI",
            },
        )
        assert conn.status_code == 200, conn.text
        sync = await ac.post(
            f"/api/v1/accounting/bank-connections/{conn.json()['data']['id']}/sync",
            headers=headers,
            json={},
        )
        assert sync.status_code == 200, sync.text
        stmts = await ac.get("/api/v1/accounting/bank-statements", headers=headers)
        assert stmts.status_code == 200, stmts.text
        rows = stmts.json()["data"] or []
    assert rows

    status = rows[0]["status"]
    assert status in {"draft", "in_progress", "reconciled"}

    filtered = await ac.get(
        f"/api/v1/accounting/bank-statements?status={status}", headers=headers
    )
    assert filtered.status_code == 200, filtered.text
    assert all(r["status"] == status for r in filtered.json()["data"])
    assert any(r["id"] == rows[0]["id"] for r in filtered.json()["data"])

    cased = await ac.get(
        "/api/v1/accounting/bank-statements?status=In_Progress", headers=headers
    )
    assert cased.status_code == 200, cased.text
    assert all(r["status"] == "in_progress" for r in cased.json()["data"])

    omit = await ac.get("/api/v1/accounting/bank-statements", headers=headers)
    assert omit.status_code == 200, omit.text
