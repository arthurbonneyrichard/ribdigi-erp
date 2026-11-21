"""Gym fitness: exercise library, workout programmes, workout logs and body measurements.

Fitness tracking only. Nothing here is medical advice, and BMI is a plain number, not a diagnosis.
Every row is scoped by tenant; a programme and its logs always belong to the same member.
"""

from __future__ import annotations

from datetime import date

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.gym import _audit, _member
from app.honesty import money_json, optional_honest_narrative, require_honest_narrative


def _num(value):
    return None if value is None else money_json(round(float(value), 2))


def bmi(weight_kg, height_cm):
    if not weight_kg or not height_cm or float(height_cm) <= 0:
        return None
    h = float(height_cm) / 100
    return round(float(weight_kg) / (h * h), 1)


# --- Exercise library -----------------------------------------------------------------------


def present_exercise(row: m.GymExercise) -> dict:
    return {"id": row.id, "name": row.name, "muscle_group": row.muscle_group, "equipment": row.equipment, "is_active": bool(row.is_active)}


async def create_exercise(db: AsyncSession, tenant_id: str, payload, *, user_id) -> m.GymExercise:
    name = require_honest_narrative(payload.name, label="exercise name", max_length=150)
    dup = (
        await db.execute(select(m.GymExercise.id).where(m.GymExercise.tenant_id == tenant_id, func.lower(m.GymExercise.name) == name.lower()))
    ).first()
    if dup:
        raise HTTPException(status_code=409, detail="This exercise is already in the library")
    row = m.GymExercise(
        tenant_id=tenant_id, name=name,
        muscle_group=optional_honest_narrative(payload.muscle_group, label="muscle group", max_length=80),
        equipment=optional_honest_narrative(payload.equipment, label="equipment", max_length=120),
    )
    db.add(row)
    await db.flush()
    await _audit(db, tenant_id, user_id, "exercise_created", "gym_exercise", row.id, {"name": name})
    return row


async def list_exercises(db: AsyncSession, tenant_id: str) -> list[dict]:
    rows = (await db.execute(select(m.GymExercise).where(m.GymExercise.tenant_id == tenant_id).order_by(m.GymExercise.name))).scalars().all()
    return [present_exercise(r) for r in rows]


# --- Programmes -----------------------------------------------------------------------------


async def _programme(db, tenant_id: str, programme_id: str, *, lock: bool = False) -> m.GymProgramme:
    stmt = select(m.GymProgramme).where(m.GymProgramme.id == programme_id, m.GymProgramme.tenant_id == tenant_id)
    if lock:
        stmt = stmt.with_for_update()
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Programme not found")
    return row


async def present_programme(db: AsyncSession, row: m.GymProgramme) -> dict:
    member = await db.get(m.GymMember, row.member_id)
    trainer = await db.get(m.GymTrainer, row.trainer_id) if row.trainer_id else None
    lines = (
        await db.execute(
            select(m.GymProgrammeLine, m.GymExercise)
            .join(m.GymExercise, m.GymExercise.id == m.GymProgrammeLine.exercise_id)
            .where(m.GymProgrammeLine.programme_id == row.id, m.GymProgrammeLine.tenant_id == row.tenant_id)
            .order_by(m.GymProgrammeLine.day_of_week, m.GymProgrammeLine.position)
        )
    ).all()
    done = {
        line_id: int(n)
        for line_id, n in (
            await db.execute(
                select(m.GymWorkoutLog.line_id, func.count())
                .where(m.GymWorkoutLog.programme_id == row.id, m.GymWorkoutLog.tenant_id == row.tenant_id)
                .group_by(m.GymWorkoutLog.line_id)
            )
        ).all()
    }
    return {
        "id": row.id, "name": row.name, "goal": row.goal, "status": row.status,
        "member_id": row.member_id, "member_name": member.full_name if member else "",
        "trainer_id": row.trainer_id, "trainer_name": trainer.full_name if trainer else None,
        "starts_on": row.starts_on.isoformat(), "ends_on": row.ends_on.isoformat() if row.ends_on else None,
        "lines": [
            {
                "id": ln.id, "exercise_id": ex.id, "exercise": ex.name, "day_of_week": ln.day_of_week, "sets": ln.sets,
                "reps": ln.reps, "weight_kg": _num(ln.weight_kg), "rest_seconds": ln.rest_seconds, "notes": ln.notes,
                "times_done": done.get(ln.id, 0),
            }
            for ln, ex in lines
        ],
    }


