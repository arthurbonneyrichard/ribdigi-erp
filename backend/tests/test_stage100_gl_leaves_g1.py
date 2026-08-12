"""Stage 100 G1 — Accounting GL leaf discoverability."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_shell_and_accounting_gl_anchors_g1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "Chart of Accounts" in shell
    assert "/accounting?tab=ledger#coa" in shell
    assert "Journals" in shell
    assert "/accounting?tab=ledger#journals" in shell
    assert "Trial Balance" in shell
    assert "/accounting?tab=ledger#trial-balance" in shell

    accounting = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert 'id="coa"' in accounting
    assert 'id="journals"' in accounting
    assert 'id="trial-balance"' in accounting
    assert "journalStatusFilter" in accounting
    assert "scrollIntoView" in accounting


@pytest.mark.asyncio
async def test_journal_entries_status_filter_api(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    bad = await ac.get("/api/v1/accounting/journal-entries?status=bogus", headers=headers)
    assert bad.status_code == 400

    posted = await ac.get("/api/v1/accounting/journal-entries?status=posted", headers=headers)
    assert posted.status_code == 200, posted.text
    for row in posted.json().get("data") or []:
        assert (row.get("status") or "posted") == "posted"

    unposted = await ac.get(
        "/api/v1/accounting/journal-entries?status=unposted", headers=headers
    )
    assert unposted.status_code == 200, unposted.text
    for row in unposted.json().get("data") or []:
        assert row.get("status") == "unposted"

    all_rows = await ac.get("/api/v1/accounting/journal-entries?status=all", headers=headers)
    assert all_rows.status_code == 200, all_rows.text
