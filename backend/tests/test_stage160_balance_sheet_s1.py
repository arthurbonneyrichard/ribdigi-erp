"""Stage 160 S1 — reports balance-sheet path CSV export."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.asyncio
async def test_reports_balance_sheet_export_csv(client):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    exported = await ac.get("/api/v1/reports/balance-sheet/export", headers=headers)
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    text = exported.text
    header = text.splitlines()[0]
    assert "as_of" in header
    assert "section" in header
    assert "total_assets" in header
    assert "balanced" in header


def test_reports_balance_sheet_export_ui_s1():
    page = (ROOT / "frontend/app/reports/page.tsx").read_text(encoding="utf-8")
    assert "Stage 160" in page
    assert "/reports/balance-sheet/export" in page
    assert "Export balance-sheet path CSV" in page
