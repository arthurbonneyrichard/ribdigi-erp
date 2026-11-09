"""Gym desk: members, plans, memberships, the door, classes and its own till, on ``gym_*`` tables.

Nothing here touches retail sales or the till. A membership is sold at the desk, paid into an
open shift and booked as revenue on the day it is sold. Every movement of money goes through
``gym_payments``, so the drawer is one sum.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import accounting
from app import audit as audit_svc
from app import models as m
from app import tax as tax_svc
from app import desk_dashboard as dash
from app.honesty import money_json, optional_honest_narrative, require_honest_narrative

METHODS = frozenset({"cash", "card", "mobile_money", "bank_transfer"})
MAX_FREEZE_DAYS = 180

_JOBS = {
    "gym_frontdesk": frozenset({"members", "desk", "door", "classes"}),
    "gym_trainer": frozenset({"door", "classes"}),
}
_WORDS = {
    "gym_frontdesk": "Front desk runs members, sales, the door and classes. Refunds, plans and reports need a manager.",
    "gym_trainer": "Trainers look after the door and classes. Ask the front desk or a manager for the rest.",
}


def job(claims: dict, area: str) -> None:
    role = str(claims.get("role") or "")
    if role in _JOBS and area not in _JOBS[role]:
        raise HTTPException(status_code=403, detail={"code": "GYM_ROLE_JOB", "message": _WORDS[role]})


def _now() -> datetime:
    return datetime.utcnow()


def _money(value) -> float:
    return money_json(round(float(value or 0), 2))


async def _next_number(db: AsyncSession, tenant_id: str, model, prefix: str) -> str:
    # key_share: see hotel._lock_numbers.
    await db.execute(select(m.Tenant.id).where(m.Tenant.id == tenant_id).with_for_update(key_share=True))
    count = (await db.execute(select(func.count()).select_from(model).where(model.tenant_id == tenant_id))).scalar_one()
    return f"{prefix}-{int(count or 0) + 1:04d}"


async def _post(db, tenant_id: str, *, user_id, description: str, lines: list[dict], reference: str, source: str, source_id: str):
    await accounting.ensure_default_accounts(db, tenant_id)
    entry = await accounting.post_journal_entry(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        description=description,
        lines=lines,
        reference=reference,
        source_type=source,
        source_id=source_id,
    )
    return entry.id


async def _audit(db, tenant_id: str, user_id, action: str, entity: str, entity_id: str, details: dict) -> None:
    await audit_svc.record_event(
        db, tenant_id=tenant_id, user_id=user_id, module="gym", action=action, entity=entity,
        entity_id=entity_id, details=details,
    )


def _method(value: str | None) -> str:
    method = str(value or "").strip().lower()
    if method not in METHODS:
        raise HTTPException(status_code=422, detail="Choose how they paid")
    return method


def _money_account(method: str) -> str:
    return accounting.pos_debit_account_for_payment_method(method)[0]


async def _split_tax(db: AsyncSession, tenant_id: str, price: float) -> tuple[float, float, float]:
    """Net, tax and gross for a plan price, using the company's default tax rate."""
    default = await tax_svc.get_default_tax_rate(db, tenant_id)
    if default is None or not default.is_active:
        return _money(price), 0.0, _money(price)
    spec = tax_svc.tax_spec_from_rate(default, supply_class="standard")
    net, tax, gross = tax_svc.compute_line_total(1, _money(price), spec.rate_pct, spec.pricing_mode)
    return _money(net), _money(tax), _money(gross)


# --- Plans -------------------------------------------------------------------------------


def serialize_plan(row: m.GymPlan) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "price": _money(row.price),
        "duration_days": int(row.duration_days),
        "visit_limit": int(row.visit_limit) if row.visit_limit else None,
        "is_active": bool(row.is_active),
    }


