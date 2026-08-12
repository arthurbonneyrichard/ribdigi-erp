"""Stage 157 T1 — dashboard top-products CSV export."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.asyncio
async def test_dashboard_top_products_export_csv(client):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    exported = await ac.get("/api/v1/dashboard/top-products/export", headers=headers)
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    text = exported.text
    header = text.splitlines()[0]
    assert "rank" in header and "sku" in header and "revenue" in header


def test_dashboard_top_products_export_ui_t1():
    page = (ROOT / "frontend/app/dashboard/page.tsx").read_text(encoding="utf-8")
    assert "Stage 157" in page
    assert "/dashboard/top-products/export" in page
    assert "Export top-products CSV" in page
