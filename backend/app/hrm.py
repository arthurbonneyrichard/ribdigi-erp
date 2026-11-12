"""HRM desk: employees, leave, attendance and payroll, on ``hrm_*`` tables.

Payroll is worked out from each company's own rates in ``hrm_settings``. The defaults are
Ghana's SSNIT rates and monthly PAYE bands; the company must check them against the current
GRA and SSNIT tables, and can change them on the Settings tab.

An approved run books the cost: wages and employer SSNIT are expenses, and what is owed to
staff, GRA and SSNIT sits in its own liability until it is paid. Paying clears the liability.
"""

from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import accounting
from app import audit as audit_svc
from app import models as m
from app import schema_compat
from app import desk_dashboard as dash
from app.honesty import money_json, optional_honest_narrative, require_honest_narrative
from app import hrm_payroll as engine

METHODS = frozenset({"bank_transfer", "cash", "mobile_money", "cheque"})
LEAVE_TYPES = frozenset({"annual", "sick", "maternity", "paternity", "compassionate", "unpaid"})
DEFAULT_PAYE_BANDS = [
    {"width": 490, "rate": 0},
    {"width": 110, "rate": 5},
    {"width": 130, "rate": 10},
    {"width": 3166.67, "rate": 17.5},
    {"width": 16000, "rate": 25},
    {"width": 30520, "rate": 30},
    {"width": None, "rate": 35},
]
PAYROLL_ACCOUNTS = [
    ("1150", "Staff Loans and Advances", "asset"),
    ("2170", "Salaries Payable", "liability"),
    ("2175", "Staff Deductions Held", "liability"),
    ("2180", "PAYE Payable", "liability"),
    ("2190", "SSNIT Payable", "liability"),
    ("2192", "Tier 2 Pension Payable", "liability"),
    ("2195", "Tier 3 Pension Payable", "liability"),
    ("6200", "Salaries and Wages", "expense"),
    ("6210", "Employer SSNIT", "expense"),
]

_JOBS = {
    "hrm_officer": frozenset({"people", "leave", "attendance"}),
    "hrm_employee": frozenset({"self"}),
}
_WORDS = {
    "hrm_officer": "HR officers look after staff records, leave and attendance. Payroll needs a manager.",
    "hrm_employee": "You can see your own leave and payslips. Ask HR for the rest.",
}


def job(claims: dict, area: str) -> None:
    role = str(claims.get("role") or "")
    if role in _JOBS and area not in _JOBS[role]:
        raise HTTPException(status_code=403, detail={"code": "HRM_ROLE_JOB", "message": _WORDS[role]})


def _money(value) -> float:
    return money_json(round(float(value or 0), 2))


async def _next_number(db: AsyncSession, tenant_id: str, model, prefix: str) -> str:
    # key_share: see hotel._lock_numbers.
    await db.execute(select(m.Tenant.id).where(m.Tenant.id == tenant_id).with_for_update(key_share=True))
    count = (await db.execute(select(func.count()).select_from(model).where(model.tenant_id == tenant_id))).scalar_one()
    return f"{prefix}-{int(count or 0) + 1:04d}"


async def _audit(db, tenant_id: str, user_id, action: str, entity: str, entity_id: str, details: dict) -> None:
    await audit_svc.record_event(
        db, tenant_id=tenant_id, user_id=user_id, module="hrm", action=action, entity=entity,
        entity_id=entity_id, details=details,
    )


async def _ensure_accounts(db: AsyncSession, tenant_id: str) -> None:
    await accounting.ensure_default_accounts(db, tenant_id)
    existing = await schema_compat.existing_codes(db, "accounts", tenant_id)
    for code, name, account_type in PAYROLL_ACCOUNTS:
        if code in existing:
            continue
        await schema_compat.insert_matching_row(
            db,
            "accounts",
            {
                "tenant_id": tenant_id,
                "code": code,
                "name": name,
                "account_type": account_type,
                "balance": 0,
                "opening_balance": 0,
                "is_cash_account": False,
                "is_bank_account": False,
                "is_system": True,
                "is_active": True,
                "parent_id": None,
                "company_id": None,
            },
        )


async def _post(db, tenant_id: str, *, user_id, description: str, lines: list[dict], reference: str, source: str, source_id: str):
    await _ensure_accounts(db, tenant_id)
    entry = await accounting.post_journal_entry(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        description=description,
        lines=[row for row in lines if float(row.get("debit") or 0) or float(row.get("credit") or 0)],
        reference=reference,
        source_type=source,
        source_id=source_id,
    )
    return entry.id


# --- Settings ----------------------------------------------------------------------------


async def get_settings(db: AsyncSession, tenant_id: str) -> m.HrmSettings:
    row = (await db.execute(select(m.HrmSettings).where(m.HrmSettings.tenant_id == tenant_id))).scalars().first()
    if row is None:
        row = m.HrmSettings(tenant_id=tenant_id, paye_bands=list(DEFAULT_PAYE_BANDS))
        db.add(row)
        await db.flush()
    return row


def serialize_settings(row: m.HrmSettings) -> dict:
    return {
        "annual_leave_days": int(row.annual_leave_days),
        "working_days_per_month": int(row.working_days_per_month),
        "ssnit_employee_percent": _money(row.ssnit_employee_percent),
        "ssnit_employer_percent": _money(row.ssnit_employer_percent),
        "paye_bands": row.paye_bands or list(DEFAULT_PAYE_BANDS),
        "two_person_payroll": bool(getattr(row, "two_person_payroll", False)),
    }