async def list_plans(db: AsyncSession, tenant_id: str, *, active_only: bool = False) -> list[m.GymPlan]:
    stmt = select(m.GymPlan).where(m.GymPlan.tenant_id == tenant_id)
    if active_only:
        stmt = stmt.where(m.GymPlan.is_active.is_(True))
    return list((await db.execute(stmt.order_by(m.GymPlan.price.asc()))).scalars().all())


async def _plan(db: AsyncSession, tenant_id: str, plan_id: str) -> m.GymPlan:
    row = await db.get(m.GymPlan, plan_id)
    if row is None or row.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Plan not found")
    return row


async def create_plan(db: AsyncSession, tenant_id: str, payload, *, user_id) -> m.GymPlan:
    name = require_honest_narrative(payload.name, label="plan name", max_length=120)
    clash = (
        await db.execute(select(m.GymPlan.id).where(m.GymPlan.tenant_id == tenant_id, func.lower(m.GymPlan.name) == name.lower()))
    ).first()
    if clash:
        raise HTTPException(status_code=409, detail="A plan with this name already exists")
    row = m.GymPlan(
        tenant_id=tenant_id, name=name, price=_money(payload.price), duration_days=int(payload.duration_days),
        visit_limit=payload.visit_limit,
    )
    db.add(row)
    await db.flush()
    await _audit(db, tenant_id, user_id, "gym_plan_created", "gym_plan", row.id, {"name": name, "price": row.price})
    return row


async def update_plan(db: AsyncSession, tenant_id: str, plan_id: str, payload, *, user_id) -> m.GymPlan:
    """Existing members keep the price they paid. A new price applies to the next sale."""
    row = await _plan(db, tenant_id, plan_id)
    if payload.price is not None:
        row.price = _money(payload.price)
    if payload.is_active is not None:
        row.is_active = bool(payload.is_active)
    await _audit(db, tenant_id, user_id, "gym_plan_updated", "gym_plan", row.id, {"price": _money(row.price), "is_active": row.is_active})
    await db.flush()
    return row


# --- Members -----------------------------------------------------------------------------


def _state(row: m.GymMembership | None, today: date) -> str:
    if row is None:
        return "none"
    if row.status in ("frozen", "cancelled"):
        return row.status
    if row.starts_on > today:
        return "upcoming"
    return "active" if row.ends_on >= today else "expired"


async def _latest(db: AsyncSession, tenant_id: str, member_id: str) -> m.GymMembership | None:
    """The membership that decides what the member can do today."""
    rows = (
        await db.execute(
            select(m.GymMembership)
            .where(
                m.GymMembership.tenant_id == tenant_id,
                m.GymMembership.member_id == member_id,
                m.GymMembership.status != "cancelled",
            )
            .order_by(m.GymMembership.starts_on.asc())
        )
    ).scalars().all()
    today = date.today()
    for row in rows:
        if _state(row, today) in ("active", "frozen"):
            return row
    return rows[-1] if rows else None


async def present_member(db: AsyncSession, row: m.GymMember) -> dict:
    today = date.today()
    current = await _latest(db, row.tenant_id, row.id)
    plan = await db.get(m.GymPlan, current.plan_id) if current else None
    state = _state(current, today)
    return {
        "id": row.id,
        "member_number": row.member_number,
        "full_name": row.full_name,
        "phone": row.phone,
        "email": row.email,
        "emergency_contact": row.emergency_contact,
        "notes": row.notes,
        "joined_on": row.joined_on.isoformat() if row.joined_on else None,
        "state": state,
        "membership_id": current.id if current else None,
        "plan_name": plan.name if plan else None,
        "ends_on": current.ends_on.isoformat() if current else None,
        "days_left": (current.ends_on - today).days if current and state == "active" else None,
        "visits_left": (
            max(int(plan.visit_limit) - int(current.visits_used or 0), 0)
            if current and plan and plan.visit_limit
            else None
        ),
    }


