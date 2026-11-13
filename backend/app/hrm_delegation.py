"""Approval cover and escalation for the manager step of leave.

- Cover (delegation): a manager going away names a colleague and the dates. While it runs,
  the colleague decides the manager's team's leave at the manager step (it is recorded as
  theirs), gets the "Leave to decide" notices, and sees those requests under My team. The
  manager can end it early. HR can set cover for anyone.
- Escalation: a request still at the manager step after `escalate_after_days` working days
  (HR settings, default 3; 0 = off) is flagged to HR once. HR can already decide at either step.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.honesty import optional_honest_narrative


async def _hrm():
    from app import hrm

    return hrm


async def active_for(db: AsyncSession, manager_id: str, on: date | None = None) -> m.HrmDelegation | None:
    on = on or date.today()
    return (
        await db.execute(
            select(m.HrmDelegation).where(
                m.HrmDelegation.from_employee_id == manager_id, m.HrmDelegation.ended_at.is_(None),
                m.HrmDelegation.starts_on <= on, m.HrmDelegation.ends_on >= on,
            ).limit(1)
        )
    ).scalar_one_or_none()


async def covered_managers(db: AsyncSession, delegate_id: str, on: date | None = None) -> list[str]:
    on = on or date.today()
    rows = (
        await db.execute(
            select(m.HrmDelegation.from_employee_id).where(
                m.HrmDelegation.to_employee_id == delegate_id, m.HrmDelegation.ended_at.is_(None),
                m.HrmDelegation.starts_on <= on, m.HrmDelegation.ends_on >= on,
            )
        )
    ).scalars().all()
    return list(rows)


async def acts_for_manager(db: AsyncSession, me: m.HrmEmployee | None, manager_id: str | None) -> bool:
    """True when `me` is the manager, or covering for them today."""
    if me is None or not manager_id:
        return False
    if me.id == manager_id:
        return True
    cover = await active_for(db, manager_id)
    return cover is not None and cover.to_employee_id == me.id


async def create(db: AsyncSession, tenant_id: str, payload, *, me: m.HrmEmployee | None, as_hr: bool, user_id) -> m.HrmDelegation:
    hrm = await _hrm()
    from_id = payload.from_employee_id or (me.id if me else None)
    if not from_id:
        raise HTTPException(status_code=422, detail="Say whose approvals are covered")
    if not as_hr and (me is None or from_id != me.id):
        raise HTTPException(status_code=403, detail="You can set cover for your own approvals only")
    manager = await hrm._employee(db, tenant_id, from_id)
    delegate = await hrm._employee(db, tenant_id, payload.to_employee_id)
    if delegate.id == manager.id:
        raise HTTPException(status_code=422, detail="Choose someone else to cover")
    if delegate.status != "active":
        raise HTTPException(status_code=409, detail="That person has left")
    if payload.ends_on < payload.starts_on:
        raise HTTPException(status_code=422, detail="The end date is before the start date")
    if payload.ends_on < date.today():
        raise HTTPException(status_code=422, detail="That cover has already ended")
    clash = (
        await db.execute(
            select(m.HrmDelegation.id).where(
                m.HrmDelegation.from_employee_id == manager.id, m.HrmDelegation.ended_at.is_(None),
                m.HrmDelegation.starts_on <= payload.ends_on, m.HrmDelegation.ends_on >= payload.starts_on,
            )
        )
    ).first()
    if clash:
        raise HTTPException(status_code=409, detail="There is already cover on some of those days")
    row = m.HrmDelegation(
        tenant_id=tenant_id, from_employee_id=manager.id, to_employee_id=delegate.id,
        starts_on=payload.starts_on, ends_on=payload.ends_on,
        reason=optional_honest_narrative(payload.reason, label="reason", max_length=255), created_by=user_id,
    )
    db.add(row)
    await db.flush()
    await hrm._audit(db, tenant_id, user_id, "hrm_cover_set", "hrm_delegation", row.id, {"from": manager.id, "to": delegate.id})
    from app import hrm_notify

    await hrm_notify.to_person(
        db, tenant_id, delegate, "Covering approvals",
        f"You cover {manager.full_name}'s leave approvals from {row.starts_on.isoformat()} to {row.ends_on.isoformat()}.",
        entity_type="hrm_delegation", entity_id=row.id, skip_user=user_id,
    )
    return row


async def end(db: AsyncSession, tenant_id: str, row_id: str, *, me: m.HrmEmployee | None, as_hr: bool, user_id) -> m.HrmDelegation:
    hrm = await _hrm()
    row = await db.get(m.HrmDelegation, row_id)
    if row is None or row.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Cover not found")
    if not as_hr and (me is None or me.id not in (row.from_employee_id, row.to_employee_id)):
        raise HTTPException(status_code=404, detail="Cover not found")
    if row.ended_at is None:
        row.ended_at = datetime.utcnow()
        await db.flush()
        await hrm._audit(db, tenant_id, user_id, "hrm_cover_ended", "hrm_delegation", row.id, {})
    return row


async def serialize(db: AsyncSession, row: m.HrmDelegation) -> dict:
    a = await db.get(m.HrmEmployee, row.from_employee_id)
    b = await db.get(m.HrmEmployee, row.to_employee_id)
    today = date.today()
    return {
        "id": row.id, "from_employee_id": row.from_employee_id, "from_name": a.full_name if a else None,
        "to_employee_id": row.to_employee_id, "to_name": b.full_name if b else None,
        "starts_on": row.starts_on.isoformat(), "ends_on": row.ends_on.isoformat(), "reason": row.reason,
        "running": row.ended_at is None and row.starts_on <= today <= row.ends_on,
        "ended": row.ended_at is not None or row.ends_on < today,
    }


async def listing(db: AsyncSession, tenant_id: str, *, me: m.HrmEmployee | None, as_hr: bool) -> list[dict]:
    stmt = select(m.HrmDelegation).where(m.HrmDelegation.tenant_id == tenant_id).order_by(m.HrmDelegation.starts_on.desc()).limit(100)
    rows = list((await db.execute(stmt)).scalars())
    if not as_hr:
        rows = [r for r in rows if me is not None and me.id in (r.from_employee_id, r.to_employee_id)]
    return [await serialize(db, r) for r in rows]


def _working_days_since(start: date, today: date) -> int:
    days, d = 0, start
    while d < today:
        d += timedelta(days=1)
        if d.weekday() < 5:
            days += 1
    return days


async def scan_escalations(db: AsyncSession, tenant_id: str, today: date | None = None) -> int:
    hrm = await _hrm()
    from app import hrm_notify

    today = today or date.today()
    settings = await hrm.get_settings(db, tenant_id)
    after = int(getattr(settings, "escalate_after_days", 3) or 0)
    if after <= 0:
        return 0
    rows = (
        await db.execute(
            select(m.HrmLeaveRequest).where(
                m.HrmLeaveRequest.tenant_id == tenant_id, m.HrmLeaveRequest.status == "pending",
                m.HrmLeaveRequest.stage == "manager", m.HrmLeaveRequest.escalated_at.is_(None),
            )
        )
    ).scalars().all()
    sent = 0
    for row in rows:
        asked = (row.created_at or datetime.utcnow()).date()
        if _working_days_since(asked, today) < after:
            continue
        person = await db.get(m.HrmEmployee, row.employee_id)
        await hrm_notify.to_hr(
            db, tenant_id, "Leave waiting on a manager",
            f"{person.full_name if person else 'Someone'}'s leave from {row.starts_on.isoformat()} has waited {after}+ working days for their manager. HR can decide it.",
            entity_type="hrm_leave", entity_id=row.id,
        )
        row.escalated_at = datetime.utcnow()
        sent += 1
    await db.flush()
    return sent
