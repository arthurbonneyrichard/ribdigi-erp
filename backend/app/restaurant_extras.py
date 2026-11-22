"""Restaurant floor extras: manager discounts and comps, the guest on a bill (loyalty), gift cards,
guest feedback, and delivery riders.

Money rules in one place:
- A discount or comp lowers the bill before tax and service are worked out (see
  restaurant._bill_amounts), so revenue is booked net and the tax stays right. A comp still books
  what the food cost.
- A gift card sold for money is a liability (2150), never revenue; spending it later moves 2150 to sales.
- Loyalty points are 1 point = 1 currency unit, kept on the customer (loyalty_gift.py).
"""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import accounting
from app import audit as audit_svc
from app import models as m
from app import restaurant as rs
from app import restaurant_till as till_svc
from app.honesty import money_json, optional_honest_narrative, require_honest_narrative

GIFT_SALE_METHODS = ("cash", "card", "mobile_money", "wallet")


def _now() -> datetime:
    return datetime.utcnow()


async def _open_order(db: AsyncSession, tenant_id: str, order_id: str, user_id: str | None) -> m.RestaurantOrder:
    order = await rs._order(db, tenant_id, order_id, user_id=user_id)
    if order.status not in rs.OPEN_STATUSES:
        raise HTTPException(status_code=409, detail="Only an open bill can be changed")
    return order


# ---------------------------------------------------------------- discounts and comps


async def set_discount(
    db: AsyncSession,
    tenant_id: str,
    order_id: str,
    *,
    kind: str,
    value: float,
    reason: str | None,
    user_id: str | None,
) -> m.RestaurantOrder:
    """Put a percent, an amount, or a full comp on an open bill; kind "clear" takes it off.

    Who may do this is decided by the restaurant job gate: waiters and cashiers are refused, so only a
    manager (or company admin) can discount or comp.
    """
    order = await _open_order(db, tenant_id, order_id, user_id)
    kind = (kind or "").strip().lower()
    before = money_json(order.discount_amount or 0)
    if kind == "clear":
        order.discount_kind = None
        order.discount_value = 0
        order.discount_reason = None
        order.discount_by = None
    else:
        if kind not in {"percent", "amount", "comp"}:
            raise HTTPException(status_code=422, detail="Choose percent, amount or comp")
        text = require_honest_narrative(reason, label="Reason", min_length=3, max_length=200)
        if kind == "comp":
            kind, value = "percent", 100.0
        amount = money_json(value)
        if amount <= 0:
            raise HTTPException(status_code=422, detail="The discount must be more than zero")
        if kind == "percent" and amount > 100:
            raise HTTPException(status_code=422, detail="A percent discount cannot be more than 100")
        order.discount_kind = kind
        order.discount_value = amount
        order.discount_reason = text
        order.discount_by = user_id
    await rs._refresh_order_totals(db, order)
    if kind != "clear" and money_json(order.discount_amount or 0) <= 0:
        raise HTTPException(status_code=409, detail="There is nothing on the bill to discount yet")
    await audit_svc.record_event(
        db, tenant_id=tenant_id, user_id=user_id, module="restaurant",
        action="restaurant_discount_cleared" if kind == "clear" else "restaurant_discount_applied",
        entity="restaurant_order", entity_id=order.id,
        details={
            "order": order.order_number, "kind": order.discount_kind, "value": money_json(order.discount_value or 0),
            "discount": money_json(order.discount_amount or 0), "was": before, "reason": order.discount_reason,
        },
    )
    return order


# ---------------------------------------------------------------- the guest on a bill


def _guest_payload(party: m.Party | None) -> dict | None:
    if party is None:
        return None
    return {
        "party_id": party.id,
        "name": party.name,
        "phone": party.phone,
        "loyalty_points": money_json(party.loyalty_points or 0),
    }


