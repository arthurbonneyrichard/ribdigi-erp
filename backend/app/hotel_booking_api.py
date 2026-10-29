"""Hotel online stay requests. A request holds a room and does not take a payment."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app import hotel as hotel_svc
from app.db import get_db
from app.schemas import E164PhoneValue, IsoDateQueryValue, UuidIdValue, WebsiteHostnameValue
from app.security import require_permission

router = APIRouter(prefix="/hotel", tags=["hotel"])
public_router = APIRouter(prefix="/public/hotel-booking", tags=["hotel-booking"])


def _env(data, message: str = "OK"):
    from app.api import env

    return env(data, message)


class HotelBookingLinkBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hostname: WebsiteHostnameValue
    link_kind: Literal["existing", "new"]


class PublicStayBody(BaseModel):
    """Guest stay request. extra=forbid so a payment field is refused."""

    model_config = ConfigDict(extra="forbid")

    guest_name: str = Field(min_length=1, max_length=150)
    phone: E164PhoneValue
    email: EmailStr | None = None
    check_in_date: IsoDateQueryValue
    check_out_date: IsoDateQueryValue
    adults: int = Field(default=1, ge=1, le=20)
    children: int = Field(default=0, ge=0, le=20)
    room_id: UuidIdValue
    notes: str | None = None


@router.get("/booking-link")
async def hotel_booking_link(
    claims=Depends(require_permission("hotel", "read")),
    db: AsyncSession = Depends(get_db),
):
    return _env(await hotel_svc.get_hotel_booking_link(db, claims["tenant_id"]))


@router.put("/booking-link")
async def hotel_save_booking_link(
    payload: HotelBookingLinkBody,
    claims=Depends(require_permission("hotel", "write")),
    db: AsyncSession = Depends(get_db),
):
    body = await hotel_svc.save_hotel_booking_link(
        db,
        claims["tenant_id"],
        hostname=payload.hostname,
        link_kind=payload.link_kind,
    )
    await db.commit()
    return _env(body, "Booking link saved")


@public_router.get("/by-host")
async def hotel_booking_by_host(
    host: str = Query(min_length=1, max_length=253),
    db: AsyncSession = Depends(get_db),
):
    return _env(await hotel_svc.hotel_booking_page_for_host(db, host))


@public_router.get("/{slug}/rooms")
async def hotel_booking_rooms(
    slug: str,
    check_in: IsoDateQueryValue = Query(),
    check_out: IsoDateQueryValue = Query(),
    adults: int = Query(default=1, ge=1, le=20),
    children: int = Query(default=0, ge=0, le=20),
    db: AsyncSession = Depends(get_db),
):
    rows = await hotel_svc.public_available_rooms(
        db,
        slug,
        check_in_date=check_in,
        check_out_date=check_out,
        adults=adults,
        children=children,
    )
    return _env(rows)


@public_router.get("/{slug}")
async def hotel_booking_page(slug: str, db: AsyncSession = Depends(get_db)):
    return _env(await hotel_svc.hotel_booking_page(db, slug))


@public_router.post("/{slug}")
async def hotel_booking_create(slug: str, payload: PublicStayBody, db: AsyncSession = Depends(get_db)):
    body = await hotel_svc.create_public_stay(
        db,
        slug,
        guest_name=payload.guest_name,
        phone=payload.phone,
        email=payload.email,
        check_in_date=payload.check_in_date,
        check_out_date=payload.check_out_date,
        adults=payload.adults,
        children=payload.children,
        room_id=payload.room_id,
        notes=payload.notes,
    )
    await db.commit()
    return _env(body, "Stay requested")
