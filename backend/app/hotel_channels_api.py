"""Hotel routes: channel links (iCal), the public room calendar, and the city ledger."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit as audit_svc
from app import hotel as hotel_svc
from app import hotel_channels as channels_svc
from app import models as m
from app.config import settings
from app.db import get_db
from pydantic import BaseModel, ConfigDict, EmailStr

from app.schemas import (
    E164PhoneValue,
    HotelBillToBody,
    HotelChannelFeedCreate,
    HotelChannelFeedUpdate,
    PartyNameValue,
    UuidIdValue,
)
from app.security import require_permission

router = APIRouter(prefix="/hotel", tags=["hotel"])
public_router = APIRouter(prefix="/hotel-calendar", tags=["hotel-calendar"])


def _env(data, message: str = "OK"):
    from app.api import env

    return env(data, message)


def _base() -> str:
    return (settings.FRONTEND_URL or "").rstrip("/")


@router.get("/channels")
async def hotel_channels(
    claims=Depends(require_permission("hotel", "read")),
    db: AsyncSession = Depends(get_db),
):
    rows = await channels_svc.list_feeds(db, tenant_id=claims["tenant_id"])
    return _env([channels_svc.serialize_feed(f, base_url=_base(), room_code=code) for f, code in rows])


@router.post("/channels")
async def hotel_channel_create(
    payload: HotelChannelFeedCreate,
    claims=Depends(require_permission("hotel", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await channels_svc.create_feed(
        db,
        tenant_id=claims["tenant_id"],
        room_id=payload.room_id,
        channel=payload.channel,
        import_url=payload.import_url,
        created_by=claims["sub"],
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="hotel",
        action="channel_linked",
        entity="hotel_channel_feed",
        entity_id=row.id,
        details={"channel": row.channel, "room_id": row.room_id},
    )
    await db.commit()
    return _env(channels_svc.serialize_feed(row, base_url=_base()), "Booking site linked")


@router.patch("/channels/{feed_id}")
async def hotel_channel_update(
    feed_id: UuidIdValue,
    payload: HotelChannelFeedUpdate,
    claims=Depends(require_permission("hotel", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await channels_svc.update_feed(
        db,
        tenant_id=claims["tenant_id"],
        feed_id=feed_id,
        import_url=payload.import_url,
        clear_import_url=payload.clear_import_url,
        is_active=payload.is_active,
    )
    await db.commit()
    return _env(channels_svc.serialize_feed(row, base_url=_base()), "Booking site link saved")


@router.delete("/channels/{feed_id}")
async def hotel_channel_delete(
    feed_id: UuidIdValue,
    claims=Depends(require_permission("hotel", "write")),
    db: AsyncSession = Depends(get_db),
):
    await channels_svc.delete_feed(db, tenant_id=claims["tenant_id"], feed_id=feed_id)
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="hotel",
        action="channel_unlinked",
        entity="hotel_channel_feed",
        entity_id=feed_id,
        details={},
    )
    await db.commit()
    return _env({"id": feed_id}, "Booking site link removed")


@router.post("/channels/{feed_id}/sync")
async def hotel_channel_sync(
    feed_id: UuidIdValue,
    claims=Depends(require_permission("hotel", "write")),
    db: AsyncSession = Depends(get_db),
):
    feed = await channels_svc._feed(db, claims["tenant_id"], feed_id)
    try:
        result = await channels_svc.sync_feed(db, tenant_id=claims["tenant_id"], feed=feed, user_id=claims["sub"])
    except Exception:
        # Keep the failure on the link's status line for staff to see.
        await db.commit()
        raise
    await db.commit()
    return _env(result, result["status"])


@public_router.get("/{token}.ics", response_class=Response)
async def hotel_room_calendar(
    token: str = Path(min_length=16, max_length=64, pattern=r"^[A-Za-z0-9_-]+$"),
    db: AsyncSession = Depends(get_db),
):
    """A room's taken nights for a booking site to read. Dates only: no names, no prices."""
    from app import desk_routing

    # The session picks its database per query, so routing first sends the read to the hotel's desk.
    await desk_routing.route_by(select(m.HotelChannelFeed.id).where(m.HotelChannelFeed.export_token == token))
    body = await channels_svc.export_calendar(db, token=token)
    return Response(
        content=body,
        media_type="text/calendar; charset=utf-8",
        headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex"},
    )


@router.post("/reservations/{reservation_id}/bill-to")
async def hotel_reservation_bill_to(
    reservation_id: UuidIdValue,
    payload: HotelBillToBody,
    claims=Depends(require_permission("hotel", "write")),
    db: AsyncSession = Depends(get_db),
):
    row, room, guest = await hotel_svc.set_bill_to(
        db, tenant_id=claims["tenant_id"], reservation_id=reservation_id, party_id=payload.party_id
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="hotel",
        action="reservation_bill_to_set",
        entity="hotel_reservation",
        entity_id=row.id,
        details={"reservation_number": row.reservation_number, "bill_to_party_id": payload.party_id},
    )
    await db.commit()
    message = "This stay is billed to the company" if payload.party_id else "This stay is billed to the guest"
    return _env(hotel_svc.serialize_reservation(row, room=room, guest=guest), message)


class HotelCompanyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: PartyNameValue
    phone: E164PhoneValue | None = None
    email: EmailStr | None = None


@router.get("/companies")
async def hotel_companies(
    claims=Depends(require_permission("hotel", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Company accounts a stay can be billed to (active customers)."""
    rows = (
        await db.execute(
            select(m.Party.id, m.Party.name)
            .where(m.Party.tenant_id == claims["tenant_id"], m.Party.kind == "customer", m.Party.status == "active")
            .order_by(m.Party.name)
            .limit(500)
        )
    ).all()
    return _env([{"id": r[0], "name": r[1]} for r in rows])


@router.post("/companies")
async def hotel_company_create(
    payload: HotelCompanyCreate,
    claims=Depends(require_permission("hotel", "write")),
    db: AsyncSession = Depends(get_db),
):
    name = payload.name.strip()
    clash = (
        await db.execute(
            select(m.Party.id).where(
                m.Party.tenant_id == claims["tenant_id"], m.Party.kind == "customer", m.Party.name == name
            )
        )
    ).scalars().first()
    if clash:
        return _env({"id": clash, "name": name}, "That company is already an account")
    party = m.Party(
        tenant_id=claims["tenant_id"],
        kind="customer",
        name=name,
        phone=payload.phone,
        email=str(payload.email) if payload.email else None,
    )
    db.add(party)
    await db.flush()
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="hotel",
        action="company_account_created",
        entity="party",
        entity_id=party.id,
        details={"name": name},
    )
    await db.commit()
    return _env({"id": party.id, "name": party.name}, "Company account added")


@router.get("/city-ledger")
async def hotel_city_ledger(
    claims=Depends(require_permission("hotel", "read")),
    db: AsyncSession = Depends(get_db),
):
    return _env(await hotel_svc.city_ledger(db, tenant_id=claims["tenant_id"]))


@router.get("/reservations/{reservation_id}/registration-card")
async def hotel_registration_card(
    reservation_id: UuidIdValue,
    claims=Depends(require_permission("hotel", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app.api import _hotel_print

    doc = await hotel_svc.registration_card_document(db, tenant_id=claims["tenant_id"], reservation_id=reservation_id)
    return _env(_hotel_print(doc))
