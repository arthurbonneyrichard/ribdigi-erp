"""FMCG staff location routes (see fmcg_tracking for the privacy rules)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app import fmcg_tracking as svc
from app.db import get_db
from app.schemas import LatitudeValue, LongitudeValue, UuidIdValue
from app.security import require_permission

router = APIRouter(prefix="/fmcg/tracking", tags=["fmcg"])


def _env(data, message: str = "OK"):
    from app.api import env

    return env(data, message)


class PingBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    latitude: LatitudeValue
    longitude: LongitudeValue
    accuracy_m: Annotated[float, Field(ge=0, le=100000, allow_inf_nan=False)] | None = None
    speed_kmh: Annotated[float, Field(ge=0, le=400, allow_inf_nan=False)] | None = None
    captured_at: datetime


class PingsBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    points: Annotated[list[PingBody], Field(min_length=1, max_length=svc.MAX_BATCH)]


class SwitchBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool


@router.get("/me")
async def tracking_me(claims=Depends(require_permission("fmcg", "read")), db: AsyncSession = Depends(get_db)):
    svc.require_fmcg(claims)
    return _env(await svc.me_status(db, claims["tenant_id"], claims["sub"]))


@router.post("/me/notice")
async def tracking_accept_notice(claims=Depends(require_permission("fmcg", "read")), db: AsyncSession = Depends(get_db)):
    svc.require_fmcg(claims)
    data = await svc.accept_notice(db, claims["tenant_id"], claims["sub"])
    await db.commit()
    return _env(data, "Thank you. Your location is shared while you are clocked in.")


@router.post("/pings")
async def tracking_pings(
    payload: PingsBody, claims=Depends(require_permission("fmcg", "read")), db: AsyncSession = Depends(get_db)
):
    svc.require_fmcg(claims)
    data = await svc.record_pings(db, claims["tenant_id"], claims["sub"], payload.points)
    await db.commit()
    return _env(data)


@router.get("/people")
async def tracking_people(claims=Depends(require_permission("fmcg", "read")), db: AsyncSession = Depends(get_db)):
    svc.require_fmcg(claims)
    return _env({"people": await svc.people(db, claims), "can_switch": str(claims.get("role") or "") in svc.WATCH_ROLES})


@router.put("/people/{user_id}")
async def tracking_switch(
    user_id: UuidIdValue,
    payload: SwitchBody,
    claims=Depends(require_permission("fmcg", "write")),
    db: AsyncSession = Depends(get_db),
):
    svc.require_fmcg(claims)
    data = await svc.set_enabled(db, claims, user_id, payload.enabled)
    await db.commit()
    return _env(data, "Location sharing switched on" if payload.enabled else "Location sharing switched off")


@router.get("/people/{user_id}/trail")
async def tracking_trail(
    user_id: UuidIdValue,
    day: Annotated[date | None, Query()] = None,
    claims=Depends(require_permission("fmcg", "read")),
    db: AsyncSession = Depends(get_db),
):
    svc.require_fmcg(claims)
    data = await svc.trail(db, claims, user_id, day)
    await db.commit()  # the audit row
    return _env(data)
