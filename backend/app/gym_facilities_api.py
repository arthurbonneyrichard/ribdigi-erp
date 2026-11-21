"""Routes for gym facilities and their bookings. Booking: front desk and trainers (`classes`). Setup: managers."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app import gym as base
from app import gym_facilities as svc
from app.db import get_db
from app.schemas import UuidIdValue
from app.security import require_permission

router = APIRouter(prefix="/gym", tags=["gym"])


def _env(data, message: str = "OK"):
    from app.api import env

    return env(data, message)


class FacilityBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Annotated[str, Field(min_length=1, max_length=120)]
    kind: Literal["sauna", "pool", "studio", "court", "steam_room", "other"] = "other"
    capacity: Annotated[int, Field(ge=1, le=500)] = 1
    open_time: Annotated[str, Field(min_length=5, max_length=5)] = "06:00"
    close_time: Annotated[str, Field(min_length=5, max_length=5)] = "22:00"
    max_minutes: Annotated[int, Field(ge=15, le=480)] = 60
    branch_id: UuidIdValue | None = None


class ActiveBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    is_active: bool


class BookBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    member_id: UuidIdValue
    starts_at: datetime
    minutes: Annotated[int, Field(ge=15, le=480)] = 60


class PortalBookBody(BaseModel):
    """A member books for themselves: the member comes from their link, never from the request."""

    model_config = ConfigDict(extra="forbid")
    starts_at: datetime
    minutes: Annotated[int, Field(ge=15, le=480)] = 60


class StatusBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["attended", "no_show", "cancelled"]


Read = Depends(require_permission("gym", "read"))
Write = Depends(require_permission("gym", "write"))


@router.get("/facilities")
async def facilities(claims=Read, db: AsyncSession = Depends(get_db)):
    base.job(claims, "classes")
    return _env(await svc.list_facilities(db, claims["tenant_id"]))


@router.post("/facilities")
async def facility_add(payload: FacilityBody, claims=Write, db: AsyncSession = Depends(get_db)):
    base.job(claims, "correct")
    data = await svc.create_facility(db, claims["tenant_id"], payload, user_id=claims.get("sub"))
    await db.commit()
    return _env(data, "Facility added")


@router.post("/facilities/{facility_id}/active")
async def facility_active(facility_id: UuidIdValue, payload: ActiveBody, claims=Write, db: AsyncSession = Depends(get_db)):
    base.job(claims, "correct")
    data = await svc.set_active(db, claims["tenant_id"], facility_id, active=payload.is_active, user_id=claims.get("sub"))
    await db.commit()
    return _env(data, "Saved")


@router.get("/facility-bookings")
async def bookings(day: date | None = None, claims=Read, db: AsyncSession = Depends(get_db)):
    base.job(claims, "classes")
    return _env(await svc.list_bookings(db, claims["tenant_id"], day=day))


@router.post("/facilities/{facility_id}/book")
async def book(facility_id: UuidIdValue, payload: BookBody, claims=Write, db: AsyncSession = Depends(get_db)):
    base.job(claims, "classes")
    data = await svc.book(db, claims["tenant_id"], facility_id, member_id=payload.member_id, starts_at=payload.starts_at, minutes=payload.minutes, user_id=claims.get("sub"))
    await db.commit()
    return _env(data, "Booked")


@router.post("/facility-bookings/{booking_id}")
async def booking_set(booking_id: UuidIdValue, payload: StatusBody, claims=Write, db: AsyncSession = Depends(get_db)):
    base.job(claims, "classes")
    data = await svc.set_booking(db, claims["tenant_id"], booking_id, status=payload.status, user_id=claims.get("sub"))
    await db.commit()
    return _env(data, "Saved")
