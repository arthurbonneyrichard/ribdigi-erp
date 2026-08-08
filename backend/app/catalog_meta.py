"""Product catalog: categories (parent), brands, units of measure, product image helpers."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m

DEFAULT_UNITS = (
    ("PCS", "Pieces"),
    ("KG", "Kilogram"),
    ("G", "Gram"),
    ("L", "Litre"),
    ("BOX", "Box"),
)

DEFAULT_CATEGORIES = (
    ("GEN", "General", None),
    ("BEV", "Beverages", None),
    ("FOOD", "Food", None),
)


def serialize_category(row: m.ProductCategory) -> dict:
    return {
        "id": row.id,
        "parent_id": row.parent_id,
        "code": row.code,
        "name": row.name,
        "is_active": bool(row.is_active),
        "created_at": row.created_at,
    }


def serialize_brand(row: m.Brand) -> dict:
    return {
        "id": row.id,
        "code": row.code,
        "name": row.name,
        "description": row.description,
        "is_active": bool(row.is_active),
        "created_at": row.created_at,
    }


def serialize_unit(row: m.UnitOfMeasure) -> dict:
    return {
        "id": row.id,
        "code": row.code,
        "name": row.name,
        "is_active": bool(row.is_active),
        "created_at": row.created_at,
    }


def serialize_product(row: m.Product) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "sku": row.sku,
        "barcode": row.barcode,
        "category": row.category,
        "category_id": row.category_id,
        "brand_id": row.brand_id,
        "unit_id": row.unit_id,
        "image_url": row.image_url,
        "has_image": bool(row.image_url),
        "cost_price": float(row.cost_price or 0),
        "selling_price": float(row.selling_price or 0),
        "stock_qty": float(row.stock_qty or 0),
        "reorder_level": float(row.reorder_level or 0),
        "tax_rate_id": row.tax_rate_id,
        "tax_exempt": bool(row.tax_exempt),
        "tracks_batches": bool(row.tracks_batches),
        "is_active": bool(row.is_active),
    }


async def ensure_default_catalog(db: AsyncSession, tenant_id: str) -> None:
    existing_units = (
        await db.execute(select(m.UnitOfMeasure.id).where(m.UnitOfMeasure.tenant_id == tenant_id).limit(1))
    ).scalar_one_or_none()
    if not existing_units:
        for code, name in DEFAULT_UNITS:
            db.add(m.UnitOfMeasure(tenant_id=tenant_id, code=code, name=name, is_active=True))

    existing_cats = (
        await db.execute(
            select(m.ProductCategory.id).where(m.ProductCategory.tenant_id == tenant_id).limit(1)
        )
    ).scalar_one_or_none()
    if not existing_cats:
        for code, name, _parent in DEFAULT_CATEGORIES:
            db.add(
                m.ProductCategory(
                    tenant_id=tenant_id,
                    code=code,
                    name=name,
                    parent_id=None,
                    is_active=True,
                )
            )
    await db.flush()


async def list_categories(db: AsyncSession, tenant_id: str) -> list[m.ProductCategory]:
    return list(
        (
            await db.execute(
                select(m.ProductCategory)
                .where(m.ProductCategory.tenant_id == tenant_id)
                .order_by(m.ProductCategory.name)
            )
        )
        .scalars()
        .all()
    )


async def create_category(
    db: AsyncSession,
    *,
    tenant_id: str,
    code: str,
    name: str,
    parent_id: str | None = None,
) -> m.ProductCategory:
    code = code.strip().upper()
    name = name.strip()
    if not code or not name:
        raise HTTPException(status_code=400, detail="code and name are required")
    if parent_id:
        parent = await db.get(m.ProductCategory, parent_id)
        if not parent or parent.tenant_id != tenant_id:
            raise HTTPException(status_code=404, detail="Parent category not found")
    dup = (
        await db.execute(
            select(m.ProductCategory).where(
                m.ProductCategory.tenant_id == tenant_id,
                m.ProductCategory.code == code,
            )
        )
    ).scalar_one_or_none()
    if dup:
        raise HTTPException(status_code=409, detail="Category code exists")
    row = m.ProductCategory(
        tenant_id=tenant_id,
        code=code,
        name=name,
        parent_id=parent_id,
        is_active=True,
    )
    db.add(row)
    await db.flush()
    return row


async def list_brands(db: AsyncSession, tenant_id: str) -> list[m.Brand]:
    return list(
        (
            await db.execute(
                select(m.Brand).where(m.Brand.tenant_id == tenant_id).order_by(m.Brand.name)
            )
        )
        .scalars()
        .all()
    )


async def create_brand(
    db: AsyncSession,
    *,
    tenant_id: str,
    code: str,
    name: str,
    description: str | None = None,
) -> m.Brand:
    code = code.strip().upper()
    name = name.strip()
    if not code or not name:
        raise HTTPException(status_code=400, detail="code and name are required")
    dup = (
        await db.execute(
            select(m.Brand).where(m.Brand.tenant_id == tenant_id, m.Brand.code == code)
        )
    ).scalar_one_or_none()
    if dup:
        raise HTTPException(status_code=409, detail="Brand code exists")
    row = m.Brand(
        tenant_id=tenant_id,
        code=code,
        name=name,
        description=(description or "").strip() or None,
        is_active=True,
    )
    db.add(row)
    await db.flush()
    return row


async def list_units(db: AsyncSession, tenant_id: str) -> list[m.UnitOfMeasure]:
    return list(
        (
            await db.execute(
                select(m.UnitOfMeasure)
                .where(m.UnitOfMeasure.tenant_id == tenant_id)
                .order_by(m.UnitOfMeasure.code)
            )
        )
        .scalars()
        .all()
    )


async def create_unit(
    db: AsyncSession,
    *,
    tenant_id: str,
    code: str,
    name: str,
) -> m.UnitOfMeasure:
    code = code.strip().upper()
    name = name.strip()
    if not code or not name:
        raise HTTPException(status_code=400, detail="code and name are required")
    dup = (
        await db.execute(
            select(m.UnitOfMeasure).where(
                m.UnitOfMeasure.tenant_id == tenant_id,
                m.UnitOfMeasure.code == code,
            )
        )
    ).scalar_one_or_none()
    if dup:
        raise HTTPException(status_code=409, detail="Unit code exists")
    row = m.UnitOfMeasure(tenant_id=tenant_id, code=code, name=name, is_active=True)
    db.add(row)
    await db.flush()
    return row


async def resolve_product_refs(
    db: AsyncSession,
    tenant_id: str,
    *,
    category_id: str | None,
    brand_id: str | None,
    unit_id: str | None,
    category_name: str | None = None,
) -> tuple[str | None, str | None, str | None, str]:
    """Validate FKs and return (category_id, brand_id, unit_id, category_label)."""
    label = (category_name or "General").strip() or "General"
    resolved_category_id = category_id
    if category_id:
        cat = await db.get(m.ProductCategory, category_id)
        if not cat or cat.tenant_id != tenant_id:
            raise HTTPException(status_code=404, detail="Category not found")
        label = cat.name
        resolved_category_id = cat.id
    if brand_id:
        brand = await db.get(m.Brand, brand_id)
        if not brand or brand.tenant_id != tenant_id:
            raise HTTPException(status_code=404, detail="Brand not found")
    if unit_id:
        unit = await db.get(m.UnitOfMeasure, unit_id)
        if not unit or unit.tenant_id != tenant_id:
            raise HTTPException(status_code=404, detail="Unit not found")
    return resolved_category_id, brand_id, unit_id, label
