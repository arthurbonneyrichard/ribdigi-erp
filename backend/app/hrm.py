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
    ("2187", "Tips Owed to Staff", "liability"),
    ("6200", "Salaries and Wages", "expense"),
    ("6210", "Employer SSNIT", "expense"),
]

_JOBS = {
    # Officers run people admin; pay, reviews, claims and confidential cases need a manager.
    # Officers are staff too: "self" lets them use their own file (documents, feedback, cover).
    "hrm_officer": frozenset({"people", "leave", "attendance", "recruitment", "training", "contracts", "assets", "notices", "self"}),
    "hrm_employee": frozenset({"self"}),
}
# A desk's manager looks after their staff's records, leave and time, but not pay.
_DESK_MANAGER_AREAS = frozenset({"people", "leave", "attendance", "training", "contracts", "assets", "notices", "recruitment", "self"})
for _role in ("store_manager", "restaurant_manager", "hotel_manager", "bakery_manager", "fmcg_manager", "gym_manager"):
    _JOBS[_role] = _DESK_MANAGER_AREAS
_WORDS = {
    "store_manager": "Managers look after staff records, leave and time. Pay needs the company admin.",
    "restaurant_manager": "Managers look after staff records, leave and time. Pay needs the company admin.",
    "hotel_manager": "Managers look after staff records, leave and time. Pay needs the company admin.",
    "bakery_manager": "Managers look after staff records, leave and time. Pay needs the company admin.",
    "fmcg_manager": "Managers look after staff records, leave and time. Pay needs the company admin.",
    "gym_manager": "Managers look after staff records, leave and time. Pay needs the company admin.",
    "hrm_officer": "HR officers look after staff records, leave, attendance, hiring, training, contracts and assets. Pay, reviews, claims and cases need a manager.",
    "hrm_employee": "You can see your own leave and payslips. Ask HR for the rest.",
}


# Who runs HR: the HRM desk's manager and each company's admin. HR officers get their list
# (_JOBS). Everyone else with the hrm grant (a cashier, a waiter, a rep) sees only their own file.
HR_FULL_ROLES = frozenset({"company_admin", "hrm_manager", "super_admin"})

# The HR each industry gets (one engine, each company's rows on its own desk). "self" is always on.
ALL_HR_AREAS = frozenset(
    {"people", "leave", "attendance", "payroll", "recruitment", "reviews", "training",
     "contracts", "cases", "assets", "claims", "notices", "self"}
)
HR_AREAS_BY_INDUSTRY: dict[str, frozenset[str]] = {
    "hrm": ALL_HR_AREAS,
    "fmcg": ALL_HR_AREAS,
    "retail": frozenset({"people", "leave", "attendance", "payroll", "reviews", "claims", "notices", "self"}),
    "wholesale": frozenset({"people", "leave", "attendance", "payroll", "reviews", "claims", "notices", "self"}),
    "pharmacy": frozenset({"people", "leave", "attendance", "payroll", "training", "contracts", "reviews", "notices", "self"}),
    "restaurant": frozenset({"people", "leave", "attendance", "payroll", "reviews", "notices", "self"}),
    "hotel": frozenset({"people", "leave", "attendance", "payroll", "training", "contracts", "reviews", "notices", "self"}),
    "bakery": frozenset({"people", "leave", "attendance", "payroll", "notices", "self"}),
    "gym": frozenset({"people", "leave", "attendance", "payroll", "training", "notices", "self"}),
}


def hr_areas_for(industry: str | None) -> frozenset[str]:
    from app import packages as packages_svc

    return HR_AREAS_BY_INDUSTRY.get(packages_svc.canonicalize_industry(industry) or "", frozenset({"self"}))


def runs_hr(claims: dict) -> bool:
    """HR manager or company admin. Platform support staff do not see salaries."""
    return str(claims.get("role") or "") in HR_FULL_ROLES


def sees_pay(claims: dict) -> bool:
    return runs_hr(claims)