async def list_members(db: AsyncSession, tenant_id: str, *, q: str = "", limit: int = 300) -> list[m.GymMember]:
    stmt = select(m.GymMember).where(m.GymMember.tenant_id == tenant_id)
    text = q.strip().lower()
    if text:
        like = f"%{text}%"
        stmt = stmt.where(
            func.lower(m.GymMember.full_name).like(like)
            | func.lower(m.GymMember.member_number).like(like)
            | m.GymMember.phone.like(like)
        )
    return list((await db.execute(stmt.order_by(m.GymMember.full_name.asc()).limit(limit))).scalars().all())


async def _member(db: AsyncSession, tenant_id: str, member_id: str) -> m.GymMember:
    row = await db.get(m.GymMember, member_id)
    if row is None or row.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Member not found")
    return row


async def create_member(db: AsyncSession, tenant_id: str, payload, *, user_id) -> m.GymMember:
    if payload.phone:
        clash = (
            await db.execute(select(m.GymMember.id).where(m.GymMember.tenant_id == tenant_id, m.GymMember.phone == payload.phone))
        ).first()
        if clash:
            raise HTTPException(status_code=409, detail="A member with this phone number already exists")
    row = m.GymMember(
        tenant_id=tenant_id,
        member_number=await _next_number(db, tenant_id, m.GymMember, "GM"),
        full_name=payload.full_name,
        phone=payload.phone,
        email=payload.email,
        emergency_contact=optional_honest_narrative(payload.emergency_contact, label="emergency contact", max_length=180),
        notes=optional_honest_narrative(payload.notes, label="notes", max_length=500),
        joined_on=date.today(),
    )
    db.add(row)
    await db.flush()
    await _audit(db, tenant_id, user_id, "gym_member_created", "gym_member", row.id, {"member_number": row.member_number})
    return row


# --- Till --------------------------------------------------------------------------------


async def current_shift(db: AsyncSession, tenant_id: str) -> m.GymTillShift | None:
    return (
        await db.execute(
            select(m.GymTillShift).where(m.GymTillShift.tenant_id == tenant_id, m.GymTillShift.status == "open")
        )
    ).scalars().first()


async def _need_shift(db: AsyncSession, tenant_id: str) -> m.GymTillShift:
    shift = await current_shift(db, tenant_id)
    if shift is None:
        raise HTTPException(status_code=409, detail={"code": "SHIFT_NOT_OPEN", "message": "Open the till first"})
    return shift


async def present_shift(db: AsyncSession, tenant_id: str, shift: m.GymTillShift) -> dict:
    rows = (
        await db.execute(
            select(m.GymPayment.method, func.coalesce(func.sum(m.GymPayment.amount), 0))
            .where(m.GymPayment.tenant_id == tenant_id, m.GymPayment.shift_id == shift.id)
            .group_by(m.GymPayment.method)
        )
    ).all()
    by_method = {method: _money(amount) for method, amount in rows}
    expected = _money(float(shift.opening_cash or 0) + by_method.get("cash", 0))
    counted = _money(shift.counted_cash) if shift.counted_cash is not None else None
    return {
        "id": shift.id,
        "status": shift.status,
        "opened_at": shift.opened_at.isoformat() if shift.opened_at else None,
        "closed_at": shift.closed_at.isoformat() if shift.closed_at else None,
        "opening_cash": _money(shift.opening_cash),
        "expected_cash": expected,
        "counted_cash": counted,
        "over_short": _money(counted - expected) if counted is not None else None,
        "by_method": by_method,
    }


async def open_shift(db: AsyncSession, tenant_id: str, *, opening_cash: float, user_id) -> m.GymTillShift:
    if await current_shift(db, tenant_id) is not None:
        raise HTTPException(status_code=409, detail="The till is already open")
    row = m.GymTillShift(tenant_id=tenant_id, status="open", opening_cash=_money(opening_cash), opened_by=user_id)
    db.add(row)
    await db.flush()
    return row


