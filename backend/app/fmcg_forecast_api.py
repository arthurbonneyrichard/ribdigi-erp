"""FMCG demand forecast routes. Managers and admins only."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app import fmcg_forecast as svc
from app import fmcg_orders as orders
from app.db import get_db
from app.security import require_permission

router = APIRouter(prefix="/fmcg/forecast", tags=["fmcg"])


def _env(data, message: str = "OK"):
    from app.api import env

    return env(data, message)


class PolicyBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lead_time_days: Annotated[int, Field(ge=1, le=120)]
    service_level: Annotated[int, Field(ge=90, le=99)]
    overstock_days: Annotated[int, Field(ge=30, le=720)]


@router.get("")
async def forecast(
    history_days: Annotated[int, Query(ge=28, le=365)] = 90,
    horizon_days: Annotated[int, Query(ge=7, le=180)] = 30,
    claims=Depends(require_permission("fmcg", "read")), db: AsyncSession = Depends(get_db),
):
    orders.job(claims, "forecast")
    return _env(await svc.forecast(db, tenant_id=claims["tenant_id"], history_days=history_days, horizon_days=horizon_days))


@router.get("/policy")
async def policy(claims=Depends(require_permission("fmcg", "read")), db: AsyncSession = Depends(get_db)):
    orders.job(claims, "forecast")
    return _env(await svc.get_policy(db, claims["tenant_id"]))


@router.put("/policy")
async def policy_save(
    payload: PolicyBody, claims=Depends(require_permission("fmcg", "write")), db: AsyncSession = Depends(get_db)
):
    orders.job(claims, "forecast")
    data = await svc.set_policy(
        db, claims["tenant_id"], lead_time_days=payload.lead_time_days, service_level=payload.service_level,
        overstock_days=payload.overstock_days, user_id=claims.get("sub"),
    )
    await db.commit()
    return _env(data, "Saved")
