"""Product variants and batch/expiry inventory helpers."""

from __future__ import annotations

import re
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.inventory import apply_stock_change

_SKU_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")


def normalize_sku(value: str | None) -> str | None:
    sku = (value or "").strip().upper()
    if not sku:
        return None
    if not _SKU_RE.fullmatch(sku):
        raise HTTPException(
            status_code=400,
            detail="SKU must be 1–100 chars: letters, digits, . _ - (start alphanumeric)",
        )
    return sku


async def sku_in_use(
    db: AsyncSession,
    tenant_id: str,
    sku: str,
    *,
    exclude_product_id: str | None = None,
    exclude_variant_id: str | None = None,
) -> bool:
    pq = select(m.Product.id).where(m.Product.tenant_id == tenant_id, m.Product.sku == sku)
    if exclude_product_id:
        pq = pq.where(m.Product.id != exclude_product_id)
    if (await db.execute(pq)).scalar_one_or_none():
        return True
    vq = select(m.ProductVariant.id).where(
        m.ProductVariant.tenant_id == tenant_id, m.ProductVariant.sku == sku
    )
    if exclude_variant_id:
        vq = vq.where(m.ProductVariant.id != exclude_variant_id)
    return (await db.execute(vq)).scalar_one_or_none() is not None


async def assert_sku_available(
    db: AsyncSession,
    tenant_id: str,
    sku: str,
    *,
    exclude_product_id: str | None = None,
    exclude_variant_id: str | None = None,
) -> None:
    if await sku_in_use(
        db,
        tenant_id,
        sku,
        exclude_product_id=exclude_product_id,
        exclude_variant_id=exclude_variant_id,
    ):
        raise HTTPException(status_code=409, detail="SKU already in use")


async def allocate_sku(db: AsyncSession, tenant_id: str, *, prefix: str = "SKU") -> str:
    """Allocate a unique tenant SKU: PREFIX-YYYY-NNNN."""
    year = datetime.utcnow().year
    head = f"{prefix}-{year}-"
    # Count existing catalog rows as a starting sequence hint
    product_count = (
        await db.execute(select(func.count()).select_from(m.Product).where(m.Product.tenant_id == tenant_id))
    ).scalar_one()
    variant_count = (
        await db.execute(
            select(func.count()).select_from(m.ProductVariant).where(m.ProductVariant.tenant_id == tenant_id)
        )
    ).scalar_one()
    start = int(product_count or 0) + int(variant_count or 0) + 1
    for n in range(start, start + 10_000):
        candidate = f"{head}{n:04d}"
        if not await sku_in_use(db, tenant_id, candidate):
            return candidate
    raise HTTPException(status_code=500, detail="Unable to allocate SKU")


def serialize_variant(v: m.ProductVariant) -> dict:
    return {
        "id": v.id,
        "product_id": v.product_id,
        "name": v.name,
        "sku": v.sku,
        "barcode": v.barcode,
        "size": v.size,
        "color": v.color,
        "flavor": v.flavor,
        "dosage": getattr(v, "dosage", None),
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
    customer_id: str | None = None,
) -> tuple[m.Product, m.ProductVariant | None, float]:
    """Validate product/variant and resolve unit price (variant price wins when set).

    When ``unit_price`` is omitted, list/variant price is used. If ``customer_id``
    is set and that customer belongs to an active group, the group's discount
    percent is applied (BR-7.1). Explicit ``unit_price`` is treated as an override.
    """
    product = await get_product(db, tenant_id, item["product_id"])
    if not product.is_active:
        raise HTTPException(status_code=400, detail="Product is inactive")
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
        if customer_id:
            from app.customer_groups import apply_discount, customer_group_discount

            pct, _group = await customer_group_discount(db, tenant_id, customer_id)
            if pct:
                unit_price = apply_discount(unit_price, pct)
    return product, variant, unit_price


async def list_variants(
    db: AsyncSession,
    tenant_id: str,
    product_id: str,
    *,
    is_active: bool | None = None,
) -> list[m.ProductVariant]:
    await get_product(db, tenant_id, product_id)
    stmt = (
        select(m.ProductVariant)
        .where(
            m.ProductVariant.tenant_id == tenant_id,
            m.ProductVariant.product_id == product_id,
        )
        .order_by(m.ProductVariant.name)
    )
    if is_active is not None:
        stmt = stmt.where(m.ProductVariant.is_active.is_(bool(is_active)))
    return (await db.execute(stmt)).scalars().all()


