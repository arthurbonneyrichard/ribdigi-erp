"""Routes for gym exercises, workout programmes and body measurements."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app import gym as base
from app import gym_fitness as svc
from app.db import get_db
from app.schemas import UuidIdValue
from app.security import require_permission

router = APIRouter(prefix="/gym", tags=["gym"])
Text = Annotated[str, Field(min_length=1, max_length=300)]
Kg = Annotated[float, Field(gt=0, le=1000, allow_inf_nan=False)]
Cm = Annotated[float, Field(gt=0, le=400, allow_inf_nan=False)]


def _env(data, message: str = "OK"):
    from app.api import env

    return env(data, message)


class ExerciseBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Annotated[str, Field(min_length=1, max_length=150)]
    muscle_group: Annotated[str, Field(min_length=1, max_length=80)] | None = None
    equipment: Annotated[str, Field(min_length=1, max_length=120)] | None = None


class LineBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    exercise_id: UuidIdValue
    day_of_week: Annotated[int, Field(ge=1, le=7)] = 1
    sets: Annotated[int, Field(ge=1, le=50)] = 3
    reps: Annotated[int, Field(ge=1, le=500)] = 10
    weight_kg: Kg | None = None
    rest_seconds: Annotated[int, Field(ge=0, le=3600)] | None = None
    notes: Text | None = None


class ProgrammeBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    member_id: UuidIdValue
    trainer_id: UuidIdValue | None = None
    name: Annotated[str, Field(min_length=1, max_length=150)]
    goal: Text | None = None
    starts_on: date
    ends_on: date | None = None
    lines: Annotated[list[LineBody], Field(min_length=1, max_length=100)]


class ProgrammeStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["completed", "cancelled"]


class WorkoutBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    line_id: UuidIdValue
    done_on: date | None = None
    sets_done: Annotated[int, Field(ge=0, le=50)]
    reps_done: Annotated[int, Field(ge=0, le=5000)]
    weight_kg: Kg | None = None


class MeasurementBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    measured_on: date | None = None
    weight_kg: Kg | None = None
    height_cm: Cm | None = None
    body_fat_pct: Annotated[float, Field(gt=0, lt=100, allow_inf_nan=False)] | None = None
    waist_cm: Cm | None = None
    chest_cm: Cm | None = None
    hips_cm: Cm | None = None
    arms_cm: Cm | None = None
    thighs_cm: Cm | None = None
    resting_hr: Annotated[int, Field(ge=20, le=250)] | None = None
    notes: Annotated[str, Field(min_length=1, max_length=500)] | None = None


Read = Depends(require_permission("gym", "read"))
Write = Depends(require_permission("gym", "write"))
AREA = "fitness"  # trainers and managers only: body and health details stay away from the front desk


@router.get("/exercises")
async def exercises(claims=Read, db: AsyncSession = Depends(get_db)):
    base.job(claims, AREA)
    return _env(await svc.list_exercises(db, claims["tenant_id"]))


@router.post("/exercises")
async def exercise_add(payload: ExerciseBody, claims=Write, db: AsyncSession = Depends(get_db)):
    base.job(claims, AREA)
    row = await svc.create_exercise(db, claims["tenant_id"], payload, user_id=claims.get("sub"))
    await db.commit()
    return _env(svc.present_exercise(row), "Exercise added")


@router.get("/programmes")
async def programmes(member_id: UuidIdValue | None = None, claims=Read, db: AsyncSession = Depends(get_db)):
    base.job(claims, AREA)
    return _env(await svc.list_programmes(db, claims["tenant_id"], member_id=member_id))


@router.post("/programmes")
async def programme_add(payload: ProgrammeBody, claims=Write, db: AsyncSession = Depends(get_db)):
    base.job(claims, AREA)
    data = await svc.create_programme(db, claims["tenant_id"], payload, user_id=claims.get("sub"))
    await db.commit()
    return _env(data, "Programme saved")


@router.post("/programmes/{programme_id}/status")
async def programme_set(programme_id: UuidIdValue, payload: ProgrammeStatus, claims=Write, db: AsyncSession = Depends(get_db)):
    base.job(claims, AREA)
    data = await svc.set_programme_status(db, claims["tenant_id"], programme_id, status=payload.status, user_id=claims.get("sub"))
    await db.commit()
    return _env(data, "Saved")


@router.post("/programmes/{programme_id}/workouts")
async def workout_add(programme_id: UuidIdValue, payload: WorkoutBody, claims=Write, db: AsyncSession = Depends(get_db)):
    base.job(claims, AREA)
    data = await svc.log_workout(db, claims["tenant_id"], programme_id, payload, user_id=claims.get("sub"))
    await db.commit()
    return _env(data, "Workout logged")


@router.get("/members/{member_id}/workouts")
async def workouts(member_id: UuidIdValue, claims=Read, db: AsyncSession = Depends(get_db)):
    base.job(claims, AREA)
    return _env(await svc.workout_history(db, claims["tenant_id"], member_id))


@router.get("/members/{member_id}/measurements")
async def measurements(member_id: UuidIdValue, claims=Read, db: AsyncSession = Depends(get_db)):
    base.job(claims, AREA)
    return _env(await svc.list_measurements(db, claims["tenant_id"], member_id))


@router.post("/members/{member_id}/measurements")
async def measurement_add(member_id: UuidIdValue, payload: MeasurementBody, claims=Write, db: AsyncSession = Depends(get_db)):
    base.job(claims, AREA)
    data = await svc.record_measurement(db, claims["tenant_id"], member_id, payload, user_id=claims.get("sub"))
    await db.commit()
    return _env(data, "Measurements saved")
