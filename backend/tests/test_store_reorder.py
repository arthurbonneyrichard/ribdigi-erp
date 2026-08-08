"""Store/warehouse reorder policies and FEFO strict mode."""

from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException

from app import catalog as catalog_svc
from app import models as m
from app import reports as reports_svc
from app import stores as stores_svc
from app.inventory import apply_stock_change


@pytest.mark.asyncio
async def test_store_reorder_policy_and_low_stock_report(db_session, seeded):
    tenant_id = seeded["t1"].id
    store = m.Store(
        tenant_id=tenant_id,
        name="Downtown",
        code="DT",
        is_active=True,
    )
    db_session.add(store)
    await db_session.flush()
    wh = m.Warehouse(
        tenant_id=tenant_id,
        store_id=store.id,
        name="Downtown WH",
        code="DT-WH",
    )
    db_session.add(wh)
    await db_session.flush()

    product = seeded["p1"]
    await apply_stock_change(
        db_session,
        tenant_id=tenant_id,
        product_id=product.id,
        quantity_delta=3,
        movement_type="stock_in",
        user_id=seeded["admin1"].id,
        warehouse_id=wh.id,
    )

    row = await stores_svc.set_store_reorder_policy(
        db_session,
        tenant_id=tenant_id,
        store_id=store.id,
        product_id=product.id,
        reorder_level=5,
        reorder_qty=25,
    )
    assert row["below_reorder"] is True
    assert row["reorder_qty"] == 25.0

    report = await reports_svc.inventory_low_stock(
        db_session, tenant_id, store_id=store.id
    )
    assert report["warehouse_count"] >= 1
    assert any(r["product_id"] == product.id for r in report["warehouse_low_stock"])
    assert report["warehouse_low_stock"][0]["suggested_order_qty"] >= 2


@pytest.mark.asyncio
async def test_fefo_strict_excludes_unassigned_batches(db_session, seeded):
    tenant_id = seeded["t1"].id
    tenant = seeded["t1"]
    tenant.fefo_strict_warehouse = True

    product = seeded["p1"]
    product.tracks_batches = True
    product.stock_qty = 10

    wh = m.Warehouse(tenant_id=tenant_id, name="Strict WH", code="S-WH")
    db_session.add(wh)
    await db_session.flush()

    # Unassigned batch (warehouse_id NULL) — ignored in strict mode
    unassigned = m.ProductBatch(
        tenant_id=tenant_id,
        product_id=product.id,
        batch_number="UN-1",
        quantity=10,
        expiry_date=datetime.utcnow() + timedelta(days=30),
        warehouse_id=None,
    )
    db_session.add(unassigned)
    await db_session.commit()

    with pytest.raises(HTTPException) as exc:
        await catalog_svc.stock_out_with_batch(
            db_session,
            tenant_id=tenant_id,
            user_id=seeded["admin1"].id,
            product_id=product.id,
            quantity=2,
            warehouse_id=wh.id,
        )
    assert exc.value.status_code == 409
