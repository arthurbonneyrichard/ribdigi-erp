"""GET /accounting/journal-entries status Query OpenAPI + Ledger filter (BR-10.2)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import JournalStatusFilterValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_journal_manage_status_literal_schema():
    adapter = TypeAdapter(JournalStatusFilterValue)
    assert adapter.validate_python("posted") == "posted"
    assert adapter.validate_python("  Unposted ") == "unposted"
    assert adapter.validate_python("POSTED") == "posted"
    with pytest.raises(ValidationError):
        adapter.validate_python("")
    with pytest.raises(ValidationError):
        adapter.validate_python("   ")
    with pytest.raises(ValidationError):
        adapter.validate_python("draft")
    with pytest.raises(ValidationError):
        adapter.validate_python("garbage_xyz")


def test_journal_manage_status_ui_and_docs():
    page = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert "journalManageFilter" in page
    assert "managedJournals" in page
    assert 'aria-label="Journal status filter"' in page
    assert 'value="posted"' in page
    assert 'value="unposted"' in page
    assert "No journals for this filter" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Journal manage status Query OpenAPI" in agents
    assert "journalManageFilter" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "journalManageFilter" in docs
    assert "GET /accounting/journal-entries" in docs
    assert "posted" in docs and "unposted" in docs


@pytest.mark.asyncio
async def test_journal_manage_status_api_blank_invalid_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    blank = await ac.get("/api/v1/accounting/journal-entries?status=", headers=headers)
    assert blank.status_code == 422, blank.text

    bad = await ac.get("/api/v1/accounting/journal-entries?status=draft", headers=headers)
    assert bad.status_code == 422, bad.text

    accounts = await ac.get("/api/v1/accounting/accounts", headers=headers)
    assert accounts.status_code == 200, accounts.text
    rows = accounts.json()["data"] or []
    # Prefer Cash + Equity-ish codes for a balanced manual JE.
    by_code = {a["code"]: a for a in rows}
    cash = by_code.get("1000") or next(
        (a for a in rows if a.get("is_cash_account") or a.get("is_bank_account")), None
    )
    equity = by_code.get("3000") or next(
        (a for a in rows if a.get("account_type") in {"equity", "liability", "revenue"}), None
    )
    assert cash and equity

    created = await ac.post(
        "/api/v1/accounting/journal-entries",
        headers=headers,
        json={
            "description": "journalManageFilter hello-world",
            "lines": [
                {"account_code": cash["code"], "debit": 25, "credit": 0},
                {"account_code": equity["code"], "debit": 0, "credit": 25},
            ],
        },
    )
    assert created.status_code == 200, created.text
    entry = created.json()["data"]
    assert entry["status"] == "posted"
    eid = entry["id"]

    posted = await ac.get(
        "/api/v1/accounting/journal-entries?status=Posted", headers=headers
    )
    assert posted.status_code == 200, posted.text
    assert any(r["id"] == eid for r in posted.json()["data"])
    assert all(r["status"] == "posted" for r in posted.json()["data"])

    unposted = await ac.get(
        "/api/v1/accounting/journal-entries?status=unposted", headers=headers
    )
    assert unposted.status_code == 200, unposted.text
    assert all(r["id"] != eid for r in unposted.json()["data"])
    assert all(r["status"] == "unposted" for r in unposted.json()["data"])

    omit = await ac.get("/api/v1/accounting/journal-entries", headers=headers)
    assert omit.status_code == 200, omit.text
    assert any(r["id"] == eid for r in omit.json()["data"])