def job(claims: dict, area: str) -> None:
    role = str(claims.get("role") or "")
    from app.rbac import is_platform_role

    # Every request carries the company's industry; only internal calls leave it out.
    if "industry" in claims and not is_platform_role(role) and area not in hr_areas_for(claims.get("industry")):
        raise HTTPException(
            status_code=403,
            detail={"code": "HRM_AREA_OFF", "message": "This part of HR is not part of your business type's HR."},
        )
    if runs_hr(claims):
        return
    allowed = _JOBS.get(role, frozenset({"self"}))
    if area not in allowed:
        message = _WORDS.get(role, "You can see your own file under My pay and leave. Ask HR for the rest.")
        raise HTTPException(status_code=403, detail={"code": "HRM_ROLE_JOB", "message": message})


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
        "hours_per_day": money_json(getattr(row, "hours_per_day", 8) or 8),
        "overtime_rate": money_json(getattr(row, "overtime_rate", 1.5) or 1.5),
        "clock_needs_site": bool(getattr(row, "clock_needs_site", False)),
        "leave_accrual": getattr(row, "leave_accrual", None) or "upfront",
        "carry_over_days": int(getattr(row, "carry_over_days", 0) or 0),
        "part_pay_percent": money_json(getattr(row, "part_pay_percent", 80) if getattr(row, "part_pay_percent", None) is not None else 80),
        "escalate_after_days": int(getattr(row, "escalate_after_days", 3) if getattr(row, "escalate_after_days", None) is not None else 3),
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
        overtime_junior_cap=engine.D(row.overtime_junior_cap) if getattr(row, "overtime_junior_cap", None) is not None else None,
        overtime_low_rate=engine.D(getattr(row, "overtime_low_rate", 5) if getattr(row, "overtime_low_rate", None) is not None else 5),
        overtime_high_rate=engine.D(getattr(row, "overtime_high_rate", 10) if getattr(row, "overtime_high_rate", None) is not None else 10),
        overtime_low_share_percent=engine.D(
            getattr(row, "overtime_low_share_percent", 50) if getattr(row, "overtime_low_share_percent", None) is not None else 50
        ),
        minimum_daily_wage=engine.D(row.minimum_daily_wage) if getattr(row, "minimum_daily_wage", None) is not None else None,
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
        "overtime_junior_cap": money_json(row.overtime_junior_cap) if row.overtime_junior_cap is not None else None,
        "overtime_low_rate": money_json(row.overtime_low_rate if row.overtime_low_rate is not None else 5),
        "overtime_high_rate": money_json(row.overtime_high_rate if row.overtime_high_rate is not None else 10),
        "overtime_low_share_percent": money_json(row.overtime_low_share_percent if row.overtime_low_share_percent is not None else 50),
        "minimum_daily_wage": money_json(row.minimum_daily_wage) if row.minimum_daily_wage is not None else None,
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
        overtime_junior_cap=getattr(payload, "overtime_junior_cap", None),
        overtime_low_rate=getattr(payload, "overtime_low_rate", 5),
        overtime_high_rate=getattr(payload, "overtime_high_rate", 10),
        overtime_low_share_percent=getattr(payload, "overtime_low_share_percent", 50),
        minimum_daily_wage=getattr(payload, "minimum_daily_wage", None),
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
        "manager_id": getattr(row, "manager_id", None),
        "biometric_id": getattr(row, "biometric_id", None),
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
                "commission_percent": money_json(getattr(row, "commission_percent", 0) or 0),
                "pay_frequency": getattr(row, "pay_frequency", None) or "monthly",
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
        commission_percent=getattr(payload, "commission_percent", 0) or 0,
        pay_frequency=getattr(payload, "pay_frequency", None) or "monthly",
        manager_id=await _check_manager(db, tenant_id, getattr(payload, "manager_id", None), None),
        biometric_id=await _check_biometric(db, tenant_id, getattr(payload, "biometric_id", None), None),
    )
    db.add(row)
    await db.flush()
    await _audit(db, tenant_id, user_id, "hrm_employee_created", "hrm_employee", row.id, {"employee_number": row.employee_number})
    return row


async def _check_biometric(db: AsyncSession, tenant_id: str, pin: str | None, employee_id: str | None) -> str | None:
    """One terminal ID per person in a company, or punches would land on the wrong file."""
    pin = (pin or "").strip() or None
    if pin is None:
        return None
    taken = (
        await db.execute(
            select(m.HrmEmployee.id).where(
                m.HrmEmployee.tenant_id == tenant_id, m.HrmEmployee.biometric_id == pin, m.HrmEmployee.id != (employee_id or "")
            )
        )
    ).first()
    if taken:
        raise HTTPException(status_code=409, detail="Someone else already has that terminal ID")
    return pin


