"""HRM public holidays, staff loans and salary advances.

Loans: someone asks (HR, or the employee themselves); a payroll manager who is neither
the borrower nor the person who asked decides; approval pays the money out once
(debit 1150 Staff Loans and Advances, credit cash or bank). Each approved payroll month
takes up to the monthly deduction, never more than the balance or the person's pay, and
books it against 1150 on approval. A loan can also be paid back in cash. No interest is
charged: the balance is the amount lent.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import accounting
from app import models as m
from app.honesty import money_json, optional_honest_narrative, require_honest_narrative

LOAN_KINDS = frozenset({"loan", "advance"})
LOAN_ACCOUNT = "1150"
ZERO = Decimal("0")


def D(value) -> Decimal:
    if value is None or value == "":
        return ZERO
    return value if isinstance(value, Decimal) else Decimal(str(value))


# --- Holidays ----------------------------------------------------------------------------


async def holidays_between(db: AsyncSession, tenant_id: str, start: date, end: date) -> set[date]:
    rows = (
        await db.execute(
            select(m.HrmHoliday.day).where(
                m.HrmHoliday.tenant_id == tenant_id, m.HrmHoliday.day >= start, m.HrmHoliday.day <= end
            )
        )
    ).scalars().all()
    return set(rows)


def serialize_holiday(row: m.HrmHoliday) -> dict:
    return {"id": row.id, "day": row.day.isoformat(), "name": row.name, "weekday": row.day.strftime("%A")}


async def list_holidays(db: AsyncSession, tenant_id: str, year: int) -> list[m.HrmHoliday]:
    return list(
        (
            await db.execute(
                select(m.HrmHoliday)
                .where(
                    m.HrmHoliday.tenant_id == tenant_id,
                    m.HrmHoliday.day >= date(year, 1, 1),
                    m.HrmHoliday.day <= date(year, 12, 31),
                )
                .order_by(m.HrmHoliday.day)
            )
        ).scalars()
    )


async def add_holidays(db: AsyncSession, tenant_id: str, items: list, *, user_id) -> list[m.HrmHoliday]:
    from app import hrm

    added: list[m.HrmHoliday] = []
    for item in items:
        name = require_honest_narrative(item.name, label="holiday name", max_length=120)
        exists = (
            await db.execute(
                select(m.HrmHoliday.id).where(m.HrmHoliday.tenant_id == tenant_id, m.HrmHoliday.day == item.day)
            )
        ).first()
        if exists:
            continue
        row = m.HrmHoliday(tenant_id=tenant_id, day=item.day, name=name, created_by=user_id)
        db.add(row)
        added.append(row)
    await db.flush()
    if added:
        await hrm._audit(
            db, tenant_id, user_id, "hrm_holidays_added", "hrm_holiday", added[0].id,
            {"days": [r.day.isoformat() for r in added]},
        )
    return added


async def delete_holiday(db: AsyncSession, tenant_id: str, holiday_id: str, *, user_id) -> None:
    from app import hrm

    row = await db.get(m.HrmHoliday, holiday_id)
    if row is None or row.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Holiday not found")
    snapshot = serialize_holiday(row)
    await db.delete(row)
    await hrm._audit(db, tenant_id, user_id, "hrm_holiday_removed", "hrm_holiday", holiday_id, snapshot)
    await db.flush()


def _easter(year: int) -> date:
    """Western Easter Sunday (anonymous Gregorian algorithm)."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    mm = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * mm + 114) // 31
    day = ((h + l - 7 * mm + 114) % 31) + 1
    return date(year, month, day)


def suggested_ghana_holidays(year: int) -> list[dict]:
    """A starting list for HR to check and pick from. It is NOT authoritative: the Public
    Holidays Act changes, a holiday on a weekend may move, and the two Eids are announced
    each year, so they are not listed. Nothing is saved until HR saves it."""
    first_friday_dec = date(year, 12, 1)
    while first_friday_dec.weekday() != 4:
        first_friday_dec += timedelta(days=1)
    easter = _easter(year)
    rows = [
        (date(year, 1, 1), "New Year's Day"),
        (date(year, 1, 7), "Constitution Day"),
        (date(year, 3, 6), "Independence Day"),
        (easter - timedelta(days=2), "Good Friday"),
        (easter + timedelta(days=1), "Easter Monday"),
        (date(year, 5, 1), "May Day"),
        (date(year, 7, 1), "Republic Day"),
        (date(year, 8, 4), "Founders' Day"),
        (date(year, 9, 21), "Kwame Nkrumah Memorial Day"),
        (first_friday_dec, "Farmers' Day"),
        (date(year, 12, 25), "Christmas Day"),
        (date(year, 12, 26), "Boxing Day"),
    ]
    return [{"day": d.isoformat(), "name": n, "weekday": d.strftime("%A")} for d, n in sorted(rows)]


# --- Loans and advances --------------------------------------------------------------------


