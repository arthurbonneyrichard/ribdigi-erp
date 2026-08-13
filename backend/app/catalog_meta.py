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
        "tax_rate_id": getattr(row, "tax_rate_id", None),
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


def serialize_unit(row: m.UnitOfMeasure, *, base: m.UnitOfMeasure | None = None) -> dict:
    return {
        "id": row.id,
        "code": row.code,
        "name": row.name,
        "base_unit_id": getattr(row, "base_unit_id", None),
        "conversion_ratio": float(getattr(row, "conversion_ratio", None) or 1),
        "base_unit_code": base.code if base else None,
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
        "tax_supply_class": getattr(row, "tax_supply_class", None)
        or ("exempt" if row.tax_exempt else "standard"),
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


async def _validate_category_tax_rate(
    db: AsyncSession, *, tenant_id: str, tax_rate_id: str | None
) -> str | None:
    if tax_rate_id is None:
        return None
    rate = await db.get(m.TaxRate, tax_rate_id)
    if rate is None or rate.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Tax rate not found")
    if not rate.is_active:
        raise HTTPException(status_code=400, detail="Tax rate is inactive")
    return rate.id


async def create_category(
    db: AsyncSession,
    *,
    tenant_id: str,
    code: str,
    name: str,
    parent_id: str | None = None,
    tax_rate_id: str | None = None,
) -> m.ProductCategory:
    code = code.strip().upper()
    name = name.strip()
    if not code or not name:
        raise HTTPException(status_code=400, detail="code and name are required")
    if parent_id:
        parent = await db.get(m.ProductCategory, parent_id)
        if not parent or parent.tenant_id != tenant_id:
            raise HTTPException(status_code=404, detail="Parent category not found")
    tax_rate_id = await _validate_category_tax_rate(db, tenant_id=tenant_id, tax_rate_id=tax_rate_id)
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
        tax_rate_id=tax_rate_id,
        is_active=True,
    )
    db.add(row)
    await db.flush()
    return row


async def update_category(
    db: AsyncSession,
    *,
    tenant_id: str,
    category_id: str,
    code: str | None = None,
    name: str | None = None,
    parent_id: str | None = None,
    tax_rate_id: str | None = None,
    is_active: bool | None = None,
    clear_parent: bool = False,
    clear_tax_rate: bool = False,
) -> m.ProductCategory:
    row = await db.get(m.ProductCategory, category_id)
    if row is None or row.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Category not found")
    if code is not None:
        code = code.strip().upper()
        if not code:
            raise HTTPException(status_code=400, detail="code is required")
        dup = (
            await db.execute(
                select(m.ProductCategory).where(
                    m.ProductCategory.tenant_id == tenant_id,
                    m.ProductCategory.code == code,
                    m.ProductCategory.id != row.id,
                )
            )
        ).scalar_one_or_none()
        if dup:
            raise HTTPException(status_code=409, detail="Category code exists")
        row.code = code
    if name is not None:
        name = name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="name is required")
        row.name = name
    if clear_parent:
        row.parent_id = None
    elif parent_id is not None:
        if parent_id == row.id:
            raise HTTPException(status_code=400, detail="Category cannot be its own parent")
        parent = await db.get(m.ProductCategory, parent_id)
        if not parent or parent.tenant_id != tenant_id:
            raise HTTPException(status_code=404, detail="Parent category not found")
        row.parent_id = parent_id
    if clear_tax_rate:
        row.tax_rate_id = None
    elif tax_rate_id is not None:
        row.tax_rate_id = await _validate_category_tax_rate(
            db, tenant_id=tenant_id, tax_rate_id=tax_rate_id
        )
    if is_active is not None:
        row.is_active = bool(is_active)
    await db.flush()
    return row


async def deactivate_category(
    db: AsyncSession, *, tenant_id: str, category_id: str
) -> m.ProductCategory:
    return await update_category(
        db, tenant_id=tenant_id, category_id=category_id, is_active=False
    )


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


async def update_brand(
    db: AsyncSession,
    *,
    tenant_id: str,
    brand_id: str,
    code: str | None = None,
    name: str | None = None,
    description: str | None = None,
    is_active: bool | None = None,
    clear_description: bool = False,
) -> m.Brand:
    row = await db.get(m.Brand, brand_id)
    if row is None or row.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Brand not found")
    if code is not None:
        code = code.strip().upper()
        if not code:
            raise HTTPException(status_code=400, detail="code is required")
        dup = (
            await db.execute(
                select(m.Brand).where(
                    m.Brand.tenant_id == tenant_id,
                    m.Brand.code == code,
                    m.Brand.id != row.id,
                )
            )
        ).scalar_one_or_none()
        if dup:
            raise HTTPException(status_code=409, detail="Brand code exists")
        row.code = code
    if name is not None:
        name = name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="name is required")
        row.name = name
    if clear_description:
        row.description = None
    elif description is not None:
        row.description = description.strip() or None
    if is_active is not None:
        row.is_active = bool(is_active)
    await db.flush()
    return row


