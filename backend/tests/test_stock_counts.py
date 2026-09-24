"""Physical stock count variance adjustments."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app import models as m
from app.inventory import apply_stock_change
from app.stock_counts import complete_count, create_count, serialize_count, update_count_items
from app.stores import create_store
from tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_stock_count_variance_adjusts_warehouse_and_product(client, db_session):
    ac, seed = client
    # Start from a known consolidated qty so warehouse allocation is deterministic.
    product = await db_session.get(m.Product, seed["p1"].id)
    product.stock_qty = 0
    await db_session.commit()

    store = await create_store(
        db_session, tenant_id=seed["t1"].id, name="Count Store", code="CNT"
    )
    await db_session.flush()
    wh = (
        await db_session.execute(
            select(m.Warehouse).where(
                m.Warehouse.tenant_id == seed["t1"].id,
                m.Warehouse.store_id == store.id,
            )
        )
    ).scalar_one()

    await apply_stock_change(
        db_session,
        tenant_id=seed["t1"].id,
        product_id=seed["p1"].id,
        quantity_delta=10,
        movement_type="stock_in",
        user_id=seed["mgr1"].id,
        warehouse_id=wh.id,
    )
    await db_session.commit()

    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    created = await ac.post(
        "/api/v1/inventory/stock-counts",
        headers=headers,
        json={"warehouse_id": wh.id, "product_ids": [seed["p1"].id]},
    )
    assert created.status_code == 200, created.text
    count = created.json()["data"]
    assert count["status"] == "draft"
    assert count["items"][0]["expected_qty"] == 10

    patched = await ac.patch(
        f"/api/v1/inventory/stock-counts/{count['id']}/items",
        headers=headers,
        json={"items": [{"product_id": seed["p1"].id, "counted_qty": 7}]},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["data"]["items"][0]["variance"] == -3

    done = await ac.post(
        f"/api/v1/inventory/stock-counts/{count['id']}/complete",
        headers=headers,
    )
    assert done.status_code == 200, done.text
    assert done.json()["data"]["status"] == "completed"

    product = await db_session.get(m.Product, seed["p1"].id)
    await db_session.refresh(product)
    assert float(product.stock_qty) == 7

    stock = (
        await db_session.execute(
            select(m.WarehouseStock).where(
                m.WarehouseStock.tenant_id == seed["t1"].id,
                m.WarehouseStock.warehouse_id == wh.id,
                m.WarehouseStock.product_id == seed["p1"].id,
            )
        )
    ).scalar_one()
    assert float(stock.quantity) == 7

    moves = await ac.get(
        f"/api/v1/inventory/movements?product_id={seed['p1'].id}&movement_type=adjustment",
        headers=headers,
    )
    assert moves.status_code == 200
    rows = moves.json()["data"]["movements"]
    assert any(float(row["quantity"]) == -3 for row in rows)


@pytest.mark.asyncio
async def test_stock_count_zero_variance_skips_movement(db_session, seeded):
    product = await db_session.get(m.Product, seeded["p1"].id)
    product.stock_qty = 0
    await db_session.commit()

    store = await create_store(
        db_session, tenant_id=seeded["t1"].id, name="Zero Store", code="ZRO"
    )
    await db_session.flush()
    wh = (
        await db_session.execute(
            select(m.Warehouse).where(
                m.Warehouse.tenant_id == seeded["t1"].id,
                m.Warehouse.store_id == store.id,
            )
        )
    ).scalar_one()
    await apply_stock_change(
        db_session,
        tenant_id=seeded["t1"].id,
        product_id=seeded["p1"].id,
        quantity_delta=4,
        movement_type="stock_in",
        user_id=seeded["mgr1"].id,
        warehouse_id=wh.id,
    )
    count = await create_count(
        db_session,
        tenant_id=seeded["t1"].id,
        user_id=seeded["mgr1"].id,
        warehouse_id=wh.id,
        product_ids=[seeded["p1"].id],
    )
    data = await serialize_count(db_session, count)
    expected = float(data["items"][0]["expected_qty"])
    await update_count_items(
        db_session,
        tenant_id=seeded["t1"].id,
        count_id=count.id,
        items=[{"product_id": seeded["p1"].id, "counted_qty": expected}],
    )
    before_moves = (
        await db_session.execute(
            select(m.StockMovement).where(
                m.StockMovement.tenant_id == seeded["t1"].id,
                m.StockMovement.reference_type == "stock_count",
            )
        )
    ).scalars().all()
    await complete_count(
        db_session,
        tenant_id=seeded["t1"].id,
        user_id=seeded["mgr1"].id,
        count_id=count.id,
    )
    await db_session.commit()
    after_moves = (
        await db_session.execute(
            select(m.StockMovement).where(
                m.StockMovement.tenant_id == seeded["t1"].id,
                m.StockMovement.reference_type == "stock_count",
            )
        )
    ).scalars().all()
    assert len(after_moves) == len(before_moves)


@pytest.mark.asyncio
async def test_foreign_stock_count_404(client, db_session):
    ac, seed = client
    store = await create_store(
        db_session, tenant_id=seed["t2"].id, name="Beta Count", code="BCN"
    )
    await db_session.flush()
    wh = (
        await db_session.execute(
            select(m.Warehouse).where(
                m.Warehouse.tenant_id == seed["t2"].id,
                m.Warehouse.store_id == store.id,
            )
        )
    ).scalar_one()
    count = await create_count(
        db_session,
        tenant_id=seed["t2"].id,
        user_id=seed["u2"].id,
        warehouse_id=wh.id,
        product_ids=[seed["p2"].id],
    )
    await db_session.commit()

    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    r = await ac.get(f"/api/v1/inventory/stock-counts/{count.id}", headers=headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_product_patch_reorder_and_foreign_404(client):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    patched = await ac.patch(
        f"/api/v1/products/{seed['p1'].id}",
        headers=headers,
        json={"reorder_level": 3, "tracks_batches": True, "selling_price": 9.5},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["data"]["reorder_level"] == 3
    assert patched.json()["data"]["tracks_batches"] is True
    assert float(patched.json()["data"]["selling_price"]) == 9.5

    missing = await ac.get(f"/api/v1/products/{seed['p2'].id}", headers=headers)
    assert missing.status_code == 404
