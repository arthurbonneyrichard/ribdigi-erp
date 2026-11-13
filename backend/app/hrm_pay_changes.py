"""HRM salary history, corrections to approved pay, and the statutory schedules.

- A salary change has a start date and a reason. Payroll uses the change in force on
  the month's first day (a change starting mid-month counts from the next month).
- An approved payroll is never edited. If a change starts on or before an approved
  month, the difference for each such month becomes back pay (arrears) on the next
  payroll. Other mistakes are corrected the same way, with a reason, positive or negative.
- PAYE and SSNIT schedules and the yearly tax statement are read from approved payslips.
  They are working papers for the company's own returns, not a filing with GRA or SSNIT.
"""

from __future__ import annotations

import calendar
from datetime import date, datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.honesty import money_json, require_honest_narrative

ZERO = Decimal("0")


def D(value) -> Decimal:
    if value is None or value == "":
        return ZERO
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _first(period: str) -> date:
    return date(int(period[:4]), int(period[5:7]), 1)


def _period(day: date) -> str:
    return f"{day.year:04d}-{day.month:02d}"


# --- Salary history ----------------------------------------------------------------------


async def salary_for(db: AsyncSession, employee: m.HrmEmployee, first_day: date) -> tuple[Decimal, Decimal]:
    row = (
        await db.execute(
            select(m.HrmSalaryChange)
            .where(m.HrmSalaryChange.employee_id == employee.id, m.HrmSalaryChange.effective_from <= first_day)
            .order_by(m.HrmSalaryChange.effective_from.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if row is not None:
        return D(row.basic_salary), D(row.allowances)
    return D(employee.basic_salary), D(employee.allowances)


def serialize_change(row: m.HrmSalaryChange) -> dict:
    return {
        "id": row.id,
        "employee_id": row.employee_id,
        "effective_from": row.effective_from.isoformat(),
        "basic_salary": money_json(row.basic_salary),
        "allowances": money_json(row.allowances),
        "reason": row.reason,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


async def list_changes(db: AsyncSession, tenant_id: str, employee_id: str) -> list[m.HrmSalaryChange]:
    return list(
        (
            await db.execute(
                select(m.HrmSalaryChange)
                .where(m.HrmSalaryChange.tenant_id == tenant_id, m.HrmSalaryChange.employee_id == employee_id)
                .order_by(m.HrmSalaryChange.effective_from.desc())
            )
        ).scalars()
    )


async def add_change(db: AsyncSession, tenant_id: str, employee_id: str, payload, *, user_id) -> dict:
    from app import hrm

    employee = await hrm._employee(db, tenant_id, employee_id)
    reason = require_honest_narrative(payload.reason, label="reason", max_length=255)
    clash = (
        await db.execute(
            select(m.HrmSalaryChange.id).where(
                m.HrmSalaryChange.employee_id == employee.id,
                m.HrmSalaryChange.effective_from == payload.effective_from,
            )
        )
    ).first()
    if clash:
        raise HTTPException(status_code=409, detail="A change already starts on that date")
    # What payroll used before this change, month by month, for the back pay below.
    approved = (
        await db.execute(
            select(m.HrmPayslip, m.HrmPayrollRun)
            .join(m.HrmPayrollRun, m.HrmPayrollRun.id == m.HrmPayslip.run_id)
            .where(
                m.HrmPayslip.tenant_id == tenant_id,
                m.HrmPayslip.employee_id == employee.id,
                m.HrmPayrollRun.status != "draft",
            )
        )
    ).all()
    row = m.HrmSalaryChange(
        tenant_id=tenant_id,
        employee_id=employee.id,
        effective_from=payload.effective_from,
        basic_salary=D(payload.basic_salary),
        allowances=D(payload.allowances),
        reason=reason,
        created_by=user_id,
    )
    db.add(row)
    await db.flush()
    raised: list[m.HrmPayrollAdjustment] = []
    for slip, run in approved:
        first = _first(run.period)
        if first < payload.effective_from:
            continue
        new_basic, new_allow = await salary_for(db, employee, first)
        # Only the months this change governs (a later change takes over after its own date).
        if (new_basic, new_allow) != (D(row.basic_salary), D(row.allowances)):
            continue
        for kind, diff in (("arrears", new_basic - D(slip.basic)), ("correction", new_allow - D(slip.allowances))):
            if diff == 0:
                continue
            adj = m.HrmPayrollAdjustment(
                tenant_id=tenant_id, employee_id=employee.id, kind=kind, for_period=run.period, amount=diff,
                reason=f"{'Back pay of basic' if kind == 'arrears' else 'Allowances put right'} for {run.period}: {reason}",
                status="pending", salary_change_id=row.id, created_by=user_id,
            )
            db.add(adj)
            raised.append(adj)
    if payload.effective_from <= date.today():
        current_basic, current_allow = await salary_for(db, employee, date.today())
        employee.basic_salary = current_basic
        employee.allowances = current_allow
    await db.flush()
    await hrm._audit(
        db, tenant_id, user_id, "hrm_salary_changed", "hrm_employee", employee.id,
        {
            "effective_from": payload.effective_from.isoformat(),
            "basic_salary": money_json(row.basic_salary),
            "allowances": money_json(row.allowances),
            "reason": reason,
            "back_pay_months": sorted({a.for_period for a in raised}),
        },
    )
    return {"change": serialize_change(row), "adjustments": [serialize_adjustment(a) for a in raised]}


# --- Corrections -------------------------------------------------------------------------


def serialize_adjustment(row: m.HrmPayrollAdjustment, employee: m.HrmEmployee | None = None) -> dict:
    return {
        "id": row.id,
        "employee_id": row.employee_id,
        "employee_name": employee.full_name if employee else None,
        "kind": row.kind,
        "for_period": row.for_period,
        "amount": money_json(row.amount),
        "reason": row.reason,
        "status": row.status,
        "run_id": row.run_id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


async def list_adjustments(db: AsyncSession, tenant_id: str) -> list[dict]:
    rows = (
        await db.execute(
            select(m.HrmPayrollAdjustment)
            .where(m.HrmPayrollAdjustment.tenant_id == tenant_id)
            .order_by(m.HrmPayrollAdjustment.created_at.desc())
        )
    ).scalars().all()
    return [serialize_adjustment(r, await db.get(m.HrmEmployee, r.employee_id)) for r in rows]


async def add_adjustment(db: AsyncSession, tenant_id: str, payload, *, user_id) -> m.HrmPayrollAdjustment:
    from app import hrm

    employee = await hrm._employee(db, tenant_id, payload.employee_id)
    amount = D(payload.amount)
    if amount == 0:
        raise HTTPException(status_code=422, detail="Enter the amount to put right")
    row = m.HrmPayrollAdjustment(
        tenant_id=tenant_id, employee_id=employee.id, kind=payload.kind, for_period=payload.for_period,
        amount=amount, reason=require_honest_narrative(payload.reason, label="reason", max_length=255),
        status="pending", created_by=user_id,
    )
    db.add(row)
    await db.flush()
    await hrm._audit(
        db, tenant_id, user_id, "hrm_adjustment_added", "hrm_payroll_adjustment", row.id,
        {"employee_id": employee.id, "amount": money_json(amount), "kind": row.kind, "reason": row.reason},
    )
    return row


async def cancel_adjustment(db: AsyncSession, tenant_id: str, adjustment_id: str, *, user_id) -> None:
    from app import hrm

    row = await db.get(m.HrmPayrollAdjustment, adjustment_id)
    if row is None or row.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Correction not found")
    if row.status != "pending":
        raise HTTPException(status_code=409, detail="Only a correction not yet on a payroll can be cancelled")
    row.status = "cancelled"
    await hrm._audit(db, tenant_id, user_id, "hrm_adjustment_cancelled", "hrm_payroll_adjustment", row.id, {})
    await db.flush()


async def take_pending(db: AsyncSession, tenant_id: str, employee_id: str, run_id: str) -> tuple[Decimal, Decimal]:
    """Put an employee's pending corrections on this draft run. Returns (arrears, other)."""
    rows = (
        await db.execute(
            select(m.HrmPayrollAdjustment).where(
                m.HrmPayrollAdjustment.tenant_id == tenant_id,
                m.HrmPayrollAdjustment.employee_id == employee_id,
                m.HrmPayrollAdjustment.status == "pending",
            )
        )
    ).scalars().all()
    arrears = other = ZERO
    for row in rows:
        row.status = "in_run"
        row.run_id = run_id
        if row.kind == "arrears":
            arrears += D(row.amount)
        else:
            other += D(row.amount)
    return arrears, other


async def release_run(db: AsyncSession, run_id: str) -> None:
    """A thrown-away draft hands its corrections back to wait for the next one."""
    rows = (await db.execute(select(m.HrmPayrollAdjustment).where(m.HrmPayrollAdjustment.run_id == run_id))).scalars()
    for row in rows:
        if row.status == "in_run":
            row.status = "pending"
            row.run_id = None


async def settle_run(db: AsyncSession, run_id: str) -> None:
    rows = (await db.execute(select(m.HrmPayrollAdjustment).where(m.HrmPayrollAdjustment.run_id == run_id))).scalars()
    for row in rows:
        if row.status == "in_run":
            row.status = "applied"


# --- Statutory schedules ------------------------------------------------------------------


async def _approved_slips(db: AsyncSession, tenant_id: str, *, period: str | None = None, year: int | None = None, employee_id: str | None = None):
    stmt = (
        select(m.HrmPayslip, m.HrmPayrollRun, m.HrmEmployee)
        .join(m.HrmPayrollRun, m.HrmPayrollRun.id == m.HrmPayslip.run_id)
        .join(m.HrmEmployee, m.HrmEmployee.id == m.HrmPayslip.employee_id)
        .where(m.HrmPayslip.tenant_id == tenant_id, m.HrmPayrollRun.status != "draft")
        .order_by(m.HrmPayrollRun.period, m.HrmEmployee.full_name)
    )
    if period:
        stmt = stmt.where(m.HrmPayrollRun.period == period)
    if year:
        stmt = stmt.where(m.HrmPayrollRun.period.like(f"{year:04d}-%"))
    if employee_id:
        stmt = stmt.where(m.HrmPayslip.employee_id == employee_id)
    return (await db.execute(stmt)).all()


def _sum(rows: list[dict], key: str) -> float:
    return money_json(sum((D(r[key]) for r in rows), ZERO))


async def paye_schedule(db: AsyncSession, tenant_id: str, period: str) -> dict:
    rows = []
    for slip, _run, person in await _approved_slips(db, tenant_id, period=period):
        rows.append(
            {
                "employee_number": person.employee_number,
                "full_name": person.full_name,
                "tin": person.tin,
                "ghana_card": person.ghana_card,
                "residence": "non-resident" if getattr(slip, "non_resident", False) else "resident",
                # Columns in the order of GRA's monthly PAYE return.
                "basic": money_json(D(slip.basic) - D(slip.unpaid_deduction) + D(getattr(slip, "arrears_basic", 0))),
                "ssnit_employee": money_json(slip.ssnit_employee),
                "tier3_relief": money_json(slip.tier3_relief),
                "cash_allowances": money_json(
                    D(slip.allowances) + D(getattr(slip, "adjustment", 0)) + D(getattr(slip, "commission", 0))
                    + D(getattr(slip, "tips", 0)) + D(getattr(slip, "leave_pay", 0))
                ),
                "bonus": money_json(getattr(slip, "bonus_concessional", 0)),
                "bonus_tax": money_json(getattr(slip, "bonus_tax", 0)),
                "excess_bonus": money_json(max(D(slip.bonus) - D(getattr(slip, "bonus_concessional", 0)), ZERO)),
                "gross": money_json(slip.gross),
                "taxable": money_json(slip.taxable),
                "tax_on_chargeable": money_json(
                    D(slip.paye) - D(getattr(slip, "bonus_tax", 0)) - D(getattr(slip, "overtime_tax", 0))
                ),
                "overtime": money_json(getattr(slip, "overtime", 0)),
                "overtime_tax": money_json(getattr(slip, "overtime_tax", 0)),
                "paye": money_json(slip.paye),
            }
        )
    missing = [r["full_name"] for r in rows if not r["tin"] and not r["ghana_card"]]
    keys = ("basic", "cash_allowances", "bonus", "bonus_tax", "excess_bonus", "gross", "taxable", "tax_on_chargeable", "overtime", "overtime_tax", "paye")
    return {
        "period": period,
        "rows": rows,
        "totals": {k: _sum(rows, k) for k in keys},
        "missing_tax_id": missing,
    }


async def ssnit_schedule(db: AsyncSession, tenant_id: str, period: str) -> dict:
    rows = []
    for slip, _run, person in await _approved_slips(db, tenant_id, period=period):
        insurable = D(slip.basic) - D(slip.unpaid_deduction) + D(getattr(slip, "arrears_basic", 0))
        cap = (slip.rates_used or {}).get("insurable_cap")
        if cap is not None:
            insurable = min(insurable, D(cap))
        rows.append(
            {
                "employee_number": person.employee_number,
                "full_name": person.full_name,
                "ssnit_number": person.ssnit_number,
                "ghana_card": person.ghana_card,
                "insurable": money_json(insurable),
                "employee_share": money_json(slip.ssnit_employee),
                "employer_share": money_json(slip.ssnit_employer),
                "tier1": money_json(slip.tier1 if D(slip.tier1) or D(slip.tier2) else D(slip.ssnit_employee) + D(slip.ssnit_employer)),
                "tier2": money_json(slip.tier2),
                "tier3": money_json(slip.tier3),
            }
        )
    return {
        "period": period,
        "rows": rows,
        "totals": {k: _sum(rows, k) for k in ("insurable", "employee_share", "employer_share", "tier1", "tier2", "tier3")},
        "missing_ssnit_number": [r["full_name"] for r in rows if not r["ssnit_number"]],
    }


async def tax_statement(db: AsyncSession, tenant_id: str, employee: m.HrmEmployee, year: int) -> dict:
    months = []
    for slip, run, _person in await _approved_slips(db, tenant_id, year=year, employee_id=employee.id):
        months.append(
            {
                "period": run.period,
                "gross": money_json(slip.gross),
                "ssnit_employee": money_json(slip.ssnit_employee),
                "tier3": money_json(slip.tier3),
                "taxable": money_json(slip.taxable),
                "paye": money_json(slip.paye),
                "net": money_json(slip.net),
            }
        )
    return {
        "year": year,
        "employee": {
            "employee_number": employee.employee_number,
            "full_name": employee.full_name,
            "tin": employee.tin,
            "ghana_card": employee.ghana_card,
            "ssnit_number": employee.ssnit_number,
        },
        "months": months,
        "totals": {k: _sum(months, k) for k in ("gross", "ssnit_employee", "tier3", "taxable", "paye", "net")},
        "note": "From approved payslips. A working paper for the company's own returns, not a GRA filing.",
        "generated_at": datetime.utcnow().isoformat(),
    }
