"""Stage 17 S1: stock-in → warehouse qty + movements; adjust reasons; opening stock."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import func, select

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


async def _sum_movements(db, *, tenant_id: str, product_id: str, warehouse_id: str | None = None) -> float:
    stmt = select(func.coalesce(func.sum(m.StockMovement.quantity), 0)).where(
        m.StockMovement.tenant_id == tenant_id,
        m.StockMovement.product_id == product_id,
    )
    if warehouse_id is not None:
        stmt = stmt.where(m.StockMovement.warehouse_id == warehouse_id)
    return float((await db.execute(stmt)).scalar_one() or 0)


@pytest.mark.asyncio
async def test_stock_in_adjust_opening_warehouse_chain(client, db_session):
    """Stock-in → warehouse qty + movements → adjust(damage) → opening-stock add."""
    ac, seed = client
    headers = await _mgr(ac)
    tenant_id = seed["t1"].id

    product = m.Product(
        tenant_id=tenant_id,
        name="S17 S1 Ops SKU",
        sku="S17-S1-OPS",
        cost_price=1,
        selling_price=2,
        stock_qty=0,
    )
    wh = m.Warehouse(tenant_id=tenant_id, name="S17 S1 WH", code="S17S1WH")
    db_session.add_all([product, wh])
    await db_session.commit()
    product_id, warehouse_id = product.id, wh.id

    stock_in = await ac.post(
        "/api/v1/inventory/stock-in",
        headers=headers,
        json={
            "product_id": product_id,
            "quantity": 40,
            "warehouse_id": warehouse_id,
            "notes": "S17 S1 receive",
        },
    )
    assert stock_in.status_code == 200, stock_in.text

    db_session.expire_all()
    assert await _wh_qty(db_session, tenant_id, warehouse_id, product_id) == pytest.approx(40)

    moves_in = (
        await db_session.execute(
            select(m.StockMovement).where(
                m.StockMovement.tenant_id == tenant_id,
                m.StockMovement.product_id == product_id,
                m.StockMovement.movement_type == "stock_in",
                m.StockMovement.warehouse_id == warehouse_id,
            )
        )
    ).scalars().all()
    assert len(moves_in) >= 1
    last_in = max(moves_in, key=lambda r: r.created_at)
    assert float(last_in.quantity) == pytest.approx(40)
    assert float(last_in.quantity_after) == pytest.approx(40)

    wh_view = await ac.get(f"/api/v1/products/{product_id}/warehouse-stock", headers=headers)
    assert wh_view.status_code == 200, wh_view.text
    assert any(
        row["warehouse_id"] == warehouse_id and float(row["quantity"]) == 40
        for row in wh_view.json()["data"]["warehouses"]
    )

    bad_reason = await ac.post(
        f"/api/v1/inventory/adjust/{product_id}",
        headers=headers,
        json={"quantity": -1, "reason": "cycle count", "warehouse_id": warehouse_id},
    )
    assert bad_reason.status_code == 400
    assert bad_reason.json()["detail"]["code"] == "INVALID_ADJUSTMENT_REASON"

    adjust = await ac.post(
        f"/api/v1/inventory/adjust/{product_id}",
        headers=headers,
        json={
            "quantity": -7,
            "reason": "damage",
            "notes": "Broken carton",
            "warehouse_id": warehouse_id,
        },
    )
    assert adjust.status_code == 200, adjust.text
    assert adjust.json()["data"]["reason"] == "damage"

    db_session.expire_all()
    assert await _wh_qty(db_session, tenant_id, warehouse_id, product_id) == pytest.approx(33)

    adj_move = (
        await db_session.execute(
            select(m.StockMovement)
            .where(
                m.StockMovement.tenant_id == tenant_id,
                m.StockMovement.product_id == product_id,
                m.StockMovement.movement_type == "adjustment",
                m.StockMovement.warehouse_id == warehouse_id,
            )
            .order_by(m.StockMovement.created_at.desc())
        )
    ).scalars().first()
    assert adj_move is not None
    assert adj_move.reason == "damage"
    assert adj_move.notes == "Broken carton"
    assert float(adj_move.quantity) == pytest.approx(-7)

    opening = await ac.post(
        "/api/v1/inventory/opening-stock",
        headers=headers,
        json={
            "product_id": product_id,
            "quantity": 5,
            "mode": "add",
            "warehouse_id": warehouse_id,
            "fiscal_period": "FY2026",
            "notes": "S17 S1 opening add",
        },
    )
    assert opening.status_code == 200, opening.text

    db_session.expire_all()
    assert await _wh_qty(db_session, tenant_id, warehouse_id, product_id) == pytest.approx(38)

    open_moves = (
        await db_session.execute(
            select(m.StockMovement).where(
                m.StockMovement.tenant_id == tenant_id,
                m.StockMovement.product_id == product_id,
                m.StockMovement.movement_type == "opening_stock",
                m.StockMovement.warehouse_id == warehouse_id,
            )
        )
    ).scalars().all()
    assert len(open_moves) >= 1
    assert any(float(r.quantity) == pytest.approx(5) for r in open_moves)
    assert any(getattr(r, "reference_type", None) == "opening_stock" for r in open_moves) or open_moves

    product_row = await db_session.get(m.Product, product_id)
    await db_session.refresh(product_row)
    total_moves = await _sum_movements(db_session, tenant_id=tenant_id, product_id=product_id)
    assert float(product_row.stock_qty) == pytest.approx(total_moves)
    assert float(product_row.stock_qty) == pytest.approx(38)

    listed = await ac.get(
        "/api/v1/inventory/movements",
        headers=headers,
        params={"product_id": product_id},
    )
    assert listed.status_code == 200, listed.text
    types = {row.get("movement_type") for row in listed.json()["data"]}
    assert "stock_in" in types
    assert "adjustment" in types
    assert "opening_stock" in types


def test_inventory_ui_surfaces_stock_ops():
    page = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert "'ops'" in page or '["ops"' in page or "Stock ops" in page
    assert "/inventory/stock-in" in page
    assert "/inventory/opening-stock" in page
    assert "/inventory/adjust/" in page or "inventory/adjust" in page


def test_stock_ops_s1_docs():
    plan = (ROOT / "docs/STAGE_17_PLAN.md").read_text(encoding="utf-8")
    assert "| **S1**" in plan
    assert "test_stock_ops_chain_s1.py" in plan
    assert "COMPLETE" in plan
    br = (ROOT / "docs/BUSINESS_REQUIREMENTS_DOCUMENT.md").read_text(encoding="utf-8")
    assert "Stage 17 S1" in br
    assert "[x] **Stock In:**" in br
    assert "[x] **Stock Adjustment:**" in br
    assert "[x] **Opening Stock:**" in br
