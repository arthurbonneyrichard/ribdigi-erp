"""Hotel online stay requests. A request holds a room and does not take a payment."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, Query
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
    notes: str | None = Field(default=None, max_length=1000)


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
async def hotel_booking_create(
    slug: str, payload: PublicStayBody, background: BackgroundTasks, db: AsyncSession = Depends(get_db)
):
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
    try:
        from sqlalchemy import select

        from app import models as m
        from app import online_alerts as alerts

        tenant = (await db.execute(select(m.Tenant).where(m.Tenant.slug == slug))).scalars().first()
        if tenant is not None:
            title, lines, link = alerts.compose_hotel(
                tenant,
                {
                    "number": body.get("reservation_number"), "name": payload.guest_name, "phone": payload.phone,
                    "email": str(payload.email) if payload.email else None, "check_in": body.get("check_in_date"),
                    "check_out": body.get("check_out_date"), "nights": body.get("nights"), "adults": payload.adults,
                    "children": payload.children, "room": body.get("room_name"), "total": body.get("estimated_total"),
                    "notes": payload.notes,
                },
            )
            alerts.schedule(
                background, tenant.id, kind="booking", title=title, lines=lines, link=link,
                entity_type="hotel_reservation", entity_id=body.get("id"),
            )
    except Exception:  # noqa: BLE001
        import logging

        logging.getLogger(__name__).exception("stay request alert could not be queued")
    return _env(body, "Stay requested")