def serialize_loan(row: m.HrmLoan, employee: m.HrmEmployee | None = None) -> dict:
    return {
        "id": row.id,
        "loan_number": row.loan_number,
        "employee_id": row.employee_id,
        "employee_name": employee.full_name if employee else None,
        "kind": row.kind,
        "principal": money_json(row.principal),
        "monthly_deduction": money_json(row.monthly_deduction),
        "balance": money_json(row.balance),
        "first_period": row.first_period,
        "status": row.status,
        "reason": row.reason,
        "decision_note": row.decision_note,
        "decided_at": row.decided_at.isoformat() if row.decided_at else None,
        "paid_out_at": row.paid_out_at.isoformat() if row.paid_out_at else None,
        "settled_at": row.settled_at.isoformat() if row.settled_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


async def present_loans(db: AsyncSession, rows: list[m.HrmLoan]) -> list[dict]:
    out = []
    for row in rows:
        out.append(serialize_loan(row, await db.get(m.HrmEmployee, row.employee_id)))
    return out


async def list_loans(db: AsyncSession, tenant_id: str, *, employee_id: str | None = None) -> list[m.HrmLoan]:
    stmt = select(m.HrmLoan).where(m.HrmLoan.tenant_id == tenant_id).order_by(m.HrmLoan.created_at.desc())
    if employee_id:
        stmt = stmt.where(m.HrmLoan.employee_id == employee_id)
    return list((await db.execute(stmt)).scalars())


async def _loan(db: AsyncSession, tenant_id: str, loan_id: str, *, lock: bool = False) -> m.HrmLoan:
    stmt = select(m.HrmLoan).where(m.HrmLoan.id == loan_id, m.HrmLoan.tenant_id == tenant_id)
    if lock:
        stmt = stmt.with_for_update()
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Loan not found")
    return row


async def request_loan(db: AsyncSession, tenant_id: str, *, employee_id: str, payload, user_id) -> m.HrmLoan:
    from app import hrm

    employee = await hrm._employee(db, tenant_id, employee_id)
    if employee.status != "active":
        raise HTTPException(status_code=409, detail="This person has left")
    principal, monthly = D(payload.principal), D(payload.monthly_deduction)
    if principal <= 0 or monthly <= 0:
        raise HTTPException(status_code=422, detail="Enter the amount and the monthly repayment")
    if monthly > principal:
        raise HTTPException(status_code=422, detail="The monthly repayment cannot be more than the amount")
    if payload.kind == "advance" and monthly != principal:
        raise HTTPException(status_code=422, detail="A salary advance is paid back in full from the next payroll")
    row = m.HrmLoan(
        tenant_id=tenant_id,
        employee_id=employee.id,
        loan_number=await hrm._next_number(db, tenant_id, m.HrmLoan, "LN"),
        kind=payload.kind,
        principal=principal,
        monthly_deduction=monthly,
        balance=principal,
        first_period=getattr(payload, "first_period", None),
        status="pending",
        reason=optional_honest_narrative(payload.reason, label="reason", max_length=500),
        requested_by=user_id,
    )
    db.add(row)
    await db.flush()
    await hrm._audit(
        db, tenant_id, user_id, "hrm_loan_requested", "hrm_loan", row.id,
        {"kind": row.kind, "principal": money_json(principal), "employee_id": employee.id},
    )
    from app import hrm_notify

    await hrm_notify.to_hr(
        db, tenant_id, "Loan to decide", f"{employee.full_name} asks for a {row.kind} ({row.loan_number}).",
        entity_type="hrm_loan", entity_id=row.id, skip_user=user_id,
    )
    return row


async def decide_loan(
    db: AsyncSession, tenant_id: str, loan_id: str, *, approve: bool, method: str | None, note: str | None, user_id
) -> m.HrmLoan:
    """Approve (and pay out) or turn down. Never by the borrower or the person who asked."""
    from app import hrm

    row = await _loan(db, tenant_id, loan_id, lock=True)
    if row.status != "pending":
        raise HTTPException(status_code=409, detail=f"This request is already {row.status}")
    if user_id and row.requested_by == user_id:
        raise HTTPException(status_code=403, detail="Someone other than the person who asked must decide")
    employee = await hrm._employee(db, tenant_id, row.employee_id)
    decider = await db.get(m.User, user_id) if user_id else None
    if decider and employee.email and (decider.email or "").lower() == employee.email.lower():
        raise HTTPException(status_code=403, detail="Someone else must decide your own loan")
    if not approve:
        if not (note or "").strip():
            raise HTTPException(status_code=422, detail="Say why it was turned down")
        row.status = "rejected"
        row.decision_note = optional_honest_narrative(note, label="note", max_length=255)
        row.decided_by = user_id
        row.decided_at = datetime.utcnow()
        await hrm._audit(db, tenant_id, user_id, "hrm_loan_rejected", "hrm_loan", row.id, {"note": row.decision_note})
        await db.flush()
        from app import hrm_notify

        await hrm_notify.to_person(
            db, tenant_id, employee, "Loan decided", f"Your {row.kind} {row.loan_number} was turned down: {row.decision_note}",
            entity_type="hrm_loan", entity_id=row.id,
        )
        return row
    if method not in hrm.METHODS:
        raise HTTPException(status_code=422, detail="Choose how the money was paid out")
    amount = D(row.principal)
    description = f"Staff {row.kind} {row.loan_number}"
    money_account = accounting.pos_debit_account_for_payment_method(method)[0]
    row.journal_entry_id = await hrm._post(
        db, tenant_id, user_id=user_id, description=description,
        lines=[
            {"account_code": LOAN_ACCOUNT, "debit": money_json(amount), "credit": 0, "description": description},
            {"account_code": money_account, "debit": 0, "credit": money_json(amount), "description": description},
        ],
        reference=row.loan_number, source="hrm_loan", source_id=row.id,
    )
    row.status = "active"
    row.decision_note = optional_honest_narrative(note, label="note", max_length=255)
    row.decided_by = user_id
    row.decided_at = datetime.utcnow()
    row.paid_out_at = datetime.utcnow()
    row.paid_out_method = method
    await hrm._audit(
        db, tenant_id, user_id, "hrm_loan_approved", "hrm_loan", row.id,
        {"principal": money_json(amount), "method": method},
    )
    await db.flush()
    from app import hrm_notify

    await hrm_notify.to_person(
        db, tenant_id, employee, "Loan decided", f"Your {row.kind} {row.loan_number} was approved and paid out.",
        entity_type="hrm_loan", entity_id=row.id,
    )
    return row


async def repay_cash(db: AsyncSession, tenant_id: str, loan_id: str, *, amount, method: str, user_id) -> m.HrmLoan:
    from app import hrm

    row = await _loan(db, tenant_id, loan_id, lock=True)
    if row.status != "active":
        raise HTTPException(status_code=409, detail="Only an active loan can be paid back")
    value = D(amount)
    if value <= 0 or value > D(row.balance):
        raise HTTPException(status_code=422, detail=f"Pay between 0 and the balance of {money_json(row.balance)}")
    if method not in hrm.METHODS:
        raise HTTPException(status_code=422, detail="Choose how it was paid")
    description = f"Repayment {row.loan_number}"
    money_account = accounting.pos_debit_account_for_payment_method(method)[0]
    entry = await hrm._post(
        db, tenant_id, user_id=user_id, description=description,
        lines=[
            {"account_code": money_account, "debit": money_json(value), "credit": 0, "description": description},
            {"account_code": LOAN_ACCOUNT, "debit": 0, "credit": money_json(value), "description": description},
        ],
        reference=row.loan_number, source="hrm_loan_repayment", source_id=row.id,
    )
    db.add(
        m.HrmLoanRepayment(
            tenant_id=tenant_id, loan_id=row.id, amount=value, source="cash", method=method,
            journal_entry_id=entry, created_by=user_id,
        )
    )
    _reduce(row, value)
    await hrm._audit(db, tenant_id, user_id, "hrm_loan_repaid", "hrm_loan", row.id, {"amount": money_json(value)})
    await db.flush()
    return row


def _reduce(row: m.HrmLoan, value: Decimal) -> None:
    row.balance = D(row.balance) - value
    if D(row.balance) <= 0:
        row.balance = ZERO
        row.status = "settled"
        row.settled_at = datetime.utcnow()


async def due_this_month(db: AsyncSession, tenant_id: str, employee_id: str, period: str) -> Decimal:
    """What payroll should take this month: each active loan's monthly amount, capped at its balance."""
    rows = (
        await db.execute(
            select(m.HrmLoan).where(
                m.HrmLoan.tenant_id == tenant_id,
                m.HrmLoan.employee_id == employee_id,
                m.HrmLoan.status == "active",
            )
        )
    ).scalars().all()
    total = ZERO
    for row in rows:
        if row.first_period and row.first_period > period:
            continue
        total += min(D(row.monthly_deduction), D(row.balance))
    return total


async def apply_payroll_repayments(db: AsyncSession, tenant_id: str, run: m.HrmPayrollRun, slips: list) -> None:
    """On approval: spread each slip's loan deduction over that person's loans, oldest first."""
    for slip in slips:
        left = D(slip.loan_deduction)
        if left <= 0:
            continue
        loans = (
            await db.execute(
                select(m.HrmLoan)
                .where(
                    m.HrmLoan.tenant_id == tenant_id,
                    m.HrmLoan.employee_id == slip.employee_id,
                    m.HrmLoan.status == "active",
                )
                .order_by(m.HrmLoan.created_at)
                .with_for_update()
            )
        ).scalars().all()
        for loan in loans:
            if left <= 0:
                break
            if loan.first_period and loan.first_period > run.period:
                continue
            take = min(left, D(loan.monthly_deduction), D(loan.balance))
            if take <= 0:
                continue
            db.add(
                m.HrmLoanRepayment(
                    tenant_id=tenant_id, loan_id=loan.id, payslip_id=slip.id, run_id=run.id,
                    amount=take, source="payroll", journal_entry_id=run.journal_entry_id,
                )
            )
            _reduce(loan, take)
            left -= take
    await db.flush()