async def attach_guest(
    db: AsyncSession, tenant_id: str, order_id: str, *, phone: str, name: str | None, user_id: str | None
) -> dict:
    """Find the customer with this phone (or make one) and put them on the bill, to earn and spend points."""
    order = await _open_order(db, tenant_id, order_id, user_id)
    number = rs.clean_phone(phone)
    party = (
        await db.execute(
            select(m.Party).where(m.Party.tenant_id == tenant_id, m.Party.kind == "customer", m.Party.phone == number).limit(1)
        )
    ).scalar_one_or_none()
    if party is None:
        text = optional_honest_narrative(name, label="Guest name", max_length=180) if name else None
        party = m.Party(
            tenant_id=tenant_id, kind="customer", name=text or order.customer_name or number, phone=number,
            profile_type="registered", status="active",
        )
        db.add(party)
        await db.flush()
    order.party_id = party.id
    if not order.customer_name:
        order.customer_name = party.name
    await db.flush()
    await audit_svc.record_event(
        db, tenant_id=tenant_id, user_id=user_id, module="restaurant",
        action="restaurant_guest_attached", entity="restaurant_order", entity_id=order.id,
        details={"order": order.order_number, "guest": party.name},
    )
    return _guest_payload(party) or {}


async def guest_for_order(db: AsyncSession, tenant_id: str, order_id: str, user_id: str | None) -> dict | None:
    order = await rs._order(db, tenant_id, order_id, user_id=user_id)
    if not order.party_id:
        return None
    party = await db.get(m.Party, order.party_id)
    if party is None or party.tenant_id != tenant_id:
        return None
    return _guest_payload(party)


# ---------------------------------------------------------------- gift cards


