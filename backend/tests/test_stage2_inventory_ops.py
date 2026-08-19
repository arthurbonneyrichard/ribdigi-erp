"""Stage 2: movement date filters, warehouse stock view, low-stock → draft PO."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app import models as m
from app.inventory import apply_stock_change
from tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_movements_date_filter(client, db_session):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    await apply_stock_change(
        db_session,
        tenant_id=seed["t1"].id,
        product_id=seed["p1"].id,
        quantity_delta=3,
        movement_type="stock_in",
        user_id=seed["mgr1"].id,
    )
    await db_session.commit()

    today = datetime.utcnow().strftime("%Y-%m-%d")
    future = (datetime.utcnow() + timedelta(days=2)).strftime("%Y-%m-%d")
    past = (datetime.utcnow() - timedelta(days=5)).strftime("%Y-%m-%d")

    ok = await ac.get(
        f"/api/v1/inventory/movements?product_id={seed['p1'].id}&from_date={today}&to_date={today}",
        headers=headers,
    )
    assert ok.status_code == 200, ok.text
    assert any(row["product_id"] == seed["p1"].id for row in ok.json()["data"])

    empty = await ac.get(
        f"/api/v1/inventory/movements?product_id={seed['p1'].id}&from_date={future}&to_date={future}",
        headers=headers,
    )
    assert empty.status_code == 200
    assert empty.json()["data"] == []

    window = await ac.get(
        f"/api/v1/inventory/movements?product_id={seed['p1'].id}&from_date={past}&to_date={today}",
        headers=headers,
    )
    assert window.status_code == 200
    assert len(window.json()["data"]) >= 1


@pytest.mark.asyncio
async def test_product_warehouse_stock(client, db_session):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    wh = m.Warehouse(tenant_id=seed["t1"].id, name="Stock View WH", code="SVWH")
    db_session.add(wh)
    await db_session.flush()
    await apply_stock_change(
        db_session,
        tenant_id=seed["t1"].id,
        product_id=seed["p1"].id,
        quantity_delta=7,
        movement_type="stock_in",
        user_id=seed["mgr1"].id,
        warehouse_id=wh.id,
    )
    await db_session.commit()

    r = await ac.get(f"/api/v1/products/{seed['p1'].id}/warehouse-stock", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["product_id"] == seed["p1"].id
    assert any(row["warehouse_id"] == wh.id and float(row["quantity"]) == 7 for row in data["warehouses"])


@pytest.mark.asyncio
async def test_low_stock_reorder_creates_draft_po(client, db_session):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    seed["p1"].reorder_level = 100
    seed["p1"].stock_qty = 2
    seed["p1"].cost_price = 4.5
    supplier = m.Party(
        tenant_id=seed["t1"].id,
        name="Reorder Supplier",
        kind="supplier",
        credit_limit=0,
    )
    db_session.add(supplier)
    await db_session.commit()

    listed = await ac.get("/api/v1/inventory/low-stock", headers=headers)
    assert listed.status_code == 200, listed.text
    rows = listed.json()["data"]
    assert any(r["id"] == seed["p1"].id and r["suggested_order_qty"] >= 1 for r in rows)

    created = await ac.post(
        "/api/v1/inventory/low-stock/reorder-po",
        headers=headers,
        json={"product_id": seed["p1"].id, "supplier_id": supplier.id},
    )
    assert created.status_code == 200, created.text
    po = created.json()["data"]
    assert po["status"] == "draft"
    assert po["supplier_id"] == supplier.id
    assert any(i["product_id"] == seed["p1"].id for i in po["items"])

    foreign = await ac.post(
        "/api/v1/inventory/low-stock/reorder-po",
        headers=headers,
        json={"product_id": seed["p1"].id, "supplier_id": seed["supplier2"].id},
    )
    assert foreign.status_code == 404