async def close_shift(db: AsyncSession, tenant_id: str, *, counted_cash: float, user_id) -> m.GymTillShift:
    row = await _need_shift(db, tenant_id)
    row.counted_cash = _money(counted_cash)
    row.status = "closed"
    row.closed_at = _now()
    row.closed_by = user_id
    await db.flush()
    return row


# --- Selling a membership ----------------------------------------------------------------


async def sell_membership(
    db: AsyncSession, tenant_id: str, *, member_id: str, plan_id: str, method: str, user_id: str | None
) -> m.GymMembership:
    """Sell or renew. A renewal starts the day after the current membership ends, so no days are lost."""
    how = _method(method)
    shift = await _need_shift(db, tenant_id)
    member = await _member(db, tenant_id, member_id)
    plan = await _plan(db, tenant_id, plan_id)
    if not plan.is_active:
        raise HTTPException(status_code=409, detail="This plan is no longer on sale")
    today = date.today()
    running = (
        await db.execute(
            select(func.max(m.GymMembership.ends_on)).where(
                m.GymMembership.tenant_id == tenant_id,
                m.GymMembership.member_id == member.id,
                m.GymMembership.status != "cancelled",
            )
        )
    ).scalar_one()
    starts = max(today, running + timedelta(days=1)) if running else today
    net, tax, gross = await _split_tax(db, tenant_id, float(plan.price))
    row = m.GymMembership(
        tenant_id=tenant_id,
        membership_number=await _next_number(db, tenant_id, m.GymMembership, "MS"),
        member_id=member.id,
        plan_id=plan.id,
        starts_on=starts,
        ends_on=starts + timedelta(days=int(plan.duration_days) - 1),
        status="active",
        subtotal=net,
        tax=tax,
        total=gross,
        is_renewal=running is not None,
        created_by=user_id,
    )
    db.add(row)
    await db.flush()
    description = f"Gym membership {row.membership_number}"
    journal = [
        {"account_code": _money_account(how), "debit": gross, "credit": 0, "description": description},
        {"account_code": "4000", "debit": 0, "credit": net, "description": description},
    ]
    if tax > 0:
        journal.append({"account_code": "2100", "debit": 0, "credit": tax, "description": description})
    row.journal_entry_id = await _post(
        db, tenant_id, user_id=user_id, description=description, lines=journal,
        reference=row.membership_number, source="gym_membership", source_id=row.id,
    )
    db.add(
        m.GymPayment(
            tenant_id=tenant_id, shift_id=shift.id, kind="sale", method=how, amount=gross,
            membership_id=row.id, member_id=member.id, created_by=user_id,
        )
    )
    await _audit(
        db, tenant_id, user_id, "gym_membership_sold", "gym_membership", row.id,
        {"membership_number": row.membership_number, "total": gross, "method": how},
    )
    await db.flush()
    return row


async def _membership(db: AsyncSession, tenant_id: str, membership_id: str, *, lock: bool = False) -> m.GymMembership:
    stmt = select(m.GymMembership).where(m.GymMembership.id == membership_id, m.GymMembership.tenant_id == tenant_id)
    if lock:
        stmt = stmt.with_for_update()
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Membership not found")
    return row


async def freeze(db: AsyncSession, tenant_id: str, membership_id: str, *, user_id) -> m.GymMembership:
    row = await _membership(db, tenant_id, membership_id, lock=True)
    if _state(row, date.today()) != "active":
        raise HTTPException(status_code=409, detail="Only an active membership can be frozen")
    row.status = "frozen"
    row.frozen_on = date.today()
    await _audit(db, tenant_id, user_id, "gym_membership_frozen", "gym_membership", row.id, {})
    await db.flush()
    return row


