"""Physical inventory counts with variance adjustments."""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit as audit_svc
from app import models as m
from app.inventory import (
    allocate_unlocated_stock,
    apply_stock_change,
    get_or_create_warehouse_stock,
)

COUNT_EDITABLE = {"draft", "in_progress"}
COUNT_COMPLETABLE = {"draft", "in_progress"}
COUNT_CANCELLABLE = {"draft", "in_progress"}


async def get_warehouse(db: AsyncSession, tenant_id: str, warehouse_id: str) -> m.Warehouse:
    warehouse = (
        await db.execute(
            select(m.Warehouse).where(
                m.Warehouse.id == warehouse_id,
                m.Warehouse.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not warehouse:
        raise HTTPException(status_code=404, detail="Warehouse not found")
    return warehouse


async def get_count(db: AsyncSession, tenant_id: str, count_id: str) -> m.StockCount:
    row = (
        await db.execute(
            select(m.StockCount).where(
                m.StockCount.id == count_id,
                m.StockCount.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Stock count not found")
    return row


async def list_count_items(
    db: AsyncSession, tenant_id: str, count_id: str
) -> list[m.StockCountItem]:
    return (
        await db.execute(
            select(m.StockCountItem).where(
                m.StockCountItem.tenant_id == tenant_id,
                m.StockCountItem.stock_count_id == count_id,
            )
        )
    ).scalars().all()


def serialize_item(item: m.StockCountItem) -> dict:
    actual = None if item.actual_qty is None else float(item.actual_qty)
    expected = float(item.expected_qty or 0)
    difference = None if item.difference is None else float(item.difference)
    if actual is not None and difference is None:
        difference = actual - expected
    return {
        "id": item.id,
        "product_id": item.product_id,
        "variant_id": item.variant_id,
        "expected_qty": expected,
        "actual_qty": actual,
        "difference": difference,
        "notes": item.notes,
    }


async def serialize_count(db: AsyncSession, count: m.StockCount) -> dict:
    items = await list_count_items(db, count.tenant_id, count.id)
    counted = sum(1 for i in items if i.actual_qty is not None)
    variance_lines = [
        i
        for i in items
        if i.actual_qty is not None and abs(float(i.actual_qty) - float(i.expected_qty or 0)) > 1e-9
    ]
    return {
        "id": count.id,
        "count_number": count.count_number,
        "warehouse_id": count.warehouse_id,
        "status": count.status,
        "notes": count.notes,
        "counted_by": count.counted_by,
        "created_by": count.created_by,
        "completed_at": count.completed_at,
        "created_at": count.created_at,
        "item_count": len(items),
        "counted_item_count": counted,
        "variance_item_count": len(variance_lines),
        "items": [serialize_item(i) for i in items],
    }


async def _expected_qty(
    db: AsyncSession,
    *,
    tenant_id: str,
    warehouse_id: str,
    product_id: str,
) -> float:
    await allocate_unlocated_stock(
        db, tenant_id=tenant_id, warehouse_id=warehouse_id, product_id=product_id
    )
    row = await get_or_create_warehouse_stock(
        db, tenant_id=tenant_id, warehouse_id=warehouse_id, product_id=product_id
    )
    return float(row.quantity or 0)


async def create_stock_count(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    warehouse_id: str,
    product_ids: list[str] | None = None,
    notes: str | None = None,
) -> m.StockCount:
    await get_warehouse(db, tenant_id, warehouse_id)
    products = (
        await db.execute(
            select(m.Product).where(
                m.Product.tenant_id == tenant_id,
                m.Product.is_active.is_(True),
            )
        )
    ).scalars().all()
    if product_ids:
        wanted = set(product_ids)
        products = [p for p in products if p.id in wanted]
        missing = wanted - {p.id for p in products}
        if missing:
            raise HTTPException(status_code=404, detail="Product not found")
    if not products:
        raise HTTPException(status_code=400, detail="Stock count requires at least one product")

    count = m.StockCount(
        tenant_id=tenant_id,
        count_number=f"CNT-{datetime.utcnow():%Y%m%d%H%M%S%f}",
        warehouse_id=warehouse_id,
        status="draft",
        notes=notes,
        created_by=user_id,
    )
    db.add(count)
    await db.flush()

    for product in products:
        expected = await _expected_qty(
            db, tenant_id=tenant_id, warehouse_id=warehouse_id, product_id=product.id
        )
        db.add(
            m.StockCountItem(
                tenant_id=tenant_id,
                stock_count_id=count.id,
                product_id=product.id,
                expected_qty=expected,
            )
        )

    await audit_svc.record_event(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        module="inventory",
        action="stock_count_created",
        entity="stock_count",
        entity_id=count.id,
        details={"count_number": count.count_number, "warehouse_id": warehouse_id},
    )
    return count


async def start_stock_count(
    db: AsyncSession, *, tenant_id: str, user_id: str, count_id: str
) -> m.StockCount:
    count = await get_count(db, tenant_id, count_id)
    if count.status != "draft":
        raise HTTPException(status_code=409, detail=f"Cannot start stock count in status {count.status}")
    count.status = "in_progress"
    count.updated_at = datetime.utcnow()
    await audit_svc.record_event(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        module="inventory",
        action="stock_count_started",
        entity="stock_count",
        entity_id=count.id,
        details={"count_number": count.count_number},
    )
    return count


async def set_count_item_actual(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    count_id: str,
    item_id: str,
    actual_qty: float,
    notes: str | None = None,
) -> m.StockCountItem:
    if actual_qty < 0:
        raise HTTPException(status_code=400, detail="Actual quantity cannot be negative")
    count = await get_count(db, tenant_id, count_id)
    if count.status not in COUNT_EDITABLE:
        raise HTTPException(status_code=409, detail=f"Cannot update items in status {count.status}")
    item = (
        await db.execute(
            select(m.StockCountItem).where(
                m.StockCountItem.id == item_id,
                m.StockCountItem.stock_count_id == count_id,
                m.StockCountItem.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Stock count item not found")
    item.actual_qty = actual_qty
    item.difference = float(actual_qty) - float(item.expected_qty or 0)
    if notes is not None:
        item.notes = notes
    count.updated_at = datetime.utcnow()
    await audit_svc.record_event(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        module="inventory",
        action="stock_count_item_updated",
        entity="stock_count",
        entity_id=count.id,
        details={"item_id": item.id, "actual_qty": float(actual_qty)},
    )
    return item


async def complete_stock_count(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    count_id: str,
    treat_uncounted_as_expected: bool = True,
) -> m.StockCount:
    count = await get_count(db, tenant_id, count_id)
    if count.status not in COUNT_COMPLETABLE:
        raise HTTPException(status_code=409, detail=f"Cannot complete stock count in status {count.status}")
    items = await list_count_items(db, tenant_id, count.id)
    if not items:
        raise HTTPException(status_code=400, detail="Cannot complete empty stock count")

    adjustments = 0
    for item in items:
        if item.actual_qty is None:
            if not treat_uncounted_as_expected:
                raise HTTPException(status_code=400, detail="All lines must have an actual quantity")
            continue
        actual = float(item.actual_qty)
        expected = float(item.expected_qty or 0)
        item.difference = actual - expected
        delta = item.difference
        if abs(delta) < 1e-9:
            continue
        await apply_stock_change(
            db,
            tenant_id=tenant_id,
            product_id=item.product_id,
            quantity_delta=delta,
            movement_type="stock_count",
            user_id=user_id,
            reference_type="stock_count",
            reference_id=count.id,
            warehouse_id=count.warehouse_id,
            variant_id=item.variant_id,
            notes=f"Physical count {count.count_number}",
            allow_negative=True,
        )
        adjustments += 1

    count.status = "completed"
    count.counted_by = user_id
    count.completed_at = datetime.utcnow()
    count.updated_at = count.completed_at
    await audit_svc.record_event(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        module="inventory",
        action="stock_count_completed",
        entity="stock_count",
        entity_id=count.id,
        details={"count_number": count.count_number, "adjustments": adjustments},
    )
    return count


async def cancel_stock_count(
    db: AsyncSession, *, tenant_id: str, user_id: str, count_id: str
) -> m.StockCount:
    count = await get_count(db, tenant_id, count_id)
    if count.status not in COUNT_CANCELLABLE:
        raise HTTPException(status_code=409, detail=f"Cannot cancel stock count in status {count.status}")
    count.status = "cancelled"
    count.updated_at = datetime.utcnow()
    await audit_svc.record_event(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        module="inventory",
        action="stock_count_cancelled",
        entity="stock_count",
        entity_id=count.id,
        details={"count_number": count.count_number},
    )
    return count
