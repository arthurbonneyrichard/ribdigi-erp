"""FMCG distributor routes. Managers and admins only."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app import fmcg_distributors as svc
from app import fmcg_orders as orders
from app.db import get_db
from app.schemas import NonNegativeMoneyValue, UuidIdValue
from app.security import require_permission

router = APIRouter(prefix="/fmcg/distributors", tags=["fmcg"])
Kind = Literal["distributor", "wholesaler", "key_account", "supermarket"]
Discount = Annotated[float, Field(ge=0, le=50, allow_inf_nan=False)]


def _env(data, message: str = "OK"):
    from app.api import env

    return env(data, message)


class DistributorBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: UuidIdValue
    kind: Kind = "distributor"
    price_discount_pct: Discount = 0
    monthly_target: NonNegativeMoneyValue | None = None
    territory_id: UuidIdValue | None = None
    notes: Annotated[str, Field(min_length=3, max_length=500)] | None = None


class DistributorUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Kind | None = None
    price_discount_pct: Discount | None = None
    monthly_target: NonNegativeMoneyValue | None = None
    territory_id: UuidIdValue | None = None
    notes: Annotated[str, Field(min_length=3, max_length=500)] | None = None
    is_active: bool | None = None


def _period(start: date | None, end: date | None) -> tuple[date, date]:
    stop = end or date.today()
    begin = start or stop.replace(day=1)
    if stop < begin or (stop - begin).days > 366:
        raise HTTPException(status_code=422, detail="Pick a period of 366 days or less, with the end after the start")
    return begin, stop


@router.get("")
async def distributors(claims=Depends(require_permission("fmcg", "read")), db: AsyncSession = Depends(get_db)):
    orders.job(claims, "distributors")
    return _env(await svc.list_all(db, tenant_id=claims["tenant_id"]))


@router.post("")
async def distributor_create(payload: DistributorBody, claims=Depends(require_permission("fmcg", "write")), db: AsyncSession = Depends(get_db)):
    orders.job(claims, "distributors")
    data = await svc.create(
        db, tenant_id=claims["tenant_id"], user_id=claims.get("sub"), customer_id=payload.customer_id, kind=payload.kind,
        price_discount_pct=payload.price_discount_pct, monthly_target=float(payload.monthly_target) if payload.monthly_target is not None else None,
        territory_id=payload.territory_id, notes=payload.notes,
    )
    await db.commit()
    return _env(data, "Distributor saved")


@router.patch("/{distributor_id}")
async def distributor_update(distributor_id: UuidIdValue, payload: DistributorUpdate, claims=Depends(require_permission("fmcg", "write")), db: AsyncSession = Depends(get_db)):
    orders.job(claims, "distributors")
    data = await svc.update(db, tenant_id=claims["tenant_id"], user_id=claims.get("sub"), distributor_id=distributor_id, changes=payload.model_dump(exclude_unset=True))
    await db.commit()
    return _env(data, "Saved")


@router.get("/ranking")
async def distributor_ranking(start: date | None = None, end: date | None = None, claims=Depends(require_permission("fmcg", "read")), db: AsyncSession = Depends(get_db)):
    orders.job(claims, "distributors")
    begin, stop = _period(start, end)
    return _env(await svc.ranking(db, tenant_id=claims["tenant_id"], start=begin, end=stop))


@router.get("/{distributor_id}/statement")
async def distributor_statement(distributor_id: UuidIdValue, start: date | None = None, end: date | None = None, claims=Depends(require_permission("fmcg", "read")), db: AsyncSession = Depends(get_db)):
    orders.job(claims, "distributors")
    begin, stop = _period(start, end)
    return _env(await svc.statement(db, tenant_id=claims["tenant_id"], distributor_id=distributor_id, start=begin, end=stop))


@router.get("/{distributor_id}/performance")
async def distributor_performance(distributor_id: UuidIdValue, start: date | None = None, end: date | None = None, claims=Depends(require_permission("fmcg", "read")), db: AsyncSession = Depends(get_db)):
    orders.job(claims, "distributors")
    begin, stop = _period(start, end)
    return _env(await svc.performance(db, tenant_id=claims["tenant_id"], distributor_id=distributor_id, start=begin, end=stop))
