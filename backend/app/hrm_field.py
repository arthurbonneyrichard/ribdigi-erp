"""FMCG field workforce, HR side: who does which field job, their monthly sales target, and one
month view of days worked, visits, sales against target and commission.

Visits, orders and territories stay in FMCG; this reads them. A person is matched to their
sign-in by the email on the staff record (as commission does). Commission shows only to people
who see pay. Only FMCG companies have this view.
"""

from __future__ import annotations

import calendar
from datetime import date, datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import hrm_commission as comm
from app import models as m
from app.honesty import money_json

ROLES = ("rep", "van_sales", "merchandiser", "delivery", "warehouse", "supervisor")
D = comm.D


async def set_profile(db: AsyncSession, tenant_id: str, employee_id: str, *, field_role: str, monthly_sales_target, user_id) -> dict:
    from app import hrm

    emp = await hrm._employee(db, tenant_id, employee_id)
    if field_role not in ROLES:
        raise HTTPException(status_code=422, detail="Choose the field job")
    if monthly_sales_target is not None and D(monthly_sales_target) < 0:
        raise HTTPException(status_code=422, detail="The target cannot be negative")
    row = (await db.execute(select(m.HrmFieldStaff).where(m.HrmFieldStaff.employee_id == emp.id))).scalar_one_or_none()
    if row is None:
        row = m.HrmFieldStaff(tenant_id=tenant_id, employee_id=emp.id, field_role=field_role)
        db.add(row)
    row.field_role = field_role
    row.monthly_sales_target = monthly_sales_target
    await hrm._audit(db, tenant_id, user_id, "hrm_field_profile_saved", "hrm_employee", emp.id, {"field_role": field_role})
    await db.flush()
    target = money_json(row.monthly_sales_target) if row.monthly_sales_target is not None else None
    return {"employee_id": emp.id, "field_role": row.field_role, "monthly_sales_target": target}


async def remove_profile(db: AsyncSession, tenant_id: str, employee_id: str) -> None:
    row = (
        await db.execute(
            select(m.HrmFieldStaff).where(m.HrmFieldStaff.tenant_id == tenant_id, m.HrmFieldStaff.employee_id == employee_id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="No field job on this person")
    await db.delete(row)
    await db.flush()


async def workforce(db: AsyncSession, tenant_id: str, period: str, *, with_pay: bool) -> dict:
    year, month = int(period[:4]), int(period[5:7])
    start, end = comm._bounds(period)
    first, last = date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])
    today = date.today()
    by_email = await comm._users_by_email(db, tenant_id)
    sales = await comm.net_sales_by_user(db, tenant_id, period)
    profiles = (await db.execute(select(m.HrmFieldStaff).where(m.HrmFieldStaff.tenant_id == tenant_id))).scalars().all()
    people = {p.id: p for p in (await db.execute(select(m.HrmEmployee).where(m.HrmEmployee.tenant_id == tenant_id))).scalars()}
    territories = {t.id: t for t in (await db.execute(select(m.FmcgTerritory).where(m.FmcgTerritory.tenant_id == tenant_id))).scalars()}
    reps: dict[str, list[str]] = {}
    for r in (await db.execute(select(m.FmcgTerritoryRep).where(m.FmcgTerritoryRep.tenant_id == tenant_id))).scalars():
        reps.setdefault(r.user_id, []).append(r.territory_id)

    rows = []
    for prof in profiles:
        emp = people.get(prof.employee_id)
        if emp is None or emp.status != "active":
            continue
        uid = by_email.get((emp.email or "").strip().lower())
        present = (
            await db.execute(
                select(func.count()).select_from(m.HrmAttendance).where(
                    m.HrmAttendance.employee_id == emp.id, m.HrmAttendance.day >= first, m.HrmAttendance.day <= last,
                    m.HrmAttendance.status.in_(("present", "late", "half_day")),
                )
            )
        ).scalar_one()
        visits = today_visits = 0
        if uid:
            visits = (
                await db.execute(
                    select(func.count()).select_from(m.FmcgVisit).where(
                        m.FmcgVisit.tenant_id == tenant_id, m.FmcgVisit.user_id == uid,
                        m.FmcgVisit.checked_in_at >= start, m.FmcgVisit.checked_in_at <= end,
                    )
                )
            ).scalar_one()
            t0 = datetime(today.year, today.month, today.day)
            today_visits = (
                await db.execute(
                    select(func.count()).select_from(m.FmcgVisit).where(
                        m.FmcgVisit.tenant_id == tenant_id, m.FmcgVisit.user_id == uid, m.FmcgVisit.checked_in_at >= t0
                    )
                )
            ).scalar_one()
        mine = [territories[t] for t in reps.get(uid or "", []) if t in territories]
        daily = max([int(t.daily_visit_target or 0) for t in mine], default=0)
        net = sales.get(uid, comm.ZERO) if uid else comm.ZERO
        target = D(prof.monthly_sales_target) if prof.monthly_sales_target is not None else None
        row = {
            "employee_id": emp.id, "name": emp.full_name, "field_role": prof.field_role, "linked_login": bool(uid),
            "territories": [t.name for t in mine], "days_present": int(present),
            "visits_month": int(visits), "visits_today": int(today_visits),
            "visit_target": daily * int(present) if daily else None,
            "net_sales": money_json(net), "sales_target": money_json(target) if target is not None else None,
            "achievement_pct": money_json((net / target * 100).quantize(D("0.1"))) if target else None,
        }
        if with_pay:
            row["commission"] = money_json(comm.commission_amount(net, getattr(emp, "commission_percent", 0)))
        rows.append(row)
    rows.sort(key=lambda r: (r["field_role"], r["name"]))
    by_role: dict[str, int] = {}
    for r in rows:
        by_role[r["field_role"]] = by_role.get(r["field_role"], 0) + 1
    return {
        "period": period, "staff": rows, "by_role": by_role,
        "no_territory": [r["name"] for r in rows if r["field_role"] in ("rep", "van_sales", "merchandiser") and not r["territories"]],
    }
