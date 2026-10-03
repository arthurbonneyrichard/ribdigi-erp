"""Loyalty points and gift cards.

One point equals one currency unit. Cards and points stay inside the tenant.
"""

from __future__ import annotations

import secrets
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.honesty import money_json, optional_honest_narrative, require_honest_narrative


def _code() -> str:
    return secrets.token_hex(4).upper()


def serialize_card(row: m.GiftCard) -> dict:
    return {
        "id": row.id,
        "code": row.code,
        "balance": money_json(row.balance or 0),
        "status": row.status,
        "issued_to_party_id": row.issued_to_party_id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


async def issue_gift_card(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str | None,
    amount: float,
    party_id: str | None = None,
) -> m.GiftCard:
    value = money_json(round(money_json(amount), 2))
    if value <= 0:
        raise HTTPException(status_code=400, detail="Gift card amount must be greater than zero")
    row = m.GiftCard(
        tenant_id=tenant_id,
        code=_code(),
        balance=value,
        status="active",
        issued_to_party_id=party_id,
        created_by=user_id,
        created_at=datetime.utcnow(),
    )
    db.add(row)
    await db.flush()
    return row


async def get_gift_card(db: AsyncSession, *, tenant_id: str, code: str) -> m.GiftCard:
    key = (code or "").strip().upper()
    if not key:
        raise HTTPException(status_code=400, detail="Gift card code is required")
    row = (
        await db.execute(
            select(m.GiftCard).where(m.GiftCard.tenant_id == tenant_id, m.GiftCard.code == key)
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Gift card not found")
    return row


async def _customer(db: AsyncSession, tenant_id: str, party_id: str) -> m.Party:
    row = (
        await db.execute(
            select(m.Party).where(m.Party.id == party_id, m.Party.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Customer not found")
    return row


async def adjust_loyalty(
    db: AsyncSession,
    *,
    tenant_id: str,
    party_id: str,
    delta: float,
) -> m.Party:
    party = await _customer(db, tenant_id, party_id)
    nxt = money_json(round(money_json(party.loyalty_points or 0) + money_json(delta), 2))
    if nxt < -1e-9:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "INSUFFICIENT_LOYALTY",
                "message": "Not enough loyalty points",
                "available": money_json(party.loyalty_points or 0),
            },
        )
    party.loyalty_points = nxt
    await db.flush()
    return party


async def settle_pos_tenders(
    db: AsyncSession,
    *,
    tenant_id: str,
    party_id: str | None,
    payments: list[dict],
) -> None:
    """Spend gift-card balance and loyalty points for tenders already on the sale."""
    for pay in payments:
        method = pay.get("payment_method")
        amount = money_json(pay.get("amount") or 0)
        if method == "gift_card":
            code = pay.get("reference") or ""
            card = await get_gift_card(db, tenant_id=tenant_id, code=str(code))
            if card.status != "active":
                raise HTTPException(status_code=409, detail="Gift card is not active")
            if money_json(card.balance or 0) + 1e-9 < amount:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "INSUFFICIENT_GIFT_CARD",
                        "message": "Gift card balance is too low",
                        "available": money_json(card.balance or 0),
                    },
                )
            card.balance = money_json(round(money_json(card.balance or 0) - amount, 2))
            if card.balance <= 1e-9:
                card.balance = 0
                card.status = "redeemed"
        elif method == "loyalty":
            if not party_id:
                raise HTTPException(status_code=400, detail="Select a customer to spend loyalty points")
            await adjust_loyalty(db, tenant_id=tenant_id, party_id=party_id, delta=-amount)
    await db.flush()


async def award_sale_points(
    db: AsyncSession,
    *,
    tenant_id: str,
    party_id: str | None,
    total: float,
    payments: list[dict],
) -> float:
    if not party_id:
        return 0
    spent = sum(money_json(p.get("amount") or 0) for p in payments if p.get("payment_method") == "loyalty")
    earn = money_json(round(max(money_json(total) - spent, 0), 2))
    if earn <= 0:
        return 0
    party = await adjust_loyalty(db, tenant_id=tenant_id, party_id=party_id, delta=earn)
    return money_json(party.loyalty_points or 0)


def notice_payload(row: m.CheckoutPaymentNotice) -> dict:
    return {
        "id": row.id,
        "amount": money_json(row.amount),
        "method": row.method,
        "reference": row.reference,
        "note": row.note,
        "funds_captured": False,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


async def record_payment_notice(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str | None,
    amount: float,
    method: str,
    reference: str,
    note: str | None,
) -> m.CheckoutPaymentNotice:
    value = money_json(round(money_json(amount), 2))
    if value <= 0:
        raise HTTPException(status_code=400, detail="Amount must be greater than zero")
    ref = require_honest_narrative(reference, label="payment reference", max_length=100)
    method_s = (method or "").strip().lower()
    if method_s not in {"cash", "card", "bank_transfer", "wallet", "other"}:
        raise HTTPException(status_code=400, detail="Unsupported payment method")
    row = m.CheckoutPaymentNotice(
        tenant_id=tenant_id,
        amount=value,
        method=method_s,
        reference=ref,
        note=optional_honest_narrative(note, label="payment note"),
        funds_captured=False,
        created_by=user_id,
        created_at=datetime.utcnow(),
    )
    db.add(row)
    await db.flush()
    return row
