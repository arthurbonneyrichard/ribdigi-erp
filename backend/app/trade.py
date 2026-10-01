"""Retail / wholesale trade channel, MOQ, and qty price tiers.

Does not duplicate POS. Hotel/restaurant/bakery/manufacturing stay gated off
these tenants via industry module allowlists. Not a gift-card or HIS module.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.honesty import money_json
from app.packages import canonicalize_industry

SALES_CHANNELS = frozenset({"retail", "wholesale"})
TRADE_INDUSTRIES = frozenset({"retail", "pharmacy", "wholesale", "retail_wholesale"})
WHOLESALE_INDUSTRIES = frozenset({"wholesale", "retail_wholesale"})
# Platform Owner provision list — other canonical industries remain valid for
# existing tenants (hotel/fmcg/…) but these four are the trade ERP surface.
PROVISION_INDUSTRIES: tuple[str, ...] = (
    "retail",
    "pharmacy",
    "wholesale",
    "retail_wholesale",
)


def normalize_sales_channel(value: str | None) -> str | None:
    if value is None:
        return None
    key = str(value).strip().lower()
    if not key:
        return None
    if key not in SALES_CHANNELS:
        raise HTTPException(
            status_code=422,
            detail=f"sales_channel must be one of: {', '.join(sorted(SALES_CHANNELS))}",
        )
    return key


def default_sales_channel(industry: str | None, *, source: str) -> str:
    """POS is the retail counter; quotes/orders are the wholesale desk.

    wholesale-only tenants use wholesale for both. retail/pharmacy stay retail.
    """
    ind = canonicalize_industry(industry) or "retail"
    src = (source or "").strip().lower()
    if src == "pos":
        return "wholesale" if ind == "wholesale" else "retail"
    if ind in WHOLESALE_INDUSTRIES:
        return "wholesale"
    return "retail"


def assert_channel_allowed(industry: str | None, channel: str, *, source: str) -> str:
    ind = canonicalize_industry(industry) or "retail"
    ch = normalize_sales_channel(channel) or default_sales_channel(ind, source=source)
    src = (source or "").strip().lower()
    if ind == "retail_wholesale":
        if src == "pos" and ch != "retail":
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "CHANNEL_MISMATCH",
                    "message": "Retail+Wholesale POS is the retail counter; use sales orders for wholesale",
                    "sales_channel": ch,
                },
            )
        if src in {"quote", "order"} and ch != "wholesale":
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "CHANNEL_MISMATCH",
                    "message": "Retail+Wholesale quotes and orders are wholesale; use POS for retail",
                    "sales_channel": ch,
                },
            )
        return ch
    if ind == "wholesale" and ch != "wholesale":
        raise HTTPException(
            status_code=409,
            detail={
                "code": "CHANNEL_MISMATCH",
                "message": "Wholesale tenants use the wholesale channel",
                "sales_channel": ch,
            },
        )
    if ind not in WHOLESALE_INDUSTRIES and ch == "wholesale":
        raise HTTPException(
            status_code=409,
            detail={
                "code": "CHANNEL_MISMATCH",
                "message": "Wholesale channel is only available for wholesale or retail+wholesale tenants",
                "industry": ind,
            },
        )
    return ch


async def resolve_document_channel(
    db: AsyncSession,
    *,
    tenant_id: str,
    requested: str | None,
    source: str,
) -> str:
    tenant = await db.get(m.Tenant, tenant_id)
    industry = getattr(tenant, "industry", None) if tenant else None
    fallback = default_sales_channel(industry, source=source)
    channel = normalize_sales_channel(requested) or fallback
    return assert_channel_allowed(industry, channel, source=source)


def serialize_tier(row: m.ProductPriceTier) -> dict:
    return {
        "id": row.id,
        "product_id": row.product_id,
        "customer_group_id": row.customer_group_id,
        "min_qty": money_json(row.min_qty),
        "unit_price": money_json(row.unit_price),
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


async def list_price_tiers(
    db: AsyncSession, *, tenant_id: str, product_id: str
) -> list[m.ProductPriceTier]:
    from app import schema_compat as schema_compat_svc

    if not await schema_compat_svc.table_column_names(db, "product_price_tiers"):
        return []
    return list(
        (
            await db.execute(
                select(m.ProductPriceTier)
                .where(
                    m.ProductPriceTier.tenant_id == tenant_id,
                    m.ProductPriceTier.product_id == product_id,
                )
                .order_by(m.ProductPriceTier.min_qty.asc())
            )
        ).scalars().all()
    )


async def create_price_tier(
    db: AsyncSession,
    *,
    tenant_id: str,
    product_id: str,
    min_qty: float,
    unit_price: float,
    customer_group_id: str | None = None,
) -> m.ProductPriceTier:
    from app import schema_compat as schema_compat_svc
    from app.catalog import get_product

    if not await schema_compat_svc.table_column_names(db, "product_price_tiers"):
        raise HTTPException(status_code=409, detail="Price tiers require migration 0132")
    await get_product(db, tenant_id, product_id)
    qty = money_json(min_qty or 0)
    if qty <= 0:
        raise HTTPException(status_code=400, detail="min_qty must be greater than zero")
    price = money_json(unit_price)
    if price < 0:
        raise HTTPException(status_code=400, detail="unit_price cannot be negative")
    group_id = (customer_group_id or "").strip() or None
    if group_id:
        from app.customer_groups import get_group

        await get_group(db, tenant_id, group_id)
    existing = (
        await db.execute(
            select(m.ProductPriceTier).where(
                m.ProductPriceTier.tenant_id == tenant_id,
                m.ProductPriceTier.product_id == product_id,
                m.ProductPriceTier.min_qty == qty,
                (
                    m.ProductPriceTier.customer_group_id == group_id
                    if group_id
                    else m.ProductPriceTier.customer_group_id.is_(None)
                ),
            )
        )
    ).scalar_one_or_none()
    if existing:
        existing.unit_price = price
        await db.flush()
        return existing
    row = m.ProductPriceTier(
        tenant_id=tenant_id,
        product_id=product_id,
        customer_group_id=group_id,
        min_qty=qty,
        unit_price=price,
    )
    db.add(row)
    await db.flush()
    return row


async def delete_price_tier(
    db: AsyncSession, *, tenant_id: str, product_id: str, tier_id: str
) -> None:
    row = (
        await db.execute(
            select(m.ProductPriceTier).where(
                m.ProductPriceTier.id == tier_id,
                m.ProductPriceTier.tenant_id == tenant_id,
                m.ProductPriceTier.product_id == product_id,
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Price tier not found")
    await db.delete(row)
    await db.flush()


async def best_tier_price(
    db: AsyncSession,
    *,
    tenant_id: str,
    product_id: str,
    quantity: float,
    customer_group_id: str | None,
) -> float | None:
    """Highest min_qty tier that the line qualifies for. Group-specific wins over open."""
    from app import schema_compat as schema_compat_svc

    if not await schema_compat_svc.table_column_names(db, "product_price_tiers"):
        return None
    qty = money_json(quantity or 0)
    rows = await list_price_tiers(db, tenant_id=tenant_id, product_id=product_id)
    eligible = [r for r in rows if money_json(r.min_qty) - 1e-9 <= qty]
    if not eligible:
        return None
    group_id = (customer_group_id or "").strip() or None
    grouped = [r for r in eligible if group_id and r.customer_group_id == group_id]
    pool = grouped or [r for r in eligible if r.customer_group_id is None]
    if not pool:
        return None
    best = max(pool, key=lambda r: money_json(r.min_qty))
    return money_json(best.unit_price)


def assert_moq(product: m.Product, quantity: float, channel: str) -> None:
    if channel != "wholesale":
        return
    floor = money_json(getattr(product, "min_order_qty", 0) or 0)
    qty = money_json(quantity or 0)
    if floor > 0 and qty + 1e-9 < floor:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "MOQ_NOT_MET",
                "message": "Quantity is below the wholesale minimum order quantity",
                "product_id": product.id,
                "min_order_qty": floor,
                "requested": qty,
            },
        )


async def allocate_delivery_note_number(db: AsyncSession, tenant_id: str) -> str:
    year = datetime.utcnow().year
    prefix = f"DN-{year}-"
    count = (
        await db.execute(
            select(func.count())
            .select_from(m.SalesOrder)
            .where(
                m.SalesOrder.tenant_id == tenant_id,
                m.SalesOrder.delivery_note_number.is_not(None),
            )
        )
    ).scalar_one()
    start = int(count or 0) + 1
    for n in range(start, start + 10_000):
        candidate = f"{prefix}{n:04d}"
        exists = (
            await db.execute(
                select(m.SalesOrder.id).where(
                    m.SalesOrder.tenant_id == tenant_id,
                    m.SalesOrder.delivery_note_number == candidate,
                )
            )
        ).scalar_one_or_none()
        if not exists:
            return candidate
    raise HTTPException(status_code=500, detail="Unable to allocate delivery note number")
