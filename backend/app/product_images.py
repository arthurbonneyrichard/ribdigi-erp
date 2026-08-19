"""Product image gallery — tenant-scoped media keys linked to products."""

from __future__ import annotations

import csv
import io
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app import storage as storage_svc

MAX_PRODUCT_IMAGES = 5

PRODUCT_IMAGE_EXPORT_COLUMNS = [
    "id",
    "product_id",
    "storage_key",
    "content_type",
    "sort_order",
    "is_primary",
    "original_filename",
    "created_at",
]


def _cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds")
    return str(value)


def serialize_image(row: m.ProductImage) -> dict:
    return {
        "id": row.id,
        "company_id": getattr(row, "company_id", None),
        "product_id": row.product_id,
        "storage_key": row.storage_key,
        "content_type": row.content_type,
        "sort_order": int(row.sort_order or 0),
        "is_primary": bool(row.is_primary),
        "original_filename": row.original_filename,
        "created_at": row.created_at,
    }


async def _get_product(
    db: AsyncSession,
    tenant_id: str,
    product_id: str,
    *,
    company_id: str | None = None,
) -> m.Product:
    stmt = select(m.Product).where(m.Product.id == product_id, m.Product.tenant_id == tenant_id)
    if company_id:
        stmt = stmt.where(m.Product.company_id == company_id)
    product = (await db.execute(stmt)).scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


async def list_product_images(
    db: AsyncSession,
    *,
    tenant_id: str,
    product_id: str,
    company_id: str | None = None,
) -> list[m.ProductImage]:
    await _get_product(db, tenant_id, product_id, company_id=company_id)
    result = await db.execute(
        select(m.ProductImage)
        .where(
            m.ProductImage.tenant_id == tenant_id,
            m.ProductImage.product_id == product_id,
        )
        .order_by(m.ProductImage.sort_order.asc(), m.ProductImage.created_at.asc())
    )
    return list(result.scalars().all())


async def add_product_image(
    db: AsyncSession,
    *,
    tenant_id: str,
    product_id: str,
    storage_key: str,
    content_type: str | None = None,
    original_filename: str | None = None,
    is_primary: bool = False,
    company_id: str | None = None,
) -> m.ProductImage:
    product = await _get_product(db, tenant_id, product_id, company_id=company_id)
    storage_key = storage_svc.validate_key(storage_key, tenant_id=tenant_id)

    images = await list_product_images(
        db, tenant_id=tenant_id, product_id=product_id, company_id=company_id
    )
    if len(images) >= MAX_PRODUCT_IMAGES:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum of {MAX_PRODUCT_IMAGES} images per product",
        )

    existing = next((img for img in images if img.storage_key == storage_key), None)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Image already linked to product")

    make_primary = is_primary or len(images) == 0
    if make_primary:
        for img in images:
            img.is_primary = False

    row = m.ProductImage(
        tenant_id=tenant_id,
        company_id=company_id or getattr(product, "company_id", None),
        product_id=product_id,
        storage_key=storage_key,
        content_type=content_type,
        sort_order=len(images),
        is_primary=make_primary,
        original_filename=original_filename,
        created_at=datetime.utcnow(),
    )
    db.add(row)
    if make_primary:
        product.image_url = storage_key
    await db.flush()
    return row


async def set_primary_product_image(
    db: AsyncSession,
    *,
    tenant_id: str,
    product_id: str,
    image_id: str,
    company_id: str | None = None,
) -> m.ProductImage:
    product = await _get_product(db, tenant_id, product_id, company_id=company_id)
    target = await db.get(m.ProductImage, image_id)
    if target is None or target.tenant_id != tenant_id or target.product_id != product_id:
        raise HTTPException(status_code=404, detail="Product image not found")
    images = await list_product_images(
        db, tenant_id=tenant_id, product_id=product_id, company_id=company_id
    )
    for img in images:
        img.is_primary = img.id == image_id
    product.image_url = target.storage_key
    await db.flush()
    return target


async def delete_product_image(
    db: AsyncSession,
    *,
    tenant_id: str,
    product_id: str,
    image_id: str,
    delete_storage: bool = True,
    company_id: str | None = None,
) -> None:
    product = await _get_product(db, tenant_id, product_id, company_id=company_id)
    target = await db.get(m.ProductImage, image_id)
    if target is None or target.tenant_id != tenant_id or target.product_id != product_id:
        raise HTTPException(status_code=404, detail="Product image not found")
    was_primary = target.is_primary
    storage_key = target.storage_key
    await db.delete(target)
    await db.flush()
    remaining = await list_product_images(
        db, tenant_id=tenant_id, product_id=product_id, company_id=company_id
    )
    if was_primary:
        if remaining:
            remaining[0].is_primary = True
            product.image_url = remaining[0].storage_key
        else:
            product.image_url = None
    for idx, img in enumerate(remaining):
        img.sort_order = idx
    if delete_storage:
        storage_svc.delete_key(storage_key, tenant_id=tenant_id)
    await db.flush()


async def delete_primary_product_image(
    db: AsyncSession,
    *,
    tenant_id: str,
    product_id: str,
    company_id: str | None = None,
) -> m.Product:
    """Legacy helper for DELETE /products/{id}/image."""
    product = await _get_product(db, tenant_id, product_id, company_id=company_id)
    if not product.image_url:
        raise HTTPException(status_code=404, detail="Product image not found")
    images = await list_product_images(
        db, tenant_id=tenant_id, product_id=product_id, company_id=company_id
    )
    primary = next((img for img in images if img.is_primary), None)
    if primary is None and images:
        primary = images[0]
    if primary is not None:
        await delete_product_image(
            db,
            tenant_id=tenant_id,
            product_id=product_id,
            image_id=primary.id,
            delete_storage=True,
            company_id=company_id,
        )
    else:
        storage_svc.delete_key(product.image_url, tenant_id=tenant_id)
        product.image_url = None
        await db.flush()
    await db.refresh(product)
    return product


async def export_product_images_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    product_id: str,
    company_id: str | None = None,
) -> str:
    """Stage 156 G1 — per-product image metadata CSV (no binary payloads)."""
    rows = await list_product_images(
        db, tenant_id=tenant_id, product_id=product_id, company_id=company_id
    )
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=PRODUCT_IMAGE_EXPORT_COLUMNS)
    writer.writeheader()
    for row in rows:
        data = serialize_image(row)
        writer.writerow({k: _cell(data.get(k)) for k in PRODUCT_IMAGE_EXPORT_COLUMNS})
    return buf.getvalue()