async def update_settings(db: AsyncSession, tenant_id: str, payload, *, user_id) -> m.HrmSettings:
    row = await get_settings(db, tenant_id)
    data = payload.model_dump(exclude_unset=True)
    if "paye_bands" in data and data["paye_bands"] is not None:
        bands = data["paye_bands"]
        if bands[-1].get("width") is not None or any(b.get("width") is None for b in bands[:-1]):
            raise HTTPException(status_code=422, detail="Only the last PAYE band can be open-ended, and it must be")
    for key, value in data.items():
        if value is not None:
            setattr(row, key, value)
    await _audit(db, tenant_id, user_id, "hrm_settings_updated", "hrm_settings", row.id, {"fields": sorted(data)})
    await db.flush()
    return row


# --- Statutory rates (effective-dated) -----------------------------------------------


def _rates_from_row(row: m.HrmStatutoryRate) -> engine.StatutoryRates:
    return engine.StatutoryRates(
        employee_percent=engine.D(row.employee_percent),
        employer_percent=engine.D(row.employer_percent),
        paye_bands=list(row.paye_bands or []),
        tier2_percent=engine.D(row.tier2_percent),
        insurable_cap=engine.D(row.insurable_cap) if row.insurable_cap is not None else None,
        tier3_relief_percent=engine.D(row.tier3_relief_percent),
        rounding=row.rounding or "half_up",
        rate_id=row.id,
        effective_from=row.effective_from.isoformat() if row.effective_from else None,
    )


def _rates_from_settings(settings: m.HrmSettings) -> engine.StatutoryRates:
    """A company with no dated rates keeps working from its settings, as before."""
    return engine.StatutoryRates(
        employee_percent=engine.D(settings.ssnit_employee_percent),
        employer_percent=engine.D(settings.ssnit_employer_percent),
        paye_bands=list(settings.paye_bands or DEFAULT_PAYE_BANDS),
    )


