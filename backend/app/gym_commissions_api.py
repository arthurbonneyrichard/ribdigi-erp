"""Routes for gym trainer commissions. Managers only (the `correct` area)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app import gym as base
from app import gym_commissions as svc
from app.db import get_db
from app.schemas import UuidIdValue
from app.security import require_permission

router = APIRouter(prefix="/gym", tags=["gym"])


def _env(data, message: str = "OK"):
    from app.api import env

    return env(data, message)


class PercentBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    commission_pct: Annotated[float, Field(ge=0, le=100, allow_inf_nan=False)]


class PayBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    trainer_id: UuidIdValue
    start_date: date
    end_date: date
    reference: Annotated[str, Field(min_length=2, max_length=100)]


Read = Depends(require_permission("gym", "read"))
Write = Depends(require_permission("gym", "write"))


@router.post("/trainers/{trainer_id}/commission")
async def commission_set(trainer_id: UuidIdValue, payload: PercentBody, claims=Write, db: AsyncSession = Depends(get_db)):
    base.job(claims, "correct")
    data = await svc.set_percent(db, claims["tenant_id"], trainer_id, payload.commission_pct, user_id=claims.get("sub"))
    await db.commit()
    return _env(data, "Saved")


@router.get("/reports/commissions")
async def commissions(start_date: date | None = None, end_date: date | None = None, trainer_id: UuidIdValue | None = None, claims=Read, db: AsyncSession = Depends(get_db)):
    base.job(claims, "correct")
    end = end_date or date.today()
    return _env(await svc.report(db, claims["tenant_id"], start=start_date or end - timedelta(days=29), end=end, trainer_id=trainer_id))


@router.post("/commissions/pay")
async def commission_pay(payload: PayBody, claims=Write, db: AsyncSession = Depends(get_db)):
    base.job(claims, "correct")
    if payload.end_date < payload.start_date:
        from fastapi import HTTPException

        raise HTTPException(status_code=422, detail="The end date is before the start date")
    data = await svc.pay(db, claims["tenant_id"], payload.trainer_id, start=payload.start_date, end=payload.end_date, reference=payload.reference, user_id=claims.get("sub"))
    await db.commit()
    return _env(data, "Marked as paid")
