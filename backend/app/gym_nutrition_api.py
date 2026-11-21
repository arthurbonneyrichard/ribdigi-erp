"""Routes for gym nutrition plans. Same access as fitness: trainers and managers only."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app import gym as base
from app import gym_nutrition as svc
from app.db import get_db
from app.schemas import UuidIdValue
from app.security import require_permission

router = APIRouter(prefix="/gym", tags=["gym"])
Cal = Annotated[int, Field(ge=0, le=20000)]
Grams = Annotated[int, Field(ge=0, le=2000)]
Ml = Annotated[int, Field(ge=0, le=20000)]
Long = Annotated[str, Field(min_length=1, max_length=4000)]
Short = Annotated[str, Field(min_length=1, max_length=300)]


def _env(data, message: str = "OK"):
    from app.api import env

    return env(data, message)


class PlanBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    member_id: UuidIdValue
    name: Annotated[str, Field(min_length=1, max_length=150)]
    calories: Cal | None = None
    protein_g: Grams | None = None
    carbs_g: Grams | None = None
    fat_g: Grams | None = None
    water_ml: Ml | None = None
    allergies: Short | None = None
    preferences: Short | None = None
    meals: Long | None = None
    starts_on: date
    ends_on: date | None = None


class PlanStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["completed", "cancelled"]


class IntakeBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    logged_on: date | None = None
    calories: Cal | None = None
    protein_g: Grams | None = None
    carbs_g: Grams | None = None
    fat_g: Grams | None = None
    water_ml: Ml | None = None


Read = Depends(require_permission("gym", "read"))
Write = Depends(require_permission("gym", "write"))
AREA = "fitness"


@router.get("/nutrition-plans")
async def plans(member_id: UuidIdValue | None = None, claims=Read, db: AsyncSession = Depends(get_db)):
    base.job(claims, AREA)
    return _env(await svc.list_plans(db, claims["tenant_id"], member_id=member_id))


@router.post("/nutrition-plans")
async def plan_add(payload: PlanBody, claims=Write, db: AsyncSession = Depends(get_db)):
    base.job(claims, AREA)
    data = await svc.create_plan(db, claims["tenant_id"], payload, user_id=claims.get("sub"))
    await db.commit()
    return _env(data, "Nutrition plan saved")


@router.post("/nutrition-plans/{plan_id}/status")
async def plan_set(plan_id: UuidIdValue, payload: PlanStatus, claims=Write, db: AsyncSession = Depends(get_db)):
    base.job(claims, AREA)
    data = await svc.set_status(db, claims["tenant_id"], plan_id, status=payload.status, user_id=claims.get("sub"))
    await db.commit()
    return _env(data, "Saved")


@router.post("/nutrition-plans/{plan_id}/intake")
async def intake_add(plan_id: UuidIdValue, payload: IntakeBody, claims=Write, db: AsyncSession = Depends(get_db)):
    base.job(claims, AREA)
    data = await svc.log_intake(db, claims["tenant_id"], plan_id, payload, user_id=claims.get("sub"))
    await db.commit()
    return _env(data, "Intake logged")
