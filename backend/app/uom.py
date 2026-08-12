"""Unit-of-measure conversion helpers (BR-5.1).

Stock ledger quantities remain in ``product.unit_id``. Entered quantities in an
alternate UoM are converted at transaction boundaries via ``to_stock_qty``.
"""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m


async def get_unit(db: AsyncSession, tenant_id: str, unit_id: str) -> m.UnitOfMeasure:
    row = (
        await db.execute(
            select(m.UnitOfMeasure).where(
                m.UnitOfMeasure.id == unit_id,
                m.UnitOfMeasure.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Unit of measure not found")
    return row


def factor_to_root(unit: m.UnitOfMeasure, base: m.UnitOfMeasure | None) -> tuple[str, float]:
    """Return (root_unit_id, factor) where 1 unit = factor × root.

    MVP depth ≤ 1: either the unit is a root, or it points at a root base.
    """
    if not unit.base_unit_id:
        return unit.id, 1.0
    if base is None:
        raise HTTPException(status_code=400, detail="Base unit missing for conversion")
    if base.base_unit_id:
        raise HTTPException(
            status_code=400,
            detail="Multi-hop unit conversions are not supported; base unit must be a root",
        )
    ratio = float(unit.conversion_ratio or 0)
    if ratio <= 0:
        raise HTTPException(status_code=400, detail="conversion_ratio must be positive")
    return base.id, ratio


async def to_stock_qty(
    db: AsyncSession,
    *,
    tenant_id: str,
    quantity: float,
    from_unit_id: str | None,
    product: m.Product,
) -> tuple[float, str | None, float]:
    """Convert entered quantity to product stockkeeping units.

    Returns ``(quantity_base, entered_unit_id, entered_quantity)``.
    When ``from_unit_id`` is omitted or equals the product unit, no conversion.
    """
    qty = float(quantity)
    if qty <= 0:
        raise HTTPException(status_code=400, detail="quantity must be positive")

    stock_unit_id = product.unit_id
    if not from_unit_id or not stock_unit_id or from_unit_id == stock_unit_id:
        return qty, from_unit_id if from_unit_id else stock_unit_id, qty

    from_unit = await get_unit(db, tenant_id, from_unit_id)
    stock_unit = await get_unit(db, tenant_id, stock_unit_id)
    if not from_unit.is_active or not stock_unit.is_active:
        raise HTTPException(status_code=409, detail="Unit of measure is inactive")

    from_base = None
    if from_unit.base_unit_id:
        from_base = await get_unit(db, tenant_id, from_unit.base_unit_id)
    stock_base = None
    if stock_unit.base_unit_id:
        stock_base = await get_unit(db, tenant_id, stock_unit.base_unit_id)

    from_root, from_factor = factor_to_root(from_unit, from_base)
    stock_root, stock_factor = factor_to_root(stock_unit, stock_base)
    if from_root != stock_root:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Cannot convert {from_unit.code} to stock unit {stock_unit.code} "
                "(units do not share a common base)"
            ),
        )

    # qty_in_root = qty * from_factor; qty_in_stock = qty_in_root / stock_factor
    quantity_base = round(qty * from_factor / stock_factor, 6)
    if quantity_base <= 0:
        raise HTTPException(status_code=400, detail="Converted quantity must be positive")
    return quantity_base, from_unit.id, qty


async def validate_unit_base(
    db: AsyncSession,
    *,
    tenant_id: str,
    unit_id: str | None,
    base_unit_id: str | None,
    conversion_ratio: float | None,
) -> tuple[str | None, float]:
    """Validate base/ratio for create/update. Returns (base_unit_id, ratio)."""
    if not base_unit_id:
        return None, 1.0
    if unit_id and base_unit_id == unit_id:
        raise HTTPException(status_code=400, detail="Unit cannot be its own base")
    base = await get_unit(db, tenant_id, base_unit_id)
    if base.base_unit_id:
        raise HTTPException(
            status_code=400,
            detail="Base unit must be a root unit (no further base)",
        )
    ratio = float(conversion_ratio if conversion_ratio is not None else 1)
    if ratio <= 0:
        raise HTTPException(status_code=422, detail="conversion_ratio must be greater than zero")
    return base.id, ratio