async def _check_manager(db: AsyncSession, tenant_id: str, manager_id: str | None, employee_id: str | None) -> str | None:
    if not manager_id:
        return None
    if manager_id == employee_id:
        raise HTTPException(status_code=422, detail="Someone cannot report to themselves")
    boss = await _employee(db, tenant_id, manager_id)
    # Refuse a loop: the new manager must not report (directly or up the line) to this person.
    seen, walk = set(), boss
    while walk is not None and walk.manager_id and walk.id not in seen:
        seen.add(walk.id)
        if walk.manager_id == employee_id:
            raise HTTPException(status_code=422, detail="That would make a reporting loop")
        walk = await db.get(m.HrmEmployee, walk.manager_id)
    return boss.id


async def update_employee(db: AsyncSession, tenant_id: str, employee_id: str, payload, *, user_id) -> m.HrmEmployee:
    row = await _employee(db, tenant_id, employee_id)
    data = payload.model_dump(exclude_unset=True)
    if "manager_id" in data:
        data["manager_id"] = await _check_manager(db, tenant_id, data["manager_id"], row.id)
    if "biometric_id" in data:
        data["biometric_id"] = await _check_biometric(db, tenant_id, data["biometric_id"], row.id)
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
    from app import hrm_leave_pay

    taken = sum(int(r.days or 0) for r in rows if r.starts_on.year == year)
    # Days paid out as money count as used.
    return taken + await hrm_leave_pay.encashed_days(db, employee_id, year)


def earned_days(annual: int, hired_on: date | None, year: int, *, accrual: str, upto: date | None = None) -> int:
    """Annual leave earned in a year. Upfront: the whole year, less months before someone
    started. Monthly: a twelfth for each month started so far (up to `upto`). Whole days, rounded down."""
    first_month = 1
    if hired_on and hired_on.year == year:
        first_month = hired_on.month
    elif hired_on and hired_on.year > year:
        return 0
    last_month = 12
    if accrual == "monthly":
        when = upto or date.today()
        if when.year < year:
            return 0
        last_month = 12 if when.year > year else when.month
    months = max(last_month - first_month + 1, 0)
    return (int(annual) * months) // 12


async def _entitlement(db: AsyncSession, tenant_id: str, employee: m.HrmEmployee, year: int, *, upto: date | None = None) -> dict:
    settings = await get_settings(db, tenant_id)
    accrual = getattr(settings, "leave_accrual", None) or "upfront"
    annual = int(settings.annual_leave_days)
    earned = earned_days(annual, employee.hired_on, year, accrual=accrual, upto=upto)
    carried = 0
    cap = int(getattr(settings, "carry_over_days", 0) or 0)
    if cap > 0:
        # Last year's own allowance less what was taken; carry-over does not stack year on year.
        last_year = earned_days(annual, employee.hired_on, year - 1, accrual="upfront")
        last_used = await _annual_used(db, tenant_id, employee.id, year - 1)
        carried = min(cap, max(last_year - last_used, 0))
    return {"earned": earned, "carried": carried, "entitled": earned + carried, "accrual": accrual}


async def leave_balance(db: AsyncSession, tenant_id: str, employee_id: str, *, year: int | None = None) -> dict:
    year = year or date.today().year
    employee = await _employee(db, tenant_id, employee_id)
    ent = await _entitlement(db, tenant_id, employee, year)
    used = await _annual_used(db, tenant_id, employee_id, year)
    return {
        "year": year,
        "entitled": ent["entitled"],
        "earned": ent["earned"],
        "carried": ent["carried"],
        "accrual": ent["accrual"],
        "used": used,
        "left": ent["entitled"] - used,
    }


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
        ent = await _entitlement(db, tenant_id, employee, payload.starts_on.year, upto=payload.ends_on)
        used = await _annual_used(db, tenant_id, employee.id, payload.starts_on.year, states=("approved", "pending"))
        if used + days > ent["entitled"]:
            left = ent["entitled"] - used
            raise HTTPException(status_code=409, detail=f"Only {max(left, 0)} annual leave days left by then")
    row = m.HrmLeaveRequest(
        tenant_id=tenant_id,
        employee_id=employee.id,
        leave_type=payload.leave_type,
        starts_on=payload.starts_on,
        ends_on=payload.ends_on,
        days=days,
        status="pending",
        stage="manager" if employee.manager_id else "hr",
        reason=optional_honest_narrative(payload.reason, label="reason", max_length=500),
        created_by=user_id,
    )
    db.add(row)
    await db.flush()
    from app import hrm_notify

    words = f"{employee.full_name} asks for {row.days} day(s) of {row.leave_type} leave from {row.starts_on.isoformat()}."
    if row.stage != "manager" or not await hrm_notify.to_manager(
        db, tenant_id, employee, "Leave to decide", words, entity_type="hrm_leave", entity_id=row.id, skip_user=user_id
    ):
        await hrm_notify.to_hr(db, tenant_id, "Leave to decide", words, entity_type="hrm_leave", entity_id=row.id, skip_user=user_id)
    return row


