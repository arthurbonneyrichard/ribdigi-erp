"""Atomic stock movement engine."""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m


def available_qty(on_hand: float, reserved: float) -> float:
    return max(float(on_hand or 0) - float(reserved or 0), 0.0)


async def get_warehouse(
    db: AsyncSession,
    tenant_id: str,
    warehouse_id: str,
    *,
    company_id: str | None = None,
) -> m.Warehouse:
    stmt = select(m.Warehouse).where(
        m.Warehouse.id == warehouse_id,
        m.Warehouse.tenant_id == tenant_id,
    )
    if company_id:
        stmt = stmt.where(m.Warehouse.company_id == company_id)
    wh = (await db.execute(stmt)).scalar_one_or_none()
    if not wh:
        raise HTTPException(status_code=404, detail="Warehouse not found")
    return wh


async def get_or_create_warehouse_stock(
    db: AsyncSession,
    *,
    tenant_id: str,
    warehouse_id: str,
    product_id: str,
    company_id: str | None = None,
) -> m.WarehouseStock:
    warehouse = await get_warehouse(db, tenant_id, warehouse_id, company_id=company_id)
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
        if not getattr(row, "company_id", None):
            product = await db.get(m.Product, product_id)
            row.company_id = (
                getattr(product, "company_id", None)
                or getattr(warehouse, "company_id", None)
            )
        return row
    product = await db.get(m.Product, product_id)
    row = m.WarehouseStock(
        tenant_id=tenant_id,
        company_id=getattr(product, "company_id", None)
        or getattr(warehouse, "company_id", None),
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
    company_id: str | None = None,
) -> m.WarehouseStock:
    row = await get_or_create_warehouse_stock(
        db,
        tenant_id=tenant_id,
        warehouse_id=warehouse_id,
        product_id=product_id,
        company_id=company_id,
    )
    before = float(row.quantity or 0)
    reserved = float(row.reserved_qty or 0)
    after = before + float(quantity_delta)
    if float(quantity_delta) < 0 and not allow_negative:
        avail = available_qty(before, reserved)
        if abs(float(quantity_delta)) > avail + 1e-9:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "INSUFFICIENT_WAREHOUSE_STOCK",
                    "message": "Insufficient available stock at source warehouse",
                    "on_hand": before,
                    "reserved": reserved,
                    "available": avail,
                    "requested": abs(float(quantity_delta)),
                    "warehouse_id": warehouse_id,
                    "product_id": product_id,
                },
            )
    elif after < 0 and not allow_negative:
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


async def reserve_product_stock(
    db: AsyncSession,
    *,
    tenant_id: str,
    product_id: str,
    quantity: float,
    sales_order_id: str,
    sales_order_item_id: str,
    warehouse_id: str | None = None,
    variant_id: str | None = None,
    user_id: str | None = None,
    company_id: str | None = None,
) -> m.StockReservation:
    """Soft-allocate on-hand stock for a sales order line (does not reduce stock_qty)."""
    qty = float(quantity)
    if qty <= 0:
        raise HTTPException(status_code=400, detail="Reservation quantity must be positive")

    product = (
        await db.execute(
            select(m.Product)
            .where(m.Product.id == product_id, m.Product.tenant_id == tenant_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    wh_row = None
    if warehouse_id:
        scope_cid = company_id or getattr(product, "company_id", None)
        await allocate_unlocated_stock(
            db,
            tenant_id=tenant_id,
            warehouse_id=warehouse_id,
            product_id=product_id,
            company_id=scope_cid,
        )
        wh_row = await get_or_create_warehouse_stock(
            db,
            tenant_id=tenant_id,
            warehouse_id=warehouse_id,
            product_id=product_id,
            company_id=scope_cid,
        )
        # re-lock warehouse row
        wh_row = (
            await db.execute(
                select(m.WarehouseStock)
                .where(m.WarehouseStock.id == wh_row.id)
                .with_for_update()
            )
        ).scalar_one()
        avail = available_qty(wh_row.quantity, wh_row.reserved_qty)
        if qty > avail + 1e-9:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "INSUFFICIENT_AVAILABLE_STOCK",
                    "message": f"Insufficient available stock for {product.sku} at warehouse",
                    "on_hand": float(wh_row.quantity or 0),
                    "reserved": float(wh_row.reserved_qty or 0),
                    "available": avail,
                    "requested": qty,
                    "product_id": product_id,
                    "warehouse_id": warehouse_id,
                },
            )
        wh_row.reserved_qty = float(wh_row.reserved_qty or 0) + qty

    # Consolidated product reservation always tracks total soft allocation.
    prod_avail = available_qty(product.stock_qty, product.reserved_qty)
    if qty > prod_avail + 1e-9:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "INSUFFICIENT_AVAILABLE_STOCK",
                "message": f"Insufficient available stock for {product.sku}",
                "on_hand": float(product.stock_qty or 0),
                "reserved": float(product.reserved_qty or 0),
                "available": prod_avail,
                "requested": qty,
                "product_id": product_id,
            },
        )
    product.reserved_qty = float(product.reserved_qty or 0) + qty

    now = datetime.utcnow()
    reservation = m.StockReservation(
        tenant_id=tenant_id,
        company_id=getattr(product, "company_id", None),
        product_id=product_id,
        variant_id=variant_id,
        warehouse_id=warehouse_id,
        sales_order_id=sales_order_id,
        sales_order_item_id=sales_order_item_id,
        quantity=qty,
        status="active",
        created_at=now,
        updated_at=now,
    )
    db.add(reservation)
    from app import audit as audit_svc

    await audit_svc.record_event(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        module="inventory",
        action="stock_reserve",
        entity="sales_order",
        entity_id=sales_order_id,
        details={
            "product_id": product_id,
            "variant_id": variant_id,
            "warehouse_id": warehouse_id,
            "quantity": qty,
            "sales_order_item_id": sales_order_item_id,
        },
    )
    await db.flush()
    return reservation


