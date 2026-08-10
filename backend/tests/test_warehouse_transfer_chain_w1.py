"""Stage 17 W1: warehouse stock grid + inter-warehouse transfer ship/receive chain."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select

from app import models as m
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


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
async def test_warehouse_stock_grid_and_transfer_ship_receive(client, db_session):
    """GET warehouse-stock + inventory stock-transfers create→ship→receive updates qty/movements."""
    ac, seed = client
    headers = await _mgr(ac)
    tenant_id = seed["t1"].id

    product = m.Product(
        tenant_id=tenant_id,
        name="S17 W1 Transfer SKU",
        sku="S17-W1-XFER",
        cost_price=1,
        selling_price=2,
        stock_qty=0,
    )
    wh_a = m.Warehouse(tenant_id=tenant_id, name="S17 W1 Source", code="S17W1A")
    wh_b = m.Warehouse(tenant_id=tenant_id, name="S17 W1 Dest", code="S17W1B")
    db_session.add_all([product, wh_a, wh_b])
    await db_session.commit()
    product_id, wh_a_id, wh_b_id = product.id, wh_a.id, wh_b.id

    stock_in = await ac.post(
        "/api/v1/inventory/stock-in",
        headers=headers,
        json={
            "product_id": product_id,
            "quantity": 50,
            "warehouse_id": wh_a_id,
            "notes": "S17 W1 seed",
        },
    )
    assert stock_in.status_code == 200, stock_in.text

    grid = await ac.get(f"/api/v1/products/{product_id}/warehouse-stock", headers=headers)
    assert grid.status_code == 200, grid.text
    data = grid.json()["data"]
    assert data["product_id"] == product_id
    assert any(
        row["warehouse_id"] == wh_a_id and float(row["quantity"]) == pytest.approx(50)
        for row in data["warehouses"]
    )
    assert await _wh_qty(db_session, tenant_id, wh_a_id, product_id) == pytest.approx(50)
    assert await _wh_qty(db_session, tenant_id, wh_b_id, product_id) == pytest.approx(0)

    product_row = await db_session.get(m.Product, product_id)
    await db_session.refresh(product_row)
    consolidated_before = float(product_row.stock_qty)
    assert consolidated_before == pytest.approx(50)

    created = await ac.post(
        "/api/v1/inventory/stock-transfers",
        headers=headers,
        json={
            "from_warehouse_id": wh_a_id,
            "to_warehouse_id": wh_b_id,
            "submit": True,
            "notes": "S17 W1 rebalance",
            "items": [{"product_id": product_id, "quantity": 20}],
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()["data"]
    transfer_id = body["id"]
    assert body["status"] == "requested"
    assert body["from_store_id"] is None
    assert body["to_store_id"] is None
    assert body["from_warehouse_id"] == wh_a_id
    assert body["to_warehouse_id"] == wh_b_id

    shipped = await ac.post(
        f"/api/v1/inventory/stock-transfers/{transfer_id}/ship",
        headers=headers,
    )
    assert shipped.status_code == 200, shipped.text
    assert shipped.json()["data"]["status"] == "in_transit"

    db_session.expire_all()
    assert await _wh_qty(db_session, tenant_id, wh_a_id, product_id) == pytest.approx(30)
    assert await _wh_qty(db_session, tenant_id, wh_b_id, product_id) == pytest.approx(0)

    out_moves = (
        await db_session.execute(
            select(m.StockMovement).where(
                m.StockMovement.tenant_id == tenant_id,
                m.StockMovement.reference_type == "stock_transfer",
                m.StockMovement.reference_id == transfer_id,
                m.StockMovement.movement_type == "transfer_out",
            )
        )
    ).scalars().all()
    assert len(out_moves) >= 1
    assert float(out_moves[0].quantity) == pytest.approx(-20)
    assert out_moves[0].warehouse_id == wh_a_id

    received = await ac.post(
        f"/api/v1/inventory/stock-transfers/{transfer_id}/receive",
        headers=headers,
    )
    assert received.status_code == 200, received.text
    assert received.json()["data"]["status"] == "received"

    db_session.expire_all()
    assert await _wh_qty(db_session, tenant_id, wh_a_id, product_id) == pytest.approx(30)
    assert await _wh_qty(db_session, tenant_id, wh_b_id, product_id) == pytest.approx(20)

    product_row = await db_session.get(m.Product, product_id)
    await db_session.refresh(product_row)
    assert float(product_row.stock_qty) == pytest.approx(consolidated_before)

    in_moves = (
        await db_session.execute(
            select(m.StockMovement).where(
                m.StockMovement.tenant_id == tenant_id,
                m.StockMovement.reference_type == "stock_transfer",
                m.StockMovement.reference_id == transfer_id,
                m.StockMovement.movement_type == "transfer_in",
            )
        )
    ).scalars().all()
    assert len(in_moves) >= 1
    assert float(in_moves[0].quantity) == pytest.approx(20)
    assert in_moves[0].warehouse_id == wh_b_id

    grid_after = await ac.get(f"/api/v1/products/{product_id}/warehouse-stock", headers=headers)
    assert grid_after.status_code == 200
    rows = {r["warehouse_id"]: float(r["quantity"]) for r in grid_after.json()["data"]["warehouses"]}
    assert rows.get(wh_a_id) == pytest.approx(30)
    assert rows.get(wh_b_id) == pytest.approx(20)

    listed_moves = await ac.get(
        "/api/v1/inventory/movements",
        headers=headers,
        params={"product_id": product_id},
    )
    assert listed_moves.status_code == 200, listed_moves.text
    move_types = {row.get("movement_type") for row in listed_moves.json()["data"]}
    assert "transfer_out" in move_types
    assert "transfer_in" in move_types
    assert any(row.get("reference_id") == transfer_id for row in listed_moves.json()["data"])


@pytest.mark.asyncio
async def test_warehouse_transfer_insufficient_stock_no_movements(client, db_session):
    ac, seed = client
    headers = await _mgr(ac)
    tenant_id = seed["t1"].id

    product = m.Product(
        tenant_id=tenant_id,
        name="S17 W1 Short SKU",
        sku="S17-W1-SHORT",
        cost_price=1,
        selling_price=2,
        stock_qty=0,
    )
    wh_a = m.Warehouse(tenant_id=tenant_id, name="S17 W1 Short A", code="S17W1SA")
    wh_b = m.Warehouse(tenant_id=tenant_id, name="S17 W1 Short B", code="S17W1SB")
    db_session.add_all([product, wh_a, wh_b])
    await db_session.commit()

    await ac.post(
        "/api/v1/inventory/stock-in",
        headers=headers,
        json={"product_id": product.id, "quantity": 3, "warehouse_id": wh_a.id},
    )

    created = await ac.post(
        "/api/v1/inventory/stock-transfers",
        headers=headers,
        json={
            "from_warehouse_id": wh_a.id,
            "to_warehouse_id": wh_b.id,
            "submit": True,
            "items": [{"product_id": product.id, "quantity": 10}],
        },
    )
    assert created.status_code == 200, created.text
    transfer_id = created.json()["data"]["id"]

    shipped = await ac.post(
        f"/api/v1/inventory/stock-transfers/{transfer_id}/ship",
        headers=headers,
    )
    assert shipped.status_code == 409, shipped.text
    detail = shipped.json()["detail"]
    code = detail.get("code") if isinstance(detail, dict) else None
    assert code == "INSUFFICIENT_WAREHOUSE_STOCK" or "INSUFFICIENT" in str(detail)

    got_list = await ac.get("/api/v1/inventory/stock-transfers", headers=headers)
    assert got_list.status_code == 200
    row = next(t for t in got_list.json()["data"] if t["id"] == transfer_id)
    assert row["status"] == "requested"

    moves = (
        await db_session.execute(
            select(m.StockMovement).where(
                m.StockMovement.tenant_id == tenant_id,
                m.StockMovement.reference_id == transfer_id,
            )
        )
    ).scalars().all()
    assert moves == []


def test_inventory_ui_surfaces_warehouse_transfers():
    page = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert "warehouse-stock" in page
    assert "/inventory/stock-transfers" in page
    assert "'transfers'" in page or "Transfers" in page
    assert "ship" in page and "receive" in page


def test_warehouse_transfer_w1_docs():
    plan = (ROOT / "docs/STAGE_17_PLAN.md").read_text(encoding="utf-8")
    assert "| **W1**" in plan
    assert "test_warehouse_transfer_chain_w1.py" in plan
    assert "COMPLETE" in plan
    br = (ROOT / "docs/BUSINESS_REQUIREMENTS_DOCUMENT.md").read_text(encoding="utf-8")
    assert "Stage 17 W1" in br
    assert "[x] **Stock Transfer:**" in br
    assert "[x] View stock levels per warehouse" in br
    assert "[x] Transfer stock between warehouses" in br
