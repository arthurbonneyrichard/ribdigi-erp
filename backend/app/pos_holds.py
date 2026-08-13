"""POS Hold/Resume — Stage 165 H1 Partial online cart park (no stock reservation)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m

ALLOWED_STATUS = {"held", "resumed", "discarded"}


def serialize_hold(row: m.PosHeldCart) -> dict[str, Any]:
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
        "stock_reserved": False,
        "message": "Held cart park only — stock is not reserved (Stage 165 H1 Partial).",
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


async def create_hold(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    session_id: str | None,
    label: str | None,
    cart_payload: dict,
) -> m.PosHeldCart:
    if not isinstance(cart_payload, dict):
        raise HTTPException(status_code=400, detail="cart_payload must be an object")
    items = cart_payload.get("items")
    if not isinstance(items, list) or not items:
        raise HTTPException(status_code=400, detail="cart_payload.items must be a non-empty list")
    cleaned_label = (label or "Held cart").strip() or "Held cart"
    if len(cleaned_label) > 120:
        cleaned_label = cleaned_label[:120]
    row = m.PosHeldCart(
        tenant_id=tenant_id,
        user_id=user_id,
        session_id=session_id,
        label=cleaned_label,
        cart_payload=cart_payload,
        status="held",
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
    row.status = "discarded"
    row.discarded_at = datetime.utcnow()
    await db.flush()
    return row
