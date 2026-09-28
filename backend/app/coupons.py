"""Sales/POS coupon codes: dates, limits, min spend, eligibility, redemptions."""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.honesty import money_json, optional_honest_narrative, require_honest_narrative
from app.sale_discounts import resolve_discount

CODE_MAX = 32


def normalize_coupon_code(value: object) -> str:
    raw = str(value or "").strip().upper()
    if not raw:
        raise HTTPException(status_code=400, detail="Coupon code is required")
    if len(raw) > CODE_MAX:
        raise HTTPException(status_code=400, detail="Coupon code is too long")
    if "://" in raw or "@" in raw or " " in raw:
        raise HTTPException(status_code=400, detail="Coupon code must be letters, digits, or hyphen")
    if not all(ch.isalnum() or ch in "-_" for ch in raw):
        raise HTTPException(status_code=400, detail="Coupon code must be letters, digits, or hyphen")
    if not any(ch.isalnum() for ch in raw):
        raise HTTPException(status_code=400, detail="Coupon code must be letters, digits, or hyphen")
    return raw


def serialize_coupon(row: m.SalesCoupon, *, redemption_count: int | None = None) -> dict:
    return {
        "id": row.id,
        "code": row.code,
        "name": row.name,
        "discount_type": row.discount_type,
        "amount": money_json(row.amount),
        "min_spend": money_json(row.min_spend or 0),
        "starts_at": row.starts_at,
        "ends_at": row.ends_at,
        "max_redemptions": row.max_redemptions,
        "per_customer_limit": int(row.per_customer_limit or 0),
        "eligible_product_ids": list(row.eligible_product_ids or []),
        "eligible_category_ids": list(row.eligible_category_ids or []),
        "is_active": bool(row.is_active),
        "notes": row.notes,
        "redemption_count": redemption_count,
        "created_at": row.created_at,
    }


async def _redemption_count(
    db: AsyncSession, tenant_id: str, coupon_id: str, *, customer_id: str | None = None
) -> int:
    q = select(func.count()).select_from(m.SalesCouponRedemption).where(
        m.SalesCouponRedemption.tenant_id == tenant_id,
        m.SalesCouponRedemption.coupon_id == coupon_id,
    )
    if customer_id:
        q = q.where(m.SalesCouponRedemption.customer_id == customer_id)
    return int((await db.execute(q)).scalar_one() or 0)


