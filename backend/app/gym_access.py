"""Gym branches and per-plan door rules (access hours, allowed days, branch scope).

Hours are read in the company's own timezone, so "6am to 10pm" means local time. The door asks
`door_refusal` after the membership checks; it never opens a door the membership already refused.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.gym import _audit, _member
from app.honesty import require_honest_narrative
from app.hotel import hotel_zone

_HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_DAY_NAMES = ["", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def parse_days(value: str | None) -> set[int]:
    return {int(x) for x in str(value or "").split(",") if x.strip().isdigit() and 1 <= int(x) <= 7}


def validate_rules(start: str | None, end: str | None, days: list[int] | None, scope: str | None) -> dict:
    if (start is None) != (end is None):
        raise HTTPException(status_code=422, detail="Give both an opening and a closing time, or neither")
    if start is not None:
        if not _HHMM.match(start) or not _HHMM.match(end):
            raise HTTPException(status_code=422, detail="Times look like 06:00")
        if start == end:
            raise HTTPException(status_code=422, detail="Opening and closing time cannot be the same")
    clean = sorted({int(d) for d in (days or [])})
    if any(d < 1 or d > 7 for d in clean):
        raise HTTPException(status_code=422, detail="Days run from 1 (Monday) to 7 (Sunday)")
    if scope not in (None, "all", "home"):
        raise HTTPException(status_code=422, detail="Branch scope is all or home")
    return {"access_start": start, "access_end": end, "access_days": ",".join(map(str, clean)) or None, "branch_scope": scope or "all"}


async def set_plan_rules(db: AsyncSession, tenant_id: str, plan_id: str, payload, *, user_id) -> dict:
    plan = await db.get(m.GymPlan, plan_id)
    if plan is None or plan.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Plan not found")
    rules = validate_rules(payload.access_start, payload.access_end, payload.access_days, payload.branch_scope)
    for key, value in rules.items():
        setattr(plan, key, value)
    await db.flush()
    await _audit(db, tenant_id, user_id, "gym_plan_access_set", "gym_plan", plan.id, rules)
    return plan_rules(plan)


def plan_rules(plan: m.GymPlan) -> dict:
    return {
        "access_start": plan.access_start, "access_end": plan.access_end,
        "access_days": sorted(parse_days(plan.access_days)), "branch_scope": plan.branch_scope or "all",
    }


def _in_window(start: str, end: str, now_hhmm: str) -> bool:
    if start < end:
        return start <= now_hhmm < end
    return now_hhmm >= start or now_hhmm < end  # a window that runs past midnight


async def door_refusal(
    db: AsyncSession, tenant_id: str, *, plan: m.GymPlan, member: m.GymMember, branch_id: str | None, at: datetime | None = None
) -> str | None:
    """A plain reason when the plan's own rules refuse this visit, else None."""
    if plan.branch_scope == "home" and branch_id and member.home_branch_id and branch_id != member.home_branch_id:
        return "This plan only works at the member's home branch"
    if plan.access_days or (plan.access_start and plan.access_end):
        zone = await hotel_zone(db, tenant_id)
        moment = (at or datetime.now(timezone.utc))
        local = moment.astimezone(zone) if moment.tzinfo else moment.replace(tzinfo=timezone.utc).astimezone(zone)
        days = parse_days(plan.access_days)
        if days and local.isoweekday() not in days:
            return "This plan does not cover " + _DAY_NAMES[local.isoweekday()]
        if plan.access_start and plan.access_end and not _in_window(plan.access_start, plan.access_end, local.strftime("%H:%M")):
            return f"This plan is for {plan.access_start} to {plan.access_end}"
    return None


# --- Branches -------------------------------------------------------------------------------


def present_branch(row: m.GymBranch) -> dict:
    return {"id": row.id, "code": row.code, "name": row.name, "is_active": bool(row.is_active)}


async def create_branch(db: AsyncSession, tenant_id: str, payload, *, user_id) -> m.GymBranch:
    code = require_honest_narrative(payload.code, label="branch code", max_length=20).upper()
    name = require_honest_narrative(payload.name, label="branch name", max_length=150)
    if (await db.execute(select(m.GymBranch.id).where(m.GymBranch.tenant_id == tenant_id, func.upper(m.GymBranch.code) == code))).first():
        raise HTTPException(status_code=409, detail="A branch with this code already exists")
    row = m.GymBranch(tenant_id=tenant_id, code=code, name=name)
    db.add(row)
    await db.flush()
    await _audit(db, tenant_id, user_id, "gym_branch_created", "gym_branch", row.id, {"code": code})
    return row


async def list_branches(db: AsyncSession, tenant_id: str) -> list[dict]:
    rows = (await db.execute(select(m.GymBranch).where(m.GymBranch.tenant_id == tenant_id).order_by(m.GymBranch.name))).scalars().all()
    return [present_branch(r) for r in rows]


async def set_branch_active(db: AsyncSession, tenant_id: str, branch_id: str, *, active: bool, user_id) -> dict:
    row = await db.get(m.GymBranch, branch_id)
    if row is None or row.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Branch not found")
    row.is_active = active
    await db.flush()
    await _audit(db, tenant_id, user_id, "gym_branch_active" if active else "gym_branch_inactive", "gym_branch", row.id, {})
    return present_branch(row)


async def usable_branch(db: AsyncSession, tenant_id: str, branch_id: str) -> m.GymBranch:
    row = await db.get(m.GymBranch, branch_id)
    if row is None or row.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Branch not found")
    if not row.is_active:
        raise HTTPException(status_code=409, detail=f"{row.name} is closed")
    return row


async def set_home_branch(db: AsyncSession, tenant_id: str, member_id: str, branch_id: str | None, *, user_id) -> dict:
    member = await _member(db, tenant_id, member_id)
    if branch_id:
        await usable_branch(db, tenant_id, branch_id)
    member.home_branch_id = branch_id
    await db.flush()
    await _audit(db, tenant_id, user_id, "gym_member_branch_set", "gym_member", member.id, {"branch_id": branch_id})
    return {"member_id": member.id, "home_branch_id": member.home_branch_id}


async def branch_report(db: AsyncSession, tenant_id: str, *, start, end) -> list[dict]:
    """Door visits per branch in a date range, plus members whose home is that branch."""
    names = {b.id: b.name for b in (await db.execute(select(m.GymBranch).where(m.GymBranch.tenant_id == tenant_id))).scalars().all()}
    lo, hi = datetime.combine(start, datetime.min.time()), datetime.combine(end, datetime.max.time())
    visits = {
        k: int(n)
        for k, n in (
            await db.execute(
                select(m.GymCheckIn.branch_id, func.count()).where(
                    m.GymCheckIn.tenant_id == tenant_id, m.GymCheckIn.allowed.is_(True), m.GymCheckIn.checked_in_at.between(lo, hi)
                ).group_by(m.GymCheckIn.branch_id)
            )
        ).all()
    }
    homes = {
        k: int(n)
        for k, n in (
            await db.execute(select(m.GymMember.home_branch_id, func.count()).where(m.GymMember.tenant_id == tenant_id).group_by(m.GymMember.home_branch_id))
        ).all()
    }
    keys = set(names) | {k for k in visits} | {k for k in homes}
    return [
        {"branch_id": k, "branch": names.get(k, "No branch set"), "visits": visits.get(k, 0), "home_members": homes.get(k, 0)}
        for k in sorted(keys, key=lambda x: names.get(x, "~"))
    ]
