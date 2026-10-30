"""Restaurant till shifts: open with a float, cash in/out, count and close.

Paid restaurant orders point at the shift that took the money
(``restaurant_orders.till_shift_id``). Cash refunds leave the drawer as a
``refund`` cash move. Nothing here touches the retail ``pos_sessions`` tables.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit as audit_svc
from app import models as m
from app.honesty import money_json, optional_honest_narrative, require_honest_narrative
from app.store_access import assert_store_access

CASH_MOVE_TYPES = frozenset({"cash_in", "cash_out"})
# Paid orders that still count as takings on the shift (a refund is a separate cash move).
TAKEN_STATUSES = ("completed", "refunded")


def _now() -> datetime:
    return datetime.utcnow()


def _money(value) -> float:
    return money_json(round(float(value or 0), 2))


async def open_shift_for_user(db: AsyncSession, tenant_id: str, user_id: str | None) -> m.RestaurantTillShift | None:
    if not user_id:
        return None
    return (
        await db.execute(
            select(m.RestaurantTillShift).where(
                m.RestaurantTillShift.tenant_id == tenant_id,
                m.RestaurantTillShift.user_id == user_id,
                m.RestaurantTillShift.status == "open",
            )
        )
    ).scalar_one_or_none()


async def _shift(db: AsyncSession, tenant_id: str, shift_id: str) -> m.RestaurantTillShift:
    row = await db.get(m.RestaurantTillShift, shift_id)
    if row is None or row.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Till shift not found")
    return row


async def _next_shift_number(db: AsyncSession, tenant_id: str) -> str:
    count = (
        await db.execute(
            select(func.count()).select_from(m.RestaurantTillShift).where(m.RestaurantTillShift.tenant_id == tenant_id)
        )
    ).scalar_one()
    return f"RS-{_now().year}-{int(count or 0) + 1:04d}"


async def shift_totals(db: AsyncSession, shift: m.RestaurantTillShift) -> dict:
    """Live takings for a shift, worked out from its paid orders and cash moves."""
    rows = (
        await db.execute(
            select(m.RestaurantOrder.payment_method, func.count(), func.coalesce(func.sum(m.RestaurantOrder.total_amount), 0))
            .where(
                m.RestaurantOrder.tenant_id == shift.tenant_id,
                m.RestaurantOrder.till_shift_id == shift.id,
                m.RestaurantOrder.status.in_(TAKEN_STATUSES),
            )
            .group_by(m.RestaurantOrder.payment_method)
        )
    ).all()
    refunded = (
        await db.execute(
            select(func.coalesce(func.sum(m.RestaurantOrder.total_amount), 0)).where(
                m.RestaurantOrder.tenant_id == shift.tenant_id,
                m.RestaurantOrder.till_shift_id == shift.id,
                m.RestaurantOrder.status == "refunded",
            )
        )
    ).scalar_one()
    by_method: dict[str, float] = {}
    sale_count = 0
    for method, count, total in rows:
        key = (method or "cash").strip().lower()
        by_method[key] = _money(by_method.get(key, 0) + float(total or 0))
        sale_count += int(count or 0)
    moves = (
        await db.execute(
            select(m.RestaurantTillCashMove.movement_type, func.coalesce(func.sum(m.RestaurantTillCashMove.amount), 0))
            .where(
                m.RestaurantTillCashMove.tenant_id == shift.tenant_id,
                m.RestaurantTillCashMove.shift_id == shift.id,
            )
            .group_by(m.RestaurantTillCashMove.movement_type)
        )
    ).all()
    move_totals = {kind: float(total or 0) for kind, total in moves}
    cash_sales = by_method.get("cash", 0.0)
    cash_in = _money(move_totals.get("cash_in", 0))
    cash_out = _money(move_totals.get("cash_out", 0))
    refunds = _money(move_totals.get("refund", 0))
    total_sales = _money(sum(by_method.values()))
    expected = _money(float(shift.opening_cash or 0) + cash_sales + cash_in - cash_out - refunds)
    return {
        "sale_count": sale_count,
        "total_sales": total_sales,
        # Bills taken on this shift that were refunded later (any payment method).
        "refunded_sales": _money(refunded),
        "cash_sales": _money(cash_sales),
        "card_sales": _money(by_method.get("card", 0)),
        "mobile_money_sales": _money(by_method.get("mobile_money", 0)),
        "wallet_sales": _money(by_method.get("wallet", 0)),
        "cash_in": cash_in,
        "cash_out": cash_out,
        "cash_refunds": refunds,
        "expected_cash": expected,
    }


async def _user_name(db: AsyncSession, tenant_id: str, user_id: str | None) -> str | None:
    if not user_id:
        return None
    user = await db.get(m.User, user_id)
    if user is None or user.tenant_id != tenant_id:
        return None
    return (user.full_name or user.email or "").strip() or None


async def present_shift(db: AsyncSession, shift: m.RestaurantTillShift, *, with_moves: bool = False) -> dict:
    live = await shift_totals(db, shift)
    closed = shift.status == "closed"
    out = {
        "id": shift.id,
        "shift_number": shift.shift_number,
        "status": shift.status,
        "store_id": shift.store_id,
        "user_id": shift.user_id,
        "cashier": await _user_name(db, shift.tenant_id, shift.user_id),
        "opening_cash": _money(shift.opening_cash),
        "opened_at": shift.opened_at.isoformat() if shift.opened_at else None,
        "closed_at": shift.closed_at.isoformat() if shift.closed_at else None,
        **live,
        # A closed shift keeps what was counted at close.
        "expected_cash": _money(shift.expected_cash) if closed else live["expected_cash"],
        "counted_cash": _money(shift.actual_cash) if shift.actual_cash is not None else None,
        "variance": _money(shift.variance) if shift.variance is not None else None,
        "notes": shift.notes,
    }
    if with_moves:
        moves = (
            await db.execute(
                select(m.RestaurantTillCashMove)
                .where(
                    m.RestaurantTillCashMove.tenant_id == shift.tenant_id,
                    m.RestaurantTillCashMove.shift_id == shift.id,
                )
                .order_by(m.RestaurantTillCashMove.created_at.desc())
            )
        ).scalars()
        out["moves"] = [
            {
                "id": row.id,
                "movement_type": row.movement_type,
                "amount": _money(row.amount),
                "reason": row.reason,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in moves
        ]
    return out


async def open_shift(
    db: AsyncSession,
    tenant_id: str,
    *,
    user_id: str,
    opening_cash: float,
    store_id: str | None,
) -> m.RestaurantTillShift:
    existing = await open_shift_for_user(db, tenant_id, user_id)
    if existing is not None:
        return existing
    if store_id:
        store = await db.get(m.Store, store_id)
        if store is None or store.tenant_id != tenant_id:
            raise HTTPException(status_code=404, detail="Store not found")
        await assert_store_access(db, tenant_id=tenant_id, user_id=user_id, store_id=store_id)
    row = m.RestaurantTillShift(
        tenant_id=tenant_id,
        store_id=store_id or None,
        user_id=user_id,
        shift_number=await _next_shift_number(db, tenant_id),
        status="open",
        opening_cash=_money(opening_cash),
        opened_at=_now(),
    )
    db.add(row)
    try:
        await db.flush()
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail="A till shift is already open for you") from exc
    await audit_svc.record_event(
        db, tenant_id=tenant_id, user_id=user_id, module="restaurant",
        action="restaurant_till_shift_opened", entity="restaurant_till_shift", entity_id=row.id,
        details={"opening_cash": row.opening_cash, "shift_number": row.shift_number},
    )
    return row


def _require_open(shift: m.RestaurantTillShift) -> None:
    if shift.status != "open":
        raise HTTPException(status_code=409, detail="This till shift is closed")


def _require_own(shift: m.RestaurantTillShift, user_id: str | None) -> None:
    if shift.user_id != user_id:
        raise HTTPException(status_code=403, detail="Only the cashier on this shift can change it")


async def move_cash(
    db: AsyncSession,
    tenant_id: str,
    shift_id: str,
    *,
    user_id: str,
    movement_type: str,
    amount: float,
    reason: str,
) -> m.RestaurantTillCashMove:
    shift = await _shift(db, tenant_id, shift_id)
    _require_open(shift)
    _require_own(shift, user_id)
    kind = (movement_type or "").strip().lower()
    if kind not in CASH_MOVE_TYPES:
        raise HTTPException(status_code=400, detail="Choose cash in or cash out")
    amt = _money(amount)
    if amt <= 0:
        raise HTTPException(status_code=400, detail="Amount must be more than zero")
    text = require_honest_narrative(reason, label="Reason", min_length=3, max_length=200)
    if kind == "cash_out":
        totals = await shift_totals(db, shift)
        if amt > totals["expected_cash"] + 0.005:
            raise HTTPException(status_code=400, detail="There is not that much cash in the drawer")
    row = m.RestaurantTillCashMove(
        tenant_id=tenant_id,
        shift_id=shift.id,
        store_id=shift.store_id,
        user_id=user_id,
        movement_type=kind,
        amount=amt,
        reason=text,
        created_at=_now(),
    )
    db.add(row)
    await db.flush()
    await audit_svc.record_event(
        db, tenant_id=tenant_id, user_id=user_id, module="restaurant",
        action=f"restaurant_till_{kind}", entity="restaurant_till_shift", entity_id=shift.id,
        details={"amount": amt, "reason": text},
    )
    return row


async def close_shift(
    db: AsyncSession,
    tenant_id: str,
    shift_id: str,
    *,
    user_id: str,
    counted_cash: float,
    notes: str | None,
) -> m.RestaurantTillShift:
    shift = await _shift(db, tenant_id, shift_id)
    _require_open(shift)
    _require_own(shift, user_id)
    counted = _money(counted_cash)
    if counted < 0:
        raise HTTPException(status_code=400, detail="Counted cash cannot be negative")
    totals = await shift_totals(db, shift)
    shift.expected_cash = totals["expected_cash"]
    shift.cash_sales = totals["cash_sales"]
    shift.card_sales = totals["card_sales"]
    shift.other_sales = _money(totals["mobile_money_sales"] + totals["wallet_sales"])
    shift.total_sales = totals["total_sales"]
    shift.sale_count = totals["sale_count"]
    shift.cash_in = totals["cash_in"]
    shift.cash_out = _money(totals["cash_out"] + totals["cash_refunds"])
    shift.actual_cash = counted
    shift.variance = _money(counted - totals["expected_cash"])
    shift.notes = optional_honest_narrative(notes, label="Notes", max_length=500)
    shift.status = "closed"
    shift.closed_at = _now()
    await db.flush()
    await audit_svc.record_event(
        db, tenant_id=tenant_id, user_id=user_id, module="restaurant",
        action="restaurant_till_shift_closed", entity="restaurant_till_shift", entity_id=shift.id,
        details={
            "expected_cash": shift.expected_cash,
            "counted_cash": counted,
            "variance": shift.variance,
            "total_sales": shift.total_sales,
        },
    )
    return shift


async def list_shifts(db: AsyncSession, tenant_id: str, *, limit: int = 30) -> list[m.RestaurantTillShift]:
    return list(
        (
            await db.execute(
                select(m.RestaurantTillShift)
                .where(m.RestaurantTillShift.tenant_id == tenant_id)
                .order_by(m.RestaurantTillShift.opened_at.desc())
                .limit(limit)
            )
        ).scalars()
    )


async def stamp_paid_order(db: AsyncSession, order: m.RestaurantOrder, *, user_id: str | None) -> None:
    """Point a just-paid order at the cashier's open shift (if there is one)."""
    shift = await open_shift_for_user(db, order.tenant_id, user_id)
    if shift is not None:
        order.till_shift_id = shift.id


async def record_cash_refund(db: AsyncSession, order: m.RestaurantOrder, *, user_id: str | None) -> None:
    """A cash refund leaves a drawer: the refunder's open shift, else the open shift that took the money."""
    if (order.payment_method or "").strip().lower() != "cash":
        return
    shift = await open_shift_for_user(db, order.tenant_id, user_id)
    if shift is None and order.till_shift_id:
        taken = await db.get(m.RestaurantTillShift, order.till_shift_id)
        if taken is not None and taken.status == "open":
            shift = taken
    if shift is None:
        return
    db.add(
        m.RestaurantTillCashMove(
            tenant_id=order.tenant_id,
            shift_id=shift.id,
            store_id=shift.store_id,
            user_id=user_id or shift.user_id,
            movement_type="refund",
            amount=_money(order.total_amount),
            reason=f"Refund {order.order_number}"[:200],
            created_at=_now(),
        )
    )
    await db.flush()
