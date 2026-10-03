"""ORM reads and stock updates when later columns are not migrated yet.

When the columns exist, values still persist. The guard only omits columns the
live table does not have.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select, text

from app import models as m
from app import schema_compat


@pytest.mark.asyncio
async def test_product_and_invoice_reads_skip_unmigrated_columns(db_engine, db_session, seeded):
    await db_session.rollback()
    async with db_engine.begin() as conn:
        await conn.execute(text("ALTER TABLE products DROP COLUMN min_order_qty"))
        await conn.execute(text("ALTER TABLE sales_invoices DROP COLUMN sales_channel"))
    schema_compat.clear_column_cache()
    try:
        product = (
            await db_session.execute(select(m.Product).where(m.Product.id == seeded["p1"].id))
        ).scalar_one()
        assert product.name == "Alpha Widget"
        assert product.min_order_qty == 0
        product.stock_qty = 7
        product.min_order_qty = 12
        await db_session.flush()
        stored = (
            await db_session.execute(
                text("SELECT stock_qty FROM products WHERE id = :id"),
                {"id": product.id},
            )
        ).scalar_one()
        assert float(stored) == 7
        picked = (
            await db_session.execute(
                select(m.Product.id, m.Product.stock_qty).where(m.Product.id == product.id)
            )
        ).one()
        assert float(picked.stock_qty) == 7

        created = m.Product(
            tenant_id=seeded["t1"].id,
            name="Guard Item",
            sku="GUARD-1",
            cost_price=1,
            selling_price=3,
            stock_qty=4,
            min_order_qty=9,
        )
        db_session.add(created)
        await db_session.flush()
        assert created.min_order_qty == 0
        assert (
            await db_session.execute(
                text("SELECT name FROM products WHERE sku = 'GUARD-1'")
            )
        ).scalar_one() == "Guard Item"

        invoice = (
            await db_session.execute(select(m.SalesInvoice).where(m.SalesInvoice.id == seeded["inv2"].id))
        ).scalar_one()
        assert invoice.invoice_number == "INV-B-1"
        assert invoice.sales_channel == "retail"
        invoice.notes = "guard note"
        invoice.sales_channel = "wholesale"
        await db_session.flush()
        note = (
            await db_session.execute(
                text("SELECT notes FROM sales_invoices WHERE id = :id"),
                {"id": invoice.id},
            )
        ).scalar_one()
        assert note == "guard note"
    finally:
        schema_compat.clear_column_cache()


@pytest.mark.asyncio
async def test_min_order_qty_persists_when_column_exists(db_session, seeded):
    schema_compat.clear_column_cache()
    product = (
        await db_session.execute(select(m.Product).where(m.Product.id == seeded["p1"].id))
    ).scalar_one()
    product.min_order_qty = 4
    await db_session.flush()
    await db_session.refresh(product)
    assert float(product.min_order_qty) == 4
    schema_compat.clear_column_cache()
