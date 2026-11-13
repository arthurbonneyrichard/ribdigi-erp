"""Restaurant tip share-outs. Managers share out and pay; everyone sees their own tips."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app import restaurant_tips as svc
from app.db import get_db
from app.restaurant_api import _restaurant_job_gate
from app.schemas import UuidIdValue
from app.security import require_permission

router = APIRouter(prefix="/restaurant/tips", tags=["restaurant"], dependencies=[Depends(_restaurant_job_gate)])


def _env(data, message: str = "OK"):
    from app.api import env

    return env(data, message)


class TipRunBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date_from: date
    date_to: date
    method: Literal["by_server", "equal", "hours"]
    pay_by: Literal["cash", "payroll"] = "cash"
    period: Annotated[str, Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")] | None = None
    user_ids: list[UuidIdValue] = []
    notes: Annotated[str, Field(max_length=500)] | None = None


class TipPayBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method: Literal["cash", "bank_transfer", "mobile_money"]


@router.get("/mine")
async def my_tips(claims=Depends(require_permission("restaurant", "read")), db: AsyncSession = Depends(get_db)):
    return _env(await svc.mine(db, claims["tenant_id"], claims["sub"]))


@router.get("/unshared")
async def unshared(
    date_from: date = Query(...), date_to: date = Query(...),
    claims=Depends(require_permission("restaurant", "read")), db: AsyncSession = Depends(get_db),
):
    svc.require_manager(claims)
    return _env(await svc.unshared(db, claims["tenant_id"], date_from, date_to))


@router.get("/staff")
async def staff(claims=Depends(require_permission("restaurant", "read")), db: AsyncSession = Depends(get_db)):
    svc.require_manager(claims)
    return _env(await svc.staff(db, claims["tenant_id"]))


@router.get("/runs")
async def runs(claims=Depends(require_permission("restaurant", "read")), db: AsyncSession = Depends(get_db)):
    svc.require_manager(claims)
    return _env(await svc.list_runs(db, claims["tenant_id"]))


@router.post("/runs")
async def create_run(payload: TipRunBody, claims=Depends(require_permission("restaurant", "write")), db: AsyncSession = Depends(get_db)):
    svc.require_manager(claims)
    run = await svc.create_run(db, claims["tenant_id"], payload, user_id=claims.get("sub"))
    await db.commit()
    return _env(await svc.serialize_run(db, run), "Tips shared out")


@router.post("/runs/{run_id}/approve")
async def approve(run_id: UuidIdValue, claims=Depends(require_permission("restaurant", "write")), db: AsyncSession = Depends(get_db)):
    svc.require_manager(claims)
    run = await svc.approve(db, claims["tenant_id"], run_id, user_id=claims.get("sub"))
    await db.commit()
    return _env(await svc.serialize_run(db, run), "Approved")


@router.post("/runs/{run_id}/pay")
async def pay(run_id: UuidIdValue, payload: TipPayBody, claims=Depends(require_permission("restaurant", "write")), db: AsyncSession = Depends(get_db)):
    svc.require_manager(claims)
    run = await svc.pay_cash(db, claims["tenant_id"], run_id, method=payload.method, user_id=claims.get("sub"))
    await db.commit()
    return _env(await svc.serialize_run(db, run), "Tips paid")


@router.post("/runs/{run_id}/cancel")
async def cancel(run_id: UuidIdValue, claims=Depends(require_permission("restaurant", "write")), db: AsyncSession = Depends(get_db)):
    svc.require_manager(claims)
    run = await svc.cancel(db, claims["tenant_id"], run_id, user_id=claims.get("sub"))
    await db.commit()
    return _env(await svc.serialize_run(db, run), "Cancelled; the tips are back in the pool")
