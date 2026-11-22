"""Gym fees taken at the till: a guest's entry fee and a locker rental.

Same money rules as selling a plan: needs an open till, the fee is booked as revenue the day it is
taken (net to 4000, tax to 2100, money to the account for how they paid), and every movement is a
row in `gym_payments`. A fee of 0 moves no money and needs no till or method.
"""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.gym import _audit, _method, _money, _money_account, _need_shift, _post, _split_tax


async def take_fee(
    db: AsyncSession, tenant_id: str, *, amount: float, method: str | None, kind: str, description: str,
    reference: str, source_id: str, member_id: str | None, user_id,
) -> float:
    """Book one fee and return the amount taken (0 when free)."""
    amount = _money(amount)
    if amount <= 0:
        return 0.0
    if not method:
        raise HTTPException(status_code=422, detail="Choose how they paid")
    how = _method(method)
    shift = await _need_shift(db, tenant_id)
    net, tax, gross = await _split_tax(db, tenant_id, amount)
    lines = [
        {"account_code": _money_account(how), "debit": gross, "credit": 0, "description": description},
        {"account_code": "4000", "debit": 0, "credit": net, "description": description},
    ]
    if tax > 0:
        lines.append({"account_code": "2100", "debit": 0, "credit": tax, "description": description})
    await _post(db, tenant_id, user_id=user_id, description=description, lines=lines, reference=reference, source=kind, source_id=source_id)
    db.add(m.GymPayment(tenant_id=tenant_id, shift_id=shift.id, kind=kind, method=how, amount=gross, member_id=member_id, created_by=user_id))
    await _audit(db, tenant_id, user_id, f"{kind}_taken", "gym_payment", source_id, {"total": gross, "method": how})
    return gross
