"""Leave encashment: unused annual leave paid as money instead of time off.

HR picks a person, a leave year and a number of days (no more than they have left). The
amount is fixed when it is approved: basic salary on that day / working days a month × days.
The days come off the person's annual leave for that year straight away. The chosen month's
payroll pays it as a taxable earning without SSNIT (an accountant should confirm this
treatment). Until a payroll takes it, it can be cancelled and the days come back.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.honesty import money_json, optional_honest_narrative

ZERO = Decimal("0")


def D(value) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value or 0))


def day_rate(basic, working_days: int) -> Decimal:
    return (D(basic) / Decimal(max(int(working_days or 0), 1))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


async def encashed_days(db: AsyncSession, employee_id: str, year: int) -> int:
    rows = (
        await db.execute(
            select(m.HrmLeaveEncashment.days).where(
                m.HrmLeaveEncashment.employee_id == employee_id, m.HrmLeaveEncashment.year == year,
                m.HrmLeaveEncashment.status.in_(("approved", "paid")),
            )
        )
    ).scalars().all()
    return sum(int(d or 0) for d in rows)


def serialize(row: m.HrmLeaveEncashment, person: m.HrmEmployee | None) -> dict:
    return {
        "id": row.id, "employee_id": row.employee_id, "employee_name": person.full_name if person else None,
        "year": row.year, "days": row.days, "day_rate": money_json(row.day_rate), "amount": money_json(row.amount),
        "period": row.period, "status": row.status, "note": row.note, "on_payroll": bool(row.run_id),
    }


async def list_all(db: AsyncSession, tenant_id: str) -> list[dict]:
    rows = (
        await db.execute(
            select(m.HrmLeaveEncashment).where(m.HrmLeaveEncashment.tenant_id == tenant_id).order_by(m.HrmLeaveEncashment.created_at.desc())
        )
    ).scalars().all()
    return [serialize(r, await db.get(m.HrmEmployee, r.employee_id)) for r in rows]


async def approve(db: AsyncSession, tenant_id: str, payload, *, user_id) -> m.HrmLeaveEncashment:
    from app import hrm, hrm_pay_changes

    person = await hrm._employee(db, tenant_id, payload.employee_id)
    me = await hrm._user_employee(db, tenant_id, user_id)
    if me is not None and me.id == person.id:
        raise HTTPException(status_code=403, detail="Someone else must approve paying out your own leave")
    if payload.year > date.today().year:
        raise HTTPException(status_code=422, detail="That leave year has not started")
    balance = await hrm.leave_balance(db, tenant_id, person.id, year=payload.year)
    if payload.days > balance["left"]:
        raise HTTPException(status_code=409, detail=f"Only {max(balance['left'], 0)} annual leave days are left for {payload.year}")
    settings = await hrm.get_settings(db, tenant_id)
    basic, _allowances = await hrm_pay_changes.salary_for(db, person, date.today())
    rate = day_rate(basic, settings.working_days_per_month)
    amount = (rate * Decimal(payload.days)).quantize(Decimal("0.01"))
    row = m.HrmLeaveEncashment(
        tenant_id=tenant_id, employee_id=person.id, year=payload.year, days=payload.days, day_rate=rate,
        amount=amount, period=payload.period, status="approved",
        note=optional_honest_narrative(payload.note, label="note", max_length=255), approved_by=user_id,
    )
    db.add(row)
    await db.flush()
    await hrm._audit(
        db, tenant_id, user_id, "hrm_leave_encashed", "hrm_leave_encashment", row.id,
        {"employee_id": person.id, "year": row.year, "days": row.days, "amount": money_json(amount), "period": row.period},
    )
    return row


async def cancel(db: AsyncSession, tenant_id: str, row_id: str, *, user_id) -> m.HrmLeaveEncashment:
    from app import hrm

    row = await db.get(m.HrmLeaveEncashment, row_id)
    if row is None or row.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Leave payout not found")
    if row.status != "approved" or row.run_id:
        raise HTTPException(status_code=409, detail="A payroll already holds this payout")
    row.status = "cancelled"
    await db.flush()
    await hrm._audit(db, tenant_id, user_id, "hrm_leave_encashment_cancelled", "hrm_leave_encashment", row.id, {"days": row.days})
    return row


# --- Payroll hooks -------------------------------------------------------------------------


async def take(db: AsyncSession, employee_id: str, period: str, run_id: str) -> Decimal:
    rows = (
        await db.execute(
            select(m.HrmLeaveEncashment).where(
                m.HrmLeaveEncashment.employee_id == employee_id, m.HrmLeaveEncashment.period == period,
                m.HrmLeaveEncashment.status == "approved", m.HrmLeaveEncashment.run_id.is_(None),
            )
        )
    ).scalars().all()
    total = ZERO
    for row in rows:
        row.run_id = run_id
        total += D(row.amount)
    return total


async def release(db: AsyncSession, run_id: str) -> None:
    for row in (await db.execute(select(m.HrmLeaveEncashment).where(m.HrmLeaveEncashment.run_id == run_id))).scalars():
        if row.status == "approved":
            row.run_id = None


async def settle(db: AsyncSession, run_id: str) -> None:
    for row in (await db.execute(select(m.HrmLeaveEncashment).where(m.HrmLeaveEncashment.run_id == run_id))).scalars():
        row.status = "paid"
        row.paid_at = datetime.utcnow()