async def deactivate_brand(db: AsyncSession, *, tenant_id: str, brand_id: str) -> m.Brand:
    return await update_brand(db, tenant_id=tenant_id, brand_id=brand_id, is_active=False)


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


async def serialize_units(db: AsyncSession, tenant_id: str, rows: list[m.UnitOfMeasure]) -> list[dict]:
    base_ids = {r.base_unit_id for r in rows if r.base_unit_id}
    bases: dict[str, m.UnitOfMeasure] = {}
    if base_ids:
        bases = {
            u.id: u
            for u in (
                await db.execute(
                    select(m.UnitOfMeasure).where(
                        m.UnitOfMeasure.tenant_id == tenant_id,
                        m.UnitOfMeasure.id.in_(base_ids),
                    )
                )
            ).scalars().all()
        }
    return [serialize_unit(r, base=bases.get(r.base_unit_id)) for r in rows]


async def create_unit(
    db: AsyncSession,
    *,
    tenant_id: str,
    code: str,
    name: str,
    base_unit_id: str | None = None,
    conversion_ratio: float | None = None,
) -> m.UnitOfMeasure:
    from app.uom import validate_unit_base

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
    base_id, ratio = await validate_unit_base(
        db,
        tenant_id=tenant_id,
        unit_id=None,
        base_unit_id=base_unit_id,
        conversion_ratio=conversion_ratio,
    )
    row = m.UnitOfMeasure(
        tenant_id=tenant_id,
        code=code,
        name=name,
        base_unit_id=base_id,
        conversion_ratio=ratio,
        is_active=True,
    )
    db.add(row)
    await db.flush()
    return row


async def update_unit(
    db: AsyncSession,
    *,
    tenant_id: str,
    unit_id: str,
    code: str | None = None,
    name: str | None = None,
    is_active: bool | None = None,
    base_unit_id: str | None = None,
    conversion_ratio: float | None = None,
    clear_base: bool = False,
) -> m.UnitOfMeasure:
    from app.uom import validate_unit_base

    row = await db.get(m.UnitOfMeasure, unit_id)
    if row is None or row.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Unit not found")
    if code is not None:
        code = code.strip().upper()
        if not code:
            raise HTTPException(status_code=400, detail="code is required")
        dup = (
            await db.execute(
                select(m.UnitOfMeasure).where(
                    m.UnitOfMeasure.tenant_id == tenant_id,
                    m.UnitOfMeasure.code == code,
                    m.UnitOfMeasure.id != row.id,
                )
            )
        ).scalar_one_or_none()
        if dup:
            raise HTTPException(status_code=409, detail="Unit code exists")
        row.code = code
    if name is not None:
        name = name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="name is required")
        row.name = name
    if is_active is not None:
        row.is_active = bool(is_active)
    if clear_base:
        row.base_unit_id = None
        row.conversion_ratio = 1
    elif base_unit_id is not None or conversion_ratio is not None:
        # Reject setting this unit as base of something that already uses it as base while becoming non-root? depth-1 only.
        if base_unit_id is None and conversion_ratio is not None and not row.base_unit_id:
            row.conversion_ratio = 1
        else:
            target_base = base_unit_id if base_unit_id is not None else row.base_unit_id
            target_ratio = (
                conversion_ratio
                if conversion_ratio is not None
                else float(row.conversion_ratio or 1)
            )
            base_id, ratio = await validate_unit_base(
                db,
                tenant_id=tenant_id,
                unit_id=row.id,
                base_unit_id=target_base,
                conversion_ratio=target_ratio,
            )
            # Prevent cycles: no unit that already has children should become a non-root via pointing elsewhere
            # while being someone's base — if this unit is used as a base by others, it must stay root.
            child = (
                await db.execute(
                    select(m.UnitOfMeasure.id).where(
                        m.UnitOfMeasure.tenant_id == tenant_id,
                        m.UnitOfMeasure.base_unit_id == row.id,
                    ).limit(1)
                )
            ).scalar_one_or_none()
            if child and base_id:
                raise HTTPException(
                    status_code=400,
                    detail="Unit is already a base for other units; clear dependents first",
                )
            row.base_unit_id = base_id
            row.conversion_ratio = ratio
    await db.flush()
    return row


async def deactivate_unit(
    db: AsyncSession, *, tenant_id: str, unit_id: str
) -> m.UnitOfMeasure:
    return await update_unit(db, tenant_id=tenant_id, unit_id=unit_id, is_active=False)


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