async def get_coupon(db: AsyncSession, tenant_id: str, coupon_id: str) -> m.SalesCoupon:
    row = (
        await db.execute(
            select(m.SalesCoupon).where(
                m.SalesCoupon.id == coupon_id,
                m.SalesCoupon.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Coupon not found")
    return row


async def get_coupon_by_code(db: AsyncSession, tenant_id: str, code: str) -> m.SalesCoupon:
    key = normalize_coupon_code(code)
    row = (
        await db.execute(
            select(m.SalesCoupon).where(
                m.SalesCoupon.tenant_id == tenant_id,
                m.SalesCoupon.code == key,
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=400, detail="Coupon code is not valid")
    return row


async def list_coupons(db: AsyncSession, tenant_id: str) -> list[dict]:
    rows = (
        (
            await db.execute(
                select(m.SalesCoupon)
                .where(m.SalesCoupon.tenant_id == tenant_id)
                .order_by(m.SalesCoupon.code)
            )
        )
        .scalars()
        .all()
    )
    out = []
    for row in rows:
        count = await _redemption_count(db, tenant_id, row.id)
        out.append(serialize_coupon(row, redemption_count=count))
    return out


async def create_coupon(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    payload: dict,
) -> m.SalesCoupon:
    code = normalize_coupon_code(payload.get("code"))
    clash = (
        await db.execute(
            select(m.SalesCoupon).where(
                m.SalesCoupon.tenant_id == tenant_id,
                m.SalesCoupon.code == code,
            )
        )
    ).scalar_one_or_none()
    if clash:
        raise HTTPException(status_code=409, detail="Coupon code already exists")
    dtype = str(payload.get("discount_type") or "percent").strip().lower()
    if dtype not in {"fixed", "percent"}:
        raise HTTPException(status_code=400, detail="Discount type must be fixed or percent")
    amount = money_json(payload.get("amount") or 0)
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Coupon amount must be greater than zero")
    if dtype == "percent" and amount > 100:
        raise HTTPException(status_code=400, detail="Percent coupons cannot exceed 100")
    min_spend = money_json(payload.get("min_spend") or 0)
    if min_spend < 0:
        raise HTTPException(status_code=400, detail="Minimum spend cannot be negative")
    starts = payload.get("starts_at")
    ends = payload.get("ends_at")
    if starts and ends and starts > ends:
        raise HTTPException(status_code=400, detail="Coupon end date must be on or after start date")
    max_red = payload.get("max_redemptions")
    if max_red is not None and int(max_red) < 1:
        raise HTTPException(status_code=400, detail="Max redemptions must be at least 1 when set")
    row = m.SalesCoupon(
        tenant_id=tenant_id,
        code=code,
        name=require_honest_narrative(payload.get("name"), label="coupon name", max_length=120),
        discount_type=dtype,
        amount=amount,
        min_spend=min_spend,
        starts_at=starts,
        ends_at=ends,
        max_redemptions=int(max_red) if max_red is not None else None,
        per_customer_limit=int(payload.get("per_customer_limit") or 0),
        eligible_product_ids=list(payload.get("eligible_product_ids") or []),
        eligible_category_ids=list(payload.get("eligible_category_ids") or []),
        is_active=bool(payload.get("is_active", True)),
        notes=optional_honest_narrative(payload.get("notes"), label="coupon notes"),
        created_by=user_id,
    )
    db.add(row)
    await db.flush()
    db.add(
        m.AuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            action="coupon_created",
            entity="sales_coupon",
            entity_id=row.id,
            details={"code": row.code},
        )
    )
    return row


async def update_coupon(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    coupon_id: str,
    payload: dict,
) -> m.SalesCoupon:
    row = await get_coupon(db, tenant_id, coupon_id)
    if "name" in payload and payload["name"] is not None:
        row.name = require_honest_narrative(payload["name"], label="coupon name", max_length=120)
    if "is_active" in payload and payload["is_active"] is not None:
        row.is_active = bool(payload["is_active"])
    if "notes" in payload:
        row.notes = optional_honest_narrative(payload.get("notes"), label="coupon notes")
    if "min_spend" in payload and payload["min_spend"] is not None:
        row.min_spend = money_json(payload["min_spend"])
    if "max_redemptions" in payload:
        max_red = payload["max_redemptions"]
        row.max_redemptions = int(max_red) if max_red is not None else None
    if "per_customer_limit" in payload and payload["per_customer_limit"] is not None:
        row.per_customer_limit = int(payload["per_customer_limit"])
    if "starts_at" in payload:
        row.starts_at = payload.get("starts_at")
    if "ends_at" in payload:
        row.ends_at = payload.get("ends_at")
    if "eligible_product_ids" in payload and payload["eligible_product_ids"] is not None:
        row.eligible_product_ids = list(payload["eligible_product_ids"])
    if "eligible_category_ids" in payload and payload["eligible_category_ids"] is not None:
        row.eligible_category_ids = list(payload["eligible_category_ids"])
    row.updated_at = datetime.utcnow()
    db.add(
        m.AuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            action="coupon_updated",
            entity="sales_coupon",
            entity_id=row.id,
            details={"code": row.code},
        )
    )
    await db.flush()
    return row


def _in_window(row: m.SalesCoupon, *, now: datetime) -> None:
    if not row.is_active:
        raise HTTPException(status_code=400, detail="Coupon is not active")
    if row.starts_at and now < row.starts_at:
        raise HTTPException(status_code=400, detail="Coupon is not active yet")
    if row.ends_at and now > row.ends_at:
        raise HTTPException(status_code=400, detail="Coupon has expired")


async def apply_coupon(
    db: AsyncSession,
    *,
    tenant_id: str,
    code: str,
    header_base: float,
    product_ids: list[str],
    category_ids: list[str] | None = None,
    customer_id: str | None = None,
    now: datetime | None = None,
) -> dict:
    """Validate and compute header discount. Does not record a redemption."""
    row = await get_coupon_by_code(db, tenant_id, code)
    now = now or datetime.utcnow()
    _in_window(row, now=now)
    base = money_json(header_base)
    if base + 1e-9 < money_json(row.min_spend or 0):
        raise HTTPException(
            status_code=400,
            detail=f"Coupon requires a minimum spend of {money_json(row.min_spend)}",
        )
    allowed_products = [str(x) for x in (row.eligible_product_ids or []) if x]
    if allowed_products:
        cart = {str(x) for x in product_ids if x}
        if not cart or not cart.issubset(set(allowed_products)):
            raise HTTPException(status_code=400, detail="Cart items are not eligible for this coupon")
    allowed_cats = [str(x) for x in (row.eligible_category_ids or []) if x]
    if allowed_cats:
        cats = {str(x) for x in (category_ids or []) if x}
        if not cats or not cats.issubset(set(allowed_cats)):
            raise HTTPException(status_code=400, detail="Cart categories are not eligible for this coupon")
    used = await _redemption_count(db, tenant_id, row.id)
    if row.max_redemptions is not None and used >= int(row.max_redemptions):
        raise HTTPException(status_code=400, detail="Coupon redemption limit reached")
    per = int(row.per_customer_limit or 0)
    if per > 0:
        if not customer_id:
            raise HTTPException(status_code=400, detail="Select a customer to use this coupon")
        used_cust = await _redemption_count(db, tenant_id, row.id, customer_id=customer_id)
        if used_cust >= per:
            raise HTTPException(status_code=400, detail="This customer has already used this coupon")
    if row.discount_type == "percent":
        amount, dtype, pct = resolve_discount(
            base_amount=base,
            discount=0,
            discount_type="percent",
            discount_percent=row.amount,
            label="Coupon",
        )
    else:
        amount, dtype, pct = resolve_discount(
            base_amount=base,
            discount=row.amount,
            discount_type="fixed",
            discount_percent=0,
            label="Coupon",
        )
    return {
        "coupon_id": row.id,
        "code": row.code,
        "discount_amount": amount,
        "discount_type": dtype,
        "discount_percent": pct,
        "name": row.name,
    }


async def record_redemption(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    coupon_id: str,
    amount: float,
    customer_id: str | None,
    source_type: str,
    source_id: str,
) -> m.SalesCouponRedemption:
    row = m.SalesCouponRedemption(
        tenant_id=tenant_id,
        coupon_id=coupon_id,
        customer_id=customer_id,
        source_type=source_type,
        source_id=source_id,
        amount=money_json(amount),
        created_by=user_id,
    )
    db.add(row)
    await db.flush()
    return row
