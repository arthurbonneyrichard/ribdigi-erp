"""Gym stage 1 operations: trainers and training sessions, lockers, equipment, guests.

Same rules as the rest of the gym desk: every row is scoped by tenant, writes lock the row they
depend on, and nothing here moves money (a session price is only shown; selling goes through
the till).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.gym import _audit, _latest, _member, _money, _state
from app.honesty import optional_honest_narrative, require_honest_narrative

ACTIVE_SESSION = ("booked", "completed")


def _t(db_row, tenant_id: str, what: str):
    if db_row is None or db_row.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail=f"{what} not found")
    return db_row


# --- Trainers and sessions ------------------------------------------------------------------


def present_trainer(row: m.GymTrainer) -> dict:
    return {
        "id": row.id, "full_name": row.full_name, "phone": row.phone, "specialization": row.specialization,
        "session_price": _money(row.session_price), "is_active": bool(row.is_active),
        "commission_pct": _money(getattr(row, "commission_pct", 0)),
    }


async def create_trainer(db: AsyncSession, tenant_id: str, payload, *, user_id) -> m.GymTrainer:
    name = require_honest_narrative(payload.full_name, label="trainer name", max_length=150)
    dup = (
        await db.execute(
            select(m.GymTrainer.id).where(m.GymTrainer.tenant_id == tenant_id, func.lower(m.GymTrainer.full_name) == name.lower())
        )
    ).first()
    if dup:
        raise HTTPException(status_code=409, detail="A trainer with this name already exists")
    row = m.GymTrainer(
        tenant_id=tenant_id, full_name=name, phone=payload.phone,
        specialization=optional_honest_narrative(payload.specialization, label="specialization", max_length=150),
        session_price=_money(payload.session_price),
    )
    db.add(row)
    await db.flush()
    await _audit(db, tenant_id, user_id, "trainer_created", "gym_trainer", row.id, {"name": name})
    return row


async def list_trainers(db: AsyncSession, tenant_id: str) -> list[m.GymTrainer]:
    stmt = select(m.GymTrainer).where(m.GymTrainer.tenant_id == tenant_id).order_by(m.GymTrainer.full_name)
    return list((await db.execute(stmt)).scalars().all())


def present_session(row: m.GymTrainingSession, trainer: m.GymTrainer, member: m.GymMember) -> dict:
    return {
        "id": row.id, "trainer_id": trainer.id, "trainer_name": trainer.full_name, "member_id": member.id,
        "member_name": member.full_name, "starts_at": row.starts_at.isoformat(), "ends_at": row.ends_at.isoformat(),
        "status": row.status, "notes": row.notes,
    }


async def book_session(db: AsyncSession, tenant_id: str, payload, *, user_id) -> dict:
    if payload.minutes < 15 or payload.minutes > 240:
        raise HTTPException(status_code=422, detail="A session runs 15 to 240 minutes")
    if payload.starts_at < datetime.utcnow() - timedelta(minutes=5):
        raise HTTPException(status_code=422, detail="Choose a time that has not passed")
    # Lock the trainer row so two desks booking the same trainer take turns.
    trainer = _t(
        (
            await db.execute(
                select(m.GymTrainer).where(m.GymTrainer.id == payload.trainer_id, m.GymTrainer.tenant_id == tenant_id).with_for_update()
            )
        ).scalar_one_or_none(),
        tenant_id, "Trainer",
    )
    if not trainer.is_active:
        raise HTTPException(status_code=409, detail=f"{trainer.full_name} is not taking sessions")
    member = await _member(db, tenant_id, payload.member_id)
    if _state(await _latest(db, tenant_id, member.id), date.today()) != "active":
        raise HTTPException(status_code=409, detail=f"{member.full_name} has no active membership")
    ends = payload.starts_at + timedelta(minutes=payload.minutes)
    clash = (
        await db.execute(
            select(m.GymTrainingSession.id).where(
                m.GymTrainingSession.tenant_id == tenant_id,
                m.GymTrainingSession.trainer_id == trainer.id,
                m.GymTrainingSession.status.in_(ACTIVE_SESSION),
                m.GymTrainingSession.starts_at < ends,
                m.GymTrainingSession.ends_at > payload.starts_at,
            )
        )
    ).first()
    if clash:
        raise HTTPException(status_code=409, detail=f"{trainer.full_name} already has a session at that time")
    row = m.GymTrainingSession(
        tenant_id=tenant_id, trainer_id=trainer.id, member_id=member.id, starts_at=payload.starts_at, ends_at=ends,
        status="booked", notes=optional_honest_narrative(payload.notes, label="notes", max_length=500), created_by=user_id,
    )
    db.add(row)
    await db.flush()
    await _audit(db, tenant_id, user_id, "training_booked", "gym_training_session", row.id, {"trainer": trainer.full_name})
    return present_session(row, trainer, member)


async def list_sessions(db: AsyncSession, tenant_id: str) -> list[dict]:
    stmt = (
        select(m.GymTrainingSession, m.GymTrainer, m.GymMember)
        .join(m.GymTrainer, m.GymTrainer.id == m.GymTrainingSession.trainer_id)
        .join(m.GymMember, m.GymMember.id == m.GymTrainingSession.member_id)
        .where(m.GymTrainingSession.tenant_id == tenant_id)
        .order_by(m.GymTrainingSession.starts_at.desc())
        .limit(200)
    )
    return [present_session(s, t, mem) for s, t, mem in (await db.execute(stmt)).all()]


async def set_session(db: AsyncSession, tenant_id: str, session_id: str, *, status: str, user_id) -> dict:
    row = _t(
        (
            await db.execute(
                select(m.GymTrainingSession)
                .where(m.GymTrainingSession.id == session_id, m.GymTrainingSession.tenant_id == tenant_id)
                .with_for_update()
            )
        ).scalar_one_or_none(),
        tenant_id, "Session",
    )
    if row.status != "booked":
        raise HTTPException(status_code=409, detail=f"This session is already {row.status.replace('_', ' ')}")
    row.status = status
    await db.flush()
    if status == "completed":
        from app import gym_commissions

        await gym_commissions.accrue_for_session(db, tenant_id, row)
    await _audit(db, tenant_id, user_id, f"training_{status}", "gym_training_session", row.id, {})
    trainer = await db.get(m.GymTrainer, row.trainer_id)
    member = await db.get(m.GymMember, row.member_id)
    return present_session(row, trainer, member)


# --- Lockers ----------------------------------------------------------------------------------


def present_locker(row: m.GymLocker, member: m.GymMember | None) -> dict:
    return {
        "id": row.id, "number": row.number, "status": row.status, "member_id": row.member_id,
        "member_name": member.full_name if member else None,
        "assigned_on": row.assigned_on.isoformat() if row.assigned_on else None,
        "rented_until": row.rented_until.isoformat() if row.rented_until else None,
        "overdue": bool(row.status == "taken" and row.rented_until and row.rented_until < date.today()),
    }


async def create_locker(db: AsyncSession, tenant_id: str, *, number: str) -> m.GymLocker:
    number = require_honest_narrative(number, label="locker number", max_length=20)
    dup = (
        await db.execute(select(m.GymLocker.id).where(m.GymLocker.tenant_id == tenant_id, m.GymLocker.number == number))
    ).first()
    if dup:
        raise HTTPException(status_code=409, detail=f"Locker {number} already exists")
    row = m.GymLocker(tenant_id=tenant_id, number=number, status="free")
    db.add(row)
    await db.flush()
    return row


async def list_lockers(db: AsyncSession, tenant_id: str) -> list[dict]:
    rows = (
        await db.execute(
            select(m.GymLocker, m.GymMember)
            .outerjoin(m.GymMember, m.GymMember.id == m.GymLocker.member_id)
            .where(m.GymLocker.tenant_id == tenant_id)
            .order_by(m.GymLocker.number)
        )
    ).all()
    return [present_locker(lk, mem) for lk, mem in rows]


async def _locker(db: AsyncSession, tenant_id: str, locker_id: str) -> m.GymLocker:
    stmt = select(m.GymLocker).where(m.GymLocker.id == locker_id, m.GymLocker.tenant_id == tenant_id).with_for_update()
    return _t((await db.execute(stmt)).scalar_one_or_none(), tenant_id, "Locker")


async def assign_locker(
    db: AsyncSession, tenant_id: str, locker_id: str, *, member_id: str, user_id, rental_days: int | None = None, fee: float = 0, method: str | None = None
) -> dict:
    row = await _locker(db, tenant_id, locker_id)
    member = await _member(db, tenant_id, member_id)
    if row.status != "free":
        raise HTTPException(status_code=409, detail=f"Locker {row.number} is {row.status}")
    if _state(await _latest(db, tenant_id, member.id), date.today()) != "active":
        raise HTTPException(status_code=409, detail=f"{member.full_name} has no active membership")
    has = (
        await db.execute(select(m.GymLocker.number).where(m.GymLocker.tenant_id == tenant_id, m.GymLocker.member_id == member.id))
    ).first()
    if has:
        raise HTTPException(status_code=409, detail=f"{member.full_name} already has locker {has[0]}")
    if fee and not rental_days:
        raise HTTPException(status_code=422, detail="A rental fee needs the number of days it covers")
    row.status, row.member_id, row.assigned_on = "taken", member.id, date.today()
    if rental_days:
        row.rented_until = date.today() + timedelta(days=int(rental_days) - 1)
        from app import gym_fees

        await gym_fees.take_fee(
            db, tenant_id, amount=fee or 0, method=method, kind="locker_fee", description=f"Gym locker {row.number} rental",
            reference=f"LOCKER-{row.number}", source_id=row.id, member_id=member.id, user_id=user_id,
        )
    await db.flush()
    await _audit(db, tenant_id, user_id, "locker_assigned", "gym_locker", row.id, {"member": member.full_name, "rented_until": str(row.rented_until or "")})
    return present_locker(row, member)


async def renew_locker(db: AsyncSession, tenant_id: str, locker_id: str, *, rental_days: int, fee: float, method: str | None, user_id) -> dict:
    """Extend a rental from the day it ends (or today if it already ended), so no paid days are lost."""
    row = (
        await db.execute(select(m.GymLocker).where(m.GymLocker.id == locker_id, m.GymLocker.tenant_id == tenant_id).with_for_update())
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Locker not found")
    if row.status != "taken":
        raise HTTPException(status_code=409, detail=f"Locker {row.number} is not in use")
    member = await db.get(m.GymMember, row.member_id)
    from app import gym_fees

    start = max(date.today(), (row.rented_until + timedelta(days=1)) if row.rented_until else date.today())
    await gym_fees.take_fee(
        db, tenant_id, amount=fee or 0, method=method, kind="locker_fee", description=f"Gym locker {row.number} rental",
        reference=f"LOCKER-{row.number}", source_id=row.id, member_id=row.member_id, user_id=user_id,
    )
    row.rented_until = start + timedelta(days=int(rental_days) - 1)
    await db.flush()
    await _audit(db, tenant_id, user_id, "locker_renewed", "gym_locker", row.id, {"rented_until": row.rented_until.isoformat()})
    return present_locker(row, member)


async def release_locker(db: AsyncSession, tenant_id: str, locker_id: str, *, user_id) -> dict:
    row = await _locker(db, tenant_id, locker_id)
    if row.status != "taken":
        raise HTTPException(status_code=409, detail=f"Locker {row.number} is not in use")
    row.status, row.member_id, row.assigned_on, row.rented_until = "free", None, None, None
    await db.flush()
    await _audit(db, tenant_id, user_id, "locker_released", "gym_locker", row.id, {})
    return present_locker(row, None)


# --- Equipment --------------------------------------------------------------------------------


def present_equipment(row: m.GymEquipment) -> dict:
    return {"id": row.id, "name": row.name, "category": row.category, "serial_number": row.serial_number, "status": row.status}


async def create_equipment(db: AsyncSession, tenant_id: str, payload, *, user_id) -> m.GymEquipment:
    row = m.GymEquipment(
        tenant_id=tenant_id,
        name=require_honest_narrative(payload.name, label="equipment name", max_length=150),
        category=optional_honest_narrative(payload.category, label="category", max_length=80),
        serial_number=optional_honest_narrative(payload.serial_number, label="serial number", max_length=80),
        status="available",
    )
    db.add(row)
    await db.flush()
    await _audit(db, tenant_id, user_id, "equipment_added", "gym_equipment", row.id, {"name": row.name})
    return row


async def list_equipment(db: AsyncSession, tenant_id: str) -> list[dict]:
    rows = (
        await db.execute(select(m.GymEquipment).where(m.GymEquipment.tenant_id == tenant_id).order_by(m.GymEquipment.name))
    ).scalars().all()
    faults = dict(
        (
            await db.execute(
                select(m.GymMaintenance.equipment_id, func.count())
                .where(m.GymMaintenance.tenant_id == tenant_id, m.GymMaintenance.status == "open")
                .group_by(m.GymMaintenance.equipment_id)
            )
        ).all()
    )
    return [{**present_equipment(r), "open_faults": int(faults.get(r.id, 0))} for r in rows]


async def _equipment(db: AsyncSession, tenant_id: str, equipment_id: str) -> m.GymEquipment:
    stmt = select(m.GymEquipment).where(m.GymEquipment.id == equipment_id, m.GymEquipment.tenant_id == tenant_id).with_for_update()
    return _t((await db.execute(stmt)).scalar_one_or_none(), tenant_id, "Equipment")


async def report_fault(db: AsyncSession, tenant_id: str, equipment_id: str, *, fault: str, user_id) -> dict:
    eq = await _equipment(db, tenant_id, equipment_id)
    if eq.status == "retired":
        raise HTTPException(status_code=409, detail="This equipment is retired")
    text = require_honest_narrative(fault, label="fault", max_length=500)
    ticket = m.GymMaintenance(tenant_id=tenant_id, equipment_id=eq.id, fault=text, status="open")
    db.add(ticket)
    eq.status = "maintenance"
    await db.flush()
    await _audit(db, tenant_id, user_id, "fault_reported", "gym_maintenance", ticket.id, {"equipment": eq.name})
    return {"id": ticket.id, "equipment_id": eq.id, "fault": text, "status": "open"}


async def list_faults(db: AsyncSession, tenant_id: str) -> list[dict]:
    rows = (
        await db.execute(
            select(m.GymMaintenance, m.GymEquipment)
            .join(m.GymEquipment, m.GymEquipment.id == m.GymMaintenance.equipment_id)
            .where(m.GymMaintenance.tenant_id == tenant_id, m.GymMaintenance.status == "open")
            .order_by(m.GymMaintenance.opened_at.asc())
        )
    ).all()
    return [
        {"id": t.id, "equipment_id": e.id, "equipment_name": e.name, "fault": t.fault, "opened_at": t.opened_at.isoformat()}
        for t, e in rows
    ]


async def close_fault(db: AsyncSession, tenant_id: str, ticket_id: str, *, resolution: str, retire: bool, user_id) -> dict:
    stmt = select(m.GymMaintenance).where(m.GymMaintenance.id == ticket_id, m.GymMaintenance.tenant_id == tenant_id).with_for_update()
    ticket = _t((await db.execute(stmt)).scalar_one_or_none(), tenant_id, "Maintenance ticket")
    if ticket.status != "open":
        raise HTTPException(status_code=409, detail="This ticket is already closed")
    eq = await _equipment(db, tenant_id, ticket.equipment_id)
    ticket.resolution = require_honest_narrative(resolution, label="resolution", max_length=500)
    ticket.status, ticket.closed_at = "closed", datetime.utcnow()
    still_open = (
        await db.execute(
            select(func.count()).select_from(m.GymMaintenance).where(
                m.GymMaintenance.equipment_id == eq.id, m.GymMaintenance.status == "open", m.GymMaintenance.id != ticket.id
            )
        )
    ).scalar_one()
    if retire:
        eq.status = "retired"
    elif not still_open:
        eq.status = "available"
    await db.flush()
    await _audit(db, tenant_id, user_id, "fault_closed", "gym_maintenance", ticket.id, {"retired": retire})
    return {"id": ticket.id, "status": "closed", "equipment_status": eq.status}


# --- Guests -----------------------------------------------------------------------------------


def present_guest(row: m.GymGuestVisit, host: m.GymMember | None) -> dict:
    return {
        "id": row.id, "guest_name": row.guest_name, "phone": row.phone,
        "host_name": host.full_name if host else None,
        "visited_at": row.visited_at.isoformat(), "left_at": row.left_at.isoformat() if row.left_at else None,
        "fee": _money(row.fee),
    }


async def register_guest(db: AsyncSession, tenant_id: str, payload, *, user_id) -> dict:
    host = None
    if payload.host_member_id:
        host = await _member(db, tenant_id, payload.host_member_id)
        if _state(await _latest(db, tenant_id, host.id), date.today()) != "active":
            raise HTTPException(status_code=409, detail=f"{host.full_name} has no active membership to bring a guest")
    name = require_honest_narrative(payload.guest_name, label="guest name", max_length=180)
    inside = (
        await db.execute(
            select(m.GymGuestVisit.id).where(
                m.GymGuestVisit.tenant_id == tenant_id,
                func.lower(m.GymGuestVisit.guest_name) == name.lower(),
                m.GymGuestVisit.left_at.is_(None),
            )
        )
    ).first()
    if inside:
        raise HTTPException(status_code=409, detail=f"{name} is already inside")
    row = m.GymGuestVisit(
        tenant_id=tenant_id, guest_name=name, phone=payload.phone, host_member_id=host.id if host else None, created_by=user_id
    )
    db.add(row)
    await db.flush()
    from app import gym_fees

    row.fee = await gym_fees.take_fee(
        db, tenant_id, amount=getattr(payload, "fee", 0) or 0, method=getattr(payload, "method", None), kind="guest_fee",
        description=f"Gym guest fee {name}", reference=f"GUEST-{row.id[:8]}", source_id=row.id, member_id=host.id if host else None, user_id=user_id,
    )
    await _audit(db, tenant_id, user_id, "guest_in", "gym_guest_visit", row.id, {"guest": name})
    return present_guest(row, host)


async def guest_out(db: AsyncSession, tenant_id: str, visit_id: str, *, user_id) -> dict:
    stmt = select(m.GymGuestVisit).where(m.GymGuestVisit.id == visit_id, m.GymGuestVisit.tenant_id == tenant_id).with_for_update()
    row = _t((await db.execute(stmt)).scalar_one_or_none(), tenant_id, "Guest visit")
    if row.left_at:
        raise HTTPException(status_code=409, detail="This guest already left")
    row.left_at = datetime.utcnow()
    await db.flush()
    host = await db.get(m.GymMember, row.host_member_id) if row.host_member_id else None
    return present_guest(row, host)


async def list_guests(db: AsyncSession, tenant_id: str) -> list[dict]:
    rows = (
        await db.execute(
            select(m.GymGuestVisit, m.GymMember)
            .outerjoin(m.GymMember, m.GymMember.id == m.GymGuestVisit.host_member_id)
            .where(m.GymGuestVisit.tenant_id == tenant_id)
            .order_by(m.GymGuestVisit.visited_at.desc())
            .limit(100)
        )
    ).all()
    return [present_guest(g, h) for g, h in rows]
