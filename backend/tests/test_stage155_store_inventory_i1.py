"""Stage 155 I1 — store inventory / reorder CSV export."""

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
async def test_store_inventory_export_csv(client, db_session):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    tenant_id = seed["t1"].id
    store = await create_store(
        db_session, tenant_id=tenant_id, code="INV155", name="Stage 155 Inv Store"
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
        quantity_delta=4,
        movement_type="stock_in",
        user_id=seed["admin1"].id,
        warehouse_id=wh.id,
    )
    await db_session.commit()

    exported = await ac.get(
        f"/api/v1/stores/{store.id}/inventory/export",
        headers=headers,
    )
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    text = exported.text
    header = text.splitlines()[0]
    assert "product_id" in header and "quantity" in header and "reorder_level" in header
    assert "sku" in header and "below_reorder" in header
    assert product.sku in text or product.id in text


def test_store_inventory_export_ui_i1():
    page = (ROOT / "frontend/app/stores/page.tsx").read_text(encoding="utf-8")
    assert "Stage 155" in page
    assert "/inventory/export" in page
    assert "Export inventory CSV" in page
