"""FMCG field routes: territories and outlet visits from the rep's phone location."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import fmcg_field as svc
from app import fmcg_orders
from app import models as m
from app.db import get_db
from app.schemas import UuidIdValue
from app.security import require_permission

router = APIRouter(prefix="/fmcg", tags=["fmcg"])

MANAGERS = frozenset({"company_admin", "fmcg_manager", "super_admin"})
Lat = Annotated[float, Field(ge=-90, le=90, allow_inf_nan=False)]
Lon = Annotated[float, Field(ge=-180, le=180, allow_inf_nan=False)]
Accuracy = Annotated[float, Field(ge=0, le=100000, allow_inf_nan=False)]
Period = Annotated[str, Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")]


def _env(data, message: str = "OK"):
    from app.api import env

    return env(data, message)


def _manager(claims: dict) -> bool:
    return str(claims.get("role") or "") in MANAGERS


class TerritoryBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,39}$")]
    name: Annotated[str, Field(min_length=1, max_length=150)]
    notes: Annotated[str, Field(max_length=2000)] | None = None
    daily_visit_target: Annotated[int, Field(ge=0, le=500)] = 0
    is_active: bool = True
    route_ids: list[UuidIdValue] = []
    rep_user_ids: list[UuidIdValue] = []


class CheckInBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outlet_id: UuidIdValue
    latitude: Lat | None = None
    longitude: Lon | None = None
    accuracy_m: Accuracy | None = None


class CheckOutBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outcome: Literal["order", "no_order", "closed", "not_found"]
    no_order_reason: Literal["has_stock", "no_money", "owner_away", "price", "competitor", "other"] | None = None
    notes: Annotated[str, Field(max_length=500)] | None = None
    latitude: Lat | None = None
    longitude: Lon | None = None
    accuracy_m: Accuracy | None = None


@router.get("/territories")
async def territories(claims=Depends(require_permission("fmcg", "read")), db: AsyncSession = Depends(get_db)):
    fmcg_orders.job(claims, "visits")
    return _env(await svc.list_territories(db, claims["tenant_id"]))


@router.post("/territories")
async def territory_create(payload: TerritoryBody, claims=Depends(require_permission("fmcg", "write")), db: AsyncSession = Depends(get_db)):
    fmcg_orders.job(claims, "correct")
    row = await svc.save_territory(db, claims["tenant_id"], payload, territory_id=None, user_id=claims.get("sub"))
    await db.commit()
    return _env(await svc.serialize_territory(db, row), "Territory saved")


@router.put("/territories/{territory_id}")
async def territory_update(
    territory_id: UuidIdValue, payload: TerritoryBody,
    claims=Depends(require_permission("fmcg", "write")), db: AsyncSession = Depends(get_db),
):
    fmcg_orders.job(claims, "correct")
    row = await svc.save_territory(db, claims["tenant_id"], payload, territory_id=territory_id, user_id=claims.get("sub"))
    await db.commit()
    return _env(await svc.serialize_territory(db, row), "Territory saved")


@router.get("/field-people")
async def field_people(claims=Depends(require_permission("fmcg", "read")), db: AsyncSession = Depends(get_db)):
    """Active staff who can be put on a territory (reps and managers)."""
    fmcg_orders.job(claims, "correct")
    rows = (
        await db.execute(
            select(m.User.id, m.User.full_name, m.User.email, m.User.role)
            .where(m.User.tenant_id == claims["tenant_id"], m.User.is_active.is_(True), m.User.role.in_(("fmcg_rep", "fmcg_manager", "company_admin")))
            .order_by(m.User.full_name)
        )
    ).all()
    return _env([{"id": i, "name": n or e, "role": r} for i, n, e, r in rows])


@router.get("/my-outlets")
async def my_outlets(claims=Depends(require_permission("fmcg", "read")), db: AsyncSession = Depends(get_db)):
    fmcg_orders.job(claims, "visits")
    return _env(await svc.outlets_for(db, claims["tenant_id"], user_id=claims.get("sub"), everyone=_manager(claims)))


@router.post("/visits/check-in")
async def visit_check_in(
    payload: CheckInBody, request: Request,
    claims=Depends(require_permission("fmcg", "write")), db: AsyncSession = Depends(get_db),
):
    fmcg_orders.job(claims, "visits")
    row = await svc.check_in(
        db, claims["tenant_id"], payload, user_id=claims["sub"], may_visit_any=_manager(claims),
        device=request.headers.get("user-agent"),
    )
    await db.commit()
    return _env(row, "Checked in")


@router.post("/visits/{visit_id}/check-out")
async def visit_check_out(
    visit_id: UuidIdValue, payload: CheckOutBody,
    claims=Depends(require_permission("fmcg", "write")), db: AsyncSession = Depends(get_db),
):
    fmcg_orders.job(claims, "visits")
    row = await svc.check_out(db, claims["tenant_id"], visit_id, payload, user_id=claims["sub"])
    await db.commit()
    return _env(row, "Visit finished")


@router.get("/visits")
async def visits(
    day: date | None = Query(default=None), user_id: UuidIdValue | None = Query(default=None),
    claims=Depends(require_permission("fmcg", "read")), db: AsyncSession = Depends(get_db),
):
    fmcg_orders.job(claims, "visits")
    zone = await svc._zone(db, claims["tenant_id"])
    day = day or datetime.now(zone).date()
    who = user_id if _manager(claims) else claims.get("sub")
    return _env(await svc.list_visits(db, claims["tenant_id"], day=day, user_id=who))


@router.get("/coverage")
async def coverage(day: date | None = Query(default=None), claims=Depends(require_permission("fmcg", "read")), db: AsyncSession = Depends(get_db)):
    fmcg_orders.job(claims, "correct")
    zone = await svc._zone(db, claims["tenant_id"])
    return _env(await svc.coverage(db, claims["tenant_id"], day or datetime.now(zone).date()))


@router.get("/territories/report")
async def territory_report(period: Period = Query(...), claims=Depends(require_permission("fmcg", "read")), db: AsyncSession = Depends(get_db)):
    fmcg_orders.job(claims, "correct")
    return _env(await svc.territory_report(db, claims["tenant_id"], period))
