"""Routes for gym branches and per-plan door rules. Managers only (the `correct` area)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app import gym as base
from app import gym_access as svc
from app.db import get_db
from app.schemas import UuidIdValue
from app.security import require_permission

router = APIRouter(prefix="/gym", tags=["gym"])


def _env(data, message: str = "OK"):
    from app.api import env

    return env(data, message)


class BranchBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: Annotated[str, Field(min_length=1, max_length=20)]
    name: Annotated[str, Field(min_length=1, max_length=150)]


class BranchActive(BaseModel):
    model_config = ConfigDict(extra="forbid")
    is_active: bool


class HomeBranch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    branch_id: UuidIdValue | None = None


class PlanRules(BaseModel):
    model_config = ConfigDict(extra="forbid")
    access_start: str | None = None
    access_end: str | None = None
    access_days: list[int] | None = None
    branch_scope: Literal["all", "home"] = "all"


Read = Depends(require_permission("gym", "read"))
Write = Depends(require_permission("gym", "write"))


@router.get("/branches")
async def branches(claims=Read, db: AsyncSession = Depends(get_db)):
    return _env(await svc.list_branches(db, claims["tenant_id"]))


@router.post("/branches")
async def branch_add(payload: BranchBody, claims=Write, db: AsyncSession = Depends(get_db)):
    base.job(claims, "correct")
    row = await svc.create_branch(db, claims["tenant_id"], payload, user_id=claims.get("sub"))
    await db.commit()
    return _env(svc.present_branch(row), "Branch added")


@router.post("/branches/{branch_id}/active")
async def branch_active(branch_id: UuidIdValue, payload: BranchActive, claims=Write, db: AsyncSession = Depends(get_db)):
    base.job(claims, "correct")
    data = await svc.set_branch_active(db, claims["tenant_id"], branch_id, active=payload.is_active, user_id=claims.get("sub"))
    await db.commit()
    return _env(data, "Saved")


@router.post("/members/{member_id}/branch")
async def member_branch(member_id: UuidIdValue, payload: HomeBranch, claims=Write, db: AsyncSession = Depends(get_db)):
    base.job(claims, "members")
    data = await svc.set_home_branch(db, claims["tenant_id"], member_id, payload.branch_id, user_id=claims.get("sub"))
    await db.commit()
    return _env(data, "Home branch saved")


@router.post("/plans/{plan_id}/access")
async def plan_access(plan_id: UuidIdValue, payload: PlanRules, claims=Write, db: AsyncSession = Depends(get_db)):
    base.job(claims, "correct")
    data = await svc.set_plan_rules(db, claims["tenant_id"], plan_id, payload, user_id=claims.get("sub"))
    await db.commit()
    return _env(data, "Door rules saved")


@router.get("/reports/branches")
async def branch_report(start_date: date | None = None, end_date: date | None = None, claims=Read, db: AsyncSession = Depends(get_db)):
    base.job(claims, "correct")
    end = end_date or date.today()
    start = start_date or end - timedelta(days=29)
    return _env(await svc.branch_report(db, claims["tenant_id"], start=start, end=end))
