"""Stage 161 X1 — reports tax path CSV export."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.asyncio
async def test_reports_tax_export_csv(client):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    exported = await ac.get("/api/v1/reports/tax/export", headers=headers)
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    text = exported.text
    header = text.splitlines()[0]
    assert "output_tax" in header
    assert "input_tax" in header
    assert "net_tax_payable" in header


def test_reports_tax_export_ui_x1():
    reports = (ROOT / "frontend/app/reports/page.tsx").read_text(encoding="utf-8")
    tax = (ROOT / "frontend/app/tax/page.tsx").read_text(encoding="utf-8")
    assert "Stage 161" in reports or "Stage 161" in tax
    assert "/reports/tax/export" in reports
    assert "Export tax path CSV" in reports
    assert "/reports/tax/export" in tax
    assert "Export tax path CSV" in tax
