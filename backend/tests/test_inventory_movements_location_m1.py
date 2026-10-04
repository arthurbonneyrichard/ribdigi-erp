"""Inventory movements warehouse/store filters (BR-14.2 / BR-5.3 / BR-14.5)."""

from __future__ import annotations

from datetime import datetime

import pyotp
import pytest

from app import models as m
from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_inventory_movements_filter_by_warehouse_store_and_type(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    tenant_id = seed["t1"].id
    product = seed["p1"]

    store_a = m.Store(tenant_id=tenant_id, code="MV-A", name="Movements Store A")
    store_b = m.Store(tenant_id=tenant_id, code="MV-B", name="Movements Store B")
    db_session.add_all([store_a, store_b])
    await db_session.flush()

    wh_a = m.Warehouse(
        tenant_id=tenant_id, code="WH-MV-A", name="WH MV A", store_id=store_a.id
    )
    wh_b = m.Warehouse(
        tenant_id=tenant_id, code="WH-MV-B", name="WH MV B", store_id=store_b.id
    )
    db_session.add_all([wh_a, wh_b])
    await db_session.flush()

    now = datetime.utcnow()
    db_session.add_all(
        [
            m.StockMovement(
                tenant_id=tenant_id,
                product_id=product.id,
                warehouse_id=wh_a.id,
                movement_type="stock_in",
                quantity=10,
                quantity_before=0,
                quantity_after=10,
                reference_type="test",
                created_at=now,
            ),
            m.StockMovement(
                tenant_id=tenant_id,
                product_id=product.id,
                warehouse_id=wh_a.id,
                movement_type="stock_out",
                quantity=-2,
                quantity_before=10,
                quantity_after=8,
                reference_type="test",
                created_at=now,
            ),
            m.StockMovement(
                tenant_id=tenant_id,
                product_id=product.id,
                warehouse_id=wh_b.id,
                movement_type="stock_in",
                quantity=5,
                quantity_before=0,
                quantity_after=5,
                reference_type="test",
                created_at=now,
            ),
        ]
    )
    await db_session.commit()

    by_wh = await ac.get(
        f"/api/v1/reports/inventory/movements?warehouse_id={wh_a.id}",
        headers=headers,
    )
    assert by_wh.status_code == 200, by_wh.text
    wdata = by_wh.json()["data"]
    assert wdata["warehouse_id"] == wh_a.id
    assert wdata["warehouse_name"] == "WH MV A"
    assert wdata["store_id"] == store_a.id
    assert wdata["count"] == 2

    by_store = await ac.get(
        f"/api/v1/reports/inventory/movements?store_id={store_b.id}",
        headers=headers,
    )
    assert by_store.status_code == 200, by_store.text
    sdata = by_store.json()["data"]
    assert sdata["store_id"] == store_b.id
    assert sdata["store_name"] == "Movements Store B"
    assert sdata["count"] == 1
    assert sdata["movements"][0]["warehouse_id"] == wh_b.id

    by_type = await ac.get(
        f"/api/v1/reports/inventory/movements?warehouse_id={wh_a.id}&movement_type=stock_out",
        headers=headers,
    )
    assert by_type.status_code == 200, by_type.text
    tdata = by_type.json()["data"]
    assert tdata["count"] == 1
    assert tdata["movement_type"] == "stock_out"
    assert tdata["movements"][0]["movement_type"] == "stock_out"

    missing = await ac.get(
        "/api/v1/reports/inventory/movements?warehouse_id=00000000-0000-0000-0000-000000000000",
        headers=headers,
    )
    assert missing.status_code == 404
