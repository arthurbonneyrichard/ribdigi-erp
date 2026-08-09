"""Stage 2 inter-warehouse stock transfers."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app import models as m
from app.inventory import apply_stock_change, get_or_create_warehouse_stock
from tests.conftest import auth_headers


async def _wh_qty(db, tenant_id: str, warehouse_id: str, product_id: str) -> float:
    row = (
        await db.execute(
            select(m.WarehouseStock).where(
                m.WarehouseStock.tenant_id == tenant_id,
                m.WarehouseStock.warehouse_id == warehouse_id,
                m.WarehouseStock.product_id == product_id,
            )
        )
    ).scalar_one_or_none()
    return float(row.quantity) if row else 0.0


@pytest.mark.asyncio
async def test_warehouse_transfer_ship_receive_qty(client, db_session):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    wh_a = m.Warehouse(tenant_id=seed["t1"].id, name="WH A", code="WHA")
    wh_b = m.Warehouse(tenant_id=seed["t1"].id, name="WH B", code="WHB")
    db_session.add_all([wh_a, wh_b])
    await db_session.flush()
    wh_a_id, wh_b_id = wh_a.id, wh_b.id
    product_id = seed["p1"].id
    tenant_id = seed["t1"].id

    await apply_stock_change(
        db_session,
        tenant_id=tenant_id,
        product_id=product_id,
        quantity_delta=50,
        movement_type="stock_in",
        user_id=seed["mgr1"].id,
        warehouse_id=wh_a_id,
    )
    await db_session.commit()
    await db_session.refresh(seed["p1"])
    consolidated_before = float(seed["p1"].stock_qty)

    created = await ac.post(
        "/api/v1/inventory/stock-transfers",
        headers=headers,
        json={
            "from_warehouse_id": wh_a_id,
            "to_warehouse_id": wh_b_id,
            "submit": True,
            "items": [{"product_id": product_id, "quantity": 20}],
        },
    )
    assert created.status_code == 200, created.text
    transfer_id = created.json()["data"]["id"]
    assert created.json()["data"]["status"] == "requested"
    assert created.json()["data"]["from_store_id"] is None
    assert created.json()["data"]["to_store_id"] is None

    shipped = await ac.post(
        f"/api/v1/inventory/stock-transfers/{transfer_id}/ship",
        headers=headers,
    )
    assert shipped.status_code == 200, shipped.text
    assert shipped.json()["data"]["status"] == "in_transit"

    db_session.expire_all()
    src_qty = await _wh_qty(db_session, tenant_id, wh_a_id, product_id)
    # Ship allocates unlocated consolidated qty into source, then deducts transfer qty.
    assert src_qty == pytest.approx(consolidated_before - 20)

    received = await ac.post(
        f"/api/v1/inventory/stock-transfers/{transfer_id}/receive",
        headers=headers,
    )
    assert received.status_code == 200, received.text
    assert received.json()["data"]["status"] == "received"

    db_session.expire_all()
    dest_qty = await _wh_qty(db_session, tenant_id, wh_b_id, product_id)
    assert dest_qty == 20

    product = (
        await db_session.execute(select(m.Product).where(m.Product.id == product_id))
    ).scalar_one()
    assert float(product.stock_qty) == pytest.approx(consolidated_before)

    moves = (
        await db_session.execute(
            select(m.StockMovement).where(
                m.StockMovement.tenant_id == tenant_id,
                m.StockMovement.reference_id == transfer_id,
            )
        )
    ).scalars().all()
    types = {mvt.movement_type for mvt in moves}
    assert "transfer_out" in types
    assert "transfer_in" in types


@pytest.mark.asyncio
async def test_warehouse_transfer_rejects_same_warehouse(client, db_session):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    wh = m.Warehouse(tenant_id=seed["t1"].id, name="Solo", code="SOLO")
    db_session.add(wh)
    await db_session.commit()

    r = await ac.post(
        "/api/v1/inventory/stock-transfers",
        headers=headers,
        json={
            "from_warehouse_id": wh.id,
            "to_warehouse_id": wh.id,
            "items": [{"product_id": seed["p1"].id, "quantity": 1}],
        },
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_warehouse_transfer_cancel_after_ship_restores_source(client, db_session):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    wh_a = m.Warehouse(tenant_id=seed["t1"].id, name="Src", code="SRC")
    wh_b = m.Warehouse(tenant_id=seed["t1"].id, name="Dst", code="DST")
    db_session.add_all([wh_a, wh_b])
    await db_session.flush()
    wh_a_id, wh_b_id = wh_a.id, wh_b.id
    product_id = seed["p1"].id
    tenant_id = seed["t1"].id
    await apply_stock_change(
        db_session,
        tenant_id=tenant_id,
        product_id=product_id,
        quantity_delta=10,
        movement_type="stock_in",
        user_id=seed["mgr1"].id,
        warehouse_id=wh_a_id,
    )
    await db_session.commit()
    await db_session.refresh(seed["p1"])
    consolidated = float(seed["p1"].stock_qty)

    created = await ac.post(
        "/api/v1/inventory/stock-transfers",
        headers=headers,
        json={
            "from_warehouse_id": wh_a_id,
            "to_warehouse_id": wh_b_id,
            "submit": True,
            "items": [{"product_id": product_id, "quantity": 4}],
        },
    )
    transfer_id = created.json()["data"]["id"]
    await ac.post(f"/api/v1/inventory/stock-transfers/{transfer_id}/ship", headers=headers)
    cancelled = await ac.post(
        f"/api/v1/inventory/stock-transfers/{transfer_id}/cancel",
        headers=headers,
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["data"]["status"] == "cancelled"

    db_session.expire_all()
    src_qty = await _wh_qty(db_session, tenant_id, wh_a_id, product_id)
    # After cancel, source holds all consolidated qty (allocated + restored).
    assert src_qty == pytest.approx(consolidated)


@pytest.mark.asyncio
async def test_foreign_warehouse_transfer_404(client, db_session):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    beta_wh = m.Warehouse(tenant_id=seed["t2"].id, name="Beta WH", code="BWH")
    alpha_wh = m.Warehouse(tenant_id=seed["t1"].id, name="Alpha WH", code="AWH")
    db_session.add_all([beta_wh, alpha_wh])
    await db_session.commit()

    r = await ac.post(
        "/api/v1/inventory/stock-transfers",
        headers=headers,
        json={
            "from_warehouse_id": alpha_wh.id,
            "to_warehouse_id": beta_wh.id,
            "items": [{"product_id": seed["p1"].id, "quantity": 1}],
        },
    )
    assert r.status_code == 404