async def _user_employee(db: AsyncSession, tenant_id: str, user_id: str | None) -> m.HrmEmployee | None:
    try:
        return await employee_for_user(db, tenant_id, user_id)
    except HTTPException:
        return None


async def decide_leave(
    db: AsyncSession, tenant_id: str, leave_id: str, *, approve: bool, note: str | None, user_id, as_hr: bool = True
) -> m.HrmLeaveRequest:
    """Two steps when someone has a manager: the manager first, then HR. HR may decide at
    either step (it is recorded). A manager who is not HR decides only their own team's first step."""
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
    me = await _user_employee(db, tenant_id, user_id)
    from app import hrm_delegation

    # The manager, or the colleague covering for them today.
    is_manager = await hrm_delegation.acts_for_manager(db, me, employee.manager_id)
    stage = getattr(row, "stage", None) or "hr"
    if stage == "manager" and is_manager and approve:
        # The manager agrees; HR has the last word.
        row.stage = "hr"
        row.manager_decided_by = user_id
        row.manager_decided_at = datetime.utcnow()
        row.manager_note = optional_honest_narrative(note, label="note", max_length=255)
        await _audit(db, tenant_id, user_id, "hrm_leave_manager_approved", "hrm_leave", row.id, {"days": row.days})
        await db.flush()
        from app import hrm_notify

        await hrm_notify.to_hr(
            db, tenant_id, "Leave to decide",
            f"The manager agreed to {employee.full_name} taking {row.days} day(s) of leave from {row.starts_on.isoformat()}. HR has the last word.",
            entity_type="hrm_leave", entity_id=row.id, skip_user=user_id,
        )
        return row
    if not as_hr and not (stage == "manager" and is_manager):
        raise HTTPException(status_code=403, detail="HR decides this request")
    if stage == "manager" and is_manager:
        row.manager_decided_by = user_id
        row.manager_decided_at = datetime.utcnow()
        row.manager_note = optional_honest_narrative(note, label="note", max_length=255)
    row.status = "approved" if approve else "rejected"
    row.decision_note = optional_honest_narrative(note, label="note", max_length=255)
    row.decided_by = user_id
    row.decided_at = datetime.utcnow()
    details = {"days": row.days, "stage": stage}
    if stage == "manager" and not is_manager:
        details["manager_step_skipped_by_hr"] = True
    await _audit(db, tenant_id, user_id, f"hrm_leave_{row.status}", "hrm_leave", row.id, details)
    await db.flush()
    from app import hrm_notify

    await hrm_notify.to_person(
        db, tenant_id, employee, "Leave approved" if approve else "Leave turned down",
        f"Your {row.leave_type} leave from {row.starts_on.isoformat()} to {row.ends_on.isoformat()} was "
        + ("approved." if approve else f"turned down: {row.decision_note}"),
        entity_type="hrm_leave", entity_id=row.id, skip_user=user_id,
    )
    return row


