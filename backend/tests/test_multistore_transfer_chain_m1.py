"""Stage 16 M1: inter-store transfer → warehouse stock → stock_movements → movements report."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app import models as m
from app.inventory import apply_stock_change
from app.rbac import permissions_for_role
from app.security import hash_password
from app.stores import create_store
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
async def test_inter_store_transfer_stock_movement_chain(client, db_session):
    ac, seed = client
    tenant_id = seed["t1"].id
    mgr_from = seed["mgr1"]

    # Dedicated product avoids seed unlocated stock being parked on ship via allocate_unlocated_stock.
    product = m.Product(
        tenant_id=tenant_id,
        name="S16 M1 Transfer SKU",
        sku="S16-M1-XFER",
        cost_price=3,
        selling_price=6,
        stock_qty=0,
    )
    db_session.add(product)
    await db_session.flush()
    product_id = product.id

    mgr_to = m.User(
        tenant_id=tenant_id,
        email="mgr-s16-m1-dest@alpha.example.com",
        full_name="S16 M1 Dest Manager",
        password_hash=hash_password("SecurePass123!"),
        role="store_manager",
        email_verified=True,
        permissions=permissions_for_role("store_manager"),
        totp_enabled=False,
    )
    db_session.add(mgr_to)
    await db_session.flush()

    from_store = await create_store(
        db_session,
        tenant_id=tenant_id,
        code="S16M1S",
        name="S16 M1 Source",
        manager_id=mgr_from.id,
    )
    to_store = await create_store(
        db_session,
        tenant_id=tenant_id,
        code="S16M1D",
        name="S16 M1 Dest",
        manager_id=mgr_to.id,
    )
    await db_session.flush()
    from_store_id, to_store_id = from_store.id, to_store.id

    from_wh = (
        await db_session.execute(
            select(m.Warehouse).where(
                m.Warehouse.tenant_id == tenant_id,
                m.Warehouse.store_id == from_store_id,
            )
        )
    ).scalar_one()
    to_wh = (
        await db_session.execute(
            select(m.Warehouse).where(
                m.Warehouse.tenant_id == tenant_id,
                m.Warehouse.store_id == to_store_id,
            )
        )
    ).scalar_one()
    from_wh_id, to_wh_id = from_wh.id, to_wh.id

    qty_ship = 7.0
    opening = 40.0
    await apply_stock_change(
        db_session,
        tenant_id=tenant_id,
        product_id=product_id,
        quantity_delta=opening,
        movement_type="stock_in",
        user_id=mgr_from.id,
        warehouse_id=from_wh_id,
    )
    await db_session.commit()

    assert await _wh_qty(db_session, tenant_id, from_wh_id, product_id) == pytest.approx(opening)
    assert await _wh_qty(db_session, tenant_id, to_wh_id, product_id) == pytest.approx(0)

    mgr_from_h = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    mgr_to_h = await auth_headers(
        ac, email="mgr-s16-m1-dest@alpha.example.com", tenant_slug="alpha"
    )

    created = await ac.post(
        "/api/v1/stores/transfers",
        headers=mgr_from_h,
        json={
            "from_store_id": from_store_id,
            "to_store_id": to_store_id,
            "submit": True,
            "items": [{"product_id": product_id, "quantity": qty_ship}],
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()["data"]
    transfer_id = body["id"]
    assert body["status"] == "requested"
    assert body["from_warehouse_id"] == from_wh_id
    assert body["to_warehouse_id"] == to_wh_id

    # Stage 4 T1 regression: destination manager cannot ship
    denied_ship = await ac.post(
        f"/api/v1/stores/transfers/{transfer_id}/ship",
        headers=mgr_to_h,
    )
    assert denied_ship.status_code == 403, denied_ship.text
    assert denied_ship.json()["detail"]["code"] == "TRANSFER_SHIP_FORBIDDEN"

    shipped = await ac.post(
        f"/api/v1/stores/transfers/{transfer_id}/ship",
        headers=mgr_from_h,
    )
    assert shipped.status_code == 200, shipped.text
    assert shipped.json()["data"]["status"] == "in_transit"

    db_session.expire_all()
    assert await _wh_qty(db_session, tenant_id, from_wh_id, product_id) == pytest.approx(
        opening - qty_ship
    )
    assert await _wh_qty(db_session, tenant_id, to_wh_id, product_id) == pytest.approx(0)

    out_moves = (
        await db_session.execute(
            select(m.StockMovement).where(
                m.StockMovement.tenant_id == tenant_id,
                m.StockMovement.reference_id == transfer_id,
                m.StockMovement.movement_type == "transfer_out",
            )
        )
    ).scalars().all()
    assert len(out_moves) == 1
    assert out_moves[0].reference_type == "stock_transfer"
    assert out_moves[0].warehouse_id == from_wh_id
    assert float(out_moves[0].quantity) == pytest.approx(-qty_ship)

    # Source manager cannot receive
    denied_recv = await ac.post(
        f"/api/v1/stores/transfers/{transfer_id}/receive",
        headers=mgr_from_h,
    )
    assert denied_recv.status_code == 403, denied_recv.text
    assert denied_recv.json()["detail"]["code"] == "TRANSFER_RECEIVE_FORBIDDEN"

    received = await ac.post(
        f"/api/v1/stores/transfers/{transfer_id}/receive",
        headers=mgr_to_h,
    )
    assert received.status_code == 200, received.text
    assert received.json()["data"]["status"] == "received"

    db_session.expire_all()
    assert await _wh_qty(db_session, tenant_id, from_wh_id, product_id) == pytest.approx(
        opening - qty_ship
    )
    assert await _wh_qty(db_session, tenant_id, to_wh_id, product_id) == pytest.approx(qty_ship)

    in_moves = (
        await db_session.execute(
            select(m.StockMovement).where(
                m.StockMovement.tenant_id == tenant_id,
                m.StockMovement.reference_id == transfer_id,
                m.StockMovement.movement_type == "transfer_in",
            )
        )
    ).scalars().all()
    assert len(in_moves) == 1
    assert in_moves[0].reference_type == "stock_transfer"
    assert in_moves[0].warehouse_id == to_wh_id
    assert float(in_moves[0].quantity) == pytest.approx(qty_ship)

    # Consolidated product qty unchanged (location move only)
    product_row = (
        await db_session.execute(select(m.Product).where(m.Product.id == product_id))
    ).scalar_one()
    assert float(product_row.stock_qty) == pytest.approx(opening)

    # Stock-per-location via store inventory API
    dest_inv = await ac.get(
        f"/api/v1/stores/{to_store_id}/inventory",
        headers=mgr_to_h,
    )
    assert dest_inv.status_code == 200, dest_inv.text
    dest_rows = dest_inv.json()["data"]
    if isinstance(dest_rows, dict):
        dest_rows = dest_rows.get("items") or dest_rows.get("products") or []
    match = next((r for r in dest_rows if r.get("product_id") == product_id), None)
    assert match is not None, dest_inv.text
    qty_field = match.get("quantity", match.get("stock_qty", match.get("on_hand")))
    assert float(qty_field) == pytest.approx(qty_ship)

    # Movements report includes both legs
    report = await ac.get(
        f"/api/v1/reports/inventory/movements?product_id={product_id}",
        headers=mgr_from_h,
    )
    assert report.status_code == 200, report.text
    movements = report.json()["data"]["movements"]
    chain = [mvt for mvt in movements if mvt.get("reference_id") == transfer_id]
    types = {mvt["movement_type"] for mvt in chain}
    assert "transfer_out" in types
    assert "transfer_in" in types
    assert all(mvt.get("reference_type") == "stock_transfer" for mvt in chain)


@pytest.mark.asyncio
async def test_inter_store_ship_insufficient_warehouse_stock(client, db_session):
    """Ship fails closed when source warehouse lacks available qty (no partial receive path)."""
    ac, seed = client
    tenant_id = seed["t1"].id
    mgr_from = seed["mgr1"]

    product = m.Product(
        tenant_id=tenant_id,
        name="S16 M1 Insuf SKU",
        sku="S16-M1-INSUF",
        cost_price=1,
        selling_price=2,
        stock_qty=0,
    )
    db_session.add(product)
    await db_session.flush()
    product_id = product.id

    mgr_to = m.User(
        tenant_id=tenant_id,
        email="mgr-s16-m1-insuf@alpha.example.com",
        full_name="S16 M1 Insuf Dest",
        password_hash=hash_password("SecurePass123!"),
        role="store_manager",
        email_verified=True,
        permissions=permissions_for_role("store_manager"),
        totp_enabled=False,
    )
    db_session.add(mgr_to)
    await db_session.flush()

    from_store = await create_store(
        db_session,
        tenant_id=tenant_id,
        code="S16M1A",
        name="S16 M1 Insuf Src",
        manager_id=mgr_from.id,
    )
    to_store = await create_store(
        db_session,
        tenant_id=tenant_id,
        code="S16M1B",
        name="S16 M1 Insuf Dst",
        manager_id=mgr_to.id,
    )
    await db_session.flush()
    from_store_id, to_store_id = from_store.id, to_store.id
    from_wh = (
        await db_session.execute(
            select(m.Warehouse).where(
                m.Warehouse.tenant_id == tenant_id,
                m.Warehouse.store_id == from_store_id,
            )
        )
    ).scalar_one()
    from_wh_id = from_wh.id
    await apply_stock_change(
        db_session,
        tenant_id=tenant_id,
        product_id=product_id,
        quantity_delta=2,
        movement_type="stock_in",
        user_id=mgr_from.id,
        warehouse_id=from_wh_id,
    )
    await db_session.commit()

    mgr_from_h = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    created = await ac.post(
        "/api/v1/stores/transfers",
        headers=mgr_from_h,
        json={
            "from_store_id": from_store_id,
            "to_store_id": to_store_id,
            "submit": True,
            "items": [{"product_id": product_id, "quantity": 10}],
        },
    )
    assert created.status_code == 200, created.text
    transfer_id = created.json()["data"]["id"]

    shipped = await ac.post(
        f"/api/v1/stores/transfers/{transfer_id}/ship",
        headers=mgr_from_h,
    )
    assert shipped.status_code == 409, shipped.text
    detail = shipped.json()["detail"]
    assert detail["code"] == "INSUFFICIENT_WAREHOUSE_STOCK"

    db_session.expire_all()
    transfer = (
        await db_session.execute(
            select(m.StockTransfer).where(m.StockTransfer.id == transfer_id)
        )
    ).scalar_one()
    assert transfer.status == "requested"
    assert await _wh_qty(db_session, tenant_id, from_wh_id, product_id) == pytest.approx(2)
    moves = (
        await db_session.execute(
            select(m.StockMovement).where(
                m.StockMovement.tenant_id == tenant_id,
                m.StockMovement.reference_id == transfer_id,
            )
        )
    ).scalars().all()
    assert moves == []
