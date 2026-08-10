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


def build_category_tree(rows: list[m.ProductCategory]) -> list[dict]:
    """Nest categories by parent_id; orphans with missing parents become roots."""
    nodes = {row.id: {**serialize_category(row), "children": []} for row in rows}
    roots: list[dict] = []
    for row in rows:
        node = nodes[row.id]
        parent_id = row.parent_id
        if parent_id and parent_id in nodes and parent_id != row.id:
            nodes[parent_id]["children"].append(node)
        else:
            roots.append(node)

    def sort_rec(items: list[dict]) -> None:
        items.sort(key=lambda x: (x.get("name") or "").lower())
        for item in items:
            sort_rec(item["children"])

    sort_rec(roots)
    return roots


def flatten_category_tree(tree: list[dict], *, depth: int = 0) -> list[dict]:
    out: list[dict] = []
    for node in tree:
        out.append({**{k: v for k, v in node.items() if k != "children"}, "depth": depth})
        out.extend(flatten_category_tree(node.get("children") or [], depth=depth + 1))
    return out


def serialize_brand(row: m.Brand) -> dict:
    return {
        "id": row.id,
        "code": row.code,
        "name": row.name,
        "description": row.description,
        "logo_url": getattr(row, "logo_url", None),
        "has_logo": bool(getattr(row, "logo_url", None)),
        "is_active": bool(row.is_active),
        "created_at": row.created_at,
    }


def serialize_unit(row: m.UnitOfMeasure) -> dict:
    return {
        "id": row.id,
        "code": row.code,
        "name": row.name,
        "base_unit_id": getattr(row, "base_unit_id", None),
        "conversion_factor": float(getattr(row, "conversion_factor", 1) or 1),
        "is_active": bool(row.is_active),
        "created_at": row.created_at,
    }


def serialize_product(row: m.Product) -> dict:
    from app.inventory import compute_stock_status

    stock_qty = float(row.stock_qty or 0)
    minimum_stock = float(getattr(row, "minimum_stock", 0) or 0)
    reorder_level = float(row.reorder_level or 0)
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
        "stock_qty": stock_qty,
        "reserved_qty": float(getattr(row, "reserved_qty", 0) or 0),
        "available_qty": max(
            stock_qty - float(getattr(row, "reserved_qty", 0) or 0),
            0.0,
        ),
        "minimum_stock": minimum_stock,
        "reorder_level": reorder_level,
        "stock_status": compute_stock_status(stock_qty, minimum_stock, reorder_level),
        "weight": float(row.weight) if getattr(row, "weight", None) is not None else None,
        "length": float(row.length) if getattr(row, "length", None) is not None else None,
        "width": float(row.width) if getattr(row, "width", None) is not None else None,
        "height": float(row.height) if getattr(row, "height", None) is not None else None,
        "tax_rate_id": row.tax_rate_id,
        "tax_exempt": bool(row.tax_exempt),
        "tracks_batches": bool(row.tracks_batches),
        "is_active": bool(row.is_active),
    }


# BR-17.1 Product Changes — fields captured on domain audit before/after
_PRODUCT_AUDIT_FIELDS = (
    "name",
    "sku",
    "barcode",
    "category",
    "category_id",
    "brand_id",
    "unit_id",
    "cost_price",
    "selling_price",
    "minimum_stock",
    "reorder_level",
    "weight",
    "length",
    "width",
    "height",
    "tax_rate_id",
    "tax_exempt",
    "tracks_batches",
    "is_active",
)


def product_audit_snapshot(row: m.Product) -> dict:
    """Serializable product fields for audit before/after (BR-17.1)."""
    data = serialize_product(row)
    return {k: data.get(k) for k in _PRODUCT_AUDIT_FIELDS}


