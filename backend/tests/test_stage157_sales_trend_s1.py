"""Stage 157 S1 — dashboard sales-trend CSV export."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.asyncio
async def test_dashboard_sales_trend_export_csv(client):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    exported = await ac.get("/api/v1/dashboard/sales-trend/export", headers=headers)
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    text = exported.text
    header = text.splitlines()[0]
    assert "row_type" in header and "period" in header and "revenue" in header


def test_dashboard_sales_trend_export_ui_s1():
    page = (ROOT / "frontend/app/dashboard/page.tsx").read_text(encoding="utf-8")
    assert "Stage 157" in page
    assert "/dashboard/sales-trend/export" in page
    assert "Export sales-trend CSV" in page
