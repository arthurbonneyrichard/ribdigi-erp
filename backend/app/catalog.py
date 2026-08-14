"""Product variants and batch/expiry inventory helpers."""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.inventory import apply_stock_change


def serialize_variant(v: m.ProductVariant) -> dict:
    return {
        "id": v.id,
        "company_id": getattr(v, "company_id", None),
        "product_id": v.product_id,
        "name": v.name,
        "sku": v.sku,
        "barcode": v.barcode,
        "size": v.size,
        "color": v.color,
        "flavor": v.flavor,
        "cost_price": float(v.cost_price or 0),
        "selling_price": float(v.selling_price or 0),
        "stock_qty": float(v.stock_qty or 0),
        "is_active": bool(v.is_active),
        "created_at": v.created_at,
    }


def serialize_batch(b: m.ProductBatch) -> dict:
    return {
        "id": b.id,
        "product_id": b.product_id,
        "variant_id": b.variant_id,
        "warehouse_id": b.warehouse_id,
        "batch_number": b.batch_number,
        "manufacturing_date": b.manufacturing_date,
        "expiry_date": b.expiry_date,
        "quantity": float(b.quantity or 0),
        "created_at": b.created_at,
        "updated_at": b.updated_at,
    }


async def get_product(db: AsyncSession, tenant_id: str, product_id: str) -> m.Product:
    product = (
        await db.execute(
            select(m.Product).where(m.Product.id == product_id, m.Product.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


async def get_variant(db: AsyncSession, tenant_id: str, variant_id: str) -> m.ProductVariant:
    row = (
        await db.execute(
            select(m.ProductVariant).where(
                m.ProductVariant.id == variant_id,
                m.ProductVariant.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Variant not found")
    return row


async def resolve_sale_line(
    db: AsyncSession,
    tenant_id: str,
    item: dict,
    *,
    group_discount_percent: float = 0,
) -> tuple[m.Product, m.ProductVariant | None, float]:
    """Validate product/variant and resolve unit price (variant price wins when set).

    When unit_price is omitted, apply customer-group discount to catalog price.
    Explicit unit_price always wins (manual override).
    """
    product = await get_product(db, tenant_id, item["product_id"])
    variant = None
    variant_id = item.get("variant_id")
    if variant_id:
        variant = await get_variant(db, tenant_id, variant_id)
        if variant.product_id != product.id:
            raise HTTPException(status_code=400, detail="Variant does not belong to product")
        if not variant.is_active:
            raise HTTPException(status_code=409, detail="Variant is inactive")
    if item.get("unit_price") is not None:
        unit_price = float(item["unit_price"])
    else:
        if variant is not None:
            unit_price = float(variant.selling_price or 0)
        else:
            unit_price = float(product.selling_price or 0)
        pct = max(0.0, min(100.0, float(group_discount_percent or 0)))
        if pct > 0:
            unit_price = round(unit_price * (1.0 - pct / 100.0), 4)
    return product, variant, unit_price


async def list_variants(
    db: AsyncSession,
    tenant_id: str,
    product_id: str,
    *,
    active_only: bool = False,
    is_active: bool | None = None,
) -> list[m.ProductVariant]:
    """Stage 124 V1 — is_active / active_only for honest inactive-only variant lists."""
    await get_product(db, tenant_id, product_id)
    stmt = select(m.ProductVariant).where(
        m.ProductVariant.tenant_id == tenant_id,
        m.ProductVariant.product_id == product_id,
    )
    if is_active is not None:
        stmt = stmt.where(m.ProductVariant.is_active.is_(bool(is_active)))
    elif active_only:
        stmt = stmt.where(m.ProductVariant.is_active.is_(True))
    return list((await db.execute(stmt.order_by(m.ProductVariant.name))).scalars().all())


async def create_variant(
    db: AsyncSession,
    *,
    tenant_id: str,
    product_id: str,
    name: str,
    sku: str,
    barcode: str | None = None,
    size: str | None = None,
    color: str | None = None,
    flavor: str | None = None,
    cost_price: float | None = None,
    selling_price: float | None = None,
) -> m.ProductVariant:
    product = await get_product(db, tenant_id, product_id)
    sku = (sku or "").strip()
    name = (name or "").strip()
    if not sku or not name:
        raise HTTPException(status_code=400, detail="Variant name and sku are required")
    company_id = getattr(product, "company_id", None)
    variant_stmt = select(m.ProductVariant).where(
        m.ProductVariant.tenant_id == tenant_id,
        m.ProductVariant.sku == sku,
    )
    product_stmt = select(m.Product).where(m.Product.tenant_id == tenant_id, m.Product.sku == sku)
    if company_id:
        variant_stmt = variant_stmt.where(m.ProductVariant.company_id == company_id)
        product_stmt = product_stmt.where(m.Product.company_id == company_id)
    exists = (await db.execute(variant_stmt)).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="Variant SKU already exists")
    # Also block collision with parent product SKUs
    prod_sku = (await db.execute(product_stmt)).scalar_one_or_none()
    if prod_sku:
        raise HTTPException(status_code=409, detail="SKU already used by a product")

    variant = m.ProductVariant(
        tenant_id=tenant_id,
        company_id=company_id,
        product_id=product.id,
        name=name,
        sku=sku,
        barcode=barcode,
        size=size,
        color=color,
        flavor=flavor,
        cost_price=float(cost_price if cost_price is not None else product.cost_price or 0),
        selling_price=float(
            selling_price if selling_price is not None else product.selling_price or 0
        ),
        stock_qty=0,
        is_active=True,
    )
    db.add(variant)
    await db.flush()
    return variant


async def update_variant(
    db: AsyncSession,
    *,
    tenant_id: str,
    product_id: str,
    variant_id: str,
    name: str | None = None,
    sku: str | None = None,
    barcode: str | None = None,
    size: str | None = None,
    color: str | None = None,
    flavor: str | None = None,
    cost_price: float | None = None,
    selling_price: float | None = None,
    is_active: bool | None = None,
    clear_barcode: bool = False,
    clear_size: bool = False,
    clear_color: bool = False,
    clear_flavor: bool = False,
) -> m.ProductVariant:
    await get_product(db, tenant_id, product_id)
    variant = await get_variant(db, tenant_id, variant_id)
    if variant.product_id != product_id:
        raise HTTPException(status_code=404, detail="Variant not found")

    if name is not None:
        name = name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Variant name is required")
        variant.name = name
    if sku is not None:
        sku = sku.strip()
        if not sku:
            raise HTTPException(status_code=400, detail="Variant sku is required")
        company_id = getattr(variant, "company_id", None)
        clash_stmt = select(m.ProductVariant).where(
            m.ProductVariant.tenant_id == tenant_id,
            m.ProductVariant.sku == sku,
            m.ProductVariant.id != variant.id,
        )
        prod_stmt = select(m.Product).where(m.Product.tenant_id == tenant_id, m.Product.sku == sku)
        if company_id:
            clash_stmt = clash_stmt.where(m.ProductVariant.company_id == company_id)
            prod_stmt = prod_stmt.where(m.Product.company_id == company_id)
        clash = (await db.execute(clash_stmt)).scalar_one_or_none()
        if clash:
            raise HTTPException(status_code=409, detail="Variant SKU already exists")
        prod_sku = (await db.execute(prod_stmt)).scalar_one_or_none()
        if prod_sku:
            raise HTTPException(status_code=409, detail="SKU already used by a product")
        variant.sku = sku
    if clear_barcode:
        variant.barcode = None
    elif barcode is not None:
        variant.barcode = barcode.strip() or None
    if clear_size:
        variant.size = None
    elif size is not None:
        variant.size = size.strip() or None
    if clear_color:
        variant.color = None
    elif color is not None:
        variant.color = color.strip() or None
    if clear_flavor:
        variant.flavor = None
    elif flavor is not None:
        variant.flavor = flavor.strip() or None
    if cost_price is not None:
        variant.cost_price = float(cost_price)
    if selling_price is not None:
        variant.selling_price = float(selling_price)
    if is_active is not None:
        variant.is_active = bool(is_active)
    await db.flush()
    return variant


async def deactivate_variant(
    db: AsyncSession, *, tenant_id: str, product_id: str, variant_id: str
) -> m.ProductVariant:
    return await update_variant(
        db,
        tenant_id=tenant_id,
        product_id=product_id,
        variant_id=variant_id,
        is_active=False,
    )


async def list_batches(
    db: AsyncSession,
    tenant_id: str,
    *,
    product_id: str | None = None,
    include_empty: bool = False,
) -> list[m.ProductBatch]:
    stmt = select(m.ProductBatch).where(m.ProductBatch.tenant_id == tenant_id)
    if product_id:
        stmt = stmt.where(m.ProductBatch.product_id == product_id)
    if not include_empty:
        stmt = stmt.where(m.ProductBatch.quantity > 0)
    stmt = stmt.order_by(
        m.ProductBatch.expiry_date.asc().nulls_last(),
        m.ProductBatch.created_at.asc(),
    )
    return (await db.execute(stmt)).scalars().all()


async def list_expiring_batches(
    db: AsyncSession,
    tenant_id: str,
    *,
    within_days: int = 30,
    company_id: str | None = None,
) -> list[m.ProductBatch]:
    within_days = max(0, min(int(within_days), 3650))
    horizon = datetime.utcnow() + timedelta(days=within_days)
    stmt = (
        select(m.ProductBatch)
        .where(
            m.ProductBatch.tenant_id == tenant_id,
            m.ProductBatch.quantity > 0,
            m.ProductBatch.expiry_date.is_not(None),
            m.ProductBatch.expiry_date <= horizon,
        )
        .order_by(m.ProductBatch.expiry_date.asc())
    )
    if company_id:
        stmt = stmt.where(m.ProductBatch.company_id == company_id)
    return list((await db.execute(stmt)).scalars().all())


async def _find_batch(
    db: AsyncSession,
    *,
    tenant_id: str,
    product_id: str,
    batch_number: str,
    variant_id: str | None,
) -> m.ProductBatch | None:
    stmt = select(m.ProductBatch).where(
        m.ProductBatch.tenant_id == tenant_id,
        m.ProductBatch.product_id == product_id,
        m.ProductBatch.batch_number == batch_number,
    )
    if variant_id:
        stmt = stmt.where(m.ProductBatch.variant_id == variant_id)
    else:
        stmt = stmt.where(m.ProductBatch.variant_id.is_(None))
    return (await db.execute(stmt)).scalar_one_or_none()


async def stock_in_with_batch(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    product_id: str,
    quantity: float,
    notes: str | None = None,
    warehouse_id: str | None = None,
    variant_id: str | None = None,
    batch_number: str | None = None,
    manufacturing_date: datetime | None = None,
    expiry_date: datetime | None = None,
    reference_type: str | None = None,
    reference_id: str | None = None,
    movement_type: str = "stock_in",
) -> dict:
    quantity = float(quantity)
    if quantity <= 0:
        raise HTTPException(status_code=400, detail="quantity must be positive")
    if movement_type not in {"stock_in", "opening_stock"}:
        raise HTTPException(status_code=400, detail="Invalid inbound movement type")
    product = await get_product(db, tenant_id, product_id)
    variant = None
    if variant_id:
        variant = await get_variant(db, tenant_id, variant_id)
        if variant.product_id != product.id:
            raise HTTPException(status_code=400, detail="Variant does not belong to product")

    if product.tracks_batches and not (batch_number or "").strip():
        raise HTTPException(status_code=400, detail="batch_number required for batch-tracked products")

    batch = None
    if batch_number:
        batch_number = batch_number.strip()
        batch = await _find_batch(
            db,
            tenant_id=tenant_id,
            product_id=product.id,
            batch_number=batch_number,
            variant_id=variant.id if variant else None,
        )
        if not batch:
            batch = m.ProductBatch(
                tenant_id=tenant_id,
                product_id=product.id,
                variant_id=variant.id if variant else None,
                warehouse_id=warehouse_id,
                batch_number=batch_number,
                manufacturing_date=manufacturing_date,
                expiry_date=expiry_date,
                quantity=0,
            )
            db.add(batch)
            await db.flush()
        else:
            if manufacturing_date:
                batch.manufacturing_date = manufacturing_date
            if expiry_date:
                batch.expiry_date = expiry_date
            if warehouse_id:
                batch.warehouse_id = warehouse_id
        batch.quantity = float(batch.quantity or 0) + quantity
        batch.updated_at = datetime.utcnow()

    product = await apply_stock_change(
        db,
        tenant_id=tenant_id,
        product_id=product.id,
        quantity_delta=quantity,
        movement_type=movement_type,
        user_id=user_id,
        notes=notes,
        warehouse_id=warehouse_id,
        variant_id=variant.id if variant else None,
        batch_id=batch.id if batch else None,
        reference_type=reference_type,
        reference_id=reference_id,
    )
    if variant:
        variant.stock_qty = float(variant.stock_qty or 0) + quantity

    return {
        "product_id": product.id,
        "stock_qty": float(product.stock_qty),
        "batch_id": batch.id if batch else None,
        "variant": serialize_variant(variant) if variant else None,
        "batch": serialize_batch(batch) if batch else None,
        "movement_type": movement_type,
        "quantity_delta": quantity,
    }


async def record_opening_stock(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    product_id: str,
    quantity: float,
    mode: str = "add",
    notes: str | None = None,
    warehouse_id: str | None = None,
    variant_id: str | None = None,
    batch_number: str | None = None,
    manufacturing_date: datetime | None = None,
    expiry_date: datetime | None = None,
    fiscal_period: str | None = None,
) -> dict:
    """Initialize stock for go-live / fiscal year start (BR-5.2 Opening Stock)."""
    from app.inventory import get_or_create_warehouse_stock, get_warehouse

    mode_norm = (mode or "add").strip().lower()
    if mode_norm not in {"add", "set"}:
        raise HTTPException(status_code=400, detail="mode must be add or set")

    quantity = float(quantity)
    if quantity < 0:
        raise HTTPException(status_code=400, detail="quantity cannot be negative")

    product = await get_product(db, tenant_id, product_id)
    if warehouse_id:
        await get_warehouse(db, tenant_id, warehouse_id)
        wh_row = await get_or_create_warehouse_stock(
            db, tenant_id=tenant_id, warehouse_id=warehouse_id, product_id=product.id
        )
        current = float(wh_row.quantity or 0)
    else:
        current = float(product.stock_qty or 0)

    if mode_norm == "add":
        if quantity <= 0:
            raise HTTPException(status_code=400, detail="quantity must be positive for add mode")
        delta = quantity
    else:
        delta = quantity - current
        if abs(delta) < 1e-9:
            raise HTTPException(status_code=400, detail="set mode would not change stock")
        if delta < 0:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "OPENING_STOCK_CANNOT_REDUCE",
                    "message": "Opening stock cannot reduce on-hand; use stock adjustment or stock count",
                    "current_qty": current,
                    "target_qty": quantity,
                },
            )

    note_parts = [notes.strip()] if notes and notes.strip() else []
    if fiscal_period and fiscal_period.strip():
        note_parts.append(f"fiscal_period={fiscal_period.strip()}")
    if mode_norm == "set":
        note_parts.append(f"opening set target={quantity:g} (was {current:g})")
    combined_notes = "; ".join(note_parts) if note_parts else "Opening stock entry"

    result = await stock_in_with_batch(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        product_id=product.id,
        quantity=delta,
        notes=combined_notes,
        warehouse_id=warehouse_id,
        variant_id=variant_id,
        batch_number=batch_number,
        manufacturing_date=manufacturing_date,
        expiry_date=expiry_date,
        reference_type="opening_stock",
        reference_id=fiscal_period.strip() if fiscal_period and fiscal_period.strip() else None,
        movement_type="opening_stock",
    )
    result["mode"] = mode_norm
    result["current_qty_before"] = current
    result["target_qty"] = quantity if mode_norm == "set" else current + delta
    result["fiscal_period"] = fiscal_period.strip() if fiscal_period and fiscal_period.strip() else None
    return result


async def record_opening_stock_batch(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    items: list[dict],
    fiscal_period: str | None = None,
) -> dict:
    if not items:
        raise HTTPException(status_code=400, detail="items required")
    if len(items) > 500:
        raise HTTPException(status_code=400, detail="Maximum 500 opening stock lines per request")
    results: list[dict] = []
    for idx, item in enumerate(items, start=1):
        try:
            results.append(
                await record_opening_stock(
                    db,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    product_id=item["product_id"],
                    quantity=float(item["quantity"]),
                    mode=item.get("mode") or "add",
                    notes=item.get("notes"),
                    warehouse_id=item.get("warehouse_id"),
                    variant_id=item.get("variant_id"),
                    batch_number=item.get("batch_number"),
                    manufacturing_date=item.get("manufacturing_date"),
                    expiry_date=item.get("expiry_date"),
                    fiscal_period=item.get("fiscal_period") or fiscal_period,
                )
            )
        except HTTPException as exc:
            detail = exc.detail
            raise HTTPException(
                status_code=exc.status_code,
                detail={"line": idx, "product_id": item.get("product_id"), "error": detail},
            ) from exc
    return {"count": len(results), "items": results}


async def stock_out_with_batch(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    product_id: str,
    quantity: float,
    notes: str | None = None,
    warehouse_id: str | None = None,
    variant_id: str | None = None,
    batch_id: str | None = None,
    reference_type: str | None = None,
    reference_id: str | None = None,
) -> dict:
    quantity = float(quantity)
    if quantity <= 0:
        raise HTTPException(status_code=400, detail="quantity must be positive")
    product = await get_product(db, tenant_id, product_id)
    variant = None
    if variant_id:
        variant = await get_variant(db, tenant_id, variant_id)
        if variant.product_id != product.id:
            raise HTTPException(status_code=400, detail="Variant does not belong to product")
        if float(variant.stock_qty or 0) + 1e-9 < quantity:
            raise HTTPException(status_code=409, detail="Insufficient variant stock")

    remaining = quantity
    consumed: list[dict] = []

    if batch_id:
        batch = (
            await db.execute(
                select(m.ProductBatch)
                .where(
                    m.ProductBatch.id == batch_id,
                    m.ProductBatch.tenant_id == tenant_id,
                    m.ProductBatch.product_id == product.id,
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if not batch:
            raise HTTPException(status_code=404, detail="Batch not found")
        avail = float(batch.quantity or 0)
        if avail + 1e-9 < quantity:
            raise HTTPException(status_code=409, detail="Insufficient batch quantity")
        batch.quantity = avail - quantity
        batch.updated_at = datetime.utcnow()
        consumed.append({"batch_id": batch.id, "quantity": quantity})
        remaining = 0
        primary_batch_id = batch.id
    else:
        # FEFO across open batches (optionally scoped to variant)
        stmt = (
            select(m.ProductBatch)
            .where(
                m.ProductBatch.tenant_id == tenant_id,
                m.ProductBatch.product_id == product.id,
                m.ProductBatch.quantity > 0,
            )
            .order_by(
                m.ProductBatch.expiry_date.asc().nulls_last(),
                m.ProductBatch.created_at.asc(),
            )
            .with_for_update()
        )
        if variant:
            stmt = stmt.where(m.ProductBatch.variant_id == variant.id)
        if warehouse_id:
            tenant = (
                await db.execute(select(m.Tenant).where(m.Tenant.id == tenant_id))
            ).scalar_one_or_none()
            strict = bool(tenant and getattr(tenant, "fefo_strict_warehouse", False))
            if strict:
                stmt = stmt.where(m.ProductBatch.warehouse_id == warehouse_id)
            else:
                stmt = stmt.where(
                    (m.ProductBatch.warehouse_id == warehouse_id)
                    | (m.ProductBatch.warehouse_id.is_(None))
                )
        batches = (await db.execute(stmt)).scalars().all()
        primary_batch_id = None
        if batches:
            for batch in batches:
                if remaining <= 1e-9:
                    break
                take = min(float(batch.quantity or 0), remaining)
                if take <= 0:
                    continue
                batch.quantity = float(batch.quantity or 0) - take
                batch.updated_at = datetime.utcnow()
                consumed.append({"batch_id": batch.id, "quantity": take})
                if primary_batch_id is None:
                    primary_batch_id = batch.id
                remaining = round(remaining - take, 6)
            if remaining > 1e-9 and (product.tracks_batches or consumed):
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "INSUFFICIENT_BATCH_STOCK",
                        "message": "Not enough batch quantity (FEFO)",
                        "shortfall": remaining,
                    },
                )

    product = await apply_stock_change(
        db,
        tenant_id=tenant_id,
        product_id=product.id,
        quantity_delta=-quantity,
        movement_type="stock_out",
        user_id=user_id,
        notes=notes,
        warehouse_id=warehouse_id,
        variant_id=variant.id if variant else None,
        batch_id=primary_batch_id,
        reference_type=reference_type,
        reference_id=reference_id,
    )
    if variant:
        variant.stock_qty = max(float(variant.stock_qty or 0) - quantity, 0)

    return {
        "product_id": product.id,
        "stock_qty": float(product.stock_qty),
        "variant": serialize_variant(variant) if variant else None,
        "batches_consumed": consumed,
    }