async def unfreeze(db: AsyncSession, tenant_id: str, membership_id: str, *, user_id) -> m.GymMembership:
    """The days spent frozen are added back to the end date, up to the limit."""
    row = await _membership(db, tenant_id, membership_id, lock=True)
    if row.status != "frozen":
        raise HTTPException(status_code=409, detail="This membership is not frozen")
    days = min((date.today() - row.frozen_on).days, MAX_FREEZE_DAYS)
    row.ends_on = row.ends_on + timedelta(days=days)
    row.status = "active"
    row.frozen_on = None
    await _audit(db, tenant_id, user_id, "gym_membership_unfrozen", "gym_membership", row.id, {"days_added": days})
    await db.flush()
    return row


async def cancel_membership(
    db: AsyncSession, tenant_id: str, membership_id: str, *, reason: str, refund: float, method: str | None, user_id
) -> m.GymMembership:
    row = await _membership(db, tenant_id, membership_id, lock=True)
    if row.status == "cancelled":
        raise HTTPException(status_code=409, detail="This membership is already cancelled")
    why = require_honest_narrative(reason, label="reason", max_length=255)
    back = _money(refund)
    if back > _money(row.total) + 0.005:
        raise HTTPException(status_code=422, detail=f"The refund cannot be more than the {_money(row.total):.2f} paid")
    if back > 0:
        how = _method(method)
        shift = await _need_shift(db, tenant_id)
        tax = _money(float(row.tax or 0) * back / float(row.total)) if float(row.total or 0) > 0 else 0.0
        description = f"Gym refund {row.membership_number}"
        journal = [
            {"account_code": "4000", "debit": _money(back - tax), "credit": 0, "description": description},
            {"account_code": _money_account(how), "debit": 0, "credit": back, "description": description},
        ]
        if tax > 0:
            journal.insert(1, {"account_code": "2100", "debit": tax, "credit": 0, "description": description})
        await _post(
            db, tenant_id, user_id=user_id, description=description, lines=journal,
            reference=row.membership_number, source="gym_refund", source_id=row.id,
        )
        db.add(
            m.GymPayment(
                tenant_id=tenant_id, shift_id=shift.id, kind="refund", method=how, amount=-back,
                membership_id=row.id, member_id=row.member_id, created_by=user_id,
            )
        )
        row.refunded = back
        row.refund_tax = tax
    row.status = "cancelled"
    row.cancel_reason = why
    await _audit(
        db, tenant_id, user_id, "gym_membership_cancelled", "gym_membership", row.id, {"reason": why, "refund": back}
    )
    await db.flush()
    return row


# --- The door ----------------------------------------------------------------------------


async def check_in(db: AsyncSession, tenant_id: str, *, member_id: str, user_id) -> dict:
    """Let a member in, or say plainly why not. Refusals are recorded too."""
    member = await _member(db, tenant_id, member_id)
    current = await _latest(db, tenant_id, member.id)
    if current is not None:
        current = await _membership(db, tenant_id, current.id, lock=True)
    today = date.today()
    state = _state(current, today)
    refused = {
        "none": "No membership yet",
        "expired": "Membership has ended",
        "frozen": "Membership is frozen",
        "upcoming": "Membership has not started",
        "cancelled": "Membership was cancelled",
    }.get(state)
    plan = await db.get(m.GymPlan, current.plan_id) if current else None
    if refused is None and plan.visit_limit and int(current.visits_used or 0) >= int(plan.visit_limit):
        refused = "No visits left on this plan"
    begin = datetime.combine(today, time.min)
    already = (
        await db.execute(
            select(m.GymCheckIn.id).where(
                m.GymCheckIn.tenant_id == tenant_id,
                m.GymCheckIn.member_id == member.id,
                m.GymCheckIn.allowed.is_(True),
                m.GymCheckIn.checked_in_at >= begin,
            )
        )
    ).first()
    if already and refused is None:
        return {"allowed": True, "already_in": True, "message": f"{member.full_name} is already in today"}
    db.add(
        m.GymCheckIn(
            tenant_id=tenant_id, member_id=member.id, membership_id=current.id if current else None,
            allowed=refused is None, refused_reason=refused, created_by=user_id,
        )
    )
    if refused is None:
        current.visits_used = int(current.visits_used or 0) + 1
    await db.flush()
    return {
        "allowed": refused is None,
        "already_in": False,
        "message": refused or f"Welcome, {member.full_name}",
        "member": await present_member(db, member),
    }


