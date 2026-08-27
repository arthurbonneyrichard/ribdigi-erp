"""Stage 2 I3: minimum_stock + traffic-light status (BR-5.5)."""

from __future__ import annotations

import pyotp
import pytest
from sqlalchemy import select

from app import models as m
from app.inventory import apply_stock_change, compute_stock_status
from tests.conftest import auth_headers


def test_compute_stock_status_thresholds():
    assert compute_stock_status(25, 5, 20) == "green"
    assert compute_stock_status(15, 5, 20) == "yellow"
    assert compute_stock_status(3, 5, 20) == "red"
    assert compute_stock_status(0, 0, 0) == "red"
    assert compute_stock_status(2, 0, 0) == "green"


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_product_minimum_stock_and_list_status(client, db_session):
    """Product-level low-stock uses tenant-wide role (store_managers omit product scope)."""
    ac, seed = client
    headers = await _super(ac, seed)
    seed["p1"].stock_qty = 8
    await db_session.commit()

    patched = await ac.patch(
        f"/api/v1/products/{seed['p1'].id}",
        headers=headers,
        json={"minimum_stock": 5, "reorder_level": 20},
    )
    assert patched.status_code == 200, patched.text
    body = patched.json()["data"]
    assert float(body["minimum_stock"]) == 5
    assert body["stock_status"] == "yellow"

    listed = await ac.get("/api/v1/products", headers=headers)
    assert listed.status_code == 200
    row = next(p for p in listed.json()["data"] if p["id"] == seed["p1"].id)
    assert row["stock_status"] == "yellow"

    low = await ac.get("/api/v1/inventory/low-stock", headers=headers)
    assert low.status_code == 200, low.text
    rows = low.json()["data"]
    match = next(r for r in rows if r["id"] == seed["p1"].id and r.get("scope") == "product")
    assert match["stock_status"] == "yellow"
    assert float(match["minimum_stock"]) == 5

    seed["p1"].stock_qty = 2
    await db_session.commit()
    low2 = await ac.get("/api/v1/inventory/low-stock", headers=headers)
    match2 = next(r for r in low2.json()["data"] if r["id"] == seed["p1"].id and r.get("scope") == "product")
    assert match2["stock_status"] == "red"


@pytest.mark.asyncio
async def test_warehouse_low_stock_uses_minimum(client, db_session):
    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    mgr = seed["mgr1"]
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    store = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Min WH Store",
        code="MINWH-S",
        manager_id=mgr.id,
        is_active=True,
    )
    db_session.add(store)
    await db_session.flush()
    wh = m.Warehouse(
        tenant_id=tid,
        company_id=cid,
        store_id=store.id,
        name="Min WH",
        code="MINWH",
    )
    db_session.add(wh)
    await db_session.flush()
    await apply_stock_change(
        db_session,
        tenant_id=tid,
        product_id=seed["p1"].id,
        quantity_delta=4,
        movement_type="stock_in",
        user_id=mgr.id,
        warehouse_id=wh.id,
    )
    stock = (
        await db_session.execute(
            select(m.WarehouseStock).where(
                m.WarehouseStock.warehouse_id == wh.id,
                m.WarehouseStock.product_id == seed["p1"].id,
            )
        )
    ).scalar_one()
    stock.minimum_stock = 10
    stock.reorder_level = 20
    await db_session.commit()

    low = await ac.get("/api/v1/inventory/low-stock", headers=headers)
    assert low.status_code == 200, low.text
    rows = low.json()["data"]
    assert not any(r.get("scope") == "product" for r in rows)
    wh_row = next(
        r
        for r in rows
        if r.get("scope") == "warehouse" and r.get("warehouse_id") == wh.id and r["id"] == seed["p1"].id
    )
    assert wh_row["stock_status"] == "red"
    assert float(wh_row["minimum_stock"]) == 10
