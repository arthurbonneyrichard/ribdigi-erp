"""HRM routes. The `hrm` permission and the industry gate come from require_permission."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app import hrm as svc
from app import hrm_loans as loans_svc
from app import hrm_pay_changes as changes_svc
from app.db import get_db
from app.schemas import E164PhoneValue, NonNegativeMoneyValue, PartyNameValue, UuidIdValue
from app.security import require_permission

router = APIRouter(prefix="/hrm", tags=["hrm"])

Short = Annotated[str, Field(min_length=1, max_length=120)]
Period = Annotated[str, Field(pattern=r"^20\d{2}-(0[1-9]|1[0-2])$")]
PayMethod = Literal["bank_transfer", "cash", "mobile_money", "cheque"]
LeaveType = Literal["annual", "sick", "maternity", "paternity", "compassionate", "unpaid"]
GhanaCard = Annotated[str, Field(pattern=r"^GHA-\d{9}-\d$")]
Percent = Annotated[Decimal, Field(ge=0, le=100, max_digits=7, decimal_places=3)]


def _env(data, message: str = "OK"):
    from app.api import env

    return env(data, message)


def _sees_pay(claims: dict) -> bool:
    return svc.sees_pay(claims)


class EmployeeBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: PartyNameValue
    phone: E164PhoneValue | None = None
    email: EmailStr | None = None
    job_title: Short | None = None
    department: Short | None = None
    hired_on: date
    basic_salary: NonNegativeMoneyValue = 0
    allowances: NonNegativeMoneyValue = 0
    ssnit_number: Annotated[str, Field(min_length=1, max_length=40)] | None = None
    tin: Annotated[str, Field(min_length=1, max_length=40)] | None = None
    bank_name: Short | None = None
    bank_account: Annotated[str, Field(min_length=1, max_length=64)] | None = None
    ghana_card: GhanaCard | None = None
    mobile_money: E164PhoneValue | None = None
    tier3_percent: Percent = Decimal("0")
    commission_percent: Percent = Decimal("0")
    manager_id: UuidIdValue | None = None
    biometric_id: Annotated[str, Field(min_length=1, max_length=32, pattern=r"^[A-Za-z0-9_-]+$")] | None = None


class EmployeeUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phone: E164PhoneValue | None = None
    email: EmailStr | None = None
    job_title: Short | None = None
    department: Short | None = None
    basic_salary: NonNegativeMoneyValue | None = None
    allowances: NonNegativeMoneyValue | None = None
    ssnit_number: Annotated[str, Field(min_length=1, max_length=40)] | None = None
    tin: Annotated[str, Field(min_length=1, max_length=40)] | None = None
    bank_name: Short | None = None
    bank_account: Annotated[str, Field(min_length=1, max_length=64)] | None = None
    ghana_card: GhanaCard | None = None
    mobile_money: E164PhoneValue | None = None
    tier3_percent: Percent | None = None
    commission_percent: Percent | None = None
    manager_id: UuidIdValue | None = None
    biometric_id: Annotated[str, Field(min_length=1, max_length=32, pattern=r"^[A-Za-z0-9_-]+$")] | None = None


class LeftBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    left_on: date
    reason: Annotated[str, Field(min_length=3, max_length=255)]


class LeaveBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    employee_id: UuidIdValue | None = None
    leave_type: LeaveType
    starts_on: date
    ends_on: date
    reason: Annotated[str, Field(min_length=1, max_length=500)] | None = None


class DecideBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approve: bool
    note: Annotated[str, Field(min_length=1, max_length=255)] | None = None


class Mark(BaseModel):
    model_config = ConfigDict(extra="forbid")

    employee_id: UuidIdValue
    status: Literal["present", "absent", "late", "leave"]


class AttendanceBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    day: date
    marks: list[Mark] = Field(min_length=1, max_length=2000)


class RunBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    period: Period


class SlipBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bonus: NonNegativeMoneyValue | None = None
    other_deductions: NonNegativeMoneyValue | None = None
    note: Annotated[str, Field(min_length=1, max_length=255)] | None = None


class PayBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    what: Literal["staff", "paye", "ssnit", "tier2", "tier3"]
    method: PayMethod


class Band(BaseModel):
    model_config = ConfigDict(extra="forbid")

    width: Annotated[float, Field(gt=0, allow_inf_nan=False)] | None = None
    rate: Annotated[float, Field(ge=0, le=100, allow_inf_nan=False)]


class SettingsBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    annual_leave_days: Annotated[int, Field(ge=0, le=120)] | None = None
    working_days_per_month: Annotated[int, Field(ge=1, le=31)] | None = None
    ssnit_employee_percent: Annotated[float, Field(ge=0, le=100, allow_inf_nan=False)] | None = None
    ssnit_employer_percent: Annotated[float, Field(ge=0, le=100, allow_inf_nan=False)] | None = None
    paye_bands: list[Band] | None = Field(default=None, min_length=1, max_length=20)
    two_person_payroll: bool | None = None
    leave_accrual: Literal["upfront", "monthly"] | None = None
    hours_per_day: Annotated[Decimal, Field(gt=0, le=24, max_digits=5, decimal_places=2)] | None = None
    overtime_rate: Annotated[Decimal, Field(ge=1, le=5, max_digits=5, decimal_places=2)] | None = None
    clock_needs_site: bool | None = None
    carry_over_days: Annotated[int, Field(ge=0, le=120)] | None = None
    escalate_after_days: Annotated[int, Field(ge=0, le=60)] | None = None


class RateBand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    width: Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=2)] | None = None
    rate: Percent


class StatutoryRateBody(BaseModel):
    """PAYE bands and SSNIT / pension rules from a date onwards. Check them against GRA and SSNIT."""

    model_config = ConfigDict(extra="forbid")

    effective_from: date
    employee_percent: Percent
    employer_percent: Percent
    tier2_percent: Percent = Decimal("0")
    insurable_cap: Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=2)] | None = None
    tier3_relief_percent: Percent = Decimal("16.5")
    paye_bands: list[RateBand] = Field(min_length=1, max_length=20)
    rounding: Literal["half_up", "down"] = "half_up"
    # Junior-staff overtime tax (GRA): monthly earned-basic limit; omit to tax overtime as ordinary pay.
    overtime_junior_cap: Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=2)] | None = None
    overtime_low_rate: Percent = Decimal("5")
    overtime_high_rate: Percent = Decimal("10")
    overtime_low_share_percent: Percent = Decimal("50")
    # National daily minimum wage; omit for no check.
    minimum_daily_wage: Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=2)] | None = None
    source_note: Annotated[str, Field(min_length=3, max_length=255)] | None = None


@router.get("/statutory-rates")
async def hrm_rates(claims=Depends(require_permission("hrm", "read")), db: AsyncSession = Depends(get_db)):
    svc.job(claims, "payroll")
    return _env(await svc.list_rates(db, claims["tenant_id"]))


@router.post("/statutory-rates")
async def hrm_rates_add(
    payload: StatutoryRateBody, claims=Depends(require_permission("hrm", "write")), db: AsyncSession = Depends(get_db)
):
    svc.job(claims, "payroll")
    row = await svc.add_rate(db, claims["tenant_id"], payload, user_id=claims.get("sub"))
    await db.commit()
    return _env(svc.serialize_rate(row), "Rates saved")


@router.delete("/statutory-rates/{rate_id}")
async def hrm_rates_delete(
    rate_id: UuidIdValue, claims=Depends(require_permission("hrm", "write")), db: AsyncSession = Depends(get_db)
):
    svc.job(claims, "payroll")
    await svc.delete_rate(db, claims["tenant_id"], rate_id, user_id=claims.get("sub"))
    await db.commit()
    return _env(None, "Rates removed")


class HolidayItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    day: date
    name: Annotated[str, Field(min_length=2, max_length=120)]


class HolidaysBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    holidays: list[HolidayItem] = Field(min_length=1, max_length=40)


Money = Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=2)]


class LoanBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    employee_id: UuidIdValue
    kind: Literal["loan", "advance"]
    principal: Money
    monthly_deduction: Money
    first_period: Period | None = None
    reason: Annotated[str, Field(min_length=3, max_length=500)] | None = None


class MyLoanBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["loan", "advance"]
    principal: Money
    monthly_deduction: Money
    reason: Annotated[str, Field(min_length=3, max_length=500)]


class LoanDecideBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approve: bool
    method: PayMethod | None = None
    note: Annotated[str, Field(min_length=1, max_length=255)] | None = None


class LoanRepayBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: Money
    method: PayMethod


@router.get("/holidays")
async def hrm_holidays(
    year: Annotated[int, Query(ge=2000, le=2100)] = date.today().year,
    claims=Depends(require_permission("hrm", "read")),
    db: AsyncSession = Depends(get_db),
):
    svc.job(claims, "leave")
    return _env([loans_svc.serialize_holiday(r) for r in await loans_svc.list_holidays(db, claims["tenant_id"], year)])


@router.get("/holidays/suggested")
async def hrm_holidays_suggested(
    year: Annotated[int, Query(ge=2000, le=2100)] = date.today().year,
    claims=Depends(require_permission("hrm", "read")),
):
    """A starting list to check, not an official one. Nothing is saved."""
    svc.job(claims, "leave")
    return _env(loans_svc.suggested_ghana_holidays(year))


@router.post("/holidays")
async def hrm_holidays_add(
    payload: HolidaysBody, claims=Depends(require_permission("hrm", "write")), db: AsyncSession = Depends(get_db)
):
    svc.job(claims, "leave")
    rows = await loans_svc.add_holidays(db, claims["tenant_id"], payload.holidays, user_id=claims.get("sub"))
    await db.commit()
    return _env([loans_svc.serialize_holiday(r) for r in rows], f"{len(rows)} holiday(s) saved")


@router.delete("/holidays/{holiday_id}")
async def hrm_holidays_delete(
    holiday_id: UuidIdValue, claims=Depends(require_permission("hrm", "write")), db: AsyncSession = Depends(get_db)
):
    svc.job(claims, "leave")
    await loans_svc.delete_holiday(db, claims["tenant_id"], holiday_id, user_id=claims.get("sub"))
    await db.commit()
    return _env(None, "Holiday removed")


@router.get("/loans")
async def hrm_loans(claims=Depends(require_permission("hrm", "read")), db: AsyncSession = Depends(get_db)):
    svc.job(claims, "payroll")
    return _env(await loans_svc.present_loans(db, await loans_svc.list_loans(db, claims["tenant_id"])))


@router.post("/loans")
async def hrm_loan_add(
    payload: LoanBody, claims=Depends(require_permission("hrm", "write")), db: AsyncSession = Depends(get_db)
):
    svc.job(claims, "payroll")
    row = await loans_svc.request_loan(
        db, claims["tenant_id"], employee_id=payload.employee_id, payload=payload, user_id=claims.get("sub")
    )
    await db.commit()
    return _env(loans_svc.serialize_loan(row), "Request recorded")


@router.post("/loans/{loan_id}/decide")
async def hrm_loan_decide(
    loan_id: UuidIdValue,
    payload: LoanDecideBody,
    claims=Depends(require_permission("hrm", "write")),
    db: AsyncSession = Depends(get_db),
):
    svc.job(claims, "payroll")
    row = await loans_svc.decide_loan(
        db, claims["tenant_id"], loan_id, approve=payload.approve, method=payload.method,
        note=payload.note, user_id=claims.get("sub"),
    )
    await db.commit()
    return _env(loans_svc.serialize_loan(row), "Approved and paid out" if payload.approve else "Turned down")


@router.post("/loans/{loan_id}/repay")
async def hrm_loan_repay(
    loan_id: UuidIdValue,
    payload: LoanRepayBody,
    claims=Depends(require_permission("hrm", "write")),
    db: AsyncSession = Depends(get_db),
):
    svc.job(claims, "payroll")
    row = await loans_svc.repay_cash(
        db, claims["tenant_id"], loan_id, amount=payload.amount, method=payload.method, user_id=claims.get("sub")
    )
    await db.commit()
    return _env(loans_svc.serialize_loan(row), "Repayment recorded")


@router.post("/me/loans")
async def hrm_my_loan(
    payload: MyLoanBody, claims=Depends(require_permission("hrm", "write")), db: AsyncSession = Depends(get_db)
):
    """Anyone with a staff record asks for their own loan or advance; payroll decides."""
    employee = await svc.employee_for_user(db, claims["tenant_id"], claims.get("sub"))
    row = await loans_svc.request_loan(
        db, claims["tenant_id"], employee_id=employee.id, payload=payload, user_id=claims.get("sub")
    )
    await db.commit()
    return _env(loans_svc.serialize_loan(row), "Request sent to payroll")


class SalaryChangeBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    effective_from: date
    basic_salary: NonNegativeMoneyValue
    allowances: NonNegativeMoneyValue = 0
    reason: Annotated[str, Field(min_length=3, max_length=255)]


class AdjustmentBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    employee_id: UuidIdValue
    kind: Literal["arrears", "correction"]
    amount: Annotated[Decimal, Field(max_digits=14, decimal_places=2, ge=-1_000_000_000, le=1_000_000_000)]
    for_period: Period | None = None
    reason: Annotated[str, Field(min_length=3, max_length=255)]


PeriodQuery = Annotated[str, Query(pattern=r"^20\d{2}-(0[1-9]|1[0-2])$")]


@router.get("/employees/{employee_id}/salary")
async def hrm_salary_history(
    employee_id: UuidIdValue, claims=Depends(require_permission("hrm", "read")), db: AsyncSession = Depends(get_db)
):
    svc.job(claims, "payroll")
    rows = await changes_svc.list_changes(db, claims["tenant_id"], employee_id)
    return _env([changes_svc.serialize_change(r) for r in rows])


@router.post("/employees/{employee_id}/salary")
async def hrm_salary_change(
    employee_id: UuidIdValue,
    payload: SalaryChangeBody,
    claims=Depends(require_permission("hrm", "write")),
    db: AsyncSession = Depends(get_db),
):
    svc.job(claims, "payroll")
    body = await changes_svc.add_change(db, claims["tenant_id"], employee_id, payload, user_id=claims.get("sub"))
    await db.commit()
    months = len({a["for_period"] for a in body["adjustments"]})
    message = "Salary change saved" + (f"; back pay raised for {months} month(s)" if months else "")
    return _env(body, message)


@router.get("/adjustments")
async def hrm_adjustments(claims=Depends(require_permission("hrm", "read")), db: AsyncSession = Depends(get_db)):
    svc.job(claims, "payroll")
    return _env(await changes_svc.list_adjustments(db, claims["tenant_id"]))


@router.post("/adjustments")
async def hrm_adjustment_add(
    payload: AdjustmentBody, claims=Depends(require_permission("hrm", "write")), db: AsyncSession = Depends(get_db)
):
    svc.job(claims, "payroll")
    row = await changes_svc.add_adjustment(db, claims["tenant_id"], payload, user_id=claims.get("sub"))
    await db.commit()
    return _env(changes_svc.serialize_adjustment(row), "Correction saved for the next payroll")


@router.delete("/adjustments/{adjustment_id}")
async def hrm_adjustment_cancel(
    adjustment_id: UuidIdValue, claims=Depends(require_permission("hrm", "write")), db: AsyncSession = Depends(get_db)
):
    svc.job(claims, "payroll")
    await changes_svc.cancel_adjustment(db, claims["tenant_id"], adjustment_id, user_id=claims.get("sub"))
    await db.commit()
    return _env(None, "Correction cancelled")


@router.get("/reports/paye")
async def hrm_paye_schedule(
    period: PeriodQuery, claims=Depends(require_permission("hrm", "read")), db: AsyncSession = Depends(get_db)
):
    svc.job(claims, "payroll")
    return _env(await changes_svc.paye_schedule(db, claims["tenant_id"], period))


@router.get("/reports/ssnit")
async def hrm_ssnit_schedule(
    period: PeriodQuery, claims=Depends(require_permission("hrm", "read")), db: AsyncSession = Depends(get_db)
):
    svc.job(claims, "payroll")
    return _env(await changes_svc.ssnit_schedule(db, claims["tenant_id"], period))


@router.get("/reports/tax-statement")
async def hrm_tax_statement(
    employee_id: UuidIdValue,
    year: Annotated[int, Query(ge=2000, le=2100)],
    claims=Depends(require_permission("hrm", "read")),
    db: AsyncSession = Depends(get_db),
):
    svc.job(claims, "payroll")
    employee = await svc._employee(db, claims["tenant_id"], employee_id)
    return _env(await changes_svc.tax_statement(db, claims["tenant_id"], employee, year))


@router.get("/me/tax-statement")
async def hrm_my_tax_statement(
    year: Annotated[int, Query(ge=2000, le=2100)],
    claims=Depends(require_permission("hrm", "read")),
    db: AsyncSession = Depends(get_db),
):
    employee = await svc.employee_for_user(db, claims["tenant_id"], claims.get("sub"))
    return _env(await changes_svc.tax_statement(db, claims["tenant_id"], employee, year))


class CommissionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    employee_id: UuidIdValue
    period: Period


@router.get("/commissions")
async def hrm_commissions(
    period: Annotated[str, Query(pattern=r"^20\d{2}-(0[1-9]|1[0-2])$")],
    claims=Depends(require_permission("hrm", "read")),
    db: AsyncSession = Depends(get_db),
):
    svc.job(claims, "payroll")
    from app import hrm_commission

    return _env(await hrm_commission.month(db, claims["tenant_id"], period))


@router.post("/commissions")
async def hrm_commission_approve(
    payload: CommissionBody, claims=Depends(require_permission("hrm", "write")), db: AsyncSession = Depends(get_db)
):
    svc.job(claims, "payroll")
    from app import hrm_commission

    row = await hrm_commission.approve(db, claims["tenant_id"], employee_id=payload.employee_id, period=payload.period, user_id=claims.get("sub"))
    await db.commit()
    return _env({"amount": float(row.amount), "net_sales": float(row.net_sales), "period": row.period}, "Commission approved for that month's payroll")


class LeaveEncashBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    employee_id: UuidIdValue
    year: Annotated[int, Field(ge=2000, le=2100)]
    days: Annotated[int, Field(ge=1, le=366)]
    period: Annotated[str, Field(pattern=r"^20\d{2}-(0[1-9]|1[0-2])$")]
    note: Annotated[str, Field(max_length=255)] | None = None


@router.get("/employees/{employee_id}/leave-balance")
async def hrm_leave_balance(
    employee_id: UuidIdValue, year: Annotated[int | None, Query(ge=2000, le=2100)] = None,
    claims=Depends(require_permission("hrm", "read")), db: AsyncSession = Depends(get_db),
):
    svc.job(claims, "leave")
    return _env(await svc.leave_balance(db, claims["tenant_id"], employee_id, year=year))


@router.get("/leave-encashments")
async def hrm_leave_encashments(claims=Depends(require_permission("hrm", "read")), db: AsyncSession = Depends(get_db)):
    svc.job(claims, "payroll")
    from app import hrm_leave_pay

    return _env(await hrm_leave_pay.list_all(db, claims["tenant_id"]))


@router.post("/leave-encashments")
async def hrm_leave_encash(payload: LeaveEncashBody, claims=Depends(require_permission("hrm", "write")), db: AsyncSession = Depends(get_db)):
    svc.job(claims, "payroll")
    from app import hrm_leave_pay

    row = await hrm_leave_pay.approve(db, claims["tenant_id"], payload, user_id=claims.get("sub"))
    await db.commit()
    return _env(hrm_leave_pay.serialize(row, await db.get(svc.m.HrmEmployee, row.employee_id)), "Leave payout approved for that month's payroll")


@router.post("/leave-encashments/{row_id}/cancel")
async def hrm_leave_encash_cancel(row_id: UuidIdValue, claims=Depends(require_permission("hrm", "write")), db: AsyncSession = Depends(get_db)):
    svc.job(claims, "payroll")
    from app import hrm_leave_pay

    row = await hrm_leave_pay.cancel(db, claims["tenant_id"], row_id, user_id=claims.get("sub"))
    await db.commit()
    return _env(hrm_leave_pay.serialize(row, None), "Cancelled; the days are back")


@router.get("/summary")
async def hrm_summary(claims=Depends(require_permission("hrm", "read")), db: AsyncSession = Depends(get_db)):
    svc.job(claims, "people")
    return _env(await svc.summary(db, claims["tenant_id"], money=_sees_pay(claims)))


@router.get("/settings")
async def hrm_settings(claims=Depends(require_permission("hrm", "read")), db: AsyncSession = Depends(get_db)):
    svc.job(claims, "payroll")
    row = await svc.get_settings(db, claims["tenant_id"])
    await db.commit()
    return _env(svc.serialize_settings(row))


@router.patch("/settings")
async def hrm_settings_update(
    payload: SettingsBody, claims=Depends(require_permission("hrm", "write")), db: AsyncSession = Depends(get_db)
):
    svc.job(claims, "payroll")
    row = await svc.update_settings(db, claims["tenant_id"], payload, user_id=claims.get("sub"))
    await db.commit()
    return _env(svc.serialize_settings(row), "Settings saved")


@router.get("/employees")
async def hrm_employees(
    show: Annotated[str, Query(pattern="^(active|left|all)$")] = "active",
    claims=Depends(require_permission("hrm", "read")),
    db: AsyncSession = Depends(get_db),
):
    svc.job(claims, "people")
    pay = _sees_pay(claims)
    return _env([svc.serialize_employee(r, pay=pay) for r in await svc.list_employees(db, claims["tenant_id"], show=show)])


@router.post("/employees")
async def hrm_employee_create(
    payload: EmployeeBody, claims=Depends(require_permission("hrm", "write")), db: AsyncSession = Depends(get_db)
):
    svc.job(claims, "people")
    row = await svc.create_employee(db, claims["tenant_id"], payload, user_id=claims.get("sub"))
    await db.commit()
    return _env(svc.serialize_employee(row, pay=_sees_pay(claims)), "Employee added")


@router.patch("/employees/{employee_id}")
async def hrm_employee_update(
    employee_id: UuidIdValue,
    payload: EmployeeUpdate,
    claims=Depends(require_permission("hrm", "write")),
    db: AsyncSession = Depends(get_db),
):
    svc.job(claims, "payroll" if {"basic_salary", "allowances", "commission_percent", "tier3_percent"} & payload.model_fields_set else "people")
    row = await svc.update_employee(db, claims["tenant_id"], employee_id, payload, user_id=claims.get("sub"))
    await db.commit()
    return _env(svc.serialize_employee(row, pay=_sees_pay(claims)), "Saved")


@router.post("/employees/{employee_id}/left")
async def hrm_employee_left(
    employee_id: UuidIdValue,
    payload: LeftBody,
    claims=Depends(require_permission("hrm", "write")),
    db: AsyncSession = Depends(get_db),
):
    svc.job(claims, "people")
    row = await svc.end_employment(
        db, claims["tenant_id"], employee_id, left_on=payload.left_on, reason=payload.reason, user_id=claims.get("sub")
    )
    await db.commit()
    return _env(svc.serialize_employee(row, pay=_sees_pay(claims)), "Marked as left")


@router.get("/leave")
async def hrm_leave(claims=Depends(require_permission("hrm", "read")), db: AsyncSession = Depends(get_db)):
    svc.job(claims, "leave")
    return _env([await svc.present_leave(db, r) for r in await svc.list_leave(db, claims["tenant_id"])])


@router.post("/leave")
async def hrm_leave_create(
    payload: LeaveBody, claims=Depends(require_permission("hrm", "write")), db: AsyncSession = Depends(get_db)
):
    tenant_id = claims["tenant_id"]
    if str(claims.get("role") or "") == "hrm_employee" or not payload.employee_id:
        employee_id = (await svc.employee_for_user(db, tenant_id, claims.get("sub"))).id
    else:
        svc.job(claims, "leave")
        employee_id = payload.employee_id
    row = await svc.request_leave(db, tenant_id, employee_id=employee_id, payload=payload, user_id=claims.get("sub"))
    await db.commit()
    return _env(await svc.present_leave(db, row), "Leave requested")


@router.post("/leave/{leave_id}/decide")
async def hrm_leave_decide(
    leave_id: UuidIdValue,
    payload: DecideBody,
    claims=Depends(require_permission("hrm", "write")),
    db: AsyncSession = Depends(get_db),
):
    # Staff who manage people decide their team's first step; everything else needs the leave job.
    as_hr = svc.runs_hr(claims) or str(claims.get("role") or "") in svc._JOBS and "leave" in svc._JOBS[str(claims.get("role"))]
    if as_hr:
        svc.job(claims, "leave")
    row = await svc.decide_leave(
        db, claims["tenant_id"], leave_id, approve=payload.approve, note=payload.note,
        user_id=claims.get("sub"), as_hr=as_hr,
    )
    await db.commit()
    return _env(await svc.present_leave(db, row), "Saved")


class CoverBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_employee_id: UuidIdValue | None = None
    to_employee_id: UuidIdValue
    starts_on: date
    ends_on: date
    reason: Annotated[str, Field(max_length=255)] | None = None


def _hr_leave(claims) -> bool:
    try:
        svc.job(claims, "leave")
        return True
    except HTTPException:
        return False


@router.get("/cover")
async def hrm_cover_list(claims=Depends(require_permission("hrm", "read")), db: AsyncSession = Depends(get_db)):
    from app import hrm_delegation

    me = await svc._user_employee(db, claims["tenant_id"], claims.get("sub"))
    return _env(await hrm_delegation.listing(db, claims["tenant_id"], me=me, as_hr=_hr_leave(claims)))


@router.get("/cover/people")
async def hrm_cover_people(claims=Depends(require_permission("hrm", "read")), db: AsyncSession = Depends(get_db)):
    """Names only, so a manager can pick who covers. No other staff details."""
    if not _hr_leave(claims):
        svc.job(claims, "self")
    return _env([{"id": p.id, "name": p.full_name} for p in await svc.list_employees(db, claims["tenant_id"])])


@router.post("/cover")
async def hrm_cover_set(payload: CoverBody, claims=Depends(require_permission("hrm", "write")), db: AsyncSession = Depends(get_db)):
    from app import hrm_delegation

    me = await svc._user_employee(db, claims["tenant_id"], claims.get("sub"))
    row = await hrm_delegation.create(db, claims["tenant_id"], payload, me=me, as_hr=_hr_leave(claims), user_id=claims.get("sub"))
    await db.commit()
    return _env(await hrm_delegation.serialize(db, row), "Cover set")


@router.post("/cover/{cover_id}/end")
async def hrm_cover_end(cover_id: UuidIdValue, claims=Depends(require_permission("hrm", "write")), db: AsyncSession = Depends(get_db)):
    from app import hrm_delegation

    me = await svc._user_employee(db, claims["tenant_id"], claims.get("sub"))
    row = await hrm_delegation.end(db, claims["tenant_id"], cover_id, me=me, as_hr=_hr_leave(claims), user_id=claims.get("sub"))
    await db.commit()
    return _env(await hrm_delegation.serialize(db, row), "Cover ended")


@router.get("/team/leave")
async def hrm_team_leave(claims=Depends(require_permission("hrm", "read")), db: AsyncSession = Depends(get_db)):
    """Leave from the people who report to me, waiting for my decision."""
    me = await svc._user_employee(db, claims["tenant_id"], claims.get("sub"))
    if me is None:
        return _env([])
    return _env([await svc.present_leave(db, r) for r in await svc.team_leave(db, claims["tenant_id"], me)])


@router.get("/attendance")
async def hrm_attendance(
    day: date | None = None,
    claims=Depends(require_permission("hrm", "read")),
    db: AsyncSession = Depends(get_db),
):
    svc.job(claims, "attendance")
    return _env(await svc.attendance_for(db, claims["tenant_id"], day or date.today()))


@router.post("/attendance")
async def hrm_attendance_mark(
    payload: AttendanceBody, claims=Depends(require_permission("hrm", "write")), db: AsyncSession = Depends(get_db)
):
    svc.job(claims, "attendance")
    saved = await svc.mark_attendance(db, claims["tenant_id"], day=payload.day, marks=payload.marks, user_id=claims.get("sub"))
    await db.commit()
    return _env({"saved": saved}, "Attendance saved")


@router.get("/payroll")
async def hrm_payroll(claims=Depends(require_permission("hrm", "read")), db: AsyncSession = Depends(get_db)):
    svc.job(claims, "payroll")
    return _env([await svc.present_run(db, r) for r in await svc.list_runs(db, claims["tenant_id"])])


@router.post("/payroll")
async def hrm_payroll_create(
    payload: RunBody, claims=Depends(require_permission("hrm", "write")), db: AsyncSession = Depends(get_db)
):
    svc.job(claims, "payroll")
    row = await svc.create_run(db, claims["tenant_id"], period=payload.period, user_id=claims.get("sub"))
    await db.commit()
    return _env(await svc.present_run(db, row), "Payroll drawn up")


@router.patch("/payslips/{slip_id}")
async def hrm_slip_update(
    slip_id: UuidIdValue,
    payload: SlipBody,
    claims=Depends(require_permission("hrm", "write")),
    db: AsyncSession = Depends(get_db),
):
    svc.job(claims, "payroll")
    row = await svc.update_slip(db, claims["tenant_id"], slip_id, payload, user_id=claims.get("sub"))
    await db.commit()
    return _env({"id": row.id, "net": svc._money(row.net)}, "Saved")


@router.delete("/payroll/{run_id}")
async def hrm_payroll_delete(
    run_id: UuidIdValue, claims=Depends(require_permission("hrm", "write")), db: AsyncSession = Depends(get_db)
):
    svc.job(claims, "payroll")
    await svc.delete_run(db, claims["tenant_id"], run_id, user_id=claims.get("sub"))
    await db.commit()
    return _env({"id": run_id}, "Draft thrown away")


@router.post("/payroll/{run_id}/approve")
async def hrm_payroll_approve(
    run_id: UuidIdValue, claims=Depends(require_permission("hrm", "write")), db: AsyncSession = Depends(get_db)
):
    svc.job(claims, "payroll")
    row = await svc.approve_run(db, claims["tenant_id"], run_id, user_id=claims.get("sub"))
    await db.commit()
    return _env(await svc.present_run(db, row), "Payroll approved")


@router.post("/payroll/{run_id}/pay")
async def hrm_payroll_pay(
    run_id: UuidIdValue,
    payload: PayBody,
    claims=Depends(require_permission("hrm", "write")),
    db: AsyncSession = Depends(get_db),
):
    svc.job(claims, "payroll")
    row = await svc.pay(db, claims["tenant_id"], run_id, what=payload.what, method=payload.method, user_id=claims.get("sub"))
    await db.commit()
    return _env(await svc.present_run(db, row), "Recorded as paid")


@router.get("/me")
async def hrm_me(claims=Depends(require_permission("hrm", "read")), db: AsyncSession = Depends(get_db)):
    tenant_id = claims["tenant_id"]
    employee = await svc.employee_for_user(db, tenant_id, claims.get("sub"))
    return _env(
        {
            "employee": svc.serialize_employee(employee, pay=False),
            "leave_balance": await svc.leave_balance(db, tenant_id, employee.id),
            "leave": [await svc.present_leave(db, r) for r in await svc.list_leave(db, tenant_id, employee_id=employee.id)],
            "payslips": await svc.my_slips(db, tenant_id, employee),
            "loans": await loans_svc.present_loans(db, await loans_svc.list_loans(db, tenant_id, employee_id=employee.id)),
        }
    )


@router.get("/reports")
async def hrm_reports(
    year: Annotated[int, Query(ge=2000, le=2100)] | None = None,
    claims=Depends(require_permission("hrm", "read")),
    db: AsyncSession = Depends(get_db),
):
    svc.job(claims, "payroll")
    return _env(await svc.report(db, claims["tenant_id"], year=year or date.today().year))
