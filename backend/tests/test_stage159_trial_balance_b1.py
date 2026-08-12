"""Stage 159 B1 — accounting trial-balance CSV export."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.asyncio
async def test_accounting_trial_balance_export_csv(client):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    exported = await ac.get("/api/v1/accounting/trial-balance/export", headers=headers)
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    text = exported.text
    header = text.splitlines()[0]
    assert "as_of" in header
    assert "account_id" in header or "code" in header
    assert "total_debit" in header and "total_credit" in header


def test_accounting_trial_balance_export_ui_b1():
    page = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert "Stage 159" in page
    assert "/accounting/trial-balance/export" in page
    assert "Export trial-balance CSV" in page
