"""Hotel module — rooms, guests, reservations, check-in / check-out."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.honesty import money_json, optional_honest_narrative, require_honest_narrative

ROOM_STATUSES = frozenset({"available", "occupied", "maintenance", "out_of_order"})
RESERVATION_STATUSES = frozenset({"booked", "checked_in", "checked_out", "cancelled", "no_show"})
ROOM_TYPES = frozenset({"standard", "deluxe", "suite", "family", "other"})


def _as_date(value: date | datetime | str | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    return date.fromisoformat(text[:10])


def serialize_room(row: m.HotelRoom) -> dict:
    return {
        "id": row.id,
        "code": row.code,
        "name": row.name,
        "room_type": row.room_type,
        "floor": row.floor,
        "max_occupancy": row.max_occupancy,
        "rate_amount": money_json(row.rate_amount or 0),
        "status": row.status,
        "notes": row.notes,
        "is_active": bool(row.is_active),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def serialize_guest(row: m.HotelGuest) -> dict:
    return {
        "id": row.id,
        "full_name": row.full_name,
        "email": row.email,
        "phone": row.phone,
        "id_document": row.id_document,
        "notes": row.notes,
        "is_active": bool(row.is_active),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def serialize_reservation(
    row: m.HotelReservation,
    *,
    room: m.HotelRoom | None = None,
    guest: m.HotelGuest | None = None,
) -> dict:
    nights = max(0, (row.check_out_date - row.check_in_date).days)
    return {
        "id": row.id,
        "reservation_number": row.reservation_number,
        "room_id": row.room_id,
        "guest_id": row.guest_id,
        "room_code": room.code if room else None,
        "room_name": room.name if room else None,
        "guest_name": guest.full_name if guest else None,
        "guest_email": guest.email if guest else None,
        "check_in_date": row.check_in_date.isoformat(),
        "check_out_date": row.check_out_date.isoformat(),
        "nights": nights,
        "adults": row.adults,
        "children": row.children,
        "status": row.status,
        "nightly_rate": money_json(row.nightly_rate or 0),
        "estimated_total": money_json(Decimal(str(row.nightly_rate or 0)) * nights),
        "notes": row.notes,
        "checked_in_at": row.checked_in_at.isoformat() if row.checked_in_at else None,
        "checked_out_at": row.checked_out_at.isoformat() if row.checked_out_at else None,
        "cancelled_at": row.cancelled_at.isoformat() if row.cancelled_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "can_check_in": row.status == "booked",
        "can_check_out": row.status == "checked_in",
        "can_cancel": row.status == "booked",
    }


async def list_rooms(
    db: AsyncSession,
    *,
    tenant_id: str,
    is_active: bool | None = None,
    status: str | None = None,
) -> list[m.HotelRoom]:
    stmt = select(m.HotelRoom).where(m.HotelRoom.tenant_id == tenant_id).order_by(m.HotelRoom.code)
    if is_active is not None:
        stmt = stmt.where(m.HotelRoom.is_active.is_(bool(is_active)))
    if status:
        stmt = stmt.where(m.HotelRoom.status == status.strip().lower())
    return list((await db.execute(stmt)).scalars().all())


async def create_room(
    db: AsyncSession,
    *,
    tenant_id: str,
    code: str,
    name: str,
    room_type: str = "standard",
    floor: str | None = None,
    max_occupancy: int = 2,
    rate_amount: float = 0,
    status: str = "available",
    notes: str | None = None,
) -> m.HotelRoom:
    code_clean = require_honest_narrative(code, label="room code", max_length=40)
    name_clean = require_honest_narrative(name, label="room name", max_length=120)
    type_key = (room_type or "standard").strip().lower()
    if type_key not in ROOM_TYPES:
        raise HTTPException(status_code=422, detail=f"room_type must be one of: {', '.join(sorted(ROOM_TYPES))}")
    status_key = (status or "available").strip().lower()
    if status_key not in ROOM_STATUSES:
        raise HTTPException(status_code=422, detail=f"status must be one of: {', '.join(sorted(ROOM_STATUSES))}")
    exists = (
        await db.execute(
            select(m.HotelRoom).where(
                m.HotelRoom.tenant_id == tenant_id,
                m.HotelRoom.code == code_clean.upper(),
            )
        )
    ).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="Room code already exists")
    row = m.HotelRoom(
        tenant_id=tenant_id,
        code=code_clean.upper(),
        name=name_clean,
        room_type=type_key,
        floor=optional_honest_narrative(floor, label="floor", max_length=40),
        max_occupancy=max(1, int(max_occupancy or 1)),
        rate_amount=rate_amount or 0,
        status=status_key,
        notes=optional_honest_narrative(notes, label="notes", max_length=500),
        is_active=True,
    )
    db.add(row)
    await db.flush()
    return row


async def update_room(
    db: AsyncSession,
    *,
    tenant_id: str,
    room_id: str,
    name: str | None = None,
    room_type: str | None = None,
    floor: str | None = None,
    max_occupancy: int | None = None,
    rate_amount: float | None = None,
    status: str | None = None,
    notes: str | None = None,
    is_active: bool | None = None,
) -> m.HotelRoom:
    row = (
        await db.execute(
            select(m.HotelRoom).where(m.HotelRoom.id == room_id, m.HotelRoom.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Room not found")
    if name is not None:
        row.name = require_honest_narrative(name, label="room name", max_length=120)
    if room_type is not None:
        type_key = room_type.strip().lower()
        if type_key not in ROOM_TYPES:
            raise HTTPException(status_code=422, detail="Invalid room_type")
        row.room_type = type_key
    if floor is not None:
        row.floor = optional_honest_narrative(floor, label="floor", max_length=40)
    if max_occupancy is not None:
        row.max_occupancy = max(1, int(max_occupancy))
    if rate_amount is not None:
        row.rate_amount = rate_amount
    if status is not None:
        status_key = status.strip().lower()
        if status_key not in ROOM_STATUSES:
            raise HTTPException(status_code=422, detail="Invalid room status")
        row.status = status_key
    if notes is not None:
        row.notes = optional_honest_narrative(notes, label="notes", max_length=500)
    if is_active is not None:
        row.is_active = bool(is_active)
    row.updated_at = datetime.utcnow()
    await db.flush()
    return row


async def list_guests(
    db: AsyncSession,
    *,
    tenant_id: str,
    is_active: bool | None = None,
) -> list[m.HotelGuest]:
    stmt = (
        select(m.HotelGuest)
        .where(m.HotelGuest.tenant_id == tenant_id)
        .order_by(m.HotelGuest.full_name.asc())
    )
    if is_active is not None:
        stmt = stmt.where(m.HotelGuest.is_active.is_(bool(is_active)))
    return list((await db.execute(stmt)).scalars().all())


async def create_guest(
    db: AsyncSession,
    *,
    tenant_id: str,
    full_name: str,
    email: str | None = None,
    phone: str | None = None,
    id_document: str | None = None,
    notes: str | None = None,
) -> m.HotelGuest:
    name = require_honest_narrative(full_name, label="guest full name", max_length=150)
    email_clean = (email or "").strip().lower() or None
    if email_clean:
        taken = (
            await db.execute(
                select(m.HotelGuest).where(
                    m.HotelGuest.tenant_id == tenant_id,
                    m.HotelGuest.email == email_clean,
                )
            )
        ).scalar_one_or_none()
        if taken:
            raise HTTPException(status_code=409, detail="Guest email already exists")
    row = m.HotelGuest(
        tenant_id=tenant_id,
        full_name=name,
        email=email_clean,
        phone=(phone or "").strip() or None,
        id_document=optional_honest_narrative(id_document, label="id document", max_length=80),
        notes=optional_honest_narrative(notes, label="notes", max_length=500),
        is_active=True,
    )
    db.add(row)
    await db.flush()
    return row


async def _next_reservation_number(db: AsyncSession, tenant_id: str) -> str:
    year = datetime.utcnow().year
    prefix = f"HR-{year}-"
    count = (
        await db.execute(
            select(func.count())
            .select_from(m.HotelReservation)
            .where(
                m.HotelReservation.tenant_id == tenant_id,
                m.HotelReservation.reservation_number.like(f"{prefix}%"),
            )
        )
    ).scalar_one()
    return f"{prefix}{int(count or 0) + 1:04d}"


async def _get_room(db: AsyncSession, tenant_id: str, room_id: str) -> m.HotelRoom:
    row = (
        await db.execute(
            select(m.HotelRoom).where(m.HotelRoom.id == room_id, m.HotelRoom.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if not row or not row.is_active:
        raise HTTPException(status_code=404, detail="Room not found")
    return row


async def _get_guest(db: AsyncSession, tenant_id: str, guest_id: str) -> m.HotelGuest:
    row = (
        await db.execute(
            select(m.HotelGuest).where(m.HotelGuest.id == guest_id, m.HotelGuest.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if not row or not row.is_active:
        raise HTTPException(status_code=404, detail="Guest not found")
    return row


async def _assert_room_available(
    db: AsyncSession,
    *,
    tenant_id: str,
    room_id: str,
    check_in: date,
    check_out: date,
    exclude_id: str | None = None,
) -> None:
    if check_out <= check_in:
        raise HTTPException(status_code=400, detail="check_out_date must be after check_in_date")
    stmt = select(m.HotelReservation).where(
        m.HotelReservation.tenant_id == tenant_id,
        m.HotelReservation.room_id == room_id,
        m.HotelReservation.status.in_(("booked", "checked_in")),
        m.HotelReservation.check_in_date < check_out,
        m.HotelReservation.check_out_date > check_in,
    )
    if exclude_id:
        stmt = stmt.where(m.HotelReservation.id != exclude_id)
    clash = (await db.execute(stmt.limit(1))).scalar_one_or_none()
    if clash:
        raise HTTPException(
            status_code=409,
            detail=f"Room is already reserved ({clash.reservation_number}) for overlapping dates",
        )


async def list_reservations(
    db: AsyncSession,
    *,
    tenant_id: str,
    status: str | None = None,
) -> list[tuple[m.HotelReservation, m.HotelRoom | None, m.HotelGuest | None]]:
    stmt = (
        select(m.HotelReservation, m.HotelRoom, m.HotelGuest)
        .outerjoin(m.HotelRoom, m.HotelRoom.id == m.HotelReservation.room_id)
        .outerjoin(m.HotelGuest, m.HotelGuest.id == m.HotelReservation.guest_id)
        .where(m.HotelReservation.tenant_id == tenant_id)
        .order_by(m.HotelReservation.check_in_date.desc(), m.HotelReservation.created_at.desc())
    )
    if status:
        stmt = stmt.where(m.HotelReservation.status == status.strip().lower())
    rows = (await db.execute(stmt)).all()
    return [(r, room, guest) for r, room, guest in rows]


async def create_reservation(
    db: AsyncSession,
    *,
    tenant_id: str,
    room_id: str,
    guest_id: str,
    check_in_date: date,
    check_out_date: date,
    adults: int = 1,
    children: int = 0,
    nightly_rate: float | None = None,
    notes: str | None = None,
    created_by: str | None = None,
) -> tuple[m.HotelReservation, m.HotelRoom, m.HotelGuest]:
    room = await _get_room(db, tenant_id, room_id)
    guest = await _get_guest(db, tenant_id, guest_id)
    check_in = _as_date(check_in_date)
    check_out = _as_date(check_out_date)
    if not check_in or not check_out:
        raise HTTPException(status_code=422, detail="check_in_date and check_out_date are required")
    await _assert_room_available(
        db,
        tenant_id=tenant_id,
        room_id=room.id,
        check_in=check_in,
        check_out=check_out,
    )
    if room.status == "maintenance" or room.status == "out_of_order":
        raise HTTPException(status_code=409, detail=f"Room is {room.status.replace('_', ' ')}")
    rate = nightly_rate if nightly_rate is not None else float(room.rate_amount or 0)
    row = m.HotelReservation(
        tenant_id=tenant_id,
        reservation_number=await _next_reservation_number(db, tenant_id),
        room_id=room.id,
        guest_id=guest.id,
        check_in_date=check_in,
        check_out_date=check_out,
        adults=max(1, int(adults or 1)),
        children=max(0, int(children or 0)),
        status="booked",
        nightly_rate=rate,
        notes=optional_honest_narrative(notes, label="notes", max_length=500),
        created_by=created_by,
    )
    db.add(row)
    await db.flush()
    return row, room, guest


async def _get_reservation(
    db: AsyncSession, tenant_id: str, reservation_id: str
) -> tuple[m.HotelReservation, m.HotelRoom, m.HotelGuest]:
    row = (
        await db.execute(
            select(m.HotelReservation).where(
                m.HotelReservation.id == reservation_id,
                m.HotelReservation.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Reservation not found")
    room = await _get_room(db, tenant_id, row.room_id)
    guest = await _get_guest(db, tenant_id, row.guest_id)
    return row, room, guest


async def check_in(
    db: AsyncSession, *, tenant_id: str, reservation_id: str
) -> tuple[m.HotelReservation, m.HotelRoom, m.HotelGuest]:
    row, room, guest = await _get_reservation(db, tenant_id, reservation_id)
    if row.status != "booked":
        raise HTTPException(status_code=400, detail=f"Cannot check in a reservation with status {row.status}")
    row.status = "checked_in"
    row.checked_in_at = datetime.utcnow()
    room.status = "occupied"
    room.updated_at = datetime.utcnow()
    row.updated_at = datetime.utcnow()
    await db.flush()
    return row, room, guest


async def check_out(
    db: AsyncSession, *, tenant_id: str, reservation_id: str
) -> tuple[m.HotelReservation, m.HotelRoom, m.HotelGuest]:
    row, room, guest = await _get_reservation(db, tenant_id, reservation_id)
    if row.status != "checked_in":
        raise HTTPException(status_code=400, detail=f"Cannot check out a reservation with status {row.status}")
    row.status = "checked_out"
    row.checked_out_at = datetime.utcnow()
    room.status = "available"
    room.updated_at = datetime.utcnow()
    row.updated_at = datetime.utcnow()
    await db.flush()
    return row, room, guest


async def cancel_reservation(
    db: AsyncSession, *, tenant_id: str, reservation_id: str
) -> tuple[m.HotelReservation, m.HotelRoom, m.HotelGuest]:
    row, room, guest = await _get_reservation(db, tenant_id, reservation_id)
    if row.status != "booked":
        raise HTTPException(status_code=400, detail=f"Cannot cancel a reservation with status {row.status}")
    row.status = "cancelled"
    row.cancelled_at = datetime.utcnow()
    row.updated_at = datetime.utcnow()
    await db.flush()
    return row, room, guest


async def summary(db: AsyncSession, *, tenant_id: str) -> dict:
    rooms = await list_rooms(db, tenant_id=tenant_id, is_active=True)
    reservations = await list_reservations(db, tenant_id=tenant_id)
    booked = sum(1 for r, _, _ in reservations if r.status == "booked")
    in_house = sum(1 for r, _, _ in reservations if r.status == "checked_in")
    return {
        "rooms_total": len(rooms),
        "rooms_available": sum(1 for r in rooms if r.status == "available"),
        "rooms_occupied": sum(1 for r in rooms if r.status == "occupied"),
        "rooms_maintenance": sum(1 for r in rooms if r.status in {"maintenance", "out_of_order"}),
        "reservations_booked": booked,
        "reservations_in_house": in_house,
        "guests_total": len(await list_guests(db, tenant_id=tenant_id, is_active=True)),
    }
