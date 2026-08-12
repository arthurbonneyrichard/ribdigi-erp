"""Soft stock reservations for confirmed sales orders (BR-7.3)."""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.inventory import allocate_unlocated_stock, get_or_create_warehouse_stock


async def active_reserved_qty(
    db: AsyncSession,
    *,
    tenant_id: str,
    warehouse_id: str,
    product_id: str,
    exclude_order_id: str | None = None,
) -> float:
    stmt = select(func.coalesce(func.sum(m.StockReservation.quantity), 0)).where(
        m.StockReservation.tenant_id == tenant_id,
        m.StockReservation.warehouse_id == warehouse_id,
        m.StockReservation.product_id == product_id,
        m.StockReservation.status == "active",
    )
    if exclude_order_id:
        stmt = stmt.where(m.StockReservation.sales_order_id != exclude_order_id)
    return float((await db.execute(stmt)).scalar() or 0)


async def available_qty(
    db: AsyncSession,
    *,
    tenant_id: str,
    warehouse_id: str,
    product_id: str,
    exclude_order_id: str | None = None,
) -> float:
    await allocate_unlocated_stock(
        db, tenant_id=tenant_id, warehouse_id=warehouse_id, product_id=product_id
    )
    row = await get_or_create_warehouse_stock(
        db, tenant_id=tenant_id, warehouse_id=warehouse_id, product_id=product_id
    )
    on_hand = float(row.quantity or 0)
    reserved = await active_reserved_qty(
        db,
        tenant_id=tenant_id,
        warehouse_id=warehouse_id,
        product_id=product_id,
        exclude_order_id=exclude_order_id,
    )
    return on_hand - reserved


async def list_order_reservations(
    db: AsyncSession, tenant_id: str, order_id: str, *, status: str | None = "active"
) -> list[m.StockReservation]:
    stmt = select(m.StockReservation).where(
        m.StockReservation.tenant_id == tenant_id,
        m.StockReservation.sales_order_id == order_id,
    )
    if status:
        stmt = stmt.where(m.StockReservation.status == status)
    return (await db.execute(stmt)).scalars().all()


async def reserve_order(
    db: AsyncSession,
    *,
    tenant_id: str,
    order: m.SalesOrder,
    items: list[m.SalesOrderItem],
    warehouse_id: str,
) -> list[m.StockReservation]:
    existing = await list_order_reservations(db, tenant_id, order.id, status="active")
    if existing:
        return existing

    created: list[m.StockReservation] = []
    # Aggregate demand by product so multi-line same SKU checks once
    demand: dict[str, float] = {}
    for item in items:
        demand[item.product_id] = demand.get(item.product_id, 0.0) + float(item.quantity)

    for product_id, qty in demand.items():
        avail = await available_qty(
            db,
            tenant_id=tenant_id,
            warehouse_id=warehouse_id,
            product_id=product_id,
            exclude_order_id=order.id,
        )
        if avail + 1e-9 < qty:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "INSUFFICIENT_AVAILABLE_STOCK",
                    "message": "Insufficient available stock to reserve for this sales order",
                    "product_id": product_id,
                    "warehouse_id": warehouse_id,
                    "available": avail,
                    "requested": qty,
                },
            )

    for item in items:
        row = m.StockReservation(
            tenant_id=tenant_id,
            sales_order_id=order.id,
            sales_order_item_id=item.id,
            product_id=item.product_id,
            variant_id=item.variant_id,
            warehouse_id=warehouse_id,
            quantity=float(item.quantity),
            status="active",
        )
        db.add(row)
        created.append(row)
    await db.flush()
    return created


async def release_order_reservations(
    db: AsyncSession, *, tenant_id: str, order_id: str
) -> int:
    rows = await list_order_reservations(db, tenant_id, order_id, status="active")
    now = datetime.utcnow()
    for row in rows:
        row.status = "released"
        row.released_at = now
    await db.flush()
    return len(rows)


async def consume_order_reservations(
    db: AsyncSession, *, tenant_id: str, order_id: str
) -> int:
    rows = await list_order_reservations(db, tenant_id, order_id, status="active")
    now = datetime.utcnow()
    for row in rows:
        row.status = "consumed"
        row.consumed_at = now
    await db.flush()
    return len(rows)