def _clean_attr(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


async def create_variant(
    db: AsyncSession,
    *,
    tenant_id: str,
    product_id: str,
    name: str,
    sku: str | None = None,
    barcode: str | None = None,
    size: str | None = None,
    color: str | None = None,
    flavor: str | None = None,
    dosage: str | None = None,
    cost_price: float | None = None,
    selling_price: float | None = None,
) -> m.ProductVariant:
    product = await get_product(db, tenant_id, product_id)
    name = (name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Variant name is required")
    sku_norm = normalize_sku(sku)
    if not sku_norm:
        sku_norm = await allocate_sku(db, tenant_id, prefix="SKU")
    else:
        await assert_sku_available(db, tenant_id, sku_norm)
    sku = sku_norm

    from app import barcodes as barcodes_svc

    barcode_norm = barcodes_svc.normalize_barcode(barcode)
    if barcode_norm:
        await barcodes_svc.assert_barcode_unique(
            db, tenant_id=tenant_id, barcode_value=barcode_norm
        )

    variant = m.ProductVariant(
        tenant_id=tenant_id,
        product_id=product.id,
        name=name,
        sku=sku,
        barcode=barcode_norm,
        size=_clean_attr(size),
        color=_clean_attr(color),
        flavor=_clean_attr(flavor),
        dosage=_clean_attr(dosage),
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
    dosage: str | None = None,
    cost_price: float | None = None,
    selling_price: float | None = None,
    is_active: bool | None = None,
    clear_barcode: bool = False,
    clear_size: bool = False,
    clear_color: bool = False,
    clear_flavor: bool = False,
    clear_dosage: bool = False,
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
        sku_norm = normalize_sku(sku)
        if not sku_norm:
            raise HTTPException(status_code=400, detail="Variant sku is required")
        await assert_sku_available(
            db, tenant_id, sku_norm, exclude_variant_id=variant.id
        )
        variant.sku = sku_norm
    if clear_barcode:
        variant.barcode = None
    elif barcode is not None:
        from app import barcodes as barcodes_svc

        barcode_norm = barcodes_svc.normalize_barcode(barcode)
        if barcode_norm:
            await barcodes_svc.assert_barcode_unique(
                db,
                tenant_id=tenant_id,
                barcode_value=barcode_norm,
                exclude_variant_id=variant.id,
            )
        variant.barcode = barcode_norm
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
    if clear_dosage:
        variant.dosage = None
    elif dosage is not None:
        variant.dosage = dosage.strip() or None
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
) -> list[m.ProductBatch]:
    within_days = max(0, min(int(within_days), 3650))
    horizon = datetime.utcnow() + timedelta(days=within_days)
    return (
        await db.execute(
            select(m.ProductBatch)
            .where(
                m.ProductBatch.tenant_id == tenant_id,
                m.ProductBatch.quantity > 0,
                m.ProductBatch.expiry_date.is_not(None),
                m.ProductBatch.expiry_date <= horizon,
            )
            .order_by(m.ProductBatch.expiry_date.asc())
        )
    ).scalars().all()


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
    unit_id: str | None = None,
    notes: str | None = None,
    warehouse_id: str | None = None,
    variant_id: str | None = None,
    batch_number: str | None = None,
    manufacturing_date: datetime | None = None,
    expiry_date: datetime | None = None,
    movement_type: str = "stock_in",
    reference_type: str | None = None,
    reference_id: str | None = None,
) -> dict:
    from app.uom import to_stock_qty

    entered_qty = float(quantity)
    if entered_qty <= 0:
        raise HTTPException(status_code=400, detail="quantity must be positive")
    product = await get_product(db, tenant_id, product_id)
    quantity_base, entered_unit_id, entered_qty = await to_stock_qty(
        db,
        tenant_id=tenant_id,
        quantity=entered_qty,
        from_unit_id=unit_id,
        product=product,
    )
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
        batch.quantity = float(batch.quantity or 0) + quantity_base
        batch.updated_at = datetime.utcnow()

    note_text = notes
    if entered_unit_id and product.unit_id and entered_unit_id != product.unit_id:
        suffix = f"entered {entered_qty:g} (unit {entered_unit_id[:8]}) → {quantity_base:g} stock"
        note_text = f"{notes}; {suffix}" if notes else suffix

    product = await apply_stock_change(
        db,
        tenant_id=tenant_id,
        product_id=product.id,
        quantity_delta=quantity_base,
        movement_type=movement_type,
        user_id=user_id,
        notes=note_text,
        warehouse_id=warehouse_id,
        variant_id=variant.id if variant else None,
        batch_id=batch.id if batch else None,
        reference_type=reference_type,
        reference_id=reference_id,
    )
    if variant:
        variant.stock_qty = float(variant.stock_qty or 0) + quantity_base

    return {
        "product_id": product.id,
        "stock_qty": float(product.stock_qty),
        "quantity_entered": entered_qty,
        "quantity_base": quantity_base,
        "unit_id": entered_unit_id,
        "stock_unit_id": product.unit_id,
        "cost_price": float(product.cost_price or 0),
        "variant": serialize_variant(variant) if variant else None,
        "batch": serialize_batch(batch) if batch else None,
    }


async def stock_out_with_batch(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    product_id: str,
    quantity: float,
    unit_id: str | None = None,
    notes: str | None = None,
    warehouse_id: str | None = None,
    variant_id: str | None = None,
    batch_id: str | None = None,
    reference_type: str | None = None,
    reference_id: str | None = None,
) -> dict:
    from app.uom import to_stock_qty

    entered_qty = float(quantity)
    if entered_qty <= 0:
        raise HTTPException(status_code=400, detail="quantity must be positive")
    product = await get_product(db, tenant_id, product_id)
    quantity, entered_unit_id, entered_qty = await to_stock_qty(
        db,
        tenant_id=tenant_id,
        quantity=entered_qty,
        from_unit_id=unit_id,
        product=product,
    )
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

    note_text = notes
    if entered_unit_id and product.unit_id and entered_unit_id != product.unit_id:
        suffix = f"entered {entered_qty:g} (unit {entered_unit_id[:8]}) → {quantity:g} stock"
        note_text = f"{notes}; {suffix}" if notes else suffix

    product = await apply_stock_change(
        db,
        tenant_id=tenant_id,
        product_id=product.id,
        quantity_delta=-quantity,
        movement_type="stock_out",
        user_id=user_id,
        notes=note_text,
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
        "quantity_entered": entered_qty,
        "quantity_base": quantity,
        "unit_id": entered_unit_id,
        "stock_unit_id": product.unit_id,
        "variant": serialize_variant(variant) if variant else None,
        "batches_consumed": consumed,
        "warehouse_id": warehouse_id,
        "reference_type": reference_type,
        "reference_id": reference_id,
    }
