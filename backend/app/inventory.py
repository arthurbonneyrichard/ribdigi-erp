"""Atomic stock movement engine."""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.honesty import money_json, optional_honest_narrative

STOCK_ADJUSTMENT_REASONS = frozenset({"damage", "theft", "expiry", "found", "lost"})
# BR-5.2 Stock Out reference (sales / transfer / adjustment / damage + internal/other)
STOCK_OUT_REFERENCE_TYPES = frozenset(
    {"sale", "transfer", "adjustment", "damage", "internal", "other"}
)
# Written by stock_in/out, opening, adjust, WH/store transfers (+ cancel reverse).
MOVEMENT_TYPES = frozenset(
    {
        "stock_in",
        "stock_out",
        "opening_stock",
        "adjustment",
        "transfer_out",
        "transfer_in",
        "transfer_cancel",
    }
)


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
    before = money_json(row.quantity or 0)
    after = before + money_json(quantity_delta)
    if after < 0 and not allow_negative:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "INSUFFICIENT_WAREHOUSE_STOCK",
                "message": "Insufficient stock at source warehouse",
                "available": money_json(before),
                "requested": money_json(abs(money_json(quantity_delta))),
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
    located = money_json(
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
    unlocated = money_json(product.stock_qty or 0) - located
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
    qty = money_json(quantity)
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

    before = money_json(product.stock_qty or 0)
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

    # OpenAPI StockIn/Out/AdjustNotesValue → 422; service defense-in-depth → 400.
    notes = optional_honest_narrative(notes, label="stock movement notes")

    result = await db.execute(
        select(m.Product)
        .where(m.Product.id == product_id, m.Product.tenant_id == tenant_id)
        .with_for_update()
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    before = money_json(product.stock_qty or 0)
    after = before + money_json(quantity_delta)
    if after < 0 and not allow_negative:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "INSUFFICIENT_STOCK",
                "message": f"Insufficient stock for {product.sku}",
                "available": money_json(before),
                "requested": money_json(abs(money_json(quantity_delta))),
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
            quantity_delta=money_json(quantity_delta),
            allow_negative=allow_negative,
            company_id=company_id,
        )
        # Warehouse-level reorder alert after stock-out
        if money_json(quantity_delta) < 0:
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
        quantity=money_json(quantity_delta),
        quantity_before=before,
        quantity_after=after,
        reference_type=reference_type,
        reference_id=reference_id,
        reason=reason,
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
                "quantity_delta": money_json(quantity_delta),
                "before": money_json(before),
                "after": money_json(after),
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
                "quantity": money_json(quantity_delta),
                "stock_qty": money_json(after),
                "warehouse_id": warehouse_id,
                "variant_id": variant_id,
                "batch_id": batch_id,
                "reference_type": reference_type,
                "reference_id": reference_id,
            },
        )
    # Outbound stock webhook — skip POS/invoice document paths (sale.created already fans out).
    if movement_type == "stock_out" and (reference_type or "").lower() not in {
        "pos_sale",
        "sales_invoice",
    }:
        from app import webhooks as webhooks_svc

        await webhooks_svc.emit_event(
            db,
            tenant_id=tenant_id,
            event="stock.out",
            data={
                "product_id": product.id,
                "sku": product.sku,
                "name": product.name,
                "quantity": abs(money_json(quantity_delta)),
                "stock_qty": money_json(after),
                "warehouse_id": warehouse_id,
                "variant_id": variant_id,
                "batch_id": batch_id,
                "reference_type": reference_type,
                "reference_id": reference_id,
            },
        )
    if after <= money_json(product.reorder_level or 0):
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
    company_id: str | None = None,
) -> None:
    """Apply stock for transaction payload items: [{product_id, quantity, unit_id?, variant_id?}]."""
    if not items:
        return
    from app.catalog import get_variant, stock_out_with_batch
    from app.workspace import assert_fk_company

    for item in items:
        product_id = item.get("product_id")
        qty = money_json(item.get("quantity") or 0)
        variant_id = item.get("variant_id")
        unit_id = item.get("unit_id")
        if not product_id or qty <= 0:
            raise HTTPException(status_code=400, detail="Each line item needs product_id and positive quantity")
        product = (
            await db.execute(
                select(m.Product).where(
                    m.Product.id == product_id,
                    m.Product.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if not product:
            raise HTTPException(status_code=404, detail=f"Product not found: {product_id}")
        assert_fk_company(product, company_id, detail=f"Product not found: {product_id}")
        if outbound:
            if warehouse_id:
                await allocate_unlocated_stock(
                    db,
                    tenant_id=tenant_id,
                    warehouse_id=warehouse_id,
                    product_id=product_id,
                    company_id=company_id,
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
                company_id=company_id,
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
                company_id=company_id,
            )
            if variant_id:
                variant = await get_variant(db, tenant_id, variant_id)
                variant.stock_qty = money_json(variant.stock_qty or 0) + stock_qty


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
        qty = money_json(stock.quantity)
        reorder = money_json(stock.reorder_level)
        reorder_qty = money_json(stock.reorder_qty)
        items.append(
            {
                "product_id": product.id,
                "sku": product.sku,
                "name": product.name,
                "quantity": qty,
                "reorder_level": reorder,
                "reorder_qty": reorder_qty,
                "below_reorder": reorder > 0 and qty <= reorder,
                "suggested_order_qty": (
                    money_json(max(reorder_qty, money_json(round(reorder - qty, 3))))
                    if reorder > 0 and qty <= reorder
                    else reorder_qty
                ),
                "warehouse_id": wh.id,
                "consolidated_stock": money_json(product.stock_qty),
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
        "total_quantity": money_json(round(sum(i["quantity"] for i in items), 3)),
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
    row.reorder_level = max(money_json(reorder_level or 0), 0)
    row.reorder_qty = max(money_json(reorder_qty or 0), 0)
    await db.flush()
    qty = money_json(row.quantity)
    reorder = money_json(row.reorder_level)
    return {
        "product_id": product.id,
        "sku": product.sku,
        "name": product.name,
        "quantity": qty,
        "reorder_level": reorder,
        "reorder_qty": money_json(row.reorder_qty),
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
        qty = money_json(stock.quantity)
        reorder = money_json(stock.reorder_level)
        items.append(
            {
                "warehouse_id": wh.id,
                "warehouse_code": wh.code,
                "warehouse_name": wh.name,
                "store_id": wh.store_id,
                "quantity": qty,
                "reorder_level": reorder,
                "reorder_qty": money_json(stock.reorder_qty),
                "below_reorder": reorder > 0 and qty <= reorder,
            }
        )
    return {
        "product_id": product.id,
        "sku": product.sku,
        "name": product.name,
        "consolidated_stock": money_json(product.stock_qty),
        "reorder_level": money_json(product.reorder_level or 0),
        "count": len(items),
        "items": items,
        "total_quantity": money_json(round(sum(i["quantity"] for i in items), 3)),
    }