async def rates_for(db: AsyncSession, tenant_id: str, on: date) -> engine.StatutoryRates:
    row = (
        await db.execute(
            select(m.HrmStatutoryRate)
            .where(m.HrmStatutoryRate.tenant_id == tenant_id, m.HrmStatutoryRate.effective_from <= on)
            .order_by(m.HrmStatutoryRate.effective_from.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if row is not None:
        return _rates_from_row(row)
    return _rates_from_settings(await get_settings(db, tenant_id))


async def _rate_in_use(db: AsyncSession, tenant_id: str, rate_id: str) -> bool:
    used = (
        await db.execute(
            select(m.HrmPayrollRun.id).where(
                m.HrmPayrollRun.tenant_id == tenant_id,
                m.HrmPayrollRun.statutory_rate_id == rate_id,
                m.HrmPayrollRun.status != "draft",
            ).limit(1)
        )
    ).first()
    return used is not None


async def list_rates(db: AsyncSession, tenant_id: str) -> list[dict]:
    rows = (
        await db.execute(
            select(m.HrmStatutoryRate)
            .where(m.HrmStatutoryRate.tenant_id == tenant_id)
            .order_by(m.HrmStatutoryRate.effective_from.desc())
        )
    ).scalars().all()
    return [{**serialize_rate(row), "locked": await _rate_in_use(db, tenant_id, row.id)} for row in rows]


def serialize_rate(row: m.HrmStatutoryRate) -> dict:
    return {
        "id": row.id,
        "effective_from": row.effective_from.isoformat(),
        "employee_percent": money_json(row.employee_percent),
        "employer_percent": money_json(row.employer_percent),
        "tier2_percent": money_json(row.tier2_percent),
        "insurable_cap": money_json(row.insurable_cap) if row.insurable_cap is not None else None,
        "tier3_relief_percent": money_json(row.tier3_relief_percent),
        "paye_bands": row.paye_bands,
        "rounding": row.rounding,
        "source_note": row.source_note,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


async def add_rate(db: AsyncSession, tenant_id: str, payload, *, user_id) -> m.HrmStatutoryRate:
    bands = [{"width": b.width, "rate": b.rate} for b in payload.paye_bands]
    try:
        engine.validate_bands(bands)
    except engine.PayrollError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if engine.D(payload.tier2_percent) > engine.D(payload.employee_percent) + engine.D(payload.employer_percent):
        raise HTTPException(status_code=422, detail="Tier 2 cannot be more than the staff and company shares together")
    # An approved month must stay explainable: a new rule cannot start inside or before it.
    last_locked = (
        await db.execute(
            select(m.HrmPayrollRun.period)
            .where(m.HrmPayrollRun.tenant_id == tenant_id, m.HrmPayrollRun.status != "draft")
            .order_by(m.HrmPayrollRun.period.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if last_locked and payload.effective_from <= _month(last_locked)[1]:
        raise HTTPException(
            status_code=409,
            detail=f"Payroll is approved up to {last_locked}. New rates must start after that month.",
        )
    clash = (
        await db.execute(
            select(m.HrmStatutoryRate.id).where(
                m.HrmStatutoryRate.tenant_id == tenant_id,
                m.HrmStatutoryRate.effective_from == payload.effective_from,
            )
        )
    ).first()
    if clash:
        raise HTTPException(status_code=409, detail="Rates already start on that date. Remove that row first.")
    row = m.HrmStatutoryRate(
        tenant_id=tenant_id,
        effective_from=payload.effective_from,
        employee_percent=payload.employee_percent,
        employer_percent=payload.employer_percent,
        tier2_percent=payload.tier2_percent,
        insurable_cap=payload.insurable_cap,
        tier3_relief_percent=payload.tier3_relief_percent,
        paye_bands=[{"width": (str(b["width"]) if b["width"] is not None else None), "rate": str(b["rate"])} for b in bands],
        rounding=payload.rounding,
        source_note=optional_honest_narrative(payload.source_note, label="source", max_length=255),
        created_by=user_id,
    )
    db.add(row)
    await db.flush()
    await _audit(db, tenant_id, user_id, "hrm_rates_added", "hrm_statutory_rate", row.id, serialize_rate(row))
    return row


async def delete_rate(db: AsyncSession, tenant_id: str, rate_id: str, *, user_id) -> None:
    row = await db.get(m.HrmStatutoryRate, rate_id)
    if row is None or row.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Rates not found")
    if await _rate_in_use(db, tenant_id, row.id):
        raise HTTPException(status_code=409, detail="An approved payroll used these rates, so they stay on record")
    snapshot = serialize_rate(row)
    await db.delete(row)
    await _audit(db, tenant_id, user_id, "hrm_rates_removed", "hrm_statutory_rate", rate_id, snapshot)
    await db.flush()


def paye_on(taxable: float, bands: list[dict]) -> float:
    """Tax on a month's taxable pay, band by band."""
    left, tax = max(float(taxable or 0), 0.0), 0.0
    for band in bands:
        width = band.get("width")
        chunk = left if width is None else min(left, float(width))
        tax += chunk * float(band.get("rate") or 0) / 100
        left -= chunk
        if left <= 0:
            break
    return _money(tax)


# --- Employees ---------------------------------------------------------------------------


def serialize_employee(row: m.HrmEmployee, *, pay: bool = True) -> dict:
    data = {
        "id": row.id,
        "employee_number": row.employee_number,
        "full_name": row.full_name,
        "phone": row.phone,
        "email": row.email,
        "job_title": row.job_title,
        "department": row.department,
        "hired_on": row.hired_on.isoformat() if row.hired_on else None,
        "left_on": row.left_on.isoformat() if row.left_on else None,
        "status": row.status,
    }
    if pay:
        data.update(
            {
                "basic_salary": _money(row.basic_salary),
                "allowances": _money(row.allowances),
                "ssnit_number": row.ssnit_number,
                "tin": row.tin,
                "bank_name": row.bank_name,
                "bank_account": row.bank_account,
                "ghana_card": row.ghana_card,
                "mobile_money": row.mobile_money,
                "tier3_percent": money_json(row.tier3_percent or 0),
            }
        )
    return data


async def list_employees(db: AsyncSession, tenant_id: str, *, show: str = "active") -> list[m.HrmEmployee]:
    stmt = select(m.HrmEmployee).where(m.HrmEmployee.tenant_id == tenant_id)
    if show != "all":
        stmt = stmt.where(m.HrmEmployee.status == show)
    return list((await db.execute(stmt.order_by(m.HrmEmployee.full_name.asc()))).scalars().all())


async def _employee(db: AsyncSession, tenant_id: str, employee_id: str) -> m.HrmEmployee:
    row = await db.get(m.HrmEmployee, employee_id)
    if row is None or row.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Employee not found")
    return row


async def create_employee(db: AsyncSession, tenant_id: str, payload, *, user_id) -> m.HrmEmployee:
    row = m.HrmEmployee(
        tenant_id=tenant_id,
        employee_number=await _next_number(db, tenant_id, m.HrmEmployee, "EMP"),
        full_name=payload.full_name,
        phone=payload.phone,
        email=str(payload.email).lower() if payload.email else None,
        job_title=optional_honest_narrative(payload.job_title, label="job title", max_length=120),
        department=optional_honest_narrative(payload.department, label="department", max_length=120),
        hired_on=payload.hired_on,
        status="active",
        basic_salary=_money(payload.basic_salary),
        allowances=_money(payload.allowances),
        ssnit_number=payload.ssnit_number,
        tin=payload.tin,
        bank_name=payload.bank_name,
        bank_account=payload.bank_account,
        ghana_card=getattr(payload, "ghana_card", None),
        mobile_money=getattr(payload, "mobile_money", None),
        tier3_percent=getattr(payload, "tier3_percent", 0) or 0,
    )
    db.add(row)
    await db.flush()
    await _audit(db, tenant_id, user_id, "hrm_employee_created", "hrm_employee", row.id, {"employee_number": row.employee_number})
    return row


async def update_employee(db: AsyncSession, tenant_id: str, employee_id: str, payload, *, user_id) -> m.HrmEmployee:
    row = await _employee(db, tenant_id, employee_id)
    data = payload.model_dump(exclude_unset=True)
    before = {k: serialize_employee(row).get(k) for k in data}
    for key, value in data.items():
        setattr(row, key, value)
    await _audit(db, tenant_id, user_id, "hrm_employee_updated", "hrm_employee", row.id, {"fields": sorted(data), "before": before})
    await db.flush()
    return row


async def end_employment(db: AsyncSession, tenant_id: str, employee_id: str, *, left_on: date, reason: str, user_id) -> m.HrmEmployee:
    row = await _employee(db, tenant_id, employee_id)
    if row.status != "active":
        raise HTTPException(status_code=409, detail="This person has already left")
    if row.hired_on and left_on < row.hired_on:
        raise HTTPException(status_code=422, detail="The leaving date is before they joined")
    why = require_honest_narrative(reason, label="reason", max_length=255)
    row.status = "left"
    row.left_on = left_on
    row.left_reason = why
    await _audit(db, tenant_id, user_id, "hrm_employee_left", "hrm_employee", row.id, {"reason": why})
    await db.flush()
    return row


async def employee_for_user(db: AsyncSession, tenant_id: str, user_id: str | None) -> m.HrmEmployee:
    """Staff log in with the email on their record. That is how they find their own file."""
    user = await db.get(m.User, user_id) if user_id else None
    email = (user.email or "").strip().lower() if user else ""
    row = (
        await db.execute(
            select(m.HrmEmployee).where(m.HrmEmployee.tenant_id == tenant_id, func.lower(m.HrmEmployee.email) == email)
        )
    ).scalars().first() if email else None
    if row is None:
        raise HTTPException(status_code=404, detail="No staff record uses your login email. Ask HR to add it.")
    return row


# --- Leave -------------------------------------------------------------------------------


def working_days(start: date, end: date, holidays: set[date] | frozenset = frozenset()) -> int:
    """Monday to Friday, less the company's public holidays."""
    days = 0
    day = start
    while day <= end:
        if day.weekday() < 5 and day not in holidays:
            days += 1
        day += timedelta(days=1)
    return days


async def _annual_used(db: AsyncSession, tenant_id: str, employee_id: str, year: int, *, states=("approved",)) -> int:
    rows = (
        await db.execute(
            select(m.HrmLeaveRequest).where(
                m.HrmLeaveRequest.tenant_id == tenant_id,
                m.HrmLeaveRequest.employee_id == employee_id,
                m.HrmLeaveRequest.leave_type == "annual",
                m.HrmLeaveRequest.status.in_(states),
            )
        )
    ).scalars().all()
    return sum(int(r.days or 0) for r in rows if r.starts_on.year == year)


async def leave_balance(db: AsyncSession, tenant_id: str, employee_id: str, *, year: int | None = None) -> dict:
    settings = await get_settings(db, tenant_id)
    year = year or date.today().year
    used = await _annual_used(db, tenant_id, employee_id, year)
    return {"year": year, "entitled": int(settings.annual_leave_days), "used": used, "left": int(settings.annual_leave_days) - used}


async def request_leave(db: AsyncSession, tenant_id: str, *, employee_id: str, payload, user_id) -> m.HrmLeaveRequest:
    employee = await _employee(db, tenant_id, employee_id)
    if employee.status != "active":
        raise HTTPException(status_code=409, detail="This person has left")
    if payload.ends_on < payload.starts_on:
        raise HTTPException(status_code=422, detail="The end date is before the start date")
    if payload.starts_on.year != payload.ends_on.year:
        raise HTTPException(status_code=422, detail="Split leave that runs across two years")
    from app import hrm_loans

    off = await hrm_loans.holidays_between(db, tenant_id, payload.starts_on, payload.ends_on)
    days = working_days(payload.starts_on, payload.ends_on, off)
    if days <= 0:
        raise HTTPException(status_code=422, detail="Those dates are all weekend or public holidays")
    clash = (
        await db.execute(
            select(m.HrmLeaveRequest.id).where(
                m.HrmLeaveRequest.tenant_id == tenant_id,
                m.HrmLeaveRequest.employee_id == employee.id,
                m.HrmLeaveRequest.status.in_(("pending", "approved")),
                m.HrmLeaveRequest.starts_on <= payload.ends_on,
                m.HrmLeaveRequest.ends_on >= payload.starts_on,
            )
        )
    ).first()
    if clash:
        raise HTTPException(status_code=409, detail="There is already leave on those dates")
    if payload.leave_type == "annual":
        settings = await get_settings(db, tenant_id)
        used = await _annual_used(db, tenant_id, employee.id, payload.starts_on.year, states=("approved", "pending"))
        if used + days > int(settings.annual_leave_days):
            left = int(settings.annual_leave_days) - used
            raise HTTPException(status_code=409, detail=f"Only {max(left, 0)} annual leave days left this year")
    row = m.HrmLeaveRequest(
        tenant_id=tenant_id,
        employee_id=employee.id,
        leave_type=payload.leave_type,
        starts_on=payload.starts_on,
        ends_on=payload.ends_on,
        days=days,
        status="pending",
        reason=optional_honest_narrative(payload.reason, label="reason", max_length=500),
        created_by=user_id,
    )
    db.add(row)
    await db.flush()
    return row


async def decide_leave(db: AsyncSession, tenant_id: str, leave_id: str, *, approve: bool, note: str | None, user_id) -> m.HrmLeaveRequest:
    row = (
        await db.execute(
            select(m.HrmLeaveRequest).where(m.HrmLeaveRequest.id == leave_id, m.HrmLeaveRequest.tenant_id == tenant_id).with_for_update()
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Leave request not found")
    if row.status != "pending":
        raise HTTPException(status_code=409, detail=f"This request is already {row.status}")
    if not approve and not (note or "").strip():
        raise HTTPException(status_code=422, detail="Say why it was turned down")
    employee = await _employee(db, tenant_id, row.employee_id)
    decider = await db.get(m.User, user_id) if user_id else None
    if decider and employee.email and (decider.email or "").lower() == employee.email.lower():
        raise HTTPException(status_code=403, detail="Someone else must decide your own leave")
    row.status = "approved" if approve else "rejected"
    row.decision_note = optional_honest_narrative(note, label="note", max_length=255)
    row.decided_by = user_id
    row.decided_at = datetime.utcnow()
    await _audit(db, tenant_id, user_id, f"hrm_leave_{row.status}", "hrm_leave", row.id, {"days": row.days})
    await db.flush()
    return row


async def present_leave(db: AsyncSession, row: m.HrmLeaveRequest) -> dict:
    employee = await db.get(m.HrmEmployee, row.employee_id)
    return {
        "id": row.id,
        "employee_id": row.employee_id,
        "employee_name": employee.full_name if employee else None,
        "leave_type": row.leave_type,
        "starts_on": row.starts_on.isoformat(),
        "ends_on": row.ends_on.isoformat(),
        "days": int(row.days),
        "status": row.status,
        "reason": row.reason,
        "decision_note": row.decision_note,
    }


async def list_leave(db: AsyncSession, tenant_id: str, *, employee_id: str | None = None, limit: int = 200) -> list[m.HrmLeaveRequest]:
    stmt = select(m.HrmLeaveRequest).where(m.HrmLeaveRequest.tenant_id == tenant_id)
    if employee_id:
        stmt = stmt.where(m.HrmLeaveRequest.employee_id == employee_id)
    return list((await db.execute(stmt.order_by(m.HrmLeaveRequest.starts_on.desc()).limit(limit))).scalars().all())


async def _unpaid_days(db: AsyncSession, tenant_id: str, employee_id: str, first: date, last: date) -> int:
    rows = (
        await db.execute(
            select(m.HrmLeaveRequest).where(
                m.HrmLeaveRequest.tenant_id == tenant_id,
                m.HrmLeaveRequest.employee_id == employee_id,
                m.HrmLeaveRequest.leave_type == "unpaid",
                m.HrmLeaveRequest.status == "approved",
                m.HrmLeaveRequest.starts_on <= last,
                m.HrmLeaveRequest.ends_on >= first,
            )
        )
    ).scalars().all()
    from app import hrm_loans

    off = await hrm_loans.holidays_between(db, tenant_id, first, last)
    return sum(working_days(max(r.starts_on, first), min(r.ends_on, last), off) for r in rows)


# --- Attendance --------------------------------------------------------------------------


async def mark_attendance(db: AsyncSession, tenant_id: str, *, day: date, marks, user_id) -> int:
    if day > date.today():
        raise HTTPException(status_code=422, detail="That day has not happened yet")
    saved = 0
    for mark in marks:
        employee = await _employee(db, tenant_id, mark.employee_id)
        row = (
            await db.execute(
                select(m.HrmAttendance).where(
                    m.HrmAttendance.tenant_id == tenant_id,
                    m.HrmAttendance.employee_id == employee.id,
                    m.HrmAttendance.day == day,
                )
            )
        ).scalars().first()
        if row is None:
            row = m.HrmAttendance(tenant_id=tenant_id, employee_id=employee.id, day=day)
            db.add(row)
        row.status = mark.status
        row.marked_by = user_id
        saved += 1
    await db.flush()
    return saved


async def attendance_for(db: AsyncSession, tenant_id: str, day: date) -> list[dict]:
    people = await list_employees(db, tenant_id)
    marks = {
        r.employee_id: r.status
        for r in (
            await db.execute(select(m.HrmAttendance).where(m.HrmAttendance.tenant_id == tenant_id, m.HrmAttendance.day == day))
        ).scalars().all()
    }
    on_leave = {
        r.employee_id
        for r in (
            await db.execute(
                select(m.HrmLeaveRequest).where(
                    m.HrmLeaveRequest.tenant_id == tenant_id,
                    m.HrmLeaveRequest.status == "approved",
                    m.HrmLeaveRequest.starts_on <= day,
                    m.HrmLeaveRequest.ends_on >= day,
                )
            )
        ).scalars().all()
    }
    return [
        {
            "employee_id": p.id,
            "full_name": p.full_name,
            "department": p.department,
            "status": marks.get(p.id) or ("leave" if p.id in on_leave else None),
        }
        for p in people
    ]


# --- Payroll -----------------------------------------------------------------------------


def _month(period: str) -> tuple[date, date]:
    year, month = int(period[:4]), int(period[5:7])
    return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])


def _work_out(slip: m.HrmPayslip, settings: m.HrmSettings, rates: engine.StatutoryRates | None = None) -> None:
    """Basic and allowances less unpaid days, SSNIT and pensions on basic, PAYE on the rest.

    All arithmetic is Decimal in hrm_payroll; the rates are the month's dated row."""
    rates = rates or _rates_from_settings(settings)

    def compute(loan):
        return engine.compute_payslip(
            engine.PayslipInput(
                basic=engine.D(slip.basic),
                allowances=engine.D(slip.allowances),
                bonus=engine.D(slip.bonus),
                other_deductions=engine.D(slip.other_deductions) + loan,
                unpaid_days=int(slip.unpaid_days or 0),
                working_days=int(settings.working_days_per_month),
                tier3_percent=engine.D(slip.tier3_percent),
            ),
            rates,
        )

    loan = engine.D(getattr(slip, "loan_deduction", 0))
    try:
        out = compute(loan)
    except engine.PayrollError as exc:
        if loan <= 0:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        # A loan repayment never takes someone's pay below nil: take what the month allows.
        try:
            before = compute(engine.ZERO)
        except engine.PayrollError as inner:
            raise HTTPException(status_code=422, detail=str(inner)) from inner
        loan = max(min(loan, before.net), engine.ZERO)
        out = compute(loan)
    slip.loan_deduction = loan
    slip.unpaid_deduction = out.unpaid_deduction
    slip.gross = out.gross
    slip.ssnit_employee = out.ssnit_employee
    slip.ssnit_employer = out.ssnit_employer
    slip.taxable = out.taxable
    slip.paye = out.paye
    slip.tier1 = out.tier1
    slip.tier2 = out.tier2
    slip.tier3 = out.tier3
    slip.tier3_relief = out.tier3_relief
    slip.net = out.net
    slip.rates_used = rates.snapshot()


async def _slips(db: AsyncSession, run_id: str) -> list[m.HrmPayslip]:
    return list((await db.execute(select(m.HrmPayslip).where(m.HrmPayslip.run_id == run_id))).scalars().all())


def _totals(run: m.HrmPayrollRun, slips: list[m.HrmPayslip]) -> None:
    run.gross = _money(sum(float(s.gross or 0) for s in slips))
    run.net = _money(sum(float(s.net or 0) for s in slips))
    run.paye = _money(sum(float(s.paye or 0) for s in slips))
    run.ssnit_employee = _money(sum(float(s.ssnit_employee or 0) for s in slips))
    run.ssnit_employer = _money(sum(float(s.ssnit_employer or 0) for s in slips))
    run.other_deductions = _money(sum(float(s.other_deductions or 0) for s in slips))
    run.tier2 = sum((engine.D(s.tier2) for s in slips), engine.ZERO)
    run.tier3 = sum((engine.D(s.tier3) for s in slips), engine.ZERO)
    run.loan_deductions = sum((engine.D(getattr(s, "loan_deduction", 0)) for s in slips), engine.ZERO)


async def create_run(db: AsyncSession, tenant_id: str, *, period: str, user_id) -> m.HrmPayrollRun:
    first, last = _month(period)
    clash = (
        await db.execute(select(m.HrmPayrollRun.id).where(m.HrmPayrollRun.tenant_id == tenant_id, m.HrmPayrollRun.period == period))
    ).first()
    if clash:
        raise HTTPException(status_code=409, detail=f"Payroll for {period} already exists")
    from app import hrm_loans

    settings = await get_settings(db, tenant_id)
    rates = await rates_for(db, tenant_id, first)
    people = [
        p for p in await list_employees(db, tenant_id, show="all")
        if (not p.hired_on or p.hired_on <= last) and (p.status == "active" or (p.left_on and p.left_on >= first))
    ]
    if not people:
        raise HTTPException(status_code=409, detail="There is nobody to pay for this month")
    run = m.HrmPayrollRun(
        tenant_id=tenant_id,
        run_number=await _next_number(db, tenant_id, m.HrmPayrollRun, "PR"),
        period=period,
        status="draft",
        statutory_rate_id=rates.rate_id,
        created_by=user_id,
    )
    db.add(run)
    await db.flush()
    slips = []
    for person in people:
        slip = m.HrmPayslip(
            tenant_id=tenant_id,
            run_id=run.id,
            employee_id=person.id,
            basic=_money(person.basic_salary),
            allowances=_money(person.allowances),
            bonus=0,
            other_deductions=0,
            tier3_percent=person.tier3_percent or 0,
            loan_deduction=await hrm_loans.due_this_month(db, tenant_id, person.id, period),
            unpaid_days=await _unpaid_days(db, tenant_id, person.id, first, last),
        )
        _work_out(slip, settings, rates)
        db.add(slip)
        slips.append(slip)
    _totals(run, slips)
    await _audit(db, tenant_id, user_id, "hrm_payroll_created", "hrm_payroll", run.id, {"period": period, "staff": len(slips)})
    await db.flush()
    return run


async def _run(db: AsyncSession, tenant_id: str, run_id: str, *, lock: bool = False) -> m.HrmPayrollRun:
    stmt = select(m.HrmPayrollRun).where(m.HrmPayrollRun.id == run_id, m.HrmPayrollRun.tenant_id == tenant_id)
    if lock:
        stmt = stmt.with_for_update()
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Payroll run not found")
    return row


async def update_slip(db: AsyncSession, tenant_id: str, slip_id: str, payload, *, user_id) -> m.HrmPayslip:
    slip = await db.get(m.HrmPayslip, slip_id)
    if slip is None or slip.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Payslip not found")
    run = await _run(db, tenant_id, slip.run_id, lock=True)
    if run.status != "draft":
        raise HTTPException(status_code=409, detail="This payroll is approved and cannot change")
    settings = await get_settings(db, tenant_id)
    rates = await rates_for(db, tenant_id, _month(run.period)[0])
    if payload.bonus is not None:
        slip.bonus = _money(payload.bonus)
    if payload.other_deductions is not None:
        slip.other_deductions = _money(payload.other_deductions)
    if payload.note is not None:
        slip.note = optional_honest_narrative(payload.note, label="note", max_length=255)
    _work_out(slip, settings, rates)
    await db.flush()
    _totals(run, await _slips(db, run.id))
    await db.flush()
    return slip


async def delete_run(db: AsyncSession, tenant_id: str, run_id: str, *, user_id) -> None:
    run = await _run(db, tenant_id, run_id, lock=True)
    if run.status != "draft":
        raise HTTPException(status_code=409, detail="Only a draft payroll can be thrown away")
    for slip in await _slips(db, run.id):
        await db.delete(slip)
    await db.delete(run)
    await _audit(db, tenant_id, user_id, "hrm_payroll_deleted", "hrm_payroll", run_id, {"period": run.period})
    await db.flush()


async def approve_run(db: AsyncSession, tenant_id: str, run_id: str, *, user_id) -> m.HrmPayrollRun:
    """Book the month's cost. What is owed to staff, GRA and SSNIT each sits in its own liability."""
    run = await _run(db, tenant_id, run_id, lock=True)
    if run.status != "draft":
        raise HTTPException(status_code=409, detail=f"This payroll is {run.status}")
    settings = await get_settings(db, tenant_id)
    if getattr(settings, "two_person_payroll", False) and user_id and run.created_by == user_id:
        raise HTTPException(
            status_code=403,
            detail={"code": "PAYROLL_SECOND_PERSON", "message": "Someone other than the person who drew up this payroll must approve it."},
        )
    slips = await _slips(db, run.id)
    _totals(run, slips)
    description = f"Payroll {run.period}"
    other = _money(run.other_deductions)
    run.journal_entry_id = await _post(
        db, tenant_id, user_id=user_id, description=description,
        lines=[
            {"account_code": "6200", "debit": _money(run.gross), "credit": 0, "description": description},
            {"account_code": "6210", "debit": _money(run.ssnit_employer), "credit": 0, "description": description},
            {"account_code": "2170", "debit": 0, "credit": _money(run.net), "description": description},
            {"account_code": "2175", "debit": 0, "credit": other, "description": description},
            {"account_code": "2180", "debit": 0, "credit": _money(run.paye), "description": description},
            {
                "account_code": "2190", "debit": 0,
                "credit": _money(engine.D(run.ssnit_employee) + engine.D(run.ssnit_employer) - engine.D(run.tier2)),
                "description": description,
            },
            {"account_code": "2192", "debit": 0, "credit": _money(run.tier2), "description": description},
            {"account_code": "2195", "debit": 0, "credit": _money(run.tier3), "description": description},
            {"account_code": "1150", "debit": 0, "credit": _money(run.loan_deductions), "description": description},
        ],
        reference=run.run_number, source="hrm_payroll", source_id=run.id,
    )
    from app import hrm_loans

    await hrm_loans.apply_payroll_repayments(db, tenant_id, run, slips)
    run.status = "approved"
    run.approved_by = user_id
    run.approved_at = datetime.utcnow()
    await _audit(db, tenant_id, user_id, "hrm_payroll_approved", "hrm_payroll", run.id, {"period": run.period, "net": _money(run.net)})
    await db.flush()
    return run


async def pay(db: AsyncSession, tenant_id: str, run_id: str, *, what: str, method: str, user_id) -> m.HrmPayrollRun:
    """Pay staff, GRA or SSNIT once. Each clears its own liability."""
    run = await _run(db, tenant_id, run_id, lock=True)
    if run.status == "draft":
        raise HTTPException(status_code=409, detail="Approve the payroll first")
    if method not in METHODS:
        raise HTTPException(status_code=422, detail="Choose how it was paid")
    plan = {
        "staff": ("staff_paid_at", "2170", _money(run.net), "Salaries"),
        "paye": ("paye_paid_at", "2180", _money(run.paye), "PAYE to GRA"),
        "ssnit": (
            "ssnit_paid_at", "2190",
            _money(engine.D(run.ssnit_employee) + engine.D(run.ssnit_employer) - engine.D(run.tier2)), "SSNIT",
        ),
        "tier2": ("tier2_paid_at", "2192", _money(run.tier2), "Tier 2 pension"),
        "tier3": ("tier3_paid_at", "2195", _money(run.tier3), "Tier 3 pension"),
    }[what]
    field, account, amount, label = plan
    if getattr(run, field) is not None:
        raise HTTPException(status_code=409, detail=f"{label} for {run.period} is already paid")
    if amount > 0:
        description = f"{label} {run.period}"
        money_account = accounting.pos_debit_account_for_payment_method(method)[0]
        await _post(
            db, tenant_id, user_id=user_id, description=description,
            lines=[
                {"account_code": account, "debit": amount, "credit": 0, "description": description},
                {"account_code": money_account, "debit": 0, "credit": amount, "description": description},
            ],
            reference=run.run_number, source=f"hrm_pay_{what}", source_id=run.id,
        )
    setattr(run, field, datetime.utcnow())
    settled = (
        run.staff_paid_at
        and run.paye_paid_at
        and run.ssnit_paid_at
        and (run.tier2_paid_at or engine.D(run.tier2) == 0)
        and (run.tier3_paid_at or engine.D(run.tier3) == 0)
    )
    if settled:
        run.status = "paid"
    await _audit(db, tenant_id, user_id, f"hrm_paid_{what}", "hrm_payroll", run.id, {"amount": amount, "method": method})
    await db.flush()
    return run


def _slip_dict(slip: m.HrmPayslip, employee: m.HrmEmployee | None) -> dict:
    return {
        "id": slip.id,
        "run_id": slip.run_id,
        "employee_id": slip.employee_id,
        "employee_name": employee.full_name if employee else None,
        "employee_number": employee.employee_number if employee else None,
        "job_title": employee.job_title if employee else None,
        "basic": _money(slip.basic),
        "allowances": _money(slip.allowances),
        "bonus": _money(slip.bonus),
        "unpaid_days": int(slip.unpaid_days or 0),
        "unpaid_deduction": _money(slip.unpaid_deduction),
        "gross": _money(slip.gross),
        "ssnit_employee": _money(slip.ssnit_employee),
        "taxable": _money(slip.taxable),
        "paye": _money(slip.paye),
        "other_deductions": _money(slip.other_deductions),
        "net": _money(slip.net),
        "ssnit_employer": _money(slip.ssnit_employer),
        "tier1": _money(slip.tier1),
        "tier2": _money(slip.tier2),
        "tier3": _money(slip.tier3),
        "tier3_relief": _money(slip.tier3_relief),
        "loan_deduction": _money(getattr(slip, "loan_deduction", 0)),
        "rates_used": slip.rates_used,
        "note": slip.note,
    }


async def present_run(db: AsyncSession, run: m.HrmPayrollRun, *, slips: bool = True) -> dict:
    data = {
        "id": run.id,
        "run_number": run.run_number,
        "period": run.period,
        "status": run.status,
        "gross": _money(run.gross),
        "net": _money(run.net),
        "paye": _money(run.paye),
        "ssnit_employee": _money(run.ssnit_employee),
        "ssnit_employer": _money(run.ssnit_employer),
        "other_deductions": _money(run.other_deductions),
        "staff_paid": run.staff_paid_at is not None,
        "paye_paid": run.paye_paid_at is not None,
        "ssnit_paid": run.ssnit_paid_at is not None,
        "tier2": _money(run.tier2),
        "tier3": _money(run.tier3),
        "ssnit_due": _money(engine.D(run.ssnit_employee) + engine.D(run.ssnit_employer) - engine.D(run.tier2)),
        "tier2_paid": run.tier2_paid_at is not None,
        "tier3_paid": run.tier3_paid_at is not None,
        "loan_deductions": _money(getattr(run, "loan_deductions", 0)),
        "statutory_rate_id": run.statutory_rate_id,
    }
    if slips:
        rows = await _slips(db, run.id)
        out = [_slip_dict(s, await db.get(m.HrmEmployee, s.employee_id)) for s in rows]
        data["slips"] = sorted(out, key=lambda r: r["employee_name"] or "")
    return data


async def list_runs(db: AsyncSession, tenant_id: str) -> list[m.HrmPayrollRun]:
    return list(
        (
            await db.execute(
                select(m.HrmPayrollRun).where(m.HrmPayrollRun.tenant_id == tenant_id).order_by(m.HrmPayrollRun.period.desc())
            )
        ).scalars().all()
    )


async def my_slips(db: AsyncSession, tenant_id: str, employee: m.HrmEmployee) -> list[dict]:
    """Staff only see payslips once the run is approved."""
    rows = (
        await db.execute(
            select(m.HrmPayslip, m.HrmPayrollRun)
            .join(m.HrmPayrollRun, m.HrmPayrollRun.id == m.HrmPayslip.run_id)
            .where(
                m.HrmPayslip.tenant_id == tenant_id,
                m.HrmPayslip.employee_id == employee.id,
                m.HrmPayrollRun.status != "draft",
            )
            .order_by(m.HrmPayrollRun.period.desc())
        )
    ).all()
    return [{**_slip_dict(slip, employee), "period": run.period} for slip, run in rows]


# --- Reports -----------------------------------------------------------------------------


async def summary(db: AsyncSession, tenant_id: str, *, money: bool = True) -> dict:
    today = date.today()
    people = await list_employees(db, tenant_id)
    pending = (
        await db.execute(
            select(func.count()).select_from(m.HrmLeaveRequest).where(
                m.HrmLeaveRequest.tenant_id == tenant_id, m.HrmLeaveRequest.status == "pending"
            )
        )
    ).scalar_one()
    marks = await attendance_for(db, tenant_id, today)
    away = [r for r in marks if r["status"] == "leave"]
    counts = {k: sum(1 for r in marks if r["status"] == k) for k in ("present", "late", "absent", "leave")}
    counts["not_marked"] = sum(1 for r in marks if not r["status"])
    data = {
        "date": today.isoformat(),
        "headcount": len(people),
        "leave_pending": int(pending or 0),
        "on_leave_today": [r["full_name"] for r in away],
        "attendance_today": counts,
    }
    attention = []
    if pending:
        attention.append(dash.item("warning", f"{dash.plural(int(pending), 'leave request')} waiting for a decision", "/hrm?tab=leave"))
    if people and counts["not_marked"] and today.weekday() < 5:
        attention.append(dash.item("info", f"Attendance not marked for {dash.plural(counts['not_marked'], 'person', 'people')} today", "/hrm?tab=attendance"))
    data["attention"] = attention
    if money:
        runs = await list_runs(db, tenant_id)
        data["monthly_basic"] = _money(sum(float(p.basic_salary or 0) + float(p.allowances or 0) for p in people))
        data["last_run"] = await present_run(db, runs[0], slips=False) if runs else None
        data["unpaid_items"] = [
            {"period": r.period, "what": label}
            for r in runs
            if r.status == "approved"
            for label, paid in (("Salaries", r.staff_paid_at), ("PAYE", r.paye_paid_at), ("SSNIT", r.ssnit_paid_at))
            if paid is None
        ]
        by_month = {r.period: float(r.gross or 0) + float(r.ssnit_employer or 0) for r in runs if r.status != "draft"}
        data["trend"] = dash.trend(
            "Payroll cost, last 6 months",
            "money",
            [{"date": key, "value": _money(by_month.get(key, 0))} for key in dash.months_back(6, today=today)],
            step="month",
        )
        for item in data["unpaid_items"]:
            attention.append(dash.item("warning", f"{item['what']} for {item['period']} not paid yet", "/hrm?tab=payroll"))
        this_month = today.strftime("%Y-%m")
        if not any(r.period == this_month for r in runs) and today.day >= 20:
            attention.append(dash.item("info", f"Payroll for {this_month} not drawn up yet", "/hrm?tab=payroll"))
        if any(r.status == "draft" for r in runs):
            attention.append(dash.item("info", "A payroll draft is waiting for approval", "/hrm?tab=payroll"))
    return data


async def report(db: AsyncSession, tenant_id: str, *, year: int) -> dict:
    runs = [r for r in await list_runs(db, tenant_id) if r.period.startswith(f"{year}-") and r.status != "draft"]
    people = await list_employees(db, tenant_id)
    departments: dict[str, int] = {}
    for person in people:
        name = person.department or "No department"
        departments[name] = departments.get(name, 0) + 1
    leave = (
        await db.execute(
            select(m.HrmLeaveRequest).where(m.HrmLeaveRequest.tenant_id == tenant_id, m.HrmLeaveRequest.status == "approved")
        )
    ).scalars().all()
    by_type: dict[str, int] = {}
    for row in leave:
        if row.starts_on.year == year:
            by_type[row.leave_type] = by_type.get(row.leave_type, 0) + int(row.days or 0)
    marks = (
        await db.execute(
            select(m.HrmAttendance.status, func.count())
            .where(
                m.HrmAttendance.tenant_id == tenant_id,
                m.HrmAttendance.day >= date(year, 1, 1),
                m.HrmAttendance.day <= date(year, 12, 31),
            )
            .group_by(m.HrmAttendance.status)
        )
    ).all()
    return {
        "year": year,
        "headcount": len(people),
        "by_department": sorted(({"name": k, "count": v} for k, v in departments.items()), key=lambda r: -r["count"]),
        "payroll": [await present_run(db, r, slips=False) for r in reversed(runs)],
        "payroll_cost": _money(sum(float(r.gross or 0) + float(r.ssnit_employer or 0) for r in runs)),
        "leave_days_by_type": by_type,
        "attendance": {status: int(count) for status, count in marks},
    }
