"""Inventory balance/valuation/expiry/low-stock store filters (BR-14.2 / BR-14.5)."""

from __future__ import annotations

from datetime import datetime, timedelta

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
async def test_inventory_stock_reports_filter_by_store(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    tenant_id = seed["t1"].id
    product = seed["p1"]

    store_a = m.Store(tenant_id=tenant_id, code="STK-A", name="Stock Store A")
    store_b = m.Store(tenant_id=tenant_id, code="STK-B", name="Stock Store B")
    db_session.add_all([store_a, store_b])
    await db_session.flush()

    wh_a = m.Warehouse(
        tenant_id=tenant_id, code="WH-STK-A", name="WH Stock A", store_id=store_a.id
    )
    wh_b = m.Warehouse(
        tenant_id=tenant_id, code="WH-STK-B", name="WH Stock B", store_id=store_b.id
    )
    db_session.add_all([wh_a, wh_b])
    await db_session.flush()

    db_session.add_all(
        [
            m.WarehouseStock(
                tenant_id=tenant_id,
                warehouse_id=wh_a.id,
                product_id=product.id,
                quantity=40,
                reorder_level=5,
                reorder_qty=10,
            ),
            m.WarehouseStock(
                tenant_id=tenant_id,
                warehouse_id=wh_b.id,
                product_id=product.id,
                quantity=3,
                reorder_level=5,
                reorder_qty=10,
            ),
        ]
    )
    batch_a = m.ProductBatch(
        tenant_id=tenant_id,
        product_id=product.id,
        warehouse_id=wh_a.id,
        batch_number="BATCH-A1",
        quantity=12,
        expiry_date=datetime.utcnow() + timedelta(days=10),
    )
    batch_b = m.ProductBatch(
        tenant_id=tenant_id,
        product_id=product.id,
        warehouse_id=wh_b.id,
        batch_number="BATCH-B1",
        quantity=4,
        expiry_date=datetime.utcnow() + timedelta(days=8),
    )
    db_session.add_all([batch_a, batch_b])
    await db_session.commit()

    bal_a = await ac.get(
        f"/api/v1/reports/inventory/balance?store_id={store_a.id}",
        headers=headers,
    )
    assert bal_a.status_code == 200, bal_a.text
    bdata = bal_a.json()["data"]
    assert bdata["store_id"] == store_a.id
    assert bdata["store_name"] == "Stock Store A"
    assert abs(float(bdata["total_quantity"]) - 40) < 0.01

    val_b = await ac.get(
        f"/api/v1/reports/inventory/valuation?store_id={store_b.id}&method=standard",
        headers=headers,
    )
    assert val_b.status_code == 200, val_b.text
    vdata = val_b.json()["data"]
    assert vdata["store_id"] == store_b.id
    assert abs(float(vdata["total_quantity"]) - 3) < 0.01

    exp_a = await ac.get(
        f"/api/v1/reports/inventory/expiry?store_id={store_a.id}&days=30",
        headers=headers,
    )
    assert exp_a.status_code == 200, exp_a.text
    edata = exp_a.json()["data"]
    assert edata["store_id"] == store_a.id
    assert edata["count"] == 1
    assert edata["batches"][0]["batch_number"] == "BATCH-A1"

    low_b = await ac.get(
        f"/api/v1/reports/inventory/low-stock?store_id={store_b.id}",
        headers=headers,
    )
    assert low_b.status_code == 200, low_b.text
    ldata = low_b.json()["data"]
    assert ldata["store_id"] == store_b.id
    assert any(w["warehouse_id"] == wh_b.id for w in ldata["warehouse_low_stock"])

    mismatch = await ac.get(
        f"/api/v1/reports/inventory/balance?store_id={store_b.id}&warehouse_id={wh_a.id}",
        headers=headers,
    )
    assert mismatch.status_code == 400

    missing = await ac.get(
        "/api/v1/reports/inventory/balance?store_id=00000000-0000-0000-0000-000000000000",
        headers=headers,
    )
    assert missing.status_code == 404
