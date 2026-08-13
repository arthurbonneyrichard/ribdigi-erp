"""POS Hold/Resume — Stage 165 H1 park + Stage 166 S1 optional soft stock reserve."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.inventory import available_qty

ALLOWED_STATUS = {"held", "resumed", "discarded"}


def serialize_hold(row: m.PosHeldCart) -> dict[str, Any]:
    reserved = bool(getattr(row, "stock_reserved", False))
    return {
        "id": row.id,
        "user_id": row.user_id,
        "session_id": row.session_id,
        "label": row.label,
        "cart_payload": row.cart_payload or {},
        "status": row.status,
        "held_at": row.held_at,
        "resumed_at": row.resumed_at,
        "discarded_at": row.discarded_at,
        "stock_reserved": reserved,
        "reservation_lines": getattr(row, "reservation_lines", None) or [],
        "message": (
            "Held cart with soft stock reservation (Stage 166 S1) — reserved_qty only; not a sale."
            if reserved
            else "Held cart park only — stock is not reserved (Stage 165 H1 Partial)."
        ),
    }


async def list_holds(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    status: str | None = "held",
) -> list[m.PosHeldCart]:
    q = select(m.PosHeldCart).where(
        m.PosHeldCart.tenant_id == tenant_id,
        m.PosHeldCart.user_id == user_id,
    )
    if status is not None:
        wanted = str(status).strip().lower()
        if wanted not in ALLOWED_STATUS and wanted != "all":
            raise HTTPException(status_code=400, detail="status must be held, resumed, discarded, or all")
        if wanted != "all":
            q = q.where(m.PosHeldCart.status == wanted)
    q = q.order_by(m.PosHeldCart.held_at.desc())
    return list((await db.execute(q)).scalars().all())


async def _soft_reserve_lines(
    db: AsyncSession, *, tenant_id: str, items: list
) -> list[dict[str, Any]]:
    """Increment product.reserved_qty for hold lines (no SO StockReservation rows)."""
    lines: list[dict[str, Any]] = []
    # Aggregate by product_id for a single lock/update per product
    by_product: dict[str, float] = {}
    for raw in items:
        if not isinstance(raw, dict):
            continue
        pid = str(raw.get("product_id") or "").strip()
        qty = float(raw.get("quantity") or 0)
        if not pid or qty <= 0:
            continue
        by_product[pid] = by_product.get(pid, 0.0) + qty

    for product_id, qty in by_product.items():
        product = (
            await db.execute(
                select(m.Product)
                .where(m.Product.id == product_id, m.Product.tenant_id == tenant_id)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if not product:
            raise HTTPException(status_code=404, detail=f"Product not found: {product_id}")
        avail = available_qty(product.stock_qty, product.reserved_qty)
        if qty > avail + 1e-9:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "INSUFFICIENT_AVAILABLE_STOCK",
                    "message": f"Insufficient available stock to hold {product.sku}",
                    "on_hand": float(product.stock_qty or 0),
                    "reserved": float(product.reserved_qty or 0),
                    "available": avail,
                    "requested": qty,
                    "product_id": product_id,
                },
            )
        product.reserved_qty = float(product.reserved_qty or 0) + qty
        lines.append({"product_id": product_id, "quantity": qty, "sku": product.sku})
    await db.flush()
    return lines


async def _release_soft_reserve(
    db: AsyncSession, *, tenant_id: str, row: m.PosHeldCart
) -> None:
    if not getattr(row, "stock_reserved", False):
        return
    for line in getattr(row, "reservation_lines", None) or []:
        if not isinstance(line, dict):
            continue
        product_id = str(line.get("product_id") or "").strip()
        qty = float(line.get("quantity") or 0)
        if not product_id or qty <= 0:
            continue
        product = (
            await db.execute(
                select(m.Product)
                .where(m.Product.id == product_id, m.Product.tenant_id == tenant_id)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if product:
            product.reserved_qty = max(float(product.reserved_qty or 0) - qty, 0.0)
    row.stock_reserved = False
    row.reservation_lines = []
    await db.flush()


async def create_hold(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    session_id: str | None,
    label: str | None,
    cart_payload: dict,
    reserve_stock: bool = False,
) -> m.PosHeldCart:
    if not isinstance(cart_payload, dict):
        raise HTTPException(status_code=400, detail="cart_payload must be an object")
    items = cart_payload.get("items")
    if not isinstance(items, list) or not items:
        raise HTTPException(status_code=400, detail="cart_payload.items must be a non-empty list")
    cleaned_label = (label or "Held cart").strip() or "Held cart"
    if len(cleaned_label) > 120:
        cleaned_label = cleaned_label[:120]

    reservation_lines: list[dict[str, Any]] = []
    stock_reserved = False
    if reserve_stock:
        reservation_lines = await _soft_reserve_lines(db, tenant_id=tenant_id, items=items)
        stock_reserved = True

    row = m.PosHeldCart(
        tenant_id=tenant_id,
        user_id=user_id,
        session_id=session_id,
        label=cleaned_label,
        cart_payload=cart_payload,
        status="held",
        stock_reserved=stock_reserved,
        reservation_lines=reservation_lines,
        held_at=datetime.utcnow(),
    )
    db.add(row)
    await db.flush()
    return row


async def get_hold(
    db: AsyncSession, *, tenant_id: str, user_id: str, hold_id: str
) -> m.PosHeldCart:
    row = (
        await db.execute(
            select(m.PosHeldCart).where(
                m.PosHeldCart.id == hold_id,
                m.PosHeldCart.tenant_id == tenant_id,
                m.PosHeldCart.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Held cart not found")
    return row


async def resume_hold(
    db: AsyncSession, *, tenant_id: str, user_id: str, hold_id: str
) -> m.PosHeldCart:
    row = await get_hold(db, tenant_id=tenant_id, user_id=user_id, hold_id=hold_id)
    if row.status != "held":
        raise HTTPException(status_code=409, detail=f"Held cart is {row.status}, not held")
    await _release_soft_reserve(db, tenant_id=tenant_id, row=row)
    row.status = "resumed"
    row.resumed_at = datetime.utcnow()
    await db.flush()
    return row


async def discard_hold(
    db: AsyncSession, *, tenant_id: str, user_id: str, hold_id: str
) -> m.PosHeldCart:
    row = await get_hold(db, tenant_id=tenant_id, user_id=user_id, hold_id=hold_id)
    if row.status == "discarded":
        return row
    await _release_soft_reserve(db, tenant_id=tenant_id, row=row)
    row.status = "discarded"
    row.discarded_at = datetime.utcnow()
    await db.flush()
    return row
