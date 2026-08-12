"""Stage 157 P1 — combined AI inventory predictions CSV export."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.asyncio
async def test_inventory_predictions_export_csv(client):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    exported = await ac.get(
        "/api/v1/ai/inventory/predictions/export?horizon_days=14",
        headers=headers,
    )
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    text = exported.text
    header = text.splitlines()[0]
    assert "row_type" in header
    assert "forecast_7d" in header or "days_to_stockout" in header
    assert "summary" in text


def test_inventory_predictions_export_ui_p1():
    page = (ROOT / "frontend/app/ai/page.tsx").read_text(encoding="utf-8")
    assert "Stage 157" in page
    assert "/ai/inventory/predictions/export" in page
    assert "Export predictions CSV" in page