async def list_check_ins(db: AsyncSession, tenant_id: str, *, limit: int = 60) -> list[dict]:
    rows = (
        await db.execute(
            select(m.GymCheckIn, m.GymMember)
            .join(m.GymMember, m.GymMember.id == m.GymCheckIn.member_id)
            .where(m.GymCheckIn.tenant_id == tenant_id)
            .order_by(m.GymCheckIn.checked_in_at.desc())
            .limit(limit)
        )
    ).all()
    return [
        {
            "id": visit.id,
            "member_name": member.full_name,
            "allowed": bool(visit.allowed),
            "refused_reason": visit.refused_reason,
            "checked_in_at": visit.checked_in_at.isoformat() if visit.checked_in_at else None,
        }
        for visit, member in rows
    ]


# --- Classes -----------------------------------------------------------------------------


async def present_class(db: AsyncSession, row: m.GymClass) -> dict:
    rows = (
        await db.execute(
            select(m.GymClassBooking, m.GymMember)
            .join(m.GymMember, m.GymMember.id == m.GymClassBooking.member_id)
            .where(m.GymClassBooking.class_id == row.id, m.GymClassBooking.status != "cancelled")
        )
    ).all()
    return {
        "id": row.id,
        "name": row.name,
        "trainer_name": row.trainer_name,
        "starts_at": row.starts_at.isoformat() if row.starts_at else None,
        "capacity": int(row.capacity),
        "booked": len(rows),
        "status": row.status,
        "bookings": [
            {"id": b.id, "member_id": b.member_id, "member_name": p.full_name, "status": b.status} for b, p in rows
        ],
    }


async def list_classes(db: AsyncSession, tenant_id: str) -> list[m.GymClass]:
    since = datetime.combine(date.today(), time.min)
    return list(
        (
            await db.execute(
                select(m.GymClass)
                .where(m.GymClass.tenant_id == tenant_id, m.GymClass.starts_at >= since, m.GymClass.status == "scheduled")
                .order_by(m.GymClass.starts_at.asc())
            )
        ).scalars().all()
    )


async def create_class(db: AsyncSession, tenant_id: str, payload, *, user_id) -> m.GymClass:
    if payload.starts_at < _now() - timedelta(minutes=5):
        raise HTTPException(status_code=422, detail="Choose a time that has not passed")
    row = m.GymClass(
        tenant_id=tenant_id,
        name=require_honest_narrative(payload.name, label="class name", max_length=120),
        trainer_name=optional_honest_narrative(payload.trainer_name, label="trainer", max_length=150),
        starts_at=payload.starts_at,
        capacity=int(payload.capacity),
        status="scheduled",
        created_by=user_id,
    )
    db.add(row)
    await db.flush()
    return row


async def _class(db: AsyncSession, tenant_id: str, class_id: str, *, lock: bool = False) -> m.GymClass:
    stmt = select(m.GymClass).where(m.GymClass.id == class_id, m.GymClass.tenant_id == tenant_id)
    if lock:
        stmt = stmt.with_for_update()
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Class not found")
    return row