async def team_leave(db: AsyncSession, tenant_id: str, manager: m.HrmEmployee) -> list[m.HrmLeaveRequest]:
    """Requests from the people who report to this manager, waiting for their decision."""
    from app import hrm_delegation

    # Their own team, and the teams of managers they cover for today.
    managers = [manager.id, *await hrm_delegation.covered_managers(db, manager.id)]
    team = select(m.HrmEmployee.id).where(m.HrmEmployee.tenant_id == tenant_id, m.HrmEmployee.manager_id.in_(managers))
    return list(
        (
            await db.execute(
                select(m.HrmLeaveRequest)
                .where(
                    m.HrmLeaveRequest.tenant_id == tenant_id,
                    m.HrmLeaveRequest.employee_id.in_(team),
                    m.HrmLeaveRequest.status == "pending",
                    m.HrmLeaveRequest.stage == "manager",
                )
                .order_by(m.HrmLeaveRequest.starts_on)
            )
        ).scalars()
    )


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
        "stage": getattr(row, "stage", None) or "hr",
        "manager_note": getattr(row, "manager_note", None),
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
                # Approved overtime: taxable, no SSNIT; junior staff may get the separate overtime tax.
                overtime=engine.D(getattr(slip, "overtime", 0)),
                arrears_basic=engine.D(getattr(slip, "arrears_basic", 0)),
                # Commission and tips are taxable earnings without SSNIT, like a correction.
                adjustment=engine.D(getattr(slip, "adjustment", 0))
                + engine.D(getattr(slip, "commission", 0))
                + engine.D(getattr(slip, "tips", 0))
                + engine.D(getattr(slip, "leave_pay", 0)),
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
    slip.overtime_tax = out.overtime_tax
    slip.warnings = list(out.warnings) or None
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
    run.tips = sum((engine.D(getattr(s, "tips", 0)) for s in slips), engine.ZERO)


