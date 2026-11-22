"""Gym trainer commissions.

A trainer has a commission percent. When a training session is marked completed, the trainer earns
that percent of the session price listed on their profile, once per session. The listed price is
used whether or not the session was charged at the till (charging a session is not wired to the
till yet), so a manager should set the percent knowing that.

This is an accrual record, not payroll. Paying it is a manager's act: `pay` marks the accrued
amount in a date range as paid with the reference of the payroll or transfer that settled it. It
does not post to the books or to the HRM payroll, so the same pay is never counted twice by two
systems; hand the report to payroll. A trainer is matched to their HRM record through their linked
login, which the trainer portal already uses.
"""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.gym import _audit, _money
from app.honesty import optional_honest_narrative, require_honest_narrative


def _amount(price, pct) -> float:
    return float((Decimal(str(price or 0)) * Decimal(str(pct or 0)) / Decimal(100)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


async def accrue_for_session(db: AsyncSession, tenant_id: str, session: m.GymTrainingSession) -> m.GymCommission | None:
    """Called once when a session becomes completed. Safe to call twice: one row per session."""
    trainer = await db.get(m.GymTrainer, session.trainer_id)
    if trainer is None or float(trainer.commission_pct or 0) <= 0 or float(trainer.session_price or 0) <= 0:
        return None
    if (await db.execute(select(m.GymCommission.id).where(m.GymCommission.session_id == session.id))).first():
        return None
    row = m.GymCommission(
        tenant_id=tenant_id, trainer_id=trainer.id, session_id=session.id, session_price=_money(trainer.session_price),
        percent=float(trainer.commission_pct), amount=_amount(trainer.session_price, trainer.commission_pct), earned_on=date.today(),
    )
    db.add(row)
    await db.flush()
    return row


async def set_percent(db: AsyncSession, tenant_id: str, trainer_id: str, percent: float, *, user_id) -> dict:
    trainer = await db.get(m.GymTrainer, trainer_id)
    if trainer is None or trainer.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Trainer not found")
    trainer.commission_pct = round(float(percent), 2)
    await db.flush()
    await _audit(db, tenant_id, user_id, "gym_trainer_commission_set", "gym_trainer", trainer.id, {"percent": float(trainer.commission_pct)})
    return {"trainer_id": trainer.id, "commission_pct": float(trainer.commission_pct)}


async def report(db: AsyncSession, tenant_id: str, *, start: date, end: date, trainer_id: str | None = None) -> dict:
    stmt = (
        select(m.GymCommission.trainer_id, m.GymTrainer.full_name, m.GymCommission.status, func.count(), func.sum(m.GymCommission.amount))
        .join(m.GymTrainer, m.GymTrainer.id == m.GymCommission.trainer_id)
        .where(m.GymCommission.tenant_id == tenant_id, m.GymCommission.earned_on >= start, m.GymCommission.earned_on <= end)
        .group_by(m.GymCommission.trainer_id, m.GymTrainer.full_name, m.GymCommission.status)
    )
    if trainer_id:
        stmt = stmt.where(m.GymCommission.trainer_id == trainer_id)
    people: dict[str, dict] = {}
    for tid, name, status, n, total in (await db.execute(stmt)).all():
        p = people.setdefault(tid, {"trainer_id": tid, "trainer": name, "sessions": 0, "accrued": 0.0, "paid": 0.0})
        p["sessions"] += int(n)
        p[status] = round(p[status] + float(total or 0), 2)
    rows = sorted(people.values(), key=lambda r: r["trainer"])
    return {
        "start_date": start.isoformat(), "end_date": end.isoformat(), "trainers": rows,
        "total_accrued": round(sum(r["accrued"] for r in rows), 2), "total_paid": round(sum(r["paid"] for r in rows), 2),
    }


async def pay(db: AsyncSession, tenant_id: str, trainer_id: str, *, start: date, end: date, reference: str, user_id) -> dict:
    ref = require_honest_narrative(reference, label="reference", max_length=100)
    trainer = await db.get(m.GymTrainer, trainer_id)
    if trainer is None or trainer.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Trainer not found")
    rows = (
        await db.execute(
            select(m.GymCommission)
            .where(
                m.GymCommission.tenant_id == tenant_id, m.GymCommission.trainer_id == trainer.id, m.GymCommission.status == "accrued",
                m.GymCommission.earned_on >= start, m.GymCommission.earned_on <= end,
            )
            .with_for_update()
        )
    ).scalars().all()
    if not rows:
        raise HTTPException(status_code=409, detail="Nothing is owed to this trainer in that period")
    total = 0.0
    for r in rows:
        r.status, r.paid_on, r.pay_reference = "paid", date.today(), ref
        total += float(r.amount)
    await db.flush()
    await _audit(db, tenant_id, user_id, "gym_commission_paid", "gym_trainer", trainer.id, {"total": round(total, 2), "sessions": len(rows), "reference": ref})
    return {"trainer_id": trainer.id, "sessions": len(rows), "paid": round(total, 2), "reference": ref}


async def accrued_for_trainer(db: AsyncSession, tenant_id: str, trainer_id: str) -> float:
    total = (
        await db.execute(
            select(func.sum(m.GymCommission.amount)).where(m.GymCommission.tenant_id == tenant_id, m.GymCommission.trainer_id == trainer_id, m.GymCommission.status == "accrued")
        )
    ).scalar_one()
    return round(float(total or 0), 2)