def serialize_card(row: m.GiftCard) -> dict:
    return {
        "id": row.id,
        "code": row.code,
        "balance": money_json(row.balance or 0),
        "status": row.status,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


async def sell_gift_card(
    db: AsyncSession, tenant_id: str, *, amount: float, method: str, buyer: str | None, user_id: str | None
) -> m.GiftCard:
    """Sell a gift card for money. The money is a liability until the card is spent."""
    from app import loyalty_gift

    value = money_json(round(money_json(amount), 2))
    if value <= 0:
        raise HTTPException(status_code=422, detail="The gift card amount must be more than zero")
    method = (method or "").strip().lower()
    if method not in GIFT_SALE_METHODS:
        raise HTTPException(status_code=422, detail="Choose cash, card, Mobile Money or wallet")
    who = optional_honest_narrative(buyer, label="Buyer", max_length=120) if buyer else None
    shift = None
    if method == "cash":
        shift = await till_svc.open_shift_for_user(db, tenant_id, user_id)
        if shift is None:
            raise HTTPException(status_code=409, detail="Open your till shift first, so the cash is counted in your drawer")
    await accounting.ensure_default_accounts(db, tenant_id)
    card = m.GiftCard(
        tenant_id=tenant_id, code=loyalty_gift._code(), balance=value, status="active",
        created_by=user_id, created_at=_now(),
    )
    db.add(card)
    await db.flush()
    debit_code, _label = accounting.pos_debit_account_for_payment_method(method)
    description = f"Gift card {card.code} sold" + (f" to {who}" if who else "")
    await accounting.post_journal_entry(
        db, tenant_id=tenant_id, user_id=user_id, description=description, reference=card.code,
        source_type="restaurant_gift_card_sale", source_id=card.id,
        lines=[
            {"account_code": debit_code, "debit": value, "credit": 0, "description": description},
            {"account_code": "2150", "debit": 0, "credit": value, "description": "Gift card liability"},
        ],
    )
    if shift is not None:
        db.add(
            m.RestaurantTillCashMove(
                tenant_id=tenant_id, shift_id=shift.id, store_id=shift.store_id, user_id=user_id,
                movement_type="cash_in", amount=value, reason=f"Gift card {card.code} sold", created_at=_now(),
            )
        )
    await db.flush()
    await audit_svc.record_event(
        db, tenant_id=tenant_id, user_id=user_id, module="restaurant",
        action="restaurant_gift_card_sold", entity="gift_card", entity_id=card.id,
        details={"code": card.code, "amount": value, "method": method},
    )
    return card


async def list_gift_cards(db: AsyncSession, tenant_id: str) -> list[dict]:
    rows = (
        await db.execute(
            select(m.GiftCard).where(m.GiftCard.tenant_id == tenant_id).order_by(m.GiftCard.created_at.desc()).limit(200)
        )
    ).scalars().all()
    return [serialize_card(r) for r in rows]


async def check_gift_card(db: AsyncSession, tenant_id: str, code: str) -> dict:
    from app import loyalty_gift

    return serialize_card(await loyalty_gift.get_gift_card(db, tenant_id=tenant_id, code=code))


# ---------------------------------------------------------------- feedback


async def add_feedback(
    db: AsyncSession,
    tenant_id: str,
    *,
    rating: int,
    comment: str | None,
    guest_name: str | None,
    order_id: str | None,
    order_number: str | None,
    source: str,
    user_id: str | None,
) -> m.RestaurantFeedback:
    if rating < 1 or rating > 5:
        raise HTTPException(status_code=422, detail="Rating must be 1 to 5")
    text = optional_honest_narrative(comment, label="Comment", max_length=1000) if comment else None
    who = optional_honest_narrative(guest_name, label="Guest name", max_length=180) if guest_name else None
    order = None
    if order_id:
        order = await db.get(m.RestaurantOrder, order_id)
    elif order_number:
        order = (
            await db.execute(
                select(m.RestaurantOrder).where(
                    m.RestaurantOrder.tenant_id == tenant_id, m.RestaurantOrder.order_number == order_number.strip()
                )
            )
        ).scalar_one_or_none()
        if order is None:
            raise HTTPException(status_code=404, detail="No order with that number")
    if order is not None and order.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Order not found")
    row = m.RestaurantFeedback(
        tenant_id=tenant_id, order_id=order.id if order else None, order_number=order.order_number if order else None,
        guest_name=who or (order.customer_name if order else None), rating=rating, comment=text,
        source=source, created_by=user_id, created_at=_now(),
    )
    db.add(row)
    await db.flush()
    return row


def serialize_feedback(row: m.RestaurantFeedback) -> dict:
    return {
        "id": row.id,
        "order_number": row.order_number,
        "guest_name": row.guest_name,
        "rating": row.rating,
        "comment": row.comment,
        "source": row.source,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


async def feedback_board(db: AsyncSession, tenant_id: str) -> dict:
    rows = (
        await db.execute(
            select(m.RestaurantFeedback)
            .where(m.RestaurantFeedback.tenant_id == tenant_id)
            .order_by(m.RestaurantFeedback.created_at.desc())
            .limit(100)
        )
    ).scalars().all()
    count, avg = (
        await db.execute(
            select(func.count(m.RestaurantFeedback.id), func.avg(m.RestaurantFeedback.rating)).where(
                m.RestaurantFeedback.tenant_id == tenant_id
            )
        )
    ).one()
    by_rating = {str(n): 0 for n in range(1, 6)}
    for rating, n in (
        await db.execute(
            select(m.RestaurantFeedback.rating, func.count(m.RestaurantFeedback.id))
            .where(m.RestaurantFeedback.tenant_id == tenant_id)
            .group_by(m.RestaurantFeedback.rating)
        )
    ).all():
        by_rating[str(rating)] = int(n)
    return {
        "count": int(count or 0),
        "average": round(float(avg), 2) if avg is not None else None,
        "by_rating": by_rating,
        "items": [serialize_feedback(r) for r in rows],
    }


async def site_feedback(db: AsyncSession, tenant_id: str, order_id: str, *, rating: int, comment: str | None) -> None:
    """A guest rates their online order once it is done."""
    order = await db.get(m.RestaurantOrder, order_id)
    if order is None or order.tenant_id != tenant_id or not rs.channel_for_order(order.notes):
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status != "completed":
        raise HTTPException(status_code=409, detail="You can rate your order once it is done")
    taken = (
        await db.execute(
            select(m.RestaurantFeedback.id).where(
                m.RestaurantFeedback.tenant_id == tenant_id, m.RestaurantFeedback.order_id == order.id
            ).limit(1)
        )
    ).scalar_one_or_none()
    if taken is not None:
        raise HTTPException(status_code=409, detail="Thank you, this order is already rated")
    await add_feedback(
        db, tenant_id, rating=rating, comment=comment, guest_name=None, order_id=order.id, order_number=None,
        source="website", user_id=None,
    )


async def feedback_given(db: AsyncSession, tenant_id: str, order_id: str) -> bool:
    return (
        await db.execute(
            select(m.RestaurantFeedback.id).where(
                m.RestaurantFeedback.tenant_id == tenant_id, m.RestaurantFeedback.order_id == order_id
            ).limit(1)
        )
    ).scalar_one_or_none() is not None


# ---------------------------------------------------------------- delivery riders


async def _delivery_order(db: AsyncSession, tenant_id: str, order_id: str, user_id: str | None) -> m.RestaurantOrder:
    order = await rs._order(db, tenant_id, order_id, user_id=user_id)
    if order.service_mode != "delivery":
        raise HTTPException(status_code=409, detail="Only a delivery order has a rider")
    if order.status in {"cancelled", "voided", "refunded"}:
        raise HTTPException(status_code=409, detail="This order is closed")
    return order


async def assign_rider(
    db: AsyncSession, tenant_id: str, order_id: str, *, name: str, phone: str | None, user_id: str | None
) -> m.RestaurantOrder:
    order = await _delivery_order(db, tenant_id, order_id, user_id)
    if order.delivery_status in {"out", "delivered"}:
        raise HTTPException(status_code=409, detail="The order has already left. Mark it delivered instead")
    order.rider_name = require_honest_narrative(name, label="Rider name", min_length=2, max_length=120)
    order.rider_phone = rs.clean_phone(phone) if phone else None
    order.delivery_status = "assigned"
    await db.flush()
    await audit_svc.record_event(
        db, tenant_id=tenant_id, user_id=user_id, module="restaurant",
        action="restaurant_rider_assigned", entity="restaurant_order", entity_id=order.id,
        details={"order": order.order_number, "rider": order.rider_name},
    )
    return order


async def dispatch_order(db: AsyncSession, tenant_id: str, order_id: str, *, user_id: str | None) -> m.RestaurantOrder:
    order = await _delivery_order(db, tenant_id, order_id, user_id)
    if not order.rider_name:
        raise HTTPException(status_code=409, detail="Assign a rider first")
    if order.delivery_status == "delivered":
        raise HTTPException(status_code=409, detail="This order was already delivered")
    if order.status not in {"ready", "completed"}:
        raise HTTPException(status_code=409, detail="The kitchen has not marked this order ready yet")
    order.delivery_status = "out"
    order.dispatched_at = _now()
    await db.flush()
    await audit_svc.record_event(
        db, tenant_id=tenant_id, user_id=user_id, module="restaurant",
        action="restaurant_order_dispatched", entity="restaurant_order", entity_id=order.id,
        details={"order": order.order_number, "rider": order.rider_name},
    )
    return order


async def deliver_order(db: AsyncSession, tenant_id: str, order_id: str, *, user_id: str | None) -> m.RestaurantOrder:
    order = await _delivery_order(db, tenant_id, order_id, user_id)
    if order.delivery_status != "out":
        raise HTTPException(status_code=409, detail="Send the order out with the rider first")
    order.delivery_status = "delivered"
    order.delivered_at = _now()
    await db.flush()
    await audit_svc.record_event(
        db, tenant_id=tenant_id, user_id=user_id, module="restaurant",
        action="restaurant_order_delivered", entity="restaurant_order", entity_id=order.id,
        details={"order": order.order_number, "rider": order.rider_name},
    )
    return order
