"""Sales commission into payroll.

A staff record carries a commission percent. For a month, each person's net sales are read
from the same place the reports read them, so the two always agree:

- FMCG: delivered orders the person booked (order total less tax less returns).
- Every other business type: the Sales by salesperson report (posted invoices they raised
  and till sales on their shift, less tax; restaurant till returns already come off it).
  Retail sales returns are not taken off there, so they are not taken off here either.

The person is matched to their sign-in by the email on the staff record. An HR manager
approves a month's commission; the payroll for that month pays it as a taxable earning
with no SSNIT. A month already on a payroll cannot be approved again.
"""

from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.honesty import money_json

ZERO = Decimal("0")


def D(value) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value or 0))


def commission_amount(net_sales, percent) -> Decimal:
    return (D(net_sales) * D(percent) / Decimal(100)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _bounds(period: str) -> tuple[datetime, datetime]:
    year, month = int(period[:4]), int(period[5:7])
    first = datetime(year, month, 1)
    last = datetime(year, month, calendar.monthrange(year, month)[1]) + timedelta(days=1) - timedelta(microseconds=1)
    return first, last


async def _users_by_email(db: AsyncSession, tenant_id: str) -> dict[str, str]:
    rows = (await db.execute(select(m.User.id, m.User.email).where(m.User.tenant_id == tenant_id))).all()
    return {(email or "").strip().lower(): uid for uid, email in rows if email}


async def net_sales_by_user(db: AsyncSession, tenant_id: str, period: str) -> dict[str, Decimal]:
    from app import packages as packages_svc

    tenant = await db.get(m.Tenant, tenant_id)
    industry = packages_svc.canonicalize_industry(getattr(tenant, "industry", None))
    start, end = _bounds(period)
    out: dict[str, Decimal] = {}
    if industry == "fmcg":
        rows = (
            await db.execute(
                select(m.FmcgOrder.created_by, func.sum(m.FmcgOrder.total - m.FmcgOrder.tax - m.FmcgOrder.returned))
                .where(
                    m.FmcgOrder.tenant_id == tenant_id,
                    m.FmcgOrder.status.in_(("delivered", "closed")),
                    m.FmcgOrder.delivered_at >= start,
                    m.FmcgOrder.delivered_at <= end,
                )
                .group_by(m.FmcgOrder.created_by)
            )
        ).all()
        for user_id, net in rows:
            if user_id:
                out[user_id] = D(net)
        return out
    from app import reports

    body = await reports.sales_by_salesperson(db, tenant_id, from_date=start, to_date=end)
    for row in body.get("salespeople") or []:
        if row.get("user_id"):
            out[row["user_id"]] = D(row.get("revenue")) - D(row.get("tax"))
    return out


async def month(db: AsyncSession, tenant_id: str, period: str) -> list[dict]:
    from app import hrm

    by_email = await _users_by_email(db, tenant_id)
    sales = await net_sales_by_user(db, tenant_id, period)
    out = []
    for person in await hrm.list_employees(db, tenant_id):
        percent = D(getattr(person, "commission_percent", 0))
        user_id = by_email.get((person.email or "").strip().lower())
        net = sales.get(user_id, ZERO) if user_id else ZERO
        approved = (
            await db.execute(select(m.HrmCommission).where(m.HrmCommission.employee_id == person.id, m.HrmCommission.period == period))
        ).scalar_one_or_none()
        if percent <= 0 and approved is None:
            continue
        out.append(
            {
                "employee_id": person.id,
                "employee_name": person.full_name,
                "period": period,
                "linked_login": bool(user_id),
                "percent": money_json(percent),
                "net_sales": money_json(net),
                "commission": money_json(commission_amount(net, percent)),
                "approved": (
                    {"amount": money_json(approved.amount), "net_sales": money_json(approved.net_sales), "status": approved.status}
                    if approved else None
                ),
            }
        )
    return out


async def approve(db: AsyncSession, tenant_id: str, *, employee_id: str, period: str, user_id) -> m.HrmCommission:
    from app import hrm

    person = await hrm._employee(db, tenant_id, employee_id)
    me = await hrm._user_employee(db, tenant_id, user_id)
    if me is not None and me.id == person.id:
        raise HTTPException(status_code=403, detail="Someone else must approve your own commission")
    percent = D(getattr(person, "commission_percent", 0))
    if percent <= 0:
        raise HTTPException(status_code=422, detail="Set a commission percent on this person's record first")
    by_email = await _users_by_email(db, tenant_id)
    login = by_email.get((person.email or "").strip().lower())
    if not login:
        raise HTTPException(status_code=422, detail="Their staff record needs the email they sign in with, so their sales can be found")
    net = (await net_sales_by_user(db, tenant_id, period)).get(login, ZERO)
    amount = commission_amount(net, percent)
    row = (
        await db.execute(select(m.HrmCommission).where(m.HrmCommission.employee_id == person.id, m.HrmCommission.period == period))
    ).scalar_one_or_none()
    if row is not None and (row.status != "approved" or row.run_id):
        raise HTTPException(status_code=409, detail="This month's commission is already on a payroll")
    if row is None:
        row = m.HrmCommission(tenant_id=tenant_id, employee_id=person.id, period=period)
        db.add(row)
    row.net_sales, row.percent, row.amount = net, percent, amount
    row.status, row.approved_by = "approved", user_id
    await db.flush()
    await hrm._audit(
        db, tenant_id, user_id, "hrm_commission_approved", "hrm_commission", row.id,
        {"employee_id": person.id, "period": period, "net_sales": money_json(net), "percent": money_json(percent), "amount": money_json(amount)},
    )
    return row


async def take(db: AsyncSession, employee_id: str, period: str, run_id: str) -> Decimal:
    row = (
        await db.execute(
            select(m.HrmCommission).where(
                m.HrmCommission.employee_id == employee_id, m.HrmCommission.period == period,
                m.HrmCommission.status == "approved", m.HrmCommission.run_id.is_(None),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        return ZERO
    row.run_id = run_id
    return D(row.amount)


async def release(db: AsyncSession, run_id: str) -> None:
    for row in (await db.execute(select(m.HrmCommission).where(m.HrmCommission.run_id == run_id))).scalars():
        if row.status == "approved":
            row.run_id = None


async def settle(db: AsyncSession, run_id: str) -> None:
    for row in (await db.execute(select(m.HrmCommission).where(m.HrmCommission.run_id == run_id))).scalars():
        row.status = "paid"
