"""Warehouse stock panel (BR-5.4)."""

from __future__ import annotations

import pyotp
import pytest

from app import models as m
from app.inventory import apply_stock_change
from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_warehouse_stock_requires_warehouse_id(client):
    ac, seed = client
    headers = await _admin(ac, seed)
    missing = await ac.get("/api/v1/inventory/warehouse-stock", headers=headers)
    assert missing.status_code == 422


@pytest.mark.asyncio
async def test_warehouse_stock_scoped_to_warehouse(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    tenant_id = seed["t1"].id
    product = seed["p1"]

    store_a = m.Store(tenant_id=tenant_id, code="WSA", name="WH Stock A")
    store_b = m.Store(tenant_id=tenant_id, code="WSB", name="WH Stock B")
    db_session.add_all([store_a, store_b])
    await db_session.flush()
    wh_a = m.Warehouse(
        tenant_id=tenant_id, code="WH-A-PANEL", name="Panel A", store_id=store_a.id
    )
    wh_b = m.Warehouse(
        tenant_id=tenant_id, code="WH-B-PANEL", name="Panel B", store_id=store_b.id
    )
    db_session.add_all([wh_a, wh_b])
    await db_session.flush()

    await apply_stock_change(
        db_session,
        tenant_id=tenant_id,
        product_id=product.id,
        quantity_delta=7,
        movement_type="stock_in",
        user_id=seed["super"].id,
        warehouse_id=wh_a.id,
        allow_negative=False,
    )
    await apply_stock_change(
        db_session,
        tenant_id=tenant_id,
        product_id=product.id,
        quantity_delta=2,
        movement_type="stock_in",
        user_id=seed["super"].id,
        warehouse_id=wh_b.id,
        allow_negative=False,
    )
    await db_session.commit()

    a = await ac.get(
        f"/api/v1/inventory/warehouse-stock?warehouse_id={wh_a.id}",
        headers=headers,
    )
    assert a.status_code == 200, a.text
    data_a = a.json()["data"]
    assert data_a["warehouse_id"] == wh_a.id
    assert data_a["warehouse_name"] == "Panel A"
    row_a = next(i for i in data_a["items"] if i["product_id"] == product.id)
    assert float(row_a["quantity"]) == 7

    b = await ac.get(
        f"/api/v1/inventory/warehouse-stock?warehouse_id={wh_b.id}",
        headers=headers,
    )
    assert b.status_code == 200, b.text
    row_b = next(i for i in b.json()["data"]["items"] if i["product_id"] == product.id)
    assert float(row_b["quantity"]) == 2
    assert float(row_a["quantity"]) != float(row_b["quantity"])


@pytest.mark.asyncio
async def test_warehouse_stock_reorder_policy(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    tenant_id = seed["t1"].id
    product = seed["p1"]

    store = m.Store(tenant_id=tenant_id, code="WSR", name="WH Reorder Store")
    db_session.add(store)
    await db_session.flush()
    wh = m.Warehouse(
        tenant_id=tenant_id, code="WH-REO", name="Reorder WH", store_id=store.id
    )
    db_session.add(wh)
    await db_session.flush()

    await apply_stock_change(
        db_session,
        tenant_id=tenant_id,
        product_id=product.id,
        quantity_delta=3,
        movement_type="stock_in",
        user_id=seed["super"].id,
        warehouse_id=wh.id,
        allow_negative=False,
    )
    await db_session.commit()

    saved = await ac.put(
        "/api/v1/inventory/warehouse-stock/reorder",
        headers=headers,
        json={
            "warehouse_id": wh.id,
            "product_id": product.id,
            "reorder_level": 10,
            "reorder_qty": 25,
        },
    )
    assert saved.status_code == 200, saved.text
    body = saved.json()["data"]
    assert body["reorder_level"] == 10
    assert body["reorder_qty"] == 25
    assert body["below_reorder"] is True
    assert body["warehouse_id"] == wh.id

    listed = await ac.get(
        f"/api/v1/inventory/warehouse-stock?warehouse_id={wh.id}",
        headers=headers,
    )
    assert listed.status_code == 200
    row = next(i for i in listed.json()["data"]["items"] if i["product_id"] == product.id)
    assert float(row["reorder_level"]) == 10
    assert float(row["reorder_qty"]) == 25
    assert row["below_reorder"] is True