def product_audit_diff(before: dict, after: dict) -> tuple[dict, dict]:
    """Return only keys that changed between two product audit snapshots."""
    changed_before: dict = {}
    changed_after: dict = {}
    keys = set(before) | set(after)
    for key in sorted(keys):
        if before.get(key) != after.get(key):
            changed_before[key] = before.get(key)
            changed_after[key] = after.get(key)
    return changed_before, changed_after


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
    rate = (
        await db.execute(
            select(m.TaxRate).where(
                m.TaxRate.id == tax_rate_id,
                m.TaxRate.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not rate:
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
    validated_tax = await _validate_category_tax_rate(
        db, tenant_id=tenant_id, tax_rate_id=tax_rate_id
    )
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
        tax_rate_id=validated_tax,
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
    is_active: bool | None = None,
    tax_rate_id: str | None = None,
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
        # Prevent cycles: walk ancestors of the new parent
        cursor = parent
        seen = {row.id}
        while cursor is not None:
            if cursor.id in seen:
                raise HTTPException(status_code=400, detail="Category parent would create a cycle")
            seen.add(cursor.id)
            if not cursor.parent_id:
                break
            cursor = await db.get(m.ProductCategory, cursor.parent_id)
            if cursor is None or cursor.tenant_id != tenant_id:
                break
        row.parent_id = parent_id
    if is_active is not None:
        row.is_active = bool(is_active)
    if clear_tax_rate:
        row.tax_rate_id = None
    elif tax_rate_id is not None:
        row.tax_rate_id = await _validate_category_tax_rate(
            db, tenant_id=tenant_id, tax_rate_id=tax_rate_id
        )
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


async def get_unit(db: AsyncSession, tenant_id: str, unit_id: str) -> m.UnitOfMeasure:
    row = await db.get(m.UnitOfMeasure, unit_id)
    if row is None or row.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Unit not found")
    return row


async def _validate_base_unit(
    db: AsyncSession,
    *,
    tenant_id: str,
    unit_id: str | None,
    base_unit_id: str | None,
) -> str | None:
    if not base_unit_id:
        return None
    if unit_id and base_unit_id == unit_id:
        raise HTTPException(status_code=400, detail="base_unit_id cannot reference itself")
    base = await get_unit(db, tenant_id, base_unit_id)
    # One-level conversions only: base unit must itself be a base (no chain)
    if getattr(base, "base_unit_id", None):
        raise HTTPException(
            status_code=400,
            detail="base_unit_id must reference a base unit (no multi-level chains)",
        )
    return base.id


def quantity_in_base(unit: m.UnitOfMeasure, quantity: float) -> tuple[str, float]:
    """Return (base_unit_id, qty_in_base)."""
    factor = float(getattr(unit, "conversion_factor", 1) or 1)
    if factor <= 0:
        raise HTTPException(status_code=400, detail="conversion_factor must be positive")
    if unit.base_unit_id:
        return unit.base_unit_id, float(quantity) * factor
    return unit.id, float(quantity)


async def convert_quantity(
    db: AsyncSession,
    *,
    tenant_id: str,
    from_unit_id: str,
    to_unit_id: str,
    quantity: float,
) -> dict:
    qty = float(quantity)
    if qty < 0:
        raise HTTPException(status_code=400, detail="quantity cannot be negative")
    from_unit = await get_unit(db, tenant_id, from_unit_id)
    to_unit = await get_unit(db, tenant_id, to_unit_id)
    from_base, from_base_qty = quantity_in_base(from_unit, qty)
    to_base, _ = quantity_in_base(to_unit, 1)
    if from_base != to_base:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INCOMPATIBLE_UNITS",
                "message": "Units do not share a common base for conversion",
                "from_unit_id": from_unit.id,
                "to_unit_id": to_unit.id,
            },
        )
    to_factor = float(getattr(to_unit, "conversion_factor", 1) or 1)
    if to_unit.base_unit_id:
        result = from_base_qty / to_factor
    else:
        result = from_base_qty
    return {
        "from_unit_id": from_unit.id,
        "from_unit_code": from_unit.code,
        "to_unit_id": to_unit.id,
        "to_unit_code": to_unit.code,
        "quantity": qty,
        "converted_quantity": round(result, 6),
        "base_unit_id": from_base,
    }


async def create_unit(
    db: AsyncSession,
    *,
    tenant_id: str,
    code: str,
    name: str,
    base_unit_id: str | None = None,
    conversion_factor: float = 1,
) -> m.UnitOfMeasure:
    code = code.strip().upper()
    name = name.strip()
    if not code or not name:
        raise HTTPException(status_code=400, detail="code and name are required")
    factor = float(conversion_factor or 1)
    if factor <= 0:
        raise HTTPException(status_code=400, detail="conversion_factor must be positive")
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
    base_id = await _validate_base_unit(
        db, tenant_id=tenant_id, unit_id=None, base_unit_id=base_unit_id
    )
    if base_id is None:
        factor = 1.0
    row = m.UnitOfMeasure(
        tenant_id=tenant_id,
        code=code,
        name=name,
        base_unit_id=base_id,
        conversion_factor=factor,
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
    base_unit_id: str | None = None,
    conversion_factor: float | None = None,
    is_active: bool | None = None,
    clear_base_unit: bool = False,
) -> m.UnitOfMeasure:
    row = await get_unit(db, tenant_id, unit_id)
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
    if clear_base_unit:
        row.base_unit_id = None
        row.conversion_factor = 1
    elif base_unit_id is not None:
        row.base_unit_id = await _validate_base_unit(
            db, tenant_id=tenant_id, unit_id=row.id, base_unit_id=base_unit_id
        )
    if conversion_factor is not None and not clear_base_unit:
        factor = float(conversion_factor)
        if factor <= 0:
            raise HTTPException(status_code=400, detail="conversion_factor must be positive")
        row.conversion_factor = factor if row.base_unit_id else 1
    if is_active is not None:
        row.is_active = bool(is_active)
    # Prevent turning a base into a dependent if other units reference it
    if row.base_unit_id:
        dependents = (
            await db.execute(
                select(m.UnitOfMeasure.id).where(
                    m.UnitOfMeasure.tenant_id == tenant_id,
                    m.UnitOfMeasure.base_unit_id == row.id,
                ).limit(1)
            )
        ).scalar_one_or_none()
        if dependents:
            raise HTTPException(
                status_code=400,
                detail="Cannot set a base for a unit that is already used as a base by others",
            )
    await db.flush()
    return row


async def deactivate_unit(
    db: AsyncSession, *, tenant_id: str, unit_id: str
) -> m.UnitOfMeasure:
    return await update_unit(db, tenant_id=tenant_id, unit_id=unit_id, is_active=False)


async def get_brand(db: AsyncSession, tenant_id: str, brand_id: str) -> m.Brand:
    row = await db.get(m.Brand, brand_id)
    if row is None or row.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Brand not found")
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
