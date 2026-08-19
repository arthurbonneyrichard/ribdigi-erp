"""Stage 160 C1 — reports cash-flow path CSV export."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.asyncio
async def test_reports_cash_flow_export_csv(client):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    exported = await ac.get("/api/v1/reports/cash-flow/export", headers=headers)
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    text = exported.text
    header = text.splitlines()[0]
    assert "opening_cash" in header or "closing_cash" in header
    assert "net_change" in header
    assert "inflow" in header and "outflow" in header


def test_reports_cash_flow_export_ui_c1():
    page = (ROOT / "frontend/app/reports/page.tsx").read_text(encoding="utf-8")
    assert "Stage 160" in page
    assert "/reports/cash-flow/export" in page
    assert "Export cash-flow path CSV" in page
