"""Atomic stock movement engine."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m

STOCK_ADJUSTMENT_REASONS = frozenset({"damage", "theft", "expiry", "found", "lost"})
# BR-5.2 Stock Out reference (sales / transfer / adjustment / damage + internal/other)
STOCK_OUT_REFERENCE_TYPES = frozenset(
    {"sale", "transfer", "adjustment", "damage", "internal", "other"}
)


async def get_or_create_warehouse_stock(
    db: AsyncSession,
    *,
    tenant_id: str,
    warehouse_id: str,
    product_id: str,
) -> m.WarehouseStock:
    row = (
        await db.execute(
            select(m.WarehouseStock)
            .where(
                m.WarehouseStock.tenant_id == tenant_id,
                m.WarehouseStock.warehouse_id == warehouse_id,
                m.WarehouseStock.product_id == product_id,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if row:
        return row
    row = m.WarehouseStock(
        tenant_id=tenant_id,
        warehouse_id=warehouse_id,
        product_id=product_id,
        quantity=0,
    )
    db.add(row)
    await db.flush()
    return row


async def apply_warehouse_stock_change(
    db: AsyncSession,
    *,
    tenant_id: str,
    warehouse_id: str,
    product_id: str,
    quantity_delta: float,
    allow_negative: bool = False,
) -> m.WarehouseStock:
    row = await get_or_create_warehouse_stock(
        db, tenant_id=tenant_id, warehouse_id=warehouse_id, product_id=product_id
    )
    before = float(row.quantity or 0)
    after = before + float(quantity_delta)
    if after < 0 and not allow_negative:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "INSUFFICIENT_WAREHOUSE_STOCK",
                "message": "Insufficient stock at source warehouse",
                "available": before,
                "requested": abs(float(quantity_delta)),
                "warehouse_id": warehouse_id,
                "product_id": product_id,
            },
        )
    row.quantity = after
    await db.flush()
    return row


async def allocate_unlocated_stock(
    db: AsyncSession,
    *,
    tenant_id: str,
    warehouse_id: str,
    product_id: str,
) -> None:
    """If product has consolidated stock but no warehouse rows, park it at warehouse_id."""
    located = float(
        (
            await db.execute(
                select(func.coalesce(func.sum(m.WarehouseStock.quantity), 0)).where(
                    m.WarehouseStock.tenant_id == tenant_id,
                    m.WarehouseStock.product_id == product_id,
                )
            )
        ).scalar()
        or 0
    )
    product = (
        await db.execute(
            select(m.Product).where(m.Product.id == product_id, m.Product.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    unlocated = float(product.stock_qty or 0) - located
    if unlocated > 0:
        await apply_warehouse_stock_change(
            db,
            tenant_id=tenant_id,
            warehouse_id=warehouse_id,
            product_id=product_id,
            quantity_delta=unlocated,
        )


async def transfer_warehouse_stock(
    db: AsyncSession,
    *,
    tenant_id: str,
    product_id: str,
    from_warehouse_id: str,
    to_warehouse_id: str,
    quantity: float,
    user_id: str | None,
    reference_id: str,
    notes: str | None = None,
) -> None:
    """Move stock between warehouses without changing consolidated product.stock_qty."""
    qty = float(quantity)
    if qty <= 0:
        raise HTTPException(status_code=400, detail="Transfer quantity must be positive")
    if from_warehouse_id == to_warehouse_id:
        raise HTTPException(status_code=400, detail="Source and destination warehouse must differ")

    from app.warehouses import require_active_warehouse

    await require_active_warehouse(db, tenant_id, from_warehouse_id)
    await require_active_warehouse(db, tenant_id, to_warehouse_id)

    await allocate_unlocated_stock(
        db, tenant_id=tenant_id, warehouse_id=from_warehouse_id, product_id=product_id
    )
    product = (
        await db.execute(
            select(m.Product)
            .where(m.Product.id == product_id, m.Product.tenant_id == tenant_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    before = float(product.stock_qty or 0)
    await apply_warehouse_stock_change(
        db,
        tenant_id=tenant_id,
        warehouse_id=from_warehouse_id,
        product_id=product_id,
        quantity_delta=-qty,
    )
    db.add(
        m.StockMovement(
            tenant_id=tenant_id,
            product_id=product_id,
            warehouse_id=from_warehouse_id,
            movement_type="transfer_out",
            quantity=-qty,
            quantity_before=before,
            quantity_after=before,
            reference_type="stock_transfer",
            reference_id=reference_id,
            notes=notes,
            created_by=user_id,
        )
    )
    await apply_warehouse_stock_change(
        db,
        tenant_id=tenant_id,
        warehouse_id=to_warehouse_id,
        product_id=product_id,
        quantity_delta=qty,
    )
    db.add(
        m.StockMovement(
            tenant_id=tenant_id,
            product_id=product_id,
            warehouse_id=to_warehouse_id,
            movement_type="transfer_in",
            quantity=qty,
            quantity_before=before,
            quantity_after=before,
            reference_type="stock_transfer",
            reference_id=reference_id,
            notes=notes,
            created_by=user_id,
        )
    )


async def apply_stock_change(
    db: AsyncSession,
    *,
    tenant_id: str,
    product_id: str,
    quantity_delta: float,
    movement_type: str,
    user_id: str | None = None,
    reference_type: str | None = None,
    reference_id: str | None = None,
    notes: str | None = None,
    reason: str | None = None,
    warehouse_id: str | None = None,
    allow_negative: bool = False,
    variant_id: str | None = None,
    batch_id: str | None = None,
) -> m.Product:
    if quantity_delta == 0:
        raise HTTPException(status_code=400, detail="Stock quantity change cannot be zero")

    result = await db.execute(
        select(m.Product)
        .where(m.Product.id == product_id, m.Product.tenant_id == tenant_id)
        .with_for_update()
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    before = float(product.stock_qty or 0)
    after = before + float(quantity_delta)
    if after < 0 and not allow_negative:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "INSUFFICIENT_STOCK",
                "message": f"Insufficient stock for {product.sku}",
                "available": before,
                "requested": abs(float(quantity_delta)),
            },
        )

    product.stock_qty = after
    if warehouse_id:
        from app.warehouses import require_active_warehouse

        await require_active_warehouse(db, tenant_id, warehouse_id)
        await apply_warehouse_stock_change(
            db,
            tenant_id=tenant_id,
            warehouse_id=warehouse_id,
            product_id=product.id,
            quantity_delta=float(quantity_delta),
            allow_negative=allow_negative,
        )
        # Warehouse-level reorder alert after stock-out
        if float(quantity_delta) < 0:
            from app.notifications import notify_warehouse_low_stock_if_needed

            wh_row = await get_or_create_warehouse_stock(
                db, tenant_id=tenant_id, warehouse_id=warehouse_id, product_id=product.id
            )
            await notify_warehouse_low_stock_if_needed(
                db, tenant_id=tenant_id, product=product, stock=wh_row
            )
    movement = m.StockMovement(
        tenant_id=tenant_id,
        product_id=product.id,
        variant_id=variant_id,
        batch_id=batch_id,
        warehouse_id=warehouse_id,
        movement_type=movement_type,
        quantity=float(quantity_delta),
        quantity_before=before,
        quantity_after=after,
        reference_type=reference_type,
        reference_id=reference_id,
        notes=notes,
        reason=reason,
        created_by=user_id,
    )
    db.add(movement)
    db.add(
        m.AuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            action=f"stock_{movement_type}",
            entity="product",
            entity_id=product.id,
            details={
                "quantity_delta": float(quantity_delta),
                "before": before,
                "after": after,
                "reference_type": reference_type,
                "reference_id": reference_id,
                "variant_id": variant_id,
                "batch_id": batch_id,
                "reason": reason,
            },
        )
    )
    # Inbound stock webhook — skip GRN (document-level purchase.grn.received already fans out).
    if movement_type == "stock_in" and (reference_type or "").lower() != "grn":
        from app import webhooks as webhooks_svc

        await webhooks_svc.emit_event(
            db,
            tenant_id=tenant_id,
            event="stock.in",
            data={
                "product_id": product.id,
                "sku": product.sku,
                "name": product.name,
                "quantity": float(quantity_delta),
                "stock_qty": after,
                "warehouse_id": warehouse_id,
                "variant_id": variant_id,
                "batch_id": batch_id,
                "reference_type": reference_type,
                "reference_id": reference_id,
            },
        )
    if after <= float(product.reorder_level or 0):
        from app.notifications import notify_low_stock_if_needed

        await notify_low_stock_if_needed(db, tenant_id=tenant_id, product=product)
    return product


async def apply_line_items_stock(
    db: AsyncSession,
    *,
    tenant_id: str,
    items: list[dict],
    movement_type: str,
    user_id: str | None,
    reference_type: str,
    reference_id: str,
    outbound: bool,
    warehouse_id: str | None = None,
) -> None:
    """Apply stock for transaction payload items: [{product_id, quantity, unit_id?, variant_id?}]."""
    if not items:
        return
    from app.catalog import get_variant, stock_out_with_batch

    for item in items:
        product_id = item.get("product_id")
        qty = float(item.get("quantity") or 0)
        variant_id = item.get("variant_id")
        unit_id = item.get("unit_id")
        if not product_id or qty <= 0:
            raise HTTPException(status_code=400, detail="Each line item needs product_id and positive quantity")
        if outbound:
            if warehouse_id:
                await allocate_unlocated_stock(
                    db,
                    tenant_id=tenant_id,
                    warehouse_id=warehouse_id,
                    product_id=product_id,
                )
            await stock_out_with_batch(
                db,
                tenant_id=tenant_id,
                user_id=user_id or "",
                product_id=product_id,
                quantity=qty,
                unit_id=unit_id,
                variant_id=variant_id,
                warehouse_id=warehouse_id,
                notes=f"{reference_type} {reference_id}",
                reference_type=reference_type,
                reference_id=reference_id,
            )
        else:
            from app.uom import to_stock_qty
            from app.catalog import get_product

            product = await get_product(db, tenant_id, product_id)
            stock_qty, _u, _e = await to_stock_qty(
                db,
                tenant_id=tenant_id,
                quantity=qty,
                from_unit_id=unit_id,
                product=product,
            )
            await apply_stock_change(
                db,
                tenant_id=tenant_id,
                product_id=product_id,
                quantity_delta=stock_qty,
                movement_type=movement_type,
                user_id=user_id,
                reference_type=reference_type,
                reference_id=reference_id,
                variant_id=variant_id,
                warehouse_id=warehouse_id,
            )
            if variant_id:
                variant = await get_variant(db, tenant_id, variant_id)
                variant.stock_qty = float(variant.stock_qty or 0) + stock_qty


async def list_warehouse_stock(
    db: AsyncSession,
    tenant_id: str,
    warehouse_id: str,
    *,
    include_zero: bool = False,
) -> dict:
    """BR-5.4 — per-warehouse on-hand + reorder policy (inventory:read)."""
    from app.warehouses import get_warehouse

    wh = await get_warehouse(db, tenant_id, warehouse_id)
    stmt = (
        select(m.WarehouseStock, m.Product)
        .join(m.Product, m.Product.id == m.WarehouseStock.product_id)
        .where(
            m.WarehouseStock.tenant_id == tenant_id,
            m.WarehouseStock.warehouse_id == wh.id,
        )
        .order_by(m.Product.name)
    )
    if not include_zero:
        stmt = stmt.where(
            (m.WarehouseStock.quantity > 0) | (m.WarehouseStock.reorder_level > 0)
        )
    rows = (await db.execute(stmt)).all()
    items = []
    for stock, product in rows:
        qty = float(stock.quantity or 0)
        reorder = float(stock.reorder_level or 0)
        reorder_qty = float(stock.reorder_qty or 0)
        items.append(
            {
                "product_id": product.id,
                "sku": product.sku,
                "name": product.name,
                "quantity": qty,
                "reorder_level": reorder,
                "reorder_qty": reorder_qty,
                "below_reorder": reorder > 0 and qty <= reorder,
                "suggested_order_qty": max(reorder_qty, round(reorder - qty, 3))
                if reorder > 0 and qty <= reorder
                else reorder_qty,
                "warehouse_id": wh.id,
                "consolidated_stock": float(product.stock_qty or 0),
            }
        )
    return {
        "warehouse_id": wh.id,
        "warehouse_code": wh.code,
        "warehouse_name": wh.name,
        "store_id": wh.store_id,
        "include_zero": include_zero,
        "count": len(items),
        "items": items,
        "total_quantity": round(sum(i["quantity"] for i in items), 3),
    }


async def set_warehouse_reorder_policy(
    db: AsyncSession,
    *,
    tenant_id: str,
    warehouse_id: str,
    product_id: str,
    reorder_level: float,
    reorder_qty: float = 0,
) -> dict:
    """BR-5.4 — set per-warehouse reorder level/qty (inventory:write)."""
    from app.warehouses import get_warehouse

    wh = await get_warehouse(db, tenant_id, warehouse_id)
    product = (
        await db.execute(
            select(m.Product).where(
                m.Product.id == product_id, m.Product.tenant_id == tenant_id
            )
        )
    ).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    row = await get_or_create_warehouse_stock(
        db, tenant_id=tenant_id, warehouse_id=wh.id, product_id=product_id
    )
    row.reorder_level = max(float(reorder_level or 0), 0)
    row.reorder_qty = max(float(reorder_qty or 0), 0)
    await db.flush()
    qty = float(row.quantity or 0)
    reorder = float(row.reorder_level or 0)
    return {
        "product_id": product.id,
        "sku": product.sku,
        "name": product.name,
        "quantity": qty,
        "reorder_level": reorder,
        "reorder_qty": float(row.reorder_qty or 0),
        "below_reorder": reorder > 0 and qty <= reorder,
        "warehouse_id": wh.id,
        "store_id": wh.store_id,
    }


async def lookup_products(
    db: AsyncSession,
    tenant_id: str,
    *,
    q: str = "",
    barcode: str | None = None,
    limit: int = 48,
) -> dict:
    """BR-18.2 barcode/SKU/name lookup under inventory:read (not POS-scoped)."""
    from app import barcodes as barcodes_svc
    from app import catalog_meta as catalog_meta_svc

    q_clean = (q or "").strip()
    barcode_key = (barcode or "").strip() or (
        q_clean if barcodes_svc.looks_like_barcode(q_clean) else ""
    )
    stmt = select(m.Product).where(
        m.Product.tenant_id == tenant_id,
        m.Product.is_active == True,  # noqa: E712
    )
    if barcode_key:
        stmt = stmt.where(
            (m.Product.barcode == barcode_key)
            | (m.Product.sku == barcode_key)
            | (func.lower(m.Product.barcode) == barcode_key.lower())
            | (func.lower(m.Product.sku) == barcode_key.lower())
        )
    elif q_clean:
        like = f"%{q_clean}%"
        stmt = stmt.where(
            m.Product.name.ilike(like)
            | m.Product.sku.ilike(like)
            | m.Product.barcode.ilike(like)
        )
    else:
        return {
            "q": q_clean,
            "barcode": barcode_key or None,
            "count": 0,
            "items": [],
        }

    lim = max(1, min(int(limit or 48), 100))
    products = (await db.execute(stmt.order_by(m.Product.name).limit(lim))).scalars().all()
    return {
        "q": q_clean,
        "barcode": barcode_key or None,
        "count": len(products),
        "items": [catalog_meta_svc.serialize_product(p) for p in products],
    }


async def list_product_warehouse_stock(
    db: AsyncSession,
    tenant_id: str,
    product_id: str,
    *,
    include_zero: bool = True,
) -> dict:
    """BR-18.2 / BR-5.4 — stock levels for one product across warehouses."""
    product = (
        await db.execute(
            select(m.Product).where(
                m.Product.id == product_id, m.Product.tenant_id == tenant_id
            )
        )
    ).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    stmt = (
        select(m.WarehouseStock, m.Warehouse)
        .join(m.Warehouse, m.Warehouse.id == m.WarehouseStock.warehouse_id)
        .where(
            m.WarehouseStock.tenant_id == tenant_id,
            m.WarehouseStock.product_id == product.id,
        )
        .order_by(m.Warehouse.code)
    )
    if not include_zero:
        stmt = stmt.where(
            (m.WarehouseStock.quantity > 0) | (m.WarehouseStock.reorder_level > 0)
        )
    rows = (await db.execute(stmt)).all()
    items = []
    for stock, wh in rows:
        qty = float(stock.quantity or 0)
        reorder = float(stock.reorder_level or 0)
        items.append(
            {
                "warehouse_id": wh.id,
                "warehouse_code": wh.code,
                "warehouse_name": wh.name,
                "store_id": wh.store_id,
                "quantity": qty,
                "reorder_level": reorder,
                "reorder_qty": float(stock.reorder_qty or 0),
                "below_reorder": reorder > 0 and qty <= reorder,
            }
        )
    return {
        "product_id": product.id,
        "sku": product.sku,
        "name": product.name,
        "consolidated_stock": float(product.stock_qty or 0),
        "reorder_level": float(product.reorder_level or 0),
        "count": len(items),
        "items": items,
        "total_quantity": round(sum(i["quantity"] for i in items), 3),
    }
