"""Org chart (who reports to whom, from each staff record's "Reports to") and headcount by
department: planned, filled (active staff) and being hired (open vacancies)."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.honesty import require_honest_narrative

NO_DEPARTMENT = "No department"


async def org_chart(db: AsyncSession, tenant_id: str) -> dict:
    from app import hrm

    people = await hrm.list_employees(db, tenant_id)
    by_id = {p.id: p for p in people}
    children: dict[str | None, list] = {}
    for p in people:
        boss = p.manager_id if p.manager_id in by_id and p.manager_id != p.id else None
        children.setdefault(boss, []).append(p)
    placed: set[str] = set()

    def node(p, depth=0):
        placed.add(p.id)
        kids = [k for k in sorted(children.get(p.id, []), key=lambda x: x.full_name or "") if k.id not in placed]
        return {
            "id": p.id, "name": p.full_name, "job_title": p.job_title, "department": p.department,
            "team_size": len(kids), "reports": [node(k, depth + 1) for k in kids] if depth < 30 else [],
        }

    roots = [node(p) for p in sorted(children.get(None, []), key=lambda x: x.full_name or "")]
    # People in a loop (A reports to B, B to A) have no top; show them so the loop can be fixed.
    loops = [node(p) for p in people if p.id not in placed]
    return {"roots": roots, "loops": loops, "people": len(people)}


def _dept(value) -> str:
    return (value or "").strip() or NO_DEPARTMENT


async def headcount(db: AsyncSession, tenant_id: str) -> list[dict]:
    from app import hrm

    plans = {
        r.department: r.planned
        for r in (await db.execute(select(m.HrmHeadcountPlan).where(m.HrmHeadcountPlan.tenant_id == tenant_id))).scalars()
    }
    filled: dict[str, int] = {}
    for p in await hrm.list_employees(db, tenant_id):
        filled[_dept(p.department)] = filled.get(_dept(p.department), 0) + 1
    hiring: dict[str, int] = {}
    rows = (
        await db.execute(
            select(m.HrmVacancy.department, func.coalesce(func.sum(m.HrmVacancy.openings), 0))
            .where(m.HrmVacancy.tenant_id == tenant_id, m.HrmVacancy.status == "open")
            .group_by(m.HrmVacancy.department)
        )
    ).all()
    for dept, count in rows:
        hiring[_dept(dept)] = hiring.get(_dept(dept), 0) + int(count or 0)
    out = []
    for dept in sorted(set(plans) | set(filled) | set(hiring)):
        planned = plans.get(dept)
        have, open_roles = filled.get(dept, 0), hiring.get(dept, 0)
        out.append(
            {
                "department": dept, "planned": planned, "filled": have, "hiring": open_roles,
                # Still to find after the open vacancies: positive = plan a vacancy; negative = over plan.
                "gap": (planned - have - open_roles) if planned is not None else None,
            }
        )
    return out


async def set_plan(db: AsyncSession, tenant_id: str, *, department: str, planned: int | None, user_id) -> None:
    from app import hrm

    name = require_honest_narrative(department, label="department", max_length=120)
    row = (
        await db.execute(select(m.HrmHeadcountPlan).where(m.HrmHeadcountPlan.tenant_id == tenant_id, m.HrmHeadcountPlan.department == name))
    ).scalar_one_or_none()
    if planned is None:
        if row is not None:
            await db.delete(row)
    else:
        if planned < 0:
            raise HTTPException(status_code=422, detail="Planned headcount cannot be below nil")
        if row is None:
            row = m.HrmHeadcountPlan(tenant_id=tenant_id, department=name, planned=planned)
            db.add(row)
        row.planned = planned
    await db.flush()
    await hrm._audit(db, tenant_id, user_id, "hrm_headcount_planned", "hrm_headcount", name, {"department": name, "planned": planned})