async def create_run(db: AsyncSession, tenant_id: str, *, period: str, user_id) -> m.HrmPayrollRun:
    first, last = _month(period)
    clash = (
        await db.execute(select(m.HrmPayrollRun.id).where(m.HrmPayrollRun.tenant_id == tenant_id, m.HrmPayrollRun.period == period))
    ).first()
    if clash:
        raise HTTPException(status_code=409, detail=f"Payroll for {period} already exists")
    from app import hrm_loans
    from app import hrm_pay_changes

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
        basic, allowances = await hrm_pay_changes.salary_for(db, person, first)
        arrears, correction = await hrm_pay_changes.take_pending(db, tenant_id, person.id, run.id)
        from app import hrm_time

        overtime = await hrm_time.take_overtime(db, person.id, period, run.id)
        from app import hrm_commission

        commission = await hrm_commission.take(db, person.id, period, run.id)
        from app import restaurant_tips

        tips = await restaurant_tips.take(db, person.id, period, run.id)
        from app import hrm_leave_pay

        leave_pay = await hrm_leave_pay.take(db, person.id, period, run.id)
        from app import hrm_part_pay

        part_paid = await hrm_part_pay.part_paid_this_month(db, person.id, period)
        slip = m.HrmPayslip(
            tenant_id=tenant_id,
            run_id=run.id,
            employee_id=person.id,
            basic=basic,
            allowances=allowances,
            arrears_basic=arrears,
            adjustment=correction,
            overtime=overtime,
            commission=commission,
            tips=tips,
            leave_pay=leave_pay,
            part_paid=part_paid,
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
    from app import hrm_pay_changes

    await hrm_pay_changes.release_run(db, run.id)
    from app import hrm_time

    await hrm_time.release_overtime(db, run.id)
    from app import hrm_commission

    await hrm_commission.release(db, run.id)
    from app import restaurant_tips

    await restaurant_tips.release(db, run.id)
    from app import hrm_leave_pay

    await hrm_leave_pay.release(db, run.id)
    for slip in await _slips(db, run.id):
        await db.delete(slip)
    # Payslips must be gone before the run: nothing tells the session their order, and
    # Postgres refuses to drop a run its payslips still point to.
    await db.flush()
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
    under = [s for s in slips if "below_minimum_wage" in (s.warnings or [])]
    if under:
        names = []
        for s in under:
            person = await db.get(m.HrmEmployee, s.employee_id)
            names.append(person.full_name if person else s.employee_id)
        raise HTTPException(
            status_code=409,
            detail={"code": "BELOW_MINIMUM_WAGE", "message": "Pay is under the daily minimum wage for: " + ", ".join(names)},
        )
    _totals(run, slips)
    description = f"Payroll {run.period}"
    other = _money(run.other_deductions)
    run.journal_entry_id = await _post(
        db, tenant_id, user_id=user_id, description=description,
        lines=[
            # Tips were already set aside in 2187 when the guests paid; they are not a wage cost.
            {"account_code": "6200", "debit": _money(engine.D(run.gross) - engine.D(run.tips)), "credit": 0, "description": description},
            {"account_code": "2187", "debit": _money(run.tips), "credit": 0, "description": description},
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
    from app import hrm_pay_changes

    await hrm_pay_changes.settle_run(db, run.id)
    from app import hrm_time

    await hrm_time.settle_overtime(db, run.id)
    from app import hrm_commission

    await hrm_commission.settle(db, run.id)
    from app import restaurant_tips

    await restaurant_tips.settle(db, run.id)
    from app import hrm_leave_pay

    await hrm_leave_pay.settle(db, run.id)
    run.status = "approved"
    run.approved_by = user_id
    run.approved_at = datetime.utcnow()
    await _audit(db, tenant_id, user_id, "hrm_payroll_approved", "hrm_payroll", run.id, {"period": run.period, "net": _money(run.net)})
    await db.flush()
    from app import hrm_notify

    for slip in slips:
        await hrm_notify.to_person(
            db, tenant_id, await db.get(m.HrmEmployee, slip.employee_id), "Payslip ready",
            f"Your payslip for {run.period} is ready under My HR.", entity_type="hrm_payslip", entity_id=slip.id,
        )
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
        "arrears_basic": _money(getattr(slip, "arrears_basic", 0)),
        "adjustment": _money(getattr(slip, "adjustment", 0)),
        "overtime": _money(getattr(slip, "overtime", 0)),
        "commission": _money(getattr(slip, "commission", 0)),
        "tips": _money(getattr(slip, "tips", 0)),
        "leave_pay": _money(getattr(slip, "leave_pay", 0)),
        # Part-payments come off first; the rest of loan_deduction is loan / advance repayment.
        "part_paid": _money(min(engine.D(getattr(slip, "part_paid", 0)), engine.D(getattr(slip, "loan_deduction", 0)))),
        "overtime_tax": _money(getattr(slip, "overtime_tax", 0)),
        "warnings": list(getattr(slip, "warnings", None) or []),
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
    # People work coming due (no money in these, so officers see them too).
    from app import hrm_people

    alerts = await hrm_people.contract_alerts(db, tenant_id)
    if alerts["contracts_ending"]:
        attention.append(dash.item("warning", f"{dash.plural(len(alerts['contracts_ending']), 'contract')} ending within 30 days", "/hrm?tab=contracts"))
    if alerts["probation_due"]:
        attention.append(dash.item("warning", f"{dash.plural(len(alerts['probation_due']), 'probation')} to confirm", "/hrm?tab=contracts"))
    gaps = await hrm_people.training_gaps(db, tenant_id)
    if gaps:
        attention.append(dash.item("info", f"{dash.plural(len(gaps), 'mandatory course')} not done or lapsed", "/hrm?tab=training"))
    if money:
        runs = await list_runs(db, tenant_id)
        data["monthly_basic"] = _money(sum(float(p.basic_salary or 0) + float(p.allowances or 0) for p in people))
        data["last_run"] = await present_run(db, runs[0], slips=False) if runs else None
        data["unpaid_items"] = [
            {"period": r.period, "what": label}
            for r in runs
            if r.status == "approved"
            for label, paid, due in (
                ("Salaries", r.staff_paid_at, True),
                ("PAYE", r.paye_paid_at, True),
                ("SSNIT", r.ssnit_paid_at, True),
                ("Tier 2 pension", r.tier2_paid_at, engine.D(r.tier2) > 0),
                ("Tier 3 pension", r.tier3_paid_at, engine.D(r.tier3) > 0),
            )
            if due and paid is None
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
        waiting_loans = (
            await db.execute(
                select(func.count()).select_from(m.HrmLoan).where(m.HrmLoan.tenant_id == tenant_id, m.HrmLoan.status == "pending")
            )
        ).scalar_one()
        if waiting_loans:
            attention.append(dash.item("warning", f"{dash.plural(int(waiting_loans), 'loan or advance request', 'loan or advance requests')} waiting", "/hrm?tab=loans"))
        waiting_claims = (
            await db.execute(
                select(func.count()).select_from(m.HrmClaim).where(m.HrmClaim.tenant_id == tenant_id, m.HrmClaim.status == "pending")
            )
        ).scalar_one()
        if waiting_claims:
            attention.append(dash.item("warning", f"{dash.plural(int(waiting_claims), 'expense claim')} waiting", "/hrm?tab=claims"))
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
