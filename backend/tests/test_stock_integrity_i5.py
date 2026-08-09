"""Stage 2 I5: movement audit fields + stock integrity / concurrency."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app import models as m
from app.inventory import apply_stock_change
from tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_movements_include_before_after_user(client, db_session):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    before = float(seed["p1"].stock_qty or 0)
    await apply_stock_change(
        db_session,
        tenant_id=seed["t1"].id,
        product_id=seed["p1"].id,
        quantity_delta=4,
        movement_type="stock_in",
        user_id=seed["mgr1"].id,
        notes="integrity probe",
    )
    await db_session.commit()

    r = await ac.get(
        f"/api/v1/inventory/movements?product_id={seed['p1'].id}&movement_type=stock_in",
        headers=headers,
    )
    assert r.status_code == 200, r.text
    rows = r.json()["data"]
    assert rows
    hit = next(row for row in rows if row.get("notes") == "integrity probe")
    assert float(hit["quantity"]) == 4
    assert float(hit["quantity_before"]) == before
    assert float(hit["quantity_after"]) == before + 4
    assert hit["created_by"] == seed["mgr1"].id
    assert hit["created_by_email"] == "mgr@alpha.example.com"
    assert hit["product_sku"] == seed["p1"].sku


@pytest.mark.asyncio
async def test_stock_qty_equals_sum_of_movements(client, db_session):
    ac, seed = client
    product = await db_session.get(m.Product, seed["p1"].id)
    product.stock_qty = 0
    await db_session.commit()

    # Clear prior movements for a clean Σ check on this product
    existing = (
        await db_session.execute(
            select(m.StockMovement).where(
                m.StockMovement.tenant_id == seed["t1"].id,
                m.StockMovement.product_id == seed["p1"].id,
            )
        )
    ).scalars().all()
    for mv in existing:
        await db_session.delete(mv)
    await db_session.commit()

    await apply_stock_change(
        db_session,
        tenant_id=seed["t1"].id,
        product_id=seed["p1"].id,
        quantity_delta=10,
        movement_type="opening_stock",
        user_id=seed["mgr1"].id,
    )
    await apply_stock_change(
        db_session,
        tenant_id=seed["t1"].id,
        product_id=seed["p1"].id,
        quantity_delta=5,
        movement_type="stock_in",
        user_id=seed["mgr1"].id,
    )
    await apply_stock_change(
        db_session,
        tenant_id=seed["t1"].id,
        product_id=seed["p1"].id,
        quantity_delta=-3,
        movement_type="stock_out",
        user_id=seed["mgr1"].id,
    )
    await db_session.commit()

    await db_session.refresh(product)
    total = (
        await db_session.execute(
            select(func.coalesce(func.sum(m.StockMovement.quantity), 0)).where(
                m.StockMovement.tenant_id == seed["t1"].id,
                m.StockMovement.product_id == seed["p1"].id,
            )
        )
    ).scalar_one()
    assert float(product.stock_qty) == float(total) == 12


@pytest.mark.asyncio
async def test_stock_out_rejects_overdraw(client, db_session):
    """Stock-out uses SELECT FOR UPDATE + available check (Postgres serializes races).

    SQLite test DB does not emulate cross-connection row locks, so this asserts the
    sequential guard: a second overdraw after a successful out returns 409.
    """
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    product = await db_session.get(m.Product, seed["p1"].id)
    product.stock_qty = 5
    product.reserved_qty = 0
    await db_session.commit()

    ok = await ac.post(
        "/api/v1/inventory/stock-out",
        headers=headers,
        json={"product_id": seed["p1"].id, "quantity": 4},
    )
    assert ok.status_code == 200, ok.text

    denied = await ac.post(
        "/api/v1/inventory/stock-out",
        headers=headers,
        json={"product_id": seed["p1"].id, "quantity": 4},
    )
    assert denied.status_code == 409
    detail = denied.json()["detail"]
    assert detail["code"] == "INSUFFICIENT_STOCK"

    await db_session.refresh(product)
    assert float(product.stock_qty) == 1
