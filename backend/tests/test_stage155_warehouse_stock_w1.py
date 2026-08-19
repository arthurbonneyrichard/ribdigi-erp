"""Stage 155 W1 — per-product warehouse-stock CSV export."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select

from app import models as m
from app.inventory import apply_stock_change
from app.stores import create_store
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.asyncio
async def test_product_warehouse_stock_export_csv(client, db_session):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    tenant_id = seed["t1"].id
    store = await create_store(
        db_session, tenant_id=tenant_id, code="WH155", name="Stage 155 WH Store"
    )
    await db_session.flush()
    wh = (
        await db_session.execute(
            select(m.Warehouse).where(m.Warehouse.store_id == store.id)
        )
    ).scalar_one()
    product = seed["p1"]
    await apply_stock_change(
        db_session,
        tenant_id=tenant_id,
        product_id=product.id,
        quantity_delta=7,
        movement_type="stock_in",
        user_id=seed["admin1"].id,
        warehouse_id=wh.id,
    )
    await db_session.commit()

    exported = await ac.get(
        f"/api/v1/products/{product.id}/warehouse-stock/export",
        headers=headers,
    )
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    text = exported.text
    header = text.splitlines()[0]
    assert "warehouse_id" in header and "warehouse_code" in header
    assert "quantity" in header and "consolidated_qty" in header
    assert wh.code in text
    assert product.id in text or product.sku in text


def test_product_warehouse_stock_export_ui_w1():
    page = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert "Stage 155" in page
    assert "/warehouse-stock/export" in page
    assert "Export warehouse-stock CSV" in page