async def create_programme(db: AsyncSession, tenant_id: str, payload, *, user_id) -> dict:
    member = await _member(db, tenant_id, payload.member_id)
    trainer = None
    if payload.trainer_id:
        trainer = await db.get(m.GymTrainer, payload.trainer_id)
        if trainer is None or trainer.tenant_id != tenant_id:
            raise HTTPException(status_code=404, detail="Trainer not found")
        if not trainer.is_active:
            raise HTTPException(status_code=409, detail=f"{trainer.full_name} is not active")
    if payload.ends_on and payload.ends_on < payload.starts_on:
        raise HTTPException(status_code=422, detail="The programme cannot end before it starts")
    ids = {ln.exercise_id for ln in payload.lines}
    found = {
        r.id: r
        for r in (await db.execute(select(m.GymExercise).where(m.GymExercise.tenant_id == tenant_id, m.GymExercise.id.in_(ids)))).scalars().all()
    }
    if len(found) != len(ids):
        raise HTTPException(status_code=404, detail="An exercise was not found")
    if any(not e.is_active for e in found.values()):
        raise HTTPException(status_code=409, detail="An exercise in this programme is no longer in use")
    row = m.GymProgramme(
        tenant_id=tenant_id, member_id=member.id, trainer_id=trainer.id if trainer else None,
        name=require_honest_narrative(payload.name, label="programme name", max_length=150),
        goal=optional_honest_narrative(payload.goal, label="goal", max_length=300),
        starts_on=payload.starts_on, ends_on=payload.ends_on, created_by=user_id,
    )
    db.add(row)
    await db.flush()
    for pos, ln in enumerate(payload.lines):
        db.add(
            m.GymProgrammeLine(
                tenant_id=tenant_id, programme_id=row.id, exercise_id=ln.exercise_id, day_of_week=ln.day_of_week, position=pos,
                sets=ln.sets, reps=ln.reps, weight_kg=ln.weight_kg, rest_seconds=ln.rest_seconds,
                notes=optional_honest_narrative(ln.notes, label="note", max_length=300),
            )
        )
    await db.flush()
    await _audit(db, tenant_id, user_id, "programme_created", "gym_programme", row.id, {"member_id": member.id, "lines": len(payload.lines)})
    return await present_programme(db, row)


async def list_programmes(db: AsyncSession, tenant_id: str, *, member_id: str | None = None) -> list[dict]:
    stmt = select(m.GymProgramme).where(m.GymProgramme.tenant_id == tenant_id).order_by(m.GymProgramme.created_at.desc())
    if member_id:
        stmt = stmt.where(m.GymProgramme.member_id == member_id)
    return [await present_programme(db, r) for r in (await db.execute(stmt)).scalars().all()]


async def set_programme_status(db: AsyncSession, tenant_id: str, programme_id: str, *, status: str, user_id) -> dict:
    row = await _programme(db, tenant_id, programme_id, lock=True)
    if row.status != "active":
        raise HTTPException(status_code=409, detail=f"This programme is already {row.status}")
    row.status = status
    await _audit(db, tenant_id, user_id, f"programme_{status}", "gym_programme", row.id, {})
    return await present_programme(db, row)


async def log_workout(db: AsyncSession, tenant_id: str, programme_id: str, payload, *, user_id) -> dict:
    prog = await _programme(db, tenant_id, programme_id, lock=True)
    if prog.status != "active":
        raise HTTPException(status_code=409, detail="This programme is not active")
    line = await db.get(m.GymProgrammeLine, payload.line_id)
    if line is None or line.tenant_id != tenant_id or line.programme_id != prog.id:
        raise HTTPException(status_code=404, detail="That exercise is not in this programme")
    done_on = payload.done_on or date.today()
    if done_on > date.today():
        raise HTTPException(status_code=422, detail="A workout cannot be logged in the future")
    if done_on < prog.starts_on:
        raise HTTPException(status_code=422, detail="That is before the programme started")
    clash = (
        await db.execute(
            select(m.GymWorkoutLog.id).where(
                m.GymWorkoutLog.line_id == line.id, m.GymWorkoutLog.done_on == done_on, m.GymWorkoutLog.tenant_id == tenant_id
            )
        )
    ).first()
    if clash:
        raise HTTPException(status_code=409, detail="This exercise is already logged for that day")
    db.add(
        m.GymWorkoutLog(
            tenant_id=tenant_id, programme_id=prog.id, line_id=line.id, member_id=prog.member_id, done_on=done_on,
            sets_done=payload.sets_done, reps_done=payload.reps_done, weight_kg=payload.weight_kg, recorded_by=user_id,
        )
    )
    await db.flush()
    await _audit(db, tenant_id, user_id, "workout_logged", "gym_programme", prog.id, {"line_id": line.id})
    return await present_programme(db, prog)