async def book_class(db: AsyncSession, tenant_id: str, class_id: str, *, member_id: str, user_id) -> m.GymClass:
    row = await _class(db, tenant_id, class_id, lock=True)
    if row.status != "scheduled":
        raise HTTPException(status_code=409, detail="This class was cancelled")
    member = await _member(db, tenant_id, member_id)
    current = await _latest(db, tenant_id, member.id)
    if _state(current, date.today()) != "active":
        raise HTTPException(status_code=409, detail=f"{member.full_name} has no active membership")
    taken = (
        await db.execute(
            select(m.GymClassBooking).where(m.GymClassBooking.class_id == row.id, m.GymClassBooking.status != "cancelled")
        )
    ).scalars().all()
    if any(b.member_id == member.id for b in taken):
        raise HTTPException(status_code=409, detail=f"{member.full_name} is already booked")
    if len(taken) >= int(row.capacity):
        raise HTTPException(status_code=409, detail="This class is full")
    db.add(m.GymClassBooking(tenant_id=tenant_id, class_id=row.id, member_id=member.id, status="booked", created_by=user_id))
    await db.flush()
    return row


async def set_booking(db: AsyncSession, tenant_id: str, booking_id: str, *, status: str) -> m.GymClass:
    row = await db.get(m.GymClassBooking, booking_id)
    if row is None or row.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Booking not found")
    row.status = status
    await db.flush()
    return await _class(db, tenant_id, row.class_id)


async def cancel_class(db: AsyncSession, tenant_id: str, class_id: str) -> m.GymClass:
    row = await _class(db, tenant_id, class_id, lock=True)
    row.status = "cancelled"
    await db.flush()
    return row


# --- Reports -----------------------------------------------------------------------------


async def expiring(db: AsyncSession, tenant_id: str, *, days: int = 7) -> list[dict]:
    today = date.today()
    rows = (
        await db.execute(
            select(m.GymMembership, m.GymMember, m.GymPlan)
            .join(m.GymMember, m.GymMember.id == m.GymMembership.member_id)
            .join(m.GymPlan, m.GymPlan.id == m.GymMembership.plan_id)
            .where(
                m.GymMembership.tenant_id == tenant_id,
                m.GymMembership.status == "active",
                m.GymMembership.ends_on >= today,
                m.GymMembership.ends_on <= today + timedelta(days=days),
            )
            .order_by(m.GymMembership.ends_on.asc())
        )
    ).all()
    later = {
        member_id
        for (member_id,) in (
            await db.execute(
                select(m.GymMembership.member_id).where(
                    m.GymMembership.tenant_id == tenant_id,
                    m.GymMembership.status == "active",
                    m.GymMembership.ends_on > today + timedelta(days=days),
                )
            )
        ).all()
    }
    return [
        {"member_id": p.id, "member_name": p.full_name, "phone": p.phone, "plan_name": plan.name, "ends_on": row.ends_on.isoformat()}
        for row, p, plan in rows
        if p.id not in later
    ]


async def active_members(db: AsyncSession, tenant_id: str) -> int:
    today = date.today()
    count = (
        await db.execute(
            select(func.count(func.distinct(m.GymMembership.member_id))).where(
                m.GymMembership.tenant_id == tenant_id,
                m.GymMembership.status == "active",
                m.GymMembership.starts_on <= today,
                m.GymMembership.ends_on >= today,
            )
        )
    ).scalar_one()
    return int(count or 0)


