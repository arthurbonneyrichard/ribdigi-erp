"""Weekly and fortnightly pay, on a monthly payroll.

Ghana PAYE and SSNIT are worked out and filed by the month, so the month's payroll stays the
one place they are calculated. Staff paid weekly or fortnightly get **part-payments** during
the month: each is booked like a salary advance (debit 1150 Staff Loans and Advances, credit
cash, bank or Mobile Money) and the same month's payroll takes them back in full, after PAYE
and SSNIT on the whole month. A part-payment never takes the payslip below nil: anything the
month's pay cannot cover stays as an advance for the next payroll, as any advance would.

The suggested amount is the person's basic for the week (basic × 12 ÷ 52) or fortnight
(× 12 ÷ 26) times the company's part-pay percent (default 80%), leaving room for tax,
SSNIT and other deductions at month end. HR can change any amount before paying.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import accounting
from app import models as m
from app.honesty import money_json

KIND = "part_pay"
PER_YEAR = {"weekly": Decimal(52), "fortnightly": Decimal(26)}
CENT = Decimal("0.01")


def D(value) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value or 0))


def suggested(basic, frequency: str, percent) -> Decimal:
    per = PER_YEAR.get(frequency)
    if per is None:
        return Decimal(0)
    return (D(basic) * 12 / per * D(percent) / 100).quantize(CENT, rounding=ROUND_HALF_UP)


async def _locked_month(db: AsyncSession, tenant_id: str, period: str) -> str | None:
    run = (
        await db.execute(select(m.HrmPayrollRun.status).where(m.HrmPayrollRun.tenant_id == tenant_id, m.HrmPayrollRun.period == period))
    ).scalar_one_or_none()
    return run


async def sheet(db: AsyncSession, tenant_id: str, paid_on: date) -> dict:
    """Who is paid weekly or fortnightly, the suggested amount, and what they have had this month."""
    from app import hrm, hrm_pay_changes

    settings = await hrm.get_settings(db, tenant_id)
    percent = D(getattr(settings, "part_pay_percent", 80) if getattr(settings, "part_pay_percent", None) is not None else 80)
    period = paid_on.strftime("%Y-%m")
    rows = []
    for person in await hrm.list_employees(db, tenant_id):
        freq = getattr(person, "pay_frequency", None) or "monthly"
        if freq == "monthly":
            continue
        basic, _ = await hrm_pay_changes.salary_for(db, person, paid_on)
        already = (
            await db.execute(
                select(m.HrmLoan).where(
                    m.HrmLoan.employee_id == person.id, m.HrmLoan.kind == KIND, m.HrmLoan.first_period == period,
                    m.HrmLoan.status.in_(("active", "settled")),
                )
            )
        ).scalars().all()
        rows.append(
            {
                "employee_id": person.id, "name": person.full_name, "frequency": freq,
                "suggested": money_json(suggested(basic, freq, percent)),
                "paid_this_month": money_json(sum((D(r.principal) for r in already), Decimal(0))),
                "paid_on_this_day": any(r.paid_out_at and r.paid_out_at.date() == paid_on for r in already),
            }
        )
    return {"period": period, "percent": money_json(percent), "payroll": await _locked_month(db, tenant_id, period), "people": rows}


async def pay(db: AsyncSession, tenant_id: str, payload, *, user_id) -> dict:
    from app import hrm

    period = payload.paid_on.strftime("%Y-%m")
    state = await _locked_month(db, tenant_id, period)
    if state is not None:
        raise HTTPException(
            status_code=409,
            detail=f"The {period} payroll is already drawn up ({state}). Pay part-payments before the month's payroll, or throw the draft away first.",
        )
    if payload.method not in hrm.METHODS:
        raise HTTPException(status_code=422, detail="Choose how they were paid")
    me = await hrm._user_employee(db, tenant_id, user_id)
    lines = [(line.employee_id, D(line.amount)) for line in payload.lines if D(line.amount) > 0]
    if not lines:
        raise HTTPException(status_code=422, detail="Enter at least one amount")
    total = Decimal(0)
    made = []
    for employee_id, amount in lines:
        person = await hrm._employee(db, tenant_id, employee_id)
        if me is not None and me.id == person.id:
            raise HTTPException(status_code=403, detail="Someone else must pay your own wages")
        if (getattr(person, "pay_frequency", None) or "monthly") == "monthly":
            raise HTTPException(status_code=422, detail=f"{person.full_name} is paid monthly")
        twice = (
            await db.execute(
                select(m.HrmLoan.id, m.HrmLoan.paid_out_at).where(
                    m.HrmLoan.employee_id == person.id, m.HrmLoan.kind == KIND, m.HrmLoan.first_period == period,
                    m.HrmLoan.status.in_(("active", "settled")),
                )
            )
        ).all()
        if any(at and at.date() == payload.paid_on for _id, at in twice):
            raise HTTPException(status_code=409, detail=f"{person.full_name} was already paid on {payload.paid_on.isoformat()}")
        row = m.HrmLoan(
            tenant_id=tenant_id, employee_id=person.id, loan_number=await hrm._next_number(db, tenant_id, m.HrmLoan, "LN"),
            kind=KIND, principal=amount, monthly_deduction=amount, balance=amount, first_period=period, status="active",
            reason=f"{getattr(person, 'pay_frequency', 'weekly').capitalize()} pay {payload.paid_on.isoformat()}",
            requested_by=user_id, decided_by=user_id, decided_at=datetime.utcnow(),
            paid_out_at=datetime.combine(payload.paid_on, datetime.min.time()), paid_out_method=payload.method,
        )
        db.add(row)
        made.append(row)
        total += amount
    await db.flush()
    description = f"Part-payments of wages {payload.paid_on.isoformat()}"
    money_account = accounting.pos_debit_account_for_payment_method(payload.method)[0]
    entry_id = await hrm._post(
        db, tenant_id, user_id=user_id, description=description,
        lines=[
            {"account_code": "1150", "debit": money_json(total), "credit": 0, "description": description},
            {"account_code": money_account, "debit": 0, "credit": money_json(total), "description": description},
        ],
        reference=f"WAGES-{payload.paid_on.isoformat()}", source="hrm_part_pay", source_id=made[0].id,
    )
    for row in made:
        row.journal_entry_id = entry_id
    await hrm._audit(db, tenant_id, user_id, "hrm_part_pay", "hrm_loan", made[0].id, {"people": len(made), "total": money_json(total), "on": payload.paid_on.isoformat()})
    await db.flush()
    return {"paid": len(made), "total": money_json(total), "period": period}


async def part_paid_this_month(db: AsyncSession, employee_id: str, period: str) -> Decimal:
    rows = (
        await db.execute(
            select(m.HrmLoan.balance).where(
                m.HrmLoan.employee_id == employee_id, m.HrmLoan.kind == KIND, m.HrmLoan.first_period == period,
                m.HrmLoan.status == "active",
            )
        )
    ).scalars().all()
    return sum((D(b) for b in rows), Decimal(0))
