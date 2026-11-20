"""Routes for gym insights. Managers see all of it; trainers can only draft workouts."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app import gym as base
from app import gym_insights as svc
from app.db import get_db
from app.schemas import UuidIdValue
from app.security import require_permission

router = APIRouter(prefix="/gym/insights", tags=["gym"])


def _env(data, message: str = "OK"):
    from app.api import env

    return env(data, message)


class Switch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    insights_enabled: bool


class DraftBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    member_id: UuidIdValue
    goal: Literal["strength", "muscle", "weight_loss", "endurance"]
    level: Literal["beginner", "intermediate", "advanced"] = "beginner"
    days_per_week: Annotated[int, Field(ge=1, le=5)] = 3


Read = Depends(require_permission("gym", "read"))
Write = Depends(require_permission("gym", "write"))


async def _gate(claims, db):
    base.job(claims, "correct")
    await svc.require_enabled(db, claims["tenant_id"])


@router.get("/status")
async def status(claims=Read, db: AsyncSession = Depends(get_db)):
    base.job(claims, "correct")
    return _env({"insights_enabled": await svc.is_enabled(db, claims["tenant_id"]), "method": svc.METHOD, "note": svc.NOTE})


@router.post("/status")
async def status_set(payload: Switch, claims=Write, db: AsyncSession = Depends(get_db)):
    base.job(claims, "correct")
    data = await svc.set_enabled(db, claims["tenant_id"], payload.insights_enabled, user_id=claims.get("sub"))
    await db.commit()
    return _env(data, "Saved")


@router.get("/summary")
async def summary(claims=Read, db: AsyncSession = Depends(get_db)):
    await _gate(claims, db)
    return _env(await svc.summary(db, claims["tenant_id"]))


@router.get("/churn-risk")
async def churn(claims=Read, db: AsyncSession = Depends(get_db)):
    await _gate(claims, db)
    return _env(await svc.churn_risk(db, claims["tenant_id"]))


@router.get("/attendance")
async def attendance(weeks: int = Query(8, ge=2, le=26), claims=Read, db: AsyncSession = Depends(get_db)):
    await _gate(claims, db)
    return _env(await svc.attendance_trends(db, claims["tenant_id"], weeks=weeks))


@router.get("/equipment")
async def equipment(claims=Read, db: AsyncSession = Depends(get_db)):
    await _gate(claims, db)
    return _env(await svc.equipment_insights(db, claims["tenant_id"]))


@router.post("/workout-draft")
async def workout_draft(payload: DraftBody, claims=Write, db: AsyncSession = Depends(get_db)):
    base.job(claims, "fitness")
    await svc.require_enabled(db, claims["tenant_id"])
    return _env(await svc.draft_workout(db, claims["tenant_id"], payload), "Draft ready for review")
