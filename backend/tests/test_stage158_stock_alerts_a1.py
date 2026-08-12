"""Stage 158 A1 — dashboard stock-alerts CSV export."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.asyncio
async def test_dashboard_stock_alerts_export_csv(client):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    exported = await ac.get("/api/v1/dashboard/stock-alerts/export", headers=headers)
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    text = exported.text
    header = text.splitlines()[0]
    assert "metric" in header and "value" in header
    assert "low_stock" in text or "products" in text


def test_dashboard_stock_alerts_export_ui_a1():
    page = (ROOT / "frontend/app/dashboard/page.tsx").read_text(encoding="utf-8")
    assert "Stage 158" in page
    assert "/dashboard/stock-alerts/export" in page
    assert "Export stock-alerts CSV" in page
