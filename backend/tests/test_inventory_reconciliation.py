"""Inventory reconciliation — BR-5.2 / BR-5.3 / roadmap data-integrity ACs.

Stage 2 I1–I6 are frozen (ADR-010). This suite hardens acceptance that every
stock change is a persisted, auditable movement and that balances reconcile:

  product.stock_qty == Σ(stock_movements.quantity)
  warehouse_stock.quantity == Σ(movements.quantity WHERE warehouse_id=…)

Also covers tenant isolation and inventory write RBAC.
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app import models as m
from tests.conftest import auth_headers


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


async def _cashier(ac):
    return await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")


async def _sum_movements(
    db, *, tenant_id: str, product_id: str, warehouse_id: str | None = None
) -> float:
    stmt = select(func.coalesce(func.sum(m.StockMovement.quantity), 0)).where(
        m.StockMovement.tenant_id == tenant_id,
        m.StockMovement.product_id == product_id,
    )
    if warehouse_id is not None:
        stmt = stmt.where(m.StockMovement.warehouse_id == warehouse_id)
    return float((await db.execute(stmt)).scalar_one() or 0)


async def _make_product(db, tenant_id: str, sku: str) -> m.Product:
    p = m.Product(
        tenant_id=tenant_id,
        name=f"Reconcile {sku}",
        sku=sku,
        cost_price=1,
        selling_price=2,
        stock_qty=0,
    )
    db.add(p)
    await db.flush()
    return p


@pytest.mark.asyncio
async def test_api_stock_ops_persist_movements_and_reconcile(client, db_session):
    ac, seed = client
    headers = await _mgr(ac)
    product = await _make_product(db_session, seed["t1"].id, "REC-API-1")
    await db_session.commit()

    stock_in = await ac.post(
        "/api/v1/inventory/stock-in",
        headers=headers,
        json={"product_id": product.id, "quantity": 20, "notes": "recv"},
    )
    assert stock_in.status_code == 200, stock_in.text

    stock_out = await ac.post(
        "/api/v1/inventory/stock-out",
        headers=headers,
        json={"product_id": product.id, "quantity": 5, "notes": "ship"},
    )
    assert stock_out.status_code == 200, stock_out.text

    adjust = await ac.post(
        f"/api/v1/inventory/adjust/{product.id}",
        headers=headers,
        json={"quantity": -2, "reason": "damage", "notes": "broken"},
    )
    assert adjust.status_code == 200, adjust.text

    opening = await ac.post(
        "/api/v1/inventory/opening-stock",
        headers=headers,
        json={"product_id": product.id, "quantity": 3, "mode": "add"},
    )
    assert opening.status_code == 200, opening.text

    await db_session.refresh(product)
    total = await _sum_movements(db_session, tenant_id=seed["t1"].id, product_id=product.id)
    assert float(product.stock_qty) == total == 16.0  # 20 - 5 - 2 + 3

    moves = (
        await db_session.execute(
            select(m.StockMovement)
            .where(
                m.StockMovement.tenant_id == seed["t1"].id,
                m.StockMovement.product_id == product.id,
            )
            .order_by(m.StockMovement.created_at.asc())
        )
    ).scalars().all()
    assert len(moves) == 4
    assert {mv.movement_type for mv in moves} == {
        "stock_in",
        "stock_out",
        "adjustment",
        "opening_stock",
    }
    # Auditable trail: each row has before/after and actor
    for mv in moves:
        assert mv.created_by == seed["mgr1"].id
        assert mv.quantity_before is not None
        assert mv.quantity_after is not None
        assert float(mv.quantity_after) == float(mv.quantity_before) + float(mv.quantity)

    # Chain continuity: first before=0, last after=balance
    assert float(moves[0].quantity_before) == 0
    assert float(moves[-1].quantity_after) == float(product.stock_qty)


@pytest.mark.asyncio
async def test_warehouse_stock_reconciles_to_warehouse_movements(client, db_session):
    ac, seed = client
    headers = await _mgr(ac)
    product = await _make_product(db_session, seed["t1"].id, "REC-WH-1")
    wh_a = m.Warehouse(tenant_id=seed["t1"].id, name="Rec A", code="RECA")
    wh_b = m.Warehouse(tenant_id=seed["t1"].id, name="Rec B", code="RECB")
    db_session.add_all([wh_a, wh_b])
    await db_session.commit()

    r1 = await ac.post(
        "/api/v1/inventory/stock-in",
        headers=headers,
        json={
            "product_id": product.id,
            "quantity": 15,
            "warehouse_id": wh_a.id,
            "notes": "wh-a in",
        },
    )
    assert r1.status_code == 200, r1.text
    r2 = await ac.post(
        "/api/v1/inventory/stock-out",
        headers=headers,
        json={
            "product_id": product.id,
            "quantity": 4,
            "warehouse_id": wh_a.id,
            "notes": "wh-a out",
        },
    )
    assert r2.status_code == 200, r2.text
    r3 = await ac.post(
        "/api/v1/inventory/stock-in",
        headers=headers,
        json={
            "product_id": product.id,
            "quantity": 6,
            "warehouse_id": wh_b.id,
            "notes": "wh-b in",
        },
    )
    assert r3.status_code == 200, r3.text

    await db_session.refresh(product)
    assert float(product.stock_qty) == await _sum_movements(
        db_session, tenant_id=seed["t1"].id, product_id=product.id
    )
    assert float(product.stock_qty) == 17.0

    for wh, expected in ((wh_a, 11.0), (wh_b, 6.0)):
        wh_row = (
            await db_session.execute(
                select(m.WarehouseStock).where(
                    m.WarehouseStock.tenant_id == seed["t1"].id,
                    m.WarehouseStock.warehouse_id == wh.id,
                    m.WarehouseStock.product_id == product.id,
                )
            )
        ).scalar_one()
        wh_sum = await _sum_movements(
            db_session,
            tenant_id=seed["t1"].id,
            product_id=product.id,
            warehouse_id=wh.id,
        )
        assert float(wh_row.quantity) == wh_sum == expected


@pytest.mark.asyncio
async def test_inter_warehouse_transfer_preserves_product_balance(client, db_session):
    ac, seed = client
    headers = await _mgr(ac)
    product = await _make_product(db_session, seed["t1"].id, "REC-XFER-1")
    wh_a = m.Warehouse(tenant_id=seed["t1"].id, name="Xfer A", code="XFERA")
    wh_b = m.Warehouse(tenant_id=seed["t1"].id, name="Xfer B", code="XFERB")
    db_session.add_all([wh_a, wh_b])
    await db_session.commit()

    seeded = await ac.post(
        "/api/v1/inventory/stock-in",
        headers=headers,
        json={"product_id": product.id, "quantity": 10, "warehouse_id": wh_a.id},
    )
    assert seeded.status_code == 200, seeded.text

    created = await ac.post(
        "/api/v1/inventory/stock-transfers",
        headers=headers,
        json={
            "from_warehouse_id": wh_a.id,
            "to_warehouse_id": wh_b.id,
            "items": [{"product_id": product.id, "quantity": 4}],
        },
    )
    assert created.status_code == 200, created.text
    transfer_id = created.json()["data"]["id"]

    submitted = await ac.post(
        f"/api/v1/inventory/stock-transfers/{transfer_id}/submit", headers=headers
    )
    assert submitted.status_code == 200, submitted.text
    shipped = await ac.post(
        f"/api/v1/inventory/stock-transfers/{transfer_id}/ship", headers=headers
    )
    assert shipped.status_code == 200, shipped.text
    received = await ac.post(
        f"/api/v1/inventory/stock-transfers/{transfer_id}/receive", headers=headers
    )
    assert received.status_code == 200, received.text

    await db_session.refresh(product)
    total = await _sum_movements(db_session, tenant_id=seed["t1"].id, product_id=product.id)
    # transfer_out (-4) + transfer_in (+4) net zero — consolidated qty stays 10
    assert float(product.stock_qty) == total == 10.0

    qty_a = (
        await db_session.execute(
            select(m.WarehouseStock.quantity).where(
                m.WarehouseStock.tenant_id == seed["t1"].id,
                m.WarehouseStock.warehouse_id == wh_a.id,
                m.WarehouseStock.product_id == product.id,
            )
        )
    ).scalar_one()
    qty_b = (
        await db_session.execute(
            select(m.WarehouseStock.quantity).where(
                m.WarehouseStock.tenant_id == seed["t1"].id,
                m.WarehouseStock.warehouse_id == wh_b.id,
                m.WarehouseStock.product_id == product.id,
            )
        )
    ).scalar_one()
    assert float(qty_a) == await _sum_movements(
        db_session, tenant_id=seed["t1"].id, product_id=product.id, warehouse_id=wh_a.id
    )
    assert float(qty_b) == await _sum_movements(
        db_session, tenant_id=seed["t1"].id, product_id=product.id, warehouse_id=wh_b.id
    )
    assert float(qty_a) == 6.0
    assert float(qty_b) == 4.0


@pytest.mark.asyncio
async def test_inventory_write_rbac_and_tenant_isolation(client, db_session):
    ac, seed = client
    mgr = await _mgr(ac)
    cashier = await _cashier(ac)
    product = await _make_product(db_session, seed["t1"].id, "REC-SEC-1")
    foreign = await _make_product(db_session, seed["t2"].id, "REC-SEC-2")
    await db_session.commit()

    denied = await ac.post(
        "/api/v1/inventory/stock-in",
        headers=cashier,
        json={"product_id": product.id, "quantity": 1},
    )
    assert denied.status_code == 403

    cross = await ac.post(
        "/api/v1/inventory/stock-in",
        headers=mgr,
        json={"product_id": foreign.id, "quantity": 1},
    )
    assert cross.status_code == 404

    await db_session.refresh(foreign)
    assert float(foreign.stock_qty) == 0
    foreign_moves = await _sum_movements(
        db_session, tenant_id=seed["t2"].id, product_id=foreign.id
    )
    assert foreign_moves == 0.0