async def _finalize_reservations(
    db: AsyncSession,
    *,
    tenant_id: str,
    sales_order_id: str,
    new_status: str,
    user_id: str | None = None,
) -> list[m.StockReservation]:
    if new_status not in {"released", "consumed"}:
        raise ValueError("new_status must be released or consumed")
    rows = (
        await db.execute(
            select(m.StockReservation)
            .where(
                m.StockReservation.tenant_id == tenant_id,
                m.StockReservation.sales_order_id == sales_order_id,
                m.StockReservation.status == "active",
            )
            .with_for_update()
        )
    ).scalars().all()
    now = datetime.utcnow()
    for row in rows:
        qty = float(row.quantity or 0)
        product = (
            await db.execute(
                select(m.Product)
                .where(m.Product.id == row.product_id, m.Product.tenant_id == tenant_id)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if product:
            product.reserved_qty = max(float(product.reserved_qty or 0) - qty, 0.0)
        if row.warehouse_id:
            wh_row = (
                await db.execute(
                    select(m.WarehouseStock)
                    .where(
                        m.WarehouseStock.tenant_id == tenant_id,
                        m.WarehouseStock.warehouse_id == row.warehouse_id,
                        m.WarehouseStock.product_id == row.product_id,
                    )
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if wh_row:
                wh_row.reserved_qty = max(float(wh_row.reserved_qty or 0) - qty, 0.0)
        row.status = new_status
        row.updated_at = now
    if rows:
        from app import audit as audit_svc

        await audit_svc.record_event(
            db,
            tenant_id=tenant_id,
            user_id=user_id,
            module="inventory",
            action=f"stock_reservation_{new_status}",
            entity="sales_order",
            entity_id=sales_order_id,
            details={"count": len(rows), "status": new_status},
        )
    await db.flush()
    return list(rows)


async def release_reservations_for_order(
    db: AsyncSession,
    *,
    tenant_id: str,
    sales_order_id: str,
    user_id: str | None = None,
) -> list[m.StockReservation]:
    return await _finalize_reservations(
        db,
        tenant_id=tenant_id,
        sales_order_id=sales_order_id,
        new_status="released",
        user_id=user_id,
    )


async def consume_reservations_for_order(
    db: AsyncSession,
    *,
    tenant_id: str,
    sales_order_id: str,
    user_id: str | None = None,
) -> list[m.StockReservation]:
    return await _finalize_reservations(
        db,
        tenant_id=tenant_id,
        sales_order_id=sales_order_id,
        new_status="consumed",
        user_id=user_id,
    )


async def allocate_unlocated_stock(
    db: AsyncSession,
    *,
    tenant_id: str,
    warehouse_id: str,
    product_id: str,
    company_id: str | None = None,
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
            company_id=company_id or getattr(product, "company_id", None),
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
            company_id=getattr(product, "company_id", None),
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
            company_id=getattr(product, "company_id", None),
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


ADJUSTMENT_REASONS = frozenset({"damage", "theft", "expiry", "found", "lost", "other"})


def serialize_movement(
    row: m.StockMovement,
    *,
    product: m.Product | None = None,
    warehouse: m.Warehouse | None = None,
    user: m.User | None = None,
) -> dict:
    return {
        "id": row.id,
        "company_id": getattr(row, "company_id", None),
        "product_id": row.product_id,
        "product_sku": product.sku if product else None,
        "product_name": product.name if product else None,
        "variant_id": row.variant_id,
        "batch_id": row.batch_id,
        "warehouse_id": row.warehouse_id,
        "warehouse_code": warehouse.code if warehouse else None,
        "movement_type": row.movement_type,
        "quantity": float(row.quantity or 0),
        "quantity_before": float(row.quantity_before or 0),
        "quantity_after": float(row.quantity_after or 0),
        "reference_type": row.reference_type,
        "reference_id": row.reference_id,
        "reason": getattr(row, "reason", None),
        "notes": row.notes,
        "created_by": row.created_by,
        "created_by_email": user.email if user else None,
        "created_by_name": user.full_name if user else None,
        "created_at": row.created_at,
    }


async def list_movements_serialized(
    db: AsyncSession,
    *,
    tenant_id: str,
    product_id: str | None = None,
    warehouse_id: str | None = None,
    movement_type: str | None = None,
    from_dt=None,
    to_dt=None,
    limit: int = 200,
    company_id: str | None = None,
) -> list[dict]:
    stmt = select(m.StockMovement).where(m.StockMovement.tenant_id == tenant_id)
    if company_id:
        stmt = stmt.where(m.StockMovement.company_id == company_id)
    if product_id:
        stmt = stmt.where(m.StockMovement.product_id == product_id)
    if warehouse_id:
        stmt = stmt.where(m.StockMovement.warehouse_id == warehouse_id)
    if movement_type:
        stmt = stmt.where(m.StockMovement.movement_type == movement_type)
    if from_dt:
        stmt = stmt.where(m.StockMovement.created_at >= from_dt)
    if to_dt:
        stmt = stmt.where(m.StockMovement.created_at <= to_dt)
    rows = list(
        (await db.execute(stmt.order_by(m.StockMovement.created_at.desc()).limit(limit))).scalars().all()
    )
    if not rows:
        return []
    product_ids = {r.product_id for r in rows}
    warehouse_ids = {r.warehouse_id for r in rows if r.warehouse_id}
    user_ids = {r.created_by for r in rows if r.created_by}
    products = {
        p.id: p
        for p in (
            await db.execute(
                select(m.Product).where(m.Product.tenant_id == tenant_id, m.Product.id.in_(product_ids))
            )
        )
        .scalars()
        .all()
    }
    warehouses = {}
    if warehouse_ids:
        warehouses = {
            w.id: w
            for w in (
                await db.execute(
                    select(m.Warehouse).where(
                        m.Warehouse.tenant_id == tenant_id, m.Warehouse.id.in_(warehouse_ids)
                    )
                )
            )
            .scalars()
            .all()
        }
    users = {}
    if user_ids:
        users = {
            u.id: u
            for u in (
                await db.execute(
                    select(m.User).where(m.User.tenant_id == tenant_id, m.User.id.in_(user_ids))
                )
            )
            .scalars()
            .all()
        }
    return [
        serialize_movement(
            r,
            product=products.get(r.product_id),
            warehouse=warehouses.get(r.warehouse_id) if r.warehouse_id else None,
            user=users.get(r.created_by) if r.created_by else None,
        )
        for r in rows
    ]


def compute_stock_status(
    quantity: float | None,
    minimum_stock: float | None,
    reorder_level: float | None,
) -> str:
    """BR-5.5 traffic light: red ≤ minimum, yellow ≤ reorder, else green."""
    qty = float(quantity or 0)
    minimum = float(minimum_stock or 0)
    reorder = float(reorder_level or 0)
    if qty <= minimum:
        return "red"
    if reorder > 0 and qty <= reorder:
        return "yellow"
    return "green"


def effective_warehouse_thresholds(
    stock: m.WarehouseStock,
    product: m.Product,
) -> tuple[float, float]:
    w_min = float(getattr(stock, "minimum_stock", 0) or 0)
    w_ro = float(getattr(stock, "reorder_level", 0) or 0)
    if w_min <= 0 and w_ro <= 0:
        return float(getattr(product, "minimum_stock", 0) or 0), float(product.reorder_level or 0)
    return w_min, w_ro


def normalize_adjustment_reason(reason: str | None) -> str:
    code = (reason or "").strip().lower()
    if code not in ADJUSTMENT_REASONS:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_ADJUSTMENT_REASON",
                "message": "reason must be one of: damage, theft, expiry, found, lost, other",
                "allowed": sorted(ADJUSTMENT_REASONS),
            },
        )
    return code


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
    company_id: str | None = None,
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
    reserved = float(product.reserved_qty or 0)
    after = before + float(quantity_delta)
    if float(quantity_delta) < 0 and not allow_negative:
        avail = available_qty(before, reserved)
        if abs(float(quantity_delta)) > avail + 1e-9:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "INSUFFICIENT_STOCK",
                    "message": f"Insufficient available stock for {product.sku}",
                    "on_hand": before,
                    "reserved": reserved,
                    "available": avail,
                    "requested": abs(float(quantity_delta)),
                },
            )
    elif after < 0 and not allow_negative:
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
        await get_warehouse(db, tenant_id, warehouse_id, company_id=company_id)
        await apply_warehouse_stock_change(
            db,
            tenant_id=tenant_id,
            warehouse_id=warehouse_id,
            product_id=product.id,
            quantity_delta=float(quantity_delta),
            allow_negative=allow_negative,
            company_id=company_id,
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
        company_id=company_id or getattr(product, "company_id", None),
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
        reason=reason,
        notes=notes,
        created_by=user_id,
    )
    db.add(movement)
    from app import audit as audit_svc

    await audit_svc.record_event(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        module="inventory",
        action=f"stock_{movement_type}",
        entity="product",
        entity_id=product.id,
        details={
            "quantity_delta": float(quantity_delta),
            "before": before,
            "after": after,
            "warehouse_id": warehouse_id,
            "reference_type": reference_type,
            "reference_id": reference_id,
            "variant_id": variant_id,
            "batch_id": batch_id,
            "reason": reason,
            "notes": notes,
        },
    )
    if compute_stock_status(
        after, getattr(product, "minimum_stock", 0), product.reorder_level
    ) != "green":
        from app.notifications import notify_low_stock_if_needed

        await notify_low_stock_if_needed(db, tenant_id=tenant_id, product=product)
    # Stage 6 P2 — stock changes invalidate catalog + dashboard KPI caches
    from app import cache as cache_svc

    await cache_svc.app_cache.invalidate_tenant(tenant_id)
    return product


async def assert_outbound_lines_stock_available(
    db: AsyncSession,
    *,
    tenant_id: str,
    items: list[dict],
) -> None:
    """Fail-fast stock check before creating payments/journals for an outbound sale.

    Aggregates requested qty per product (+ optional variant) so multi-line carts
    cannot bypass the check line-by-line. Raises 409 INSUFFICIENT_STOCK with the
    same structured detail shape as ``apply_stock_change``. Warehouse-scoped
    enforcement remains on the authoritative ``apply_line_items_stock`` path.
    """
    if not items:
        return
    needed: dict[tuple[str, str | None], float] = {}
    for item in items:
        product_id = item.get("product_id")
        qty = float(item.get("quantity") or 0)
        variant_id = item.get("variant_id") or None
        if not product_id or qty <= 0:
            raise HTTPException(
                status_code=400,
                detail="Each line item needs product_id and positive quantity",
            )
        key = (str(product_id), str(variant_id) if variant_id else None)
        needed[key] = needed.get(key, 0.0) + qty

    for (product_id, variant_id), qty in needed.items():
        product = (
            await db.execute(
                select(m.Product).where(
                    m.Product.id == product_id,
                    m.Product.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        on_hand = float(product.stock_qty or 0)
        reserved = float(product.reserved_qty or 0)
        avail = available_qty(on_hand, reserved)
        if qty > avail + 1e-9:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "INSUFFICIENT_STOCK",
                    "message": f"Insufficient available stock for {product.sku}",
                    "on_hand": on_hand,
                    "reserved": reserved,
                    "available": avail,
                    "requested": qty,
                },
            )
        if variant_id:
            from app.catalog import get_variant

            variant = await get_variant(db, tenant_id, variant_id)
            if variant.product_id != product.id:
                raise HTTPException(
                    status_code=400, detail="Variant does not belong to product"
                )
            v_avail = float(variant.stock_qty or 0)
            if qty > v_avail + 1e-9:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "INSUFFICIENT_STOCK",
                        "message": f"Insufficient variant stock for {variant.sku}",
                        "available": v_avail,
                        "requested": qty,
                    },
                )


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
    """Apply stock for transaction payload items: [{product_id, quantity, variant_id?}]."""
    if not items:
        return
    from app.catalog import get_variant, stock_out_with_batch

    for item in items:
        product_id = item.get("product_id")
        qty = float(item.get("quantity") or 0)
        variant_id = item.get("variant_id")
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
                variant_id=variant_id,
                warehouse_id=warehouse_id,
                notes=f"{reference_type} {reference_id}",
                reference_type=reference_type,
                reference_id=reference_id,
            )
        else:
            await apply_stock_change(
                db,
                tenant_id=tenant_id,
                product_id=product_id,
                quantity_delta=qty,
                movement_type=movement_type,
                user_id=user_id,
                reference_type=reference_type,
                reference_id=reference_id,
                variant_id=variant_id,
                warehouse_id=warehouse_id,
            )
            if variant_id:
                variant = await get_variant(db, tenant_id, variant_id)
                variant.stock_qty = float(variant.stock_qty or 0) + qty
