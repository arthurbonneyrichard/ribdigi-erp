"""Store-scoped stock deduction on sales invoice post / POS."""

from datetime import datetime

import pytest
from sqlalchemy import select

from app import models as m
from app import sales as sales_svc
from app.inventory import get_or_create_warehouse_stock


@pytest.mark.asyncio
async def test_post_invoice_deducts_store_warehouse_stock(db_session, seeded):
    tenant_id = seeded["t1"].id
    product = seeded["p1"]
    product.stock_qty = 20
    await db_session.flush()

    store = m.Store(
        tenant_id=tenant_id,
        name="North Branch",
        code="NORTH",
        is_active=True,
    )
    db_session.add(store)
    await db_session.flush()
    wh = m.Warehouse(
        tenant_id=tenant_id,
        store_id=store.id,
        name="North WH",
        code="WH-NORTH",
    )
    db_session.add(wh)
    await db_session.flush()

    # Pre-locate some stock at the store warehouse; leave rest unlocated on product
    row = await get_or_create_warehouse_stock(
        db_session, tenant_id=tenant_id, warehouse_id=wh.id, product_id=product.id
    )
    row.quantity = 5
    await db_session.flush()

    party = m.Party(tenant_id=tenant_id, name="Buyer", kind="customer", credit_limit=0)
    db_session.add(party)
    await db_session.flush()

    inv = await sales_svc.create_sales_invoice(
        db_session,
        tenant_id=tenant_id,
        user_id=seeded["admin1"].id,
        customer_id=party.id,
        store_id=store.id,
        items=[{"product_id": product.id, "quantity": 3, "unit_price": 2, "tax_rate": 0}],
    )
    await db_session.flush()
    assert inv.store_id == store.id

    posted = await sales_svc.post_sales_invoice(
        db_session,
        tenant_id=tenant_id,
        user_id=seeded["admin1"].id,
        invoice_id=inv.id,
    )
    await db_session.commit()
    assert posted.status == "posted"

    await db_session.refresh(product)
    assert float(product.stock_qty) == 17.0

    wh_stock = (
        await db_session.execute(
            select(m.WarehouseStock).where(
                m.WarehouseStock.warehouse_id == wh.id,
                m.WarehouseStock.product_id == product.id,
            )
        )
    ).scalar_one()
    # started 5 at warehouse; allocate_unlocated parks 15 more → 20, then out 3 → 17
    assert float(wh_stock.quantity) == 17.0

    movement = (
        await db_session.execute(
            select(m.StockMovement)
            .where(
                m.StockMovement.tenant_id == tenant_id,
                m.StockMovement.reference_type == "sales_invoice",
                m.StockMovement.reference_id == inv.id,
            )
            .order_by(m.StockMovement.created_at.desc())
        )
    ).scalars().first()
    assert movement is not None
    assert movement.warehouse_id == wh.id
    assert float(movement.quantity) == -3.0


@pytest.mark.asyncio
async def test_post_invoice_without_store_skips_warehouse(db_session, seeded):
    tenant_id = seeded["t1"].id
    product = seeded["p1"]
    start = float(product.stock_qty or 0)

    party = m.Party(tenant_id=tenant_id, name="Buyer2", kind="customer", credit_limit=0)
    db_session.add(party)
    await db_session.flush()

    inv = await sales_svc.create_sales_invoice(
        db_session,
        tenant_id=tenant_id,
        user_id=seeded["admin1"].id,
        customer_id=party.id,
        items=[{"product_id": product.id, "quantity": 1, "unit_price": 2, "tax_rate": 0}],
    )
    await sales_svc.post_sales_invoice(
        db_session,
        tenant_id=tenant_id,
        user_id=seeded["admin1"].id,
        invoice_id=inv.id,
    )
    await db_session.commit()

    movement = (
        await db_session.execute(
            select(m.StockMovement).where(
                m.StockMovement.reference_type == "sales_invoice",
                m.StockMovement.reference_id == inv.id,
            )
        )
    ).scalar_one()
    assert movement.warehouse_id is None
    await db_session.refresh(product)
    assert float(product.stock_qty) == start - 1
