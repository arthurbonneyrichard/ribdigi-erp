"""Stage 2 I1: dedicated opening stock entry (BR-5.2)."""

from __future__ import annotations

import io

import pytest
from sqlalchemy import select

from app import models as m
from app.inventory import apply_stock_change
from tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_opening_stock_add_for_existing_product(client, db_session):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    before = float(seed["p1"].stock_qty or 0)

    r = await ac.post(
        "/api/v1/inventory/opening-stock",
        headers=headers,
        json={
            "product_id": seed["p1"].id,
            "quantity": 12,
            "mode": "add",
            "notes": "Go-live opening",
            "fiscal_period": "FY2026",
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["movement_type"] == "opening_stock"
    assert float(data["quantity_delta"]) == 12
    assert float(data["stock_qty"]) == before + 12

    moves = (
        await db_session.execute(
            select(m.StockMovement).where(
                m.StockMovement.tenant_id == seed["t1"].id,
                m.StockMovement.product_id == seed["p1"].id,
                m.StockMovement.movement_type == "opening_stock",
            )
        )
    ).scalars().all()
    assert any(float(mv.quantity) == 12 and "FY2026" in (mv.notes or "") for mv in moves)


@pytest.mark.asyncio
async def test_opening_stock_set_and_cannot_reduce(client, db_session):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    seed["p1"].stock_qty = 0
    await db_session.commit()

    set_ok = await ac.post(
        "/api/v1/inventory/opening-stock",
        headers=headers,
        json={"product_id": seed["p1"].id, "quantity": 40, "mode": "set"},
    )
    assert set_ok.status_code == 200, set_ok.text
    assert float(set_ok.json()["data"]["stock_qty"]) == 40

    reduce = await ac.post(
        "/api/v1/inventory/opening-stock",
        headers=headers,
        json={"product_id": seed["p1"].id, "quantity": 10, "mode": "set"},
    )
    assert reduce.status_code == 400
    detail = reduce.json()["detail"]
    assert detail.get("code") == "OPENING_STOCK_CANNOT_REDUCE" or (
        isinstance(detail, dict) and detail.get("code") == "OPENING_STOCK_CANNOT_REDUCE"
    )


@pytest.mark.asyncio
async def test_opening_stock_warehouse_and_batch_items(client, db_session):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    wh = m.Warehouse(tenant_id=seed["t1"].id, name="Opening WH", code="OPWH")
    db_session.add(wh)
    await db_session.flush()
    p2 = m.Product(
        tenant_id=seed["t1"].id,
        name="Opening P2",
        sku="OP-P2",
        cost_price=1,
        selling_price=1,
        stock_qty=0,
        reorder_level=0,
    )
    db_session.add(p2)
    await db_session.commit()

    r = await ac.post(
        "/api/v1/inventory/opening-stock",
        headers=headers,
        json={
            "fiscal_period": "FY2026-Q1",
            "items": [
                {
                    "product_id": seed["p1"].id,
                    "quantity": 5,
                    "mode": "add",
                    "warehouse_id": wh.id,
                },
                {
                    "product_id": p2.id,
                    "quantity": 8,
                    "mode": "set",
                    "warehouse_id": wh.id,
                },
            ],
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert body["count"] == 2
    assert all(row["movement_type"] == "opening_stock" for row in body["items"])

    foreign = await ac.post(
        "/api/v1/inventory/opening-stock",
        headers=headers,
        json={"product_id": seed["p2"].id, "quantity": 1, "mode": "add"},
    )
    assert foreign.status_code == 404


@pytest.mark.asyncio
async def test_opening_stock_csv_mode(client, db_session):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    product = seed["p1"]
    await apply_stock_change(
        db_session,
        tenant_id=seed["t1"].id,
        product_id=product.id,
        quantity_delta=1,
        movement_type="stock_in",
        user_id=seed["mgr1"].id,
    )
    await db_session.commit()
    await db_session.refresh(product)
    before = float(product.stock_qty or 0)

    csv_body = (
        "sku,barcode,warehouse_code,quantity,mode,reason\n"
        f"{product.sku},,,3,opening,Fiscal opening CSV\n"
    )
    r = await ac.post(
        "/api/v1/inventory/stock/import?dry_run=false",
        headers=headers,
        files={"file": ("opening.csv", io.BytesIO(csv_body.encode()), "text/csv")},
    )
    assert r.status_code == 200, r.text
    report = r.json()["data"]
    assert report["applied"]
    assert report["applied"][0]["movement_type"] == "opening_stock"
    assert float(report["applied"][0]["delta"]) == 3

    await db_session.refresh(product)
    assert float(product.stock_qty or 0) == before + 3

    moves = list(
        (
            await db_session.execute(
                select(m.StockMovement).where(
                    m.StockMovement.tenant_id == seed["t1"].id,
                    m.StockMovement.product_id == product.id,
                    m.StockMovement.movement_type == "opening_stock",
                    m.StockMovement.reference_type == "stock_import",
                )
            )
        )
        .scalars()
        .all()
    )
    assert any(float(mv.quantity) == 3 for mv in moves)