async def workout_history(db: AsyncSession, tenant_id: str, member_id: str) -> list[dict]:
    await _member(db, tenant_id, member_id)
    rows = (
        await db.execute(
            select(m.GymWorkoutLog, m.GymExercise.name)
            .join(m.GymProgrammeLine, m.GymProgrammeLine.id == m.GymWorkoutLog.line_id)
            .join(m.GymExercise, m.GymExercise.id == m.GymProgrammeLine.exercise_id)
            .where(m.GymWorkoutLog.member_id == member_id, m.GymWorkoutLog.tenant_id == tenant_id)
            .order_by(m.GymWorkoutLog.done_on.desc())
        )
    ).all()
    return [
        {"id": lg.id, "done_on": lg.done_on.isoformat(), "exercise": name, "sets_done": lg.sets_done, "reps_done": lg.reps_done, "weight_kg": _num(lg.weight_kg)}
        for lg, name in rows
    ]


# --- Body measurements ----------------------------------------------------------------------

_FIELDS = ("weight_kg", "height_cm", "body_fat_pct", "waist_cm", "chest_cm", "hips_cm", "arms_cm", "thighs_cm", "resting_hr")


def present_measurement(row: m.GymMeasurement) -> dict:
    out = {"id": row.id, "measured_on": row.measured_on.isoformat(), "notes": row.notes, "bmi": bmi(row.weight_kg, row.height_cm)}
    for f in _FIELDS:
        v = getattr(row, f)
        out[f] = None if v is None else (int(v) if f == "resting_hr" else _num(v))
    return out


async def record_measurement(db: AsyncSession, tenant_id: str, member_id: str, payload, *, user_id) -> dict:
    member = await _member(db, tenant_id, member_id)
    when = payload.measured_on or date.today()
    if when > date.today():
        raise HTTPException(status_code=422, detail="A measurement cannot be dated in the future")
    if all(getattr(payload, f) is None for f in _FIELDS):
        raise HTTPException(status_code=422, detail="Enter at least one measurement")
    height = payload.height_cm
    if height is None:  # keep the last known height so BMI works on later visits
        height = (
            await db.execute(
                select(m.GymMeasurement.height_cm)
                .where(m.GymMeasurement.member_id == member.id, m.GymMeasurement.tenant_id == tenant_id, m.GymMeasurement.height_cm.is_not(None))
                .order_by(m.GymMeasurement.measured_on.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
    values = {f: getattr(payload, f) for f in _FIELDS}
    values["height_cm"] = height
    row = m.GymMeasurement(
        tenant_id=tenant_id, member_id=member.id, measured_on=when, recorded_by=user_id,
        notes=optional_honest_narrative(payload.notes, label="note", max_length=500), **values,
    )
    db.add(row)
    await db.flush()
    await _audit(db, tenant_id, user_id, "measurement_recorded", "gym_member", member.id, {"on": when.isoformat()})
    return present_measurement(row)


async def list_measurements(db: AsyncSession, tenant_id: str, member_id: str) -> dict:
    await _member(db, tenant_id, member_id)
    rows = (
        await db.execute(
            select(m.GymMeasurement)
            .where(m.GymMeasurement.member_id == member_id, m.GymMeasurement.tenant_id == tenant_id)
            .order_by(m.GymMeasurement.measured_on, m.GymMeasurement.created_at)
        )
    ).scalars().all()
    items = [present_measurement(r) for r in rows]
    change = {}
    if len(items) >= 2:
        for f in ("weight_kg", "body_fat_pct", "waist_cm", "bmi"):
            a, b = items[0].get(f), items[-1].get(f)
            if a is not None and b is not None:
                change[f] = round(b - a, 2)
    return {"items": list(reversed(items)), "change_since_first": change}