async def period_numbers(db: AsyncSession, tenant_id: str, *, start: date, end: date) -> dict:
    begin, finish = datetime.combine(start, time.min), datetime.combine(end, time.max)
    sold = (
        await db.execute(
            select(m.GymMembership, m.GymPlan)
            .join(m.GymPlan, m.GymPlan.id == m.GymMembership.plan_id)
            .where(m.GymMembership.tenant_id == tenant_id, m.GymMembership.created_at >= begin, m.GymMembership.created_at <= finish)
        )
    ).all()
    payments = (
        await db.execute(
            select(m.GymPayment).where(m.GymPayment.tenant_id == tenant_id, m.GymPayment.created_at >= begin, m.GymPayment.created_at <= finish)
        )
    ).scalars().all()
    visits = (
        await db.execute(
            select(func.count()).select_from(m.GymCheckIn).where(
                m.GymCheckIn.tenant_id == tenant_id, m.GymCheckIn.allowed.is_(True),
                m.GymCheckIn.checked_in_at >= begin, m.GymCheckIn.checked_in_at <= finish,
            )
        )
    ).scalar_one()
    joined = (
        await db.execute(
            select(func.count()).select_from(m.GymMember).where(
                m.GymMember.tenant_id == tenant_id, m.GymMember.joined_on >= start, m.GymMember.joined_on <= end
            )
        )
    ).scalar_one()
    by_plan: dict[str, dict] = {}
    for row, plan in sold:
        item = by_plan.setdefault(plan.name, {"name": plan.name, "sold": 0, "total": 0.0})
        item["sold"] += 1
        item["total"] += float(row.total or 0)
    by_method: dict[str, float] = {}
    for payment in payments:
        by_method[payment.method] = by_method.get(payment.method, 0) + float(payment.amount or 0)
    takings = sum(float(p.amount or 0) for p in payments)
    return {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "sold": len(sold),
        "renewals": sum(1 for row, _ in sold if row.is_renewal),
        "new_members": int(joined or 0),
        "takings": _money(takings),
        "refunds": _money(-sum(float(p.amount or 0) for p in payments if float(p.amount or 0) < 0)),
        "by_method": {k: _money(v) for k, v in by_method.items()},
        "visits": int(visits or 0),
        "by_plan": sorted(
            ({**v, "total": _money(v["total"])} for v in by_plan.values()), key=lambda r: -r["total"]
        ),
    }


async def today(db: AsyncSession, tenant_id: str, *, money: bool = True) -> dict:
    day = date.today()
    numbers = await period_numbers(db, tenant_id, start=day, end=day)
    classes = [c for c in await list_classes(db, tenant_id) if c.starts_at.date() == day]
    shift = await current_shift(db, tenant_id)
    first, begin, finish = dash.window()
    visits = (
        await db.execute(
            select(m.GymCheckIn.checked_in_at, m.GymCheckIn.allowed).where(
                m.GymCheckIn.tenant_id == tenant_id,
                m.GymCheckIn.checked_in_at >= begin,
                m.GymCheckIn.checked_in_at <= finish,
            )
        )
    ).all()
    points: dict[date, float] = {}
    refused = 0
    for when, allowed in visits:
        if allowed:
            points[when.date()] = points.get(when.date(), 0.0) + 1
        elif when.date() == day:
            refused += 1
    ending = await expiring(db, tenant_id)
    data = {
        "date": day.isoformat(),
        "active_members": await active_members(db, tenant_id),
        "visits_today": numbers["visits"],
        "visits_yesterday": int(points.get(day - timedelta(days=1), 0)),
        "refused_today": refused,
        "classes_today": len(classes),
        "classes": [await present_class(db, c) for c in classes],
        "expiring": ending,
        "till_open": shift is not None,
        "trend": dash.trend("Visits, last 14 days", "count", dash.daily(points, first=first)),
    }
    attention = []
    if money and shift is None:
        attention.append(dash.item("warning", "The till is closed. Open it to sell plans.", "/gym?tab=members"))
    if ending:
        attention.append(dash.item("warning", f"{dash.plural(len(ending), 'member')} ending this week. A call now keeps them.", "/gym?tab=reports" if money else "/gym?tab=members"))
    if refused:
        attention.append(dash.item("info", f"{dash.plural(refused, 'person', 'people')} turned away at the door today", "/gym?tab=door"))
    if classes:
        attention.append(dash.item("info", f"{dash.plural(len(classes), 'class', 'classes')} on today", "/gym?tab=classes"))
    data["attention"] = attention
    if money:
        data["takings_today"] = numbers["takings"]
        yesterday = day - timedelta(days=1)
        data["takings_yesterday"] = (await period_numbers(db, tenant_id, start=yesterday, end=yesterday))["takings"]
    return data
