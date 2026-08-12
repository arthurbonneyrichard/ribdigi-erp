"""Stage 146 K1 — AI dead-stock CSV export."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


@pytest.mark.asyncio
async def test_dead_stock_export_csv(client, db_session):
    ac, seed = client
    headers = await _mgr(ac)
    product = seed["p1"]
    product.stock_qty = 40
    product.cost_price = 3
    product.is_active = True
    # No recent sales → should appear as dead stock with lookback 90
    await db_session.commit()

    exported = await ac.get(
        "/api/v1/ai/inventory/dead-stock/export?lookback_days=90",
        headers=headers,
    )
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    text = exported.text
    header = text.splitlines()[0]
    assert "stock_qty" in header and "days_without_sale" in header
    assert "estimated_carrying_cost" in header
    assert product.id in text
    assert product.sku in text


def test_dead_stock_export_ui_k1():
    page = (ROOT / "frontend/app/ai/page.tsx").read_text(encoding="utf-8")
    assert "Stage 146" in page
    assert "/ai/inventory/dead-stock/export" in page
    assert "Export dead stock CSV" in page
    assert 'id="dead-stock"' in page
