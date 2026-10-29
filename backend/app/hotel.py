"""Hotel module — rooms, guests, reservations, folio, housekeeping, maintenance."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import AsyncIterator

from fastapi import HTTPException
from sqlalchemy import func, inspect as sa_inspect, or_, select
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import undefer

from app import models as m
from app.honesty import money_json, optional_honest_narrative, require_honest_narrative

import logging

logger = logging.getLogger("ribdigi.hotel")

HOTEL_FEATURE_UNAVAILABLE = (
    "This hotel extra is not ready on the server yet. Rooms and reservations still work."
)


def _raise_schema_behind(exc: BaseException) -> None:
    raise HTTPException(status_code=400, detail=HOTEL_FEATURE_UNAVAILABLE) from exc


def _opt(row, name: str, default=None):
    """Read a mapped column if already loaded; skip extras that need a later migration."""
    if row is None:
        return default
    try:
        if name in sa_inspect(row).unloaded:
            return default
        return getattr(row, name, default)
    except Exception:
        return default


async def _optional_all(db: AsyncSession, stmt) -> list:
    """Return rows, or [] if a newer hotel column/table is not on this database yet."""
    try:
        async with db.begin_nested():
            return list((await db.execute(stmt)).all())
    except (ProgrammingError, OperationalError):
        logger.warning("hotel optional query skipped", exc_info=True)
        return []


async def _optional_scalars(db: AsyncSession, stmt) -> list:
    try:
        async with db.begin_nested():
            return list((await db.execute(stmt)).scalars().all())
    except (ProgrammingError, OperationalError):
        logger.warning("hotel optional query skipped", exc_info=True)
        return []


async def _scalars_or_schema_behind(db: AsyncSession, stmt) -> list:
    """Hotel extras (services, later folio columns) stay off the room and reservation tables."""
    try:
        async with db.begin_nested():
            return list((await db.execute(stmt)).scalars().all())
    except (ProgrammingError, OperationalError) as exc:
        _raise_schema_behind(exc)
        return []


async def _one_or_schema_behind(db: AsyncSession, stmt):
    try:
        async with db.begin_nested():
            return (await db.execute(stmt)).scalar_one_or_none()
    except (ProgrammingError, OperationalError) as exc:
        _raise_schema_behind(exc)


async def _flush_extra(db: AsyncSession) -> None:
    try:
        async with db.begin_nested():
            await db.flush()
    except (ProgrammingError, OperationalError) as exc:
        _raise_schema_behind(exc)

# In-process serialization for same-room bookings (SQLite tests + single-worker).
# Postgres multi-worker still relies on SELECT … FOR UPDATE on the room row.
_room_booking_locks: dict[str, asyncio.Lock] = {}
_room_booking_locks_guard = asyncio.Lock()


async def _booking_lock_for(tenant_id: str, room_id: str) -> asyncio.Lock:
    key = f"{tenant_id}:{room_id}"
    async with _room_booking_locks_guard:
        lock = _room_booking_locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            _room_booking_locks[key] = lock
        return lock


@asynccontextmanager
async def room_booking_lock(tenant_id: str, room_id: str) -> AsyncIterator[None]:
    """Hold through flush+commit so concurrent overlapping bookings cannot both succeed."""
    lock = await _booking_lock_for(tenant_id, room_id)
    async with lock:
        yield

ROOM_STATUSES = frozenset(
    {
        "available",
        "reserved",
        "occupied",
        "dirty",
        "clean",
        "inspected",
        "maintenance",
        "out_of_order",
        "blocked",
    }
)
HOUSEKEEPING_STATUSES = frozenset({"dirty", "clean", "inspected"})
RESERVATION_STATUSES = frozenset(
    {"tentative", "booked", "checked_in", "checked_out", "cancelled", "no_show", "waitlisted"}
)
ROOM_TYPES = frozenset({"standard", "deluxe", "executive", "suite", "family", "other"})
ROOM_AMENITIES = frozenset(
    {"wifi", "air_conditioning", "television", "minibar", "safe", "balcony", "breakfast", "accessible"}
)
BOOKING_SOURCES = frozenset({"direct", "walk_in", "ota", "corporate", "phone", "staff", "group", "online", "other"})
ACTIVE_BOOKING_STATUSES = ("tentative", "booked", "checked_in")
CHARGE_TYPES = frozenset(
    {
        "room",
        "restaurant",
        "bar",
        "laundry",
        "transport",
        "spa",
        "service",
        "damage",
        "extra",
        "tax",
        "discount",
        "adjustment",
    }
)
PAYMENT_METHODS = frozenset({"cash", "momo", "card", "bank", "credit", "other"})
HK_TASK_STATUSES = frozenset({"pending", "in_progress", "completed", "cancelled"})
HK_PRIORITIES = frozenset({"low", "normal", "high", "urgent"})
MAINT_STATUSES = frozenset({"open", "in_progress", "completed", "cancelled"})
BLOCKING_ROOM_STATUSES = frozenset({"maintenance", "out_of_order", "blocked", "occupied", "dirty"})


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


def _operational_checkout(row) -> date | None:
    """Last night a stay still holds on the desk.

    A guest who has already left releases the room from the departure date.
    Hotel reports keep the planned checkout so billed nights stay in ADR.
    """
    planned = _as_date(getattr(row, "check_out_date", None))
    if getattr(row, "status", None) != "checked_out":
        return planned
    left = _as_date(getattr(row, "checked_out_at", None))
    if left and planned and left < planned:
        return left
    return planned


def _departure_day(row) -> date | None:
    """The day this stay leaves the front desk.

    A guest still in house leaves on the planned checkout.
    A guest who already left is counted on that day.
    A missing leave timestamp keeps the planned checkout.
    """
    status = getattr(row, "status", None)
    planned = _as_date(getattr(row, "check_out_date", None))
    if status == "checked_in":
        return planned
    if status != "checked_out":
        return None
    return _as_date(getattr(row, "checked_out_at", None)) or planned


def _room_description(value: str | None) -> str | None:
    if value is None:
        return None
    if not str(value).strip():
        raise HTTPException(status_code=422, detail="Room description cannot be blank")
    return optional_honest_narrative(value, label="description", max_length=2000)


def _amenity_flags(value) -> dict:
    if value is None:
        return {}
    data = value.model_dump() if hasattr(value, "model_dump") else value
    if not isinstance(data, dict):
        raise HTTPException(status_code=422, detail="amenities must be an object")
    unknown = [str(key) for key in data if str(key) not in ROOM_AMENITIES]
    if unknown:
        raise HTTPException(status_code=422, detail="Unknown room amenity")
    flags: dict[str, bool] = {}
    for key in ROOM_AMENITIES:
        raw = data.get(key, False)
        if not isinstance(raw, bool):
            raise HTTPException(status_code=422, detail="Room amenity must be true or false")
        if raw:
            flags[key] = True
    return flags


def serialize_room(row: m.HotelRoom) -> dict:
    return {
        "id": row.id,
        "code": row.code,
        "name": row.name,
        "room_type": row.room_type,
        "floor": row.floor,
        "bed_type": getattr(row, "bed_type", None),
        "max_occupancy": row.max_occupancy,
        "rate_amount": money_json(row.rate_amount or 0),
        "weekend_rate": money_json(row.weekend_rate) if row.weekend_rate is not None else None,
        "extra_person_charge": money_json(getattr(row, "extra_person_charge", 0) or 0),
        "amenities": getattr(row, "amenities", None) or {},
        "description": getattr(row, "description", None),
        "status": row.status,
        "housekeeping_status": getattr(row, "housekeeping_status", None) or "clean",
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
        "address": getattr(row, "address", None),
        "nationality": getattr(row, "nationality", None),
        "id_type": getattr(row, "id_type", None),
        "id_document": row.id_document,
        "emergency_contact": getattr(row, "emergency_contact", None),
        "company_name": getattr(row, "company_name", None),
        "preferences": getattr(row, "preferences", None),
        "notes": row.notes,
        "is_active": bool(row.is_active),
        "consent_marketing": bool(_opt(row, "consent_marketing", False)),
        "travel_agent": _opt(row, "travel_agent"),
        "loyalty_tier": _opt(row, "loyalty_tier"),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def arrival_clock(check_in_time: str | None) -> time:
    raw = (check_in_time or "14:00").strip()
    parts = raw.split(":")
    try:
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
    except ValueError:
        return time(14, 0)
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        return time(14, 0)
    return time(hour, minute)


def cancellation_deadline(check_in: date, hours: int, check_in_time: str | None = None) -> datetime:
    """Free-cancel cutoff is the property check-in clock, minus the stored hours."""
    return datetime.combine(check_in, arrival_clock(check_in_time)) - timedelta(hours=max(0, int(hours)))


def inside_cancellation_window(
    check_in: date,
    hours: int,
    *,
    now: datetime | None = None,
    check_in_time: str | None = None,
) -> bool:
    return (now or datetime.utcnow()) >= cancellation_deadline(check_in, hours, check_in_time)


async def stored_cancellation_hours(db: AsyncSession, *, tenant_id: str) -> int:
    rows = await _optional_scalars(
        db,
        select(m.HotelSettings).where(m.HotelSettings.tenant_id == tenant_id),
    )
    if not rows:
        return 24
    return max(0, int(getattr(rows[0], "cancellation_hours", 24) or 24))


async def stored_check_in_time(db: AsyncSession, *, tenant_id: str) -> str:
    rows = await _optional_scalars(
        db,
        select(m.HotelSettings).where(m.HotelSettings.tenant_id == tenant_id),
    )
    if not rows:
        return "14:00"
    return str(getattr(rows[0], "check_in_time", None) or "14:00")


def serialize_reservation(
    row: m.HotelReservation,
    *,
    room: m.HotelRoom | None = None,
    guest: m.HotelGuest | None = None,
    folio_id: str | None = None,
    folio_balance: float | None = None,
    cancellation_hours: int | None = None,
    check_in_time: str | None = None,
    group_name: str | None = None,
) -> dict:
    nights = max(0, (row.check_out_date - row.check_in_date).days)
    hours = 24 if cancellation_hours is None else max(0, int(cancellation_hours))
    cancellable = row.status in {"tentative", "booked", "waitlisted"}
    clock = check_in_time or "14:00"
    deadline = cancellation_deadline(row.check_in_date, hours, clock)
    return {
        "id": row.id,
        "reservation_number": row.reservation_number,
        "room_id": row.room_id,
        "guest_id": row.guest_id,
        "room_code": room.code if room else None,
        "room_name": room.name if room else None,
        "guest_name": guest.full_name if guest else None,
        "guest_email": guest.email if guest else None,
        "guest_phone": (guest.phone or "").strip() or None if guest else None,
        "check_in_date": row.check_in_date.isoformat(),
        "check_out_date": row.check_out_date.isoformat(),
        "nights": nights,
        "adults": row.adults,
        "children": row.children,
        "status": row.status,
        "booking_source": getattr(row, "booking_source", None) or "direct",
        "special_requests": getattr(row, "special_requests", None),
        "nightly_rate": money_json(row.nightly_rate or 0),
        "deposit_amount": money_json(getattr(row, "deposit_amount", 0) or 0),
        "deposit_method": getattr(row, "deposit_method", None),
        "group_id": _opt(row, "group_id"),
        "group_name": group_name,
        "estimated_total": money_json(Decimal(str(row.nightly_rate or 0)) * nights),
        "notes": row.notes,
        "folio_id": folio_id,
        "folio_balance": money_json(folio_balance) if folio_balance is not None else None,
        "checked_in_at": row.checked_in_at.isoformat() if row.checked_in_at else None,
        "checked_out_at": row.checked_out_at.isoformat() if row.checked_out_at else None,
        "cancelled_at": row.cancelled_at.isoformat() if row.cancelled_at else None,
        "no_show_at": row.no_show_at.isoformat() if getattr(row, "no_show_at", None) else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "rate_plan_id": _opt(row, "rate_plan_id"),
        "discount_percent": money_json(_opt(row, "discount_percent", 0) or 0),
        "can_check_in": row.status == "booked",
        "can_confirm": row.status in {"tentative", "waitlisted"},
        "can_check_out": row.status == "checked_in",
        "can_cancel": cancellable,
        "cancellation_hours": hours,
        "check_in_time": clock,
        "free_cancel_until": deadline.isoformat(),
        "inside_cancellation_window": cancellable and datetime.utcnow() >= deadline,
        "can_no_show": row.status == "booked" and _as_date(row.check_in_date) is not None and _as_date(row.check_in_date) <= date.today(),
        "can_extend": row.status in {"tentative", "booked", "checked_in"},
        "can_move": row.status in {"tentative", "booked", "checked_in"},
        "can_duplicate": True,
    }


def serialize_charge(row: m.HotelFolioCharge) -> dict:
    return {
        "id": row.id,
        "folio_id": row.folio_id,
        "charge_type": row.charge_type,
        "description": row.description,
        "quantity": money_json(row.quantity or 0),
        "unit_amount": money_json(row.unit_amount or 0),
        "tax_amount": money_json(row.tax_amount or 0),
        "discount_amount": money_json(row.discount_amount or 0),
        "line_total": money_json(row.line_total or 0),
        "is_void": bool(row.is_void),
        "void_reason": row.void_reason,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def serialize_payment(row: m.HotelFolioPayment) -> dict:
    return {
        "id": row.id,
        "folio_id": row.folio_id,
        "method": row.method,
        "amount": money_json(row.amount or 0),
        "reference": row.reference,
        "notes": row.notes,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def serialize_folio(
    row: m.HotelFolio,
    *,
    charges: list[m.HotelFolioCharge] | None = None,
    payments: list[m.HotelFolioPayment] | None = None,
) -> dict:
    charge_rows = charges or []
    payment_rows = payments or []
    charge_total = money_json(
        sum(money_json(c.line_total or 0) for c in charge_rows if not c.is_void)
    )
    payment_total = money_json(sum(money_json(p.amount or 0) for p in payment_rows))
    return {
        "id": row.id,
        "reservation_id": row.reservation_id,
        "guest_id": row.guest_id,
        "folio_number": row.folio_number,
        "status": row.status,
        "sales_invoice_id": getattr(row, "sales_invoice_id", None),
        "notes": row.notes,
        "charges_total": money_json(charge_total),
        "payments_total": money_json(payment_total),
        "balance": money_json(charge_total - payment_total),
        "charges": [serialize_charge(c) for c in charge_rows],
        "payments": [serialize_payment(p) for p in payment_rows],
        "opened_at": row.opened_at.isoformat() if row.opened_at else None,
        "closed_at": row.closed_at.isoformat() if row.closed_at else None,
    }


def folio_stay_fields(
    reservation: m.HotelReservation | None,
    guest: m.HotelGuest | None,
    room: m.HotelRoom | None,
) -> dict:
    left = reservation.checked_out_at if reservation and reservation.checked_out_at else None
    return {
        "guest_name": guest.full_name if guest else None,
        "reservation_number": reservation.reservation_number if reservation else None,
        "reservation_status": reservation.status if reservation else None,
        "room_code": room.code if room else None,
        "check_in_date": reservation.check_in_date.isoformat() if reservation and reservation.check_in_date else None,
        "check_out_date": reservation.check_out_date.isoformat() if reservation and reservation.check_out_date else None,
        "checked_out_at": left.isoformat() if left else None,
    }


async def present_folio(
    db: AsyncSession,
    *,
    tenant_id: str,
    folio: m.HotelFolio,
    charges: list[m.HotelFolioCharge] | None = None,
    payments: list[m.HotelFolioPayment] | None = None,
) -> dict:
    payload = serialize_folio(folio, charges=charges, payments=payments)
    reservation = None
    if folio.reservation_id:
        reservation = (
            await db.execute(
                select(m.HotelReservation).where(
                    m.HotelReservation.id == folio.reservation_id,
                    m.HotelReservation.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
    room = None
    if reservation and reservation.room_id:
        room = (
            await db.execute(
                select(m.HotelRoom).where(
                    m.HotelRoom.id == reservation.room_id,
                    m.HotelRoom.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
    guest_id = folio.guest_id or (reservation.guest_id if reservation else None)
    guest = None
    if guest_id:
        guest = (
            await db.execute(
                select(m.HotelGuest).where(
                    m.HotelGuest.id == guest_id,
                    m.HotelGuest.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
    payload.update(folio_stay_fields(reservation, guest, room))
    return payload


async def update_folio_notes(
    db: AsyncSession,
    *,
    tenant_id: str,
    folio_id: str,
    notes: str | None = None,
) -> m.HotelFolio:
    folio = (
        await db.execute(
            select(m.HotelFolio).where(m.HotelFolio.id == folio_id, m.HotelFolio.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if not folio:
        raise HTTPException(status_code=404, detail="Folio not found")
    if notes is not None:
        if not str(notes).strip():
            raise HTTPException(status_code=422, detail="Folio notes cannot be blank")
        folio.notes = optional_honest_narrative(notes, label="notes", max_length=1000)
        folio.updated_at = datetime.utcnow()
        await db.flush()
    return folio


def serialize_hk_task(row: m.HotelHousekeepingTask, *, room_code: str | None = None) -> dict:
    due = _opt(row, "due_at")
    return {
        "id": row.id,
        "room_id": row.room_id,
        "room_code": room_code,
        "task_type": row.task_type,
        "priority": row.priority,
        "status": row.status,
        "assigned_to": row.assigned_to,
        "notes": row.notes,
        "due_at": due.isoformat() if due else None,
        "overdue": bool(due and row.status not in {"completed", "cancelled"} and due < datetime.utcnow()),
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def serialize_maint(row: m.HotelMaintenanceTicket, *, room_code: str | None = None) -> dict:
    starts = _opt(row, "ooo_starts_on")
    ends = _opt(row, "ooo_ends_on")
    return {
        "id": row.id,
        "room_id": row.room_id,
        "room_code": room_code,
        "title": row.title,
        "priority": row.priority,
        "status": row.status,
        "block_room": bool(row.block_room),
        "ooo_starts_on": starts.isoformat() if starts else None,
        "ooo_ends_on": ends.isoformat() if ends else None,
        "assigned_to": row.assigned_to,
        "notes": row.notes,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


async def list_rooms(
    db: AsyncSession,
    *,
    tenant_id: str,
    is_active: bool | None = None,
    status: str | None = None,
    housekeeping_status: str | None = None,
) -> list[m.HotelRoom]:
    stmt = select(m.HotelRoom).where(m.HotelRoom.tenant_id == tenant_id).order_by(m.HotelRoom.code)
    if is_active is not None:
        stmt = stmt.where(m.HotelRoom.is_active.is_(bool(is_active)))
    if status:
        stmt = stmt.where(m.HotelRoom.status == status.strip().lower())
    if housekeeping_status:
        stmt = stmt.where(m.HotelRoom.housekeeping_status == housekeeping_status.strip().lower())
    return list((await db.execute(stmt)).scalars().all())


async def create_room(
    db: AsyncSession,
    *,
    tenant_id: str,
    code: str,
    name: str,
    room_type: str = "standard",
    floor: str | None = None,
    bed_type: str | None = None,
    max_occupancy: int = 2,
    rate_amount: float = 0,
    weekend_rate: float | None = None,
    extra_person_charge: float = 0,
    amenities: dict | None = None,
    description: str | None = None,
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
    if notes is not None and not str(notes).strip():
        raise HTTPException(status_code=422, detail="Room notes cannot be blank")
    row = m.HotelRoom(
        tenant_id=tenant_id,
        code=code_clean.upper(),
        name=name_clean,
        room_type=type_key,
        floor=optional_honest_narrative(floor, label="floor", max_length=40),
        bed_type=optional_honest_narrative(bed_type, label="bed type", max_length=40),
        max_occupancy=max(1, int(max_occupancy or 1)),
        rate_amount=money_json(rate_amount or 0),
        weekend_rate=money_json(weekend_rate) if weekend_rate is not None else None,
        extra_person_charge=money_json(extra_person_charge or 0),
        amenities=_amenity_flags(amenities),
        description=_room_description(description),
        status=status_key,
        housekeeping_status="clean",
        notes=optional_honest_narrative(notes, label="notes", max_length=500),
        is_active=True,
    )
    db.add(row)
    await db.flush()
    return row


_READY_ROOM_STATUSES = frozenset({"available", "clean", "inspected", "reserved"})


async def _ready_block_reason(db: AsyncSession, *, tenant_id: str, room_id: str) -> str | None:
    """Why a room must not be marked sellable right now."""
    today = date.today()
    tickets = await _optional_scalars(
        db,
        select(m.HotelMaintenanceTicket).where(
            m.HotelMaintenanceTicket.tenant_id == tenant_id,
            m.HotelMaintenanceTicket.room_id == room_id,
            m.HotelMaintenanceTicket.block_room.is_(True),
            m.HotelMaintenanceTicket.status.in_(("open", "in_progress")),
        ),
    )
    for ticket in tickets:
        start = _as_date(getattr(ticket, "ooo_starts_on", None)) or date.min
        end = _as_date(getattr(ticket, "ooo_ends_on", None)) or date.max
        if start <= today <= end:
            return "Room stays out of service until maintenance is finished"
    stay = (
        await db.execute(
            select(m.HotelReservation.id).where(
                m.HotelReservation.tenant_id == tenant_id,
                m.HotelReservation.room_id == room_id,
                m.HotelReservation.status == "checked_in",
            ).limit(1)
        )
    ).first()
    if stay:
        return "Room is occupied"
    return None


async def update_room(
    db: AsyncSession,
    *,
    tenant_id: str,
    room_id: str,
    name: str | None = None,
    room_type: str | None = None,
    floor: str | None = None,
    bed_type: str | None = None,
    max_occupancy: int | None = None,
    rate_amount: float | None = None,
    weekend_rate: float | None = None,
    extra_person_charge: float | None = None,
    amenities: dict | None = None,
    description: str | None = None,
    status: str | None = None,
    housekeeping_status: str | None = None,
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
    if bed_type is not None:
        row.bed_type = optional_honest_narrative(bed_type, label="bed type", max_length=40)
    if max_occupancy is not None:
        row.max_occupancy = max(1, int(max_occupancy))
    if rate_amount is not None:
        row.rate_amount = money_json(rate_amount)
    if weekend_rate is not None:
        row.weekend_rate = money_json(weekend_rate)
    if extra_person_charge is not None:
        row.extra_person_charge = money_json(extra_person_charge)
    if amenities is not None:
        row.amenities = _amenity_flags(amenities)
    if description is not None:
        row.description = _room_description(description)
    if status is not None:
        status_key = status.strip().lower()
        if status_key not in ROOM_STATUSES:
            raise HTTPException(status_code=422, detail="Invalid room status")
        if status_key in _READY_ROOM_STATUSES:
            reason = await _ready_block_reason(db, tenant_id=tenant_id, room_id=row.id)
            if reason:
                raise HTTPException(status_code=409, detail=reason)
        row.status = status_key
    if housekeeping_status is not None:
        hk = housekeeping_status.strip().lower()
        if hk not in HOUSEKEEPING_STATUSES:
            raise HTTPException(status_code=422, detail="Invalid housekeeping_status")
        row.housekeeping_status = hk
    if notes is not None:
        if not str(notes).strip():
            raise HTTPException(status_code=422, detail="Room notes cannot be blank")
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
    q: str | None = None,
) -> list[m.HotelGuest]:
    stmt = (
        select(m.HotelGuest)
        .where(m.HotelGuest.tenant_id == tenant_id)
        .order_by(m.HotelGuest.full_name.asc())
    )
    if is_active is not None:
        stmt = stmt.where(m.HotelGuest.is_active.is_(bool(is_active)))
    if q and q.strip():
        term = f"%{q.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(m.HotelGuest.full_name).like(term),
                func.lower(func.coalesce(m.HotelGuest.email, "")).like(term),
                func.lower(func.coalesce(m.HotelGuest.phone, "")).like(term),
                func.lower(func.coalesce(m.HotelGuest.id_document, "")).like(term),
            )
        )
    return list((await db.execute(stmt)).scalars().all())


async def create_guest(
    db: AsyncSession,
    *,
    tenant_id: str,
    full_name: str,
    email: str | None = None,
    phone: str | None = None,
    address: str | None = None,
    nationality: str | None = None,
    id_type: str | None = None,
    id_document: str | None = None,
    emergency_contact: str | None = None,
    company_name: str | None = None,
    preferences: str | None = None,
    notes: str | None = None,
    consent_marketing: bool = False,
    travel_agent: str | None = None,
    loyalty_tier: str | None = None,
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
    # Duplicate detection by phone + name
    phone_clean = (phone or "").strip() or None
    if phone_clean:
        dup = (
            await db.execute(
                select(m.HotelGuest).where(
                    m.HotelGuest.tenant_id == tenant_id,
                    m.HotelGuest.phone == phone_clean,
                    func.lower(m.HotelGuest.full_name) == name.lower(),
                    m.HotelGuest.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()
        if dup:
            raise HTTPException(
                status_code=409,
                detail=f"Possible duplicate guest already exists ({dup.full_name})",
            )
    row = m.HotelGuest(
        tenant_id=tenant_id,
        full_name=name,
        email=email_clean,
        phone=phone_clean,
        address=optional_honest_narrative(address, label="address", max_length=500),
        nationality=optional_honest_narrative(nationality, label="nationality", max_length=80),
        id_type=optional_honest_narrative(id_type, label="id type", max_length=40),
        id_document=optional_honest_narrative(id_document, label="id document", max_length=80),
        emergency_contact=optional_honest_narrative(
            emergency_contact, label="emergency contact", max_length=200
        ),
        company_name=optional_honest_narrative(company_name, label="company name", max_length=150),
        preferences=optional_honest_narrative(preferences, label="preferences", max_length=1000),
        notes=optional_honest_narrative(notes, label="notes", max_length=500),
        is_active=True,
    )
    if consent_marketing:
        row.consent_marketing = True
    if travel_agent:
        row.travel_agent = optional_honest_narrative(travel_agent, label="travel agent", max_length=150)
    if loyalty_tier:
        row.loyalty_tier = optional_honest_narrative(loyalty_tier, label="loyalty tier", max_length=40)
    db.add(row)
    try:
        await db.flush()
    except (ProgrammingError, OperationalError) as exc:
        _raise_schema_behind(exc)
    return row


async def update_guest(
    db: AsyncSession,
    *,
    tenant_id: str,
    guest_id: str,
    full_name: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    address: str | None = None,
    nationality: str | None = None,
    id_type: str | None = None,
    id_document: str | None = None,
    emergency_contact: str | None = None,
    company_name: str | None = None,
    preferences: str | None = None,
    notes: str | None = None,
    is_active: bool | None = None,
    travel_agent: str | None = None,
    loyalty_tier: str | None = None,
) -> m.HotelGuest:
    row = await _get_guest(db, tenant_id, guest_id, require_active=False)
    if full_name is not None:
        row.full_name = require_honest_narrative(full_name, label="guest full name", max_length=150)
    if email is not None:
        email_clean = email.strip().lower() or None
        if email_clean:
            taken = (
                await db.execute(
                    select(m.HotelGuest).where(
                        m.HotelGuest.tenant_id == tenant_id,
                        m.HotelGuest.email == email_clean,
                        m.HotelGuest.id != guest_id,
                    )
                )
            ).scalar_one_or_none()
            if taken:
                raise HTTPException(status_code=409, detail="Guest email already exists")
        row.email = email_clean
    if phone is not None:
        row.phone = phone.strip() or None
    if address is not None:
        row.address = optional_honest_narrative(address, label="address", max_length=500)
    if nationality is not None:
        row.nationality = optional_honest_narrative(nationality, label="nationality", max_length=80)
    if id_type is not None:
        row.id_type = optional_honest_narrative(id_type, label="id type", max_length=40)
    if id_document is not None:
        row.id_document = optional_honest_narrative(id_document, label="id document", max_length=80)
    if emergency_contact is not None:
        row.emergency_contact = optional_honest_narrative(
            emergency_contact, label="emergency contact", max_length=200
        )
    if company_name is not None:
        row.company_name = optional_honest_narrative(company_name, label="company name", max_length=150)
    if preferences is not None:
        row.preferences = optional_honest_narrative(preferences, label="preferences", max_length=1000)
    if notes is not None:
        row.notes = optional_honest_narrative(notes, label="notes", max_length=500)
    if travel_agent is not None:
        row.travel_agent = optional_honest_narrative(travel_agent, label="travel agent", max_length=150)
    if loyalty_tier is not None:
        row.loyalty_tier = optional_honest_narrative(loyalty_tier, label="loyalty tier", max_length=40)
    if is_active is not None:
        row.is_active = bool(is_active)
    row.updated_at = datetime.utcnow()
    await db.flush()
    return row


async def merge_guests(
    db: AsyncSession,
    *,
    tenant_id: str,
    keep_guest_id: str,
    source_guest_id: str,
) -> m.HotelGuest:
    if keep_guest_id == source_guest_id:
        raise HTTPException(status_code=400, detail="Cannot merge a guest into itself")
    keep = await _get_guest(db, tenant_id, keep_guest_id, require_active=False)
    source = await _get_guest(db, tenant_id, source_guest_id, require_active=False)
    res_rows = (
        await db.execute(
            select(m.HotelReservation).where(
                m.HotelReservation.tenant_id == tenant_id,
                m.HotelReservation.guest_id == source.id,
            )
        )
    ).scalars().all()
    for row in res_rows:
        row.guest_id = keep.id
        row.updated_at = datetime.utcnow()
    folios = (
        await db.execute(
            select(m.HotelFolio).where(
                m.HotelFolio.tenant_id == tenant_id, m.HotelFolio.guest_id == source.id
            )
        )
    ).scalars().all()
    for folio in folios:
        folio.guest_id = keep.id
        folio.updated_at = datetime.utcnow()
    source.is_active = False
    note = f"Merged into {keep.full_name} ({keep.id})"
    source.notes = ((source.notes or "") + "\n" + note).strip()[:500]
    source.updated_at = datetime.utcnow()
    await db.flush()
    return keep


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


async def _next_folio_number(db: AsyncSession, tenant_id: str) -> str:
    year = datetime.utcnow().year
    prefix = f"HF-{year}-"
    count = (
        await db.execute(
            select(func.count())
            .select_from(m.HotelFolio)
            .where(
                m.HotelFolio.tenant_id == tenant_id,
                m.HotelFolio.folio_number.like(f"{prefix}%"),
            )
        )
    ).scalar_one()
    return f"{prefix}{int(count or 0) + 1:04d}"


async def _get_room(
    db: AsyncSession, tenant_id: str, room_id: str, *, for_update: bool = False
) -> m.HotelRoom:
    stmt = select(m.HotelRoom).where(m.HotelRoom.id == room_id, m.HotelRoom.tenant_id == tenant_id)
    if for_update:
        stmt = stmt.with_for_update()
    row = (await db.execute(stmt)).scalar_one_or_none()
    if not row or not row.is_active:
        raise HTTPException(status_code=404, detail="Room not found")
    return row


async def _get_guest(
    db: AsyncSession, tenant_id: str, guest_id: str, *, require_active: bool = True
) -> m.HotelGuest:
    row = (
        await db.execute(
            select(m.HotelGuest).where(m.HotelGuest.id == guest_id, m.HotelGuest.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if not row or (require_active and not row.is_active):
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
    stmt = (
        select(m.HotelReservation)
        .where(
            m.HotelReservation.tenant_id == tenant_id,
            m.HotelReservation.room_id == room_id,
            m.HotelReservation.status.in_(ACTIVE_BOOKING_STATUSES),
            m.HotelReservation.check_in_date < check_out,
            m.HotelReservation.check_out_date > check_in,
        )
        .with_for_update()
    )
    if exclude_id:
        stmt = stmt.where(m.HotelReservation.id != exclude_id)
    clash = (await db.execute(stmt.limit(1))).scalar_one_or_none()
    if clash:
        raise HTTPException(
            status_code=409,
            detail=f"Room is already reserved ({clash.reservation_number}) for overlapping dates",
        )
    tickets = await _optional_scalars(
        db,
        select(m.HotelMaintenanceTicket).where(
            m.HotelMaintenanceTicket.tenant_id == tenant_id,
            m.HotelMaintenanceTicket.room_id == room_id,
            m.HotelMaintenanceTicket.block_room.is_(True),
            m.HotelMaintenanceTicket.status.in_(("open", "in_progress")),
        ),
    )
    for ticket in tickets:
        start = _as_date(getattr(ticket, "ooo_starts_on", None)) or date.min
        end_d = _as_date(getattr(ticket, "ooo_ends_on", None))
        end_excl = (end_d + timedelta(days=1)) if end_d else date.max
        if start < check_out and end_excl > check_in:
            raise HTTPException(
                status_code=409,
                detail="Room is out of order for overlapping dates",
            )
    events = await _optional_scalars(
        db,
        select(m.HotelEvent).where(
            m.HotelEvent.tenant_id == tenant_id,
            m.HotelEvent.room_id == room_id,
            m.HotelEvent.status.in_(("inquiry", "confirmed")),
            m.HotelEvent.starts_on < check_out,
            m.HotelEvent.ends_on > check_in,
        ),
    )
    if events:
        raise HTTPException(
            status_code=409,
            detail=f"Room is booked for an event ({events[0].title}) on overlapping dates",
        )


async def list_reservations(
    db: AsyncSession,
    *,
    tenant_id: str,
    status: str | None = None,
    list_kind: str | None = None,
    on_date: date | None = None,
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
    day = _as_date(on_date) or date.today()
    kind = (list_kind or "").strip().lower()
    if kind == "arrivals":
        stmt = stmt.where(
            m.HotelReservation.check_in_date == day,
            m.HotelReservation.status.in_(("booked", "checked_in")),
        )
    elif kind == "departures":
        stmt = stmt.where(
            m.HotelReservation.status.in_(("checked_in", "checked_out")),
        )
    elif kind == "in_house":
        stmt = stmt.where(m.HotelReservation.status == "checked_in")
    elif kind == "upcoming":
        stmt = stmt.where(
            m.HotelReservation.status.in_(("tentative", "booked")),
            m.HotelReservation.check_in_date >= day,
        )
    elif kind == "tentative":
        stmt = stmt.where(m.HotelReservation.status == "tentative")
    elif kind == "cancelled":
        stmt = stmt.where(m.HotelReservation.status == "cancelled")
    elif kind == "no_show":
        stmt = stmt.where(m.HotelReservation.status == "no_show")
    elif kind == "waitlist":
        stmt = stmt.where(m.HotelReservation.status == "waitlisted")
    rows = (await db.execute(stmt)).all()
    picked = [(r, room, guest) for r, room, guest in rows]
    if kind == "departures":
        picked = [item for item in picked if _departure_day(item[0]) == day]
    return picked


async def group_labels(
    db: AsyncSession, *, tenant_id: str, group_ids: list[str]
) -> dict[str, str]:
    ids = [str(item) for item in group_ids if item]
    if not ids:
        return {}
    rows = await _optional_all(
        db,
        select(
            m.HotelReservationGroup.id,
            m.HotelReservationGroup.name,
            m.HotelReservationGroup.group_number,
        ).where(
            m.HotelReservationGroup.tenant_id == tenant_id,
            m.HotelReservationGroup.id.in_(ids),
        ),
    )
    labels: dict[str, str] = {}
    for group_id, name, number in rows:
        label = str(name or "").strip() or str(number or "").strip()
        if label:
            labels[str(group_id)] = label
    return labels


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
    booking_source: str = "direct",
    special_requests: str | None = None,
    deposit_amount: float = 0,
    deposit_method: str | None = None,
    notes: str | None = None,
    created_by: str | None = None,
    walk_in: bool = False,
    status: str = "booked",
    rate_plan_id: str | None = None,
    discount_percent: float = 0,
    discount_authorized_by: str | None = None,
) -> tuple[m.HotelReservation, m.HotelRoom, m.HotelGuest]:
    # Lock room row first so concurrent bookings for the same room serialize.
    room = await _get_room(db, tenant_id, room_id, for_update=True)
    guest = await _get_guest(db, tenant_id, guest_id)
    check_in = _as_date(check_in_date)
    check_out = _as_date(check_out_date)
    if not check_in or not check_out:
        raise HTTPException(status_code=422, detail="check_in_date and check_out_date are required")
    occ = max(1, int(adults or 1)) + max(0, int(children or 0))
    if occ > int(room.max_occupancy or 1):
        raise HTTPException(status_code=409, detail="Occupancy exceeds room capacity")
    source = (booking_source or ("walk_in" if walk_in else "direct")).strip().lower()
    if source not in BOOKING_SOURCES:
        raise HTTPException(status_code=422, detail="Invalid booking_source")
    if deposit_method and deposit_method.strip().lower() not in PAYMENT_METHODS:
        raise HTTPException(status_code=422, detail="Invalid deposit_method")
    if nightly_rate is not None:
        rate = money_json(nightly_rate)
    else:
        # Prefer weekend rate for stays that include Sat/Sun nights when configured.
        rate = money_json(room.rate_amount or 0)
        weekend = getattr(room, "weekend_rate", None)
        if weekend is not None:
            d = check_in
            while d < check_out:
                if d.weekday() >= 5:  # Sat/Sun
                    rate = money_json(weekend)
                    break
                from datetime import timedelta as _td
                d = d + _td(days=1)
    status_key = (status or "booked").strip().lower()
    if walk_in:
        status_key = "booked"
    if status_key not in {"tentative", "booked", "waitlisted"}:
        raise HTTPException(status_code=422, detail="status must be tentative, booked, or waitlisted")
    waiting = status_key == "waitlisted"
    if waiting:
        if not check_in or not check_out or check_out <= check_in:
            raise HTTPException(status_code=400, detail="check_out_date must be after check_in_date")
    else:
        await _assert_room_available(
            db,
            tenant_id=tenant_id,
            room_id=room.id,
            check_in=check_in,
            check_out=check_out,
        )
        if room.status in {"maintenance", "out_of_order", "blocked"}:
            raise HTTPException(status_code=409, detail=f"Room is {room.status.replace('_', ' ')}")
        if room.status == "dirty":
            raise HTTPException(status_code=409, detail="Room is dirty — complete housekeeping first")
    if rate_plan_id:
        try:
            async with db.begin_nested():
                plan = (
                    await db.execute(
                        select(m.HotelRatePlan).where(
                            m.HotelRatePlan.id == rate_plan_id,
                            m.HotelRatePlan.tenant_id == tenant_id,
                            m.HotelRatePlan.is_active.is_(True),
                        )
                    )
                ).scalar_one_or_none()
        except (ProgrammingError, OperationalError) as exc:
            _raise_schema_behind(exc)
        if not plan:
            raise HTTPException(status_code=404, detail="Rate plan not found")
        nights = max(1, (check_out - check_in).days)
        if nights < int(plan.min_nights or 1):
            raise HTTPException(status_code=409, detail="Stay is shorter than the rate plan minimum nights")
        _assert_rate_plan_fits(plan, room, check_in, check_out)
        rate = money_json(plan.amount or 0)
    if nightly_rate is None:
        included = 1 if int(room.max_occupancy or 1) <= 1 else 2
        extra_people = max(0, occ - included)
        extra_each = money_json(getattr(room, "extra_person_charge", 0) or 0)
        if extra_people and extra_each > 0:
            rate = money_json(rate + (extra_people * extra_each))
    raw_disc = money_json(discount_percent or 0)
    if raw_disc > 100:
        raise HTTPException(status_code=422, detail="Stay discount percent cannot be above 100")
    disc = max(0.0, raw_disc)
    if disc > 0 and not discount_authorized_by:
        raise HTTPException(status_code=422, detail="discount_authorized_by is required when applying a discount")
    if disc:
        rate = money_json(rate * (1 - disc / 100.0))
    if notes is not None and not str(notes).strip():
        raise HTTPException(status_code=422, detail="Reservation notes cannot be blank")
    row = m.HotelReservation(
        tenant_id=tenant_id,
        reservation_number=await _next_reservation_number(db, tenant_id),
        room_id=room.id,
        guest_id=guest.id,
        check_in_date=check_in,
        check_out_date=check_out,
        adults=max(1, int(adults or 1)),
        children=max(0, int(children or 0)),
        status=status_key,
        booking_source=source,
        special_requests=optional_honest_narrative(
            special_requests, label="special requests", max_length=1000
        ),
        nightly_rate=money_json(rate),
        deposit_amount=money_json(deposit_amount or 0),
        deposit_method=(deposit_method or "").strip().lower() or None,
        notes=optional_honest_narrative(notes, label="notes", max_length=500),
        created_by=created_by,
    )
    if rate_plan_id:
        row.rate_plan_id = rate_plan_id
    if disc:
        row.discount_percent = disc
        row.discount_authorized_by = discount_authorized_by
    db.add(row)
    if status_key == "booked" and room.status in {"available", "clean", "inspected"}:
        room.status = "reserved"
        room.updated_at = datetime.utcnow()
    try:
        await db.flush()
    except (ProgrammingError, OperationalError) as exc:
        _raise_schema_behind(exc)
    # A waiting-list row does not hold the room. Booked and tentative rows re-check overlap.
    if not waiting:
        await _assert_room_available(
            db,
            tenant_id=tenant_id,
            room_id=room.id,
            check_in=check_in,
            check_out=check_out,
            exclude_id=row.id,
        )
    return row, room, guest


def _assert_rate_plan_fits(plan, room: m.HotelRoom, check_in: date, check_out: date) -> None:
    plan_type = (getattr(plan, "room_type", None) or "").strip().lower()
    if plan_type and plan_type != (room.room_type or "").strip().lower():
        raise HTTPException(status_code=409, detail="Rate plan is for a different room type")
    night = check_in
    has_weekday = False
    has_weekend = False
    while night < check_out:
        if night.weekday() >= 5:
            has_weekend = True
        else:
            has_weekday = True
        night = night + timedelta(days=1)
    if getattr(plan, "weekday_only", False) and has_weekend:
        raise HTTPException(status_code=409, detail="This rate plan is for weekday nights only")
    if getattr(plan, "weekend_only", False) and has_weekday:
        raise HTTPException(status_code=409, detail="This rate plan is for weekend nights only")
    start = _as_date(getattr(plan, "starts_on", None))
    end = _as_date(getattr(plan, "ends_on", None))
    last_night = check_out - timedelta(days=1)
    if start and check_in < start:
        raise HTTPException(status_code=409, detail="Stay starts before this rate plan")
    if end and last_night > end:
        raise HTTPException(status_code=409, detail="Stay ends after this rate plan")


async def update_reservation(
    db: AsyncSession,
    *,
    tenant_id: str,
    reservation_id: str,
    room_id: str | None = None,
    check_in_date: date | None = None,
    check_out_date: date | None = None,
    adults: int | None = None,
    children: int | None = None,
    nightly_rate: float | None = None,
    booking_source: str | None = None,
    special_requests: str | None = None,
    notes: str | None = None,
) -> tuple[m.HotelReservation, m.HotelRoom, m.HotelGuest]:
    row, room, guest = await _get_reservation(db, tenant_id, reservation_id)
    if row.status not in {"booked", "tentative"}:
        raise HTTPException(status_code=400, detail="Only tentative or booked reservations can be edited")
    new_room = room
    if room_id and room_id != row.room_id:
        new_room = await _get_room(db, tenant_id, room_id, for_update=True)
        if new_room.status in {"maintenance", "out_of_order", "blocked"}:
            raise HTTPException(status_code=409, detail=f"Room is {new_room.status.replace('_', ' ')}")
        if new_room.status == "dirty":
            raise HTTPException(status_code=409, detail="Room is dirty — complete housekeeping first")
    check_in = _as_date(check_in_date) or row.check_in_date
    check_out = _as_date(check_out_date) or row.check_out_date
    await _assert_room_available(
        db,
        tenant_id=tenant_id,
        room_id=new_room.id,
        check_in=check_in,
        check_out=check_out,
        exclude_id=row.id,
    )
    if booking_source is not None:
        source = booking_source.strip().lower()
        if source not in BOOKING_SOURCES:
            raise HTTPException(status_code=422, detail="Invalid booking_source")
        row.booking_source = source
    row.room_id = new_room.id
    row.check_in_date = check_in
    row.check_out_date = check_out
    if adults is not None:
        row.adults = max(1, int(adults))
    if children is not None:
        row.children = max(0, int(children))
    if nightly_rate is not None:
        row.nightly_rate = money_json(nightly_rate)
    if special_requests is not None:
        row.special_requests = optional_honest_narrative(
            special_requests, label="special requests", max_length=1000
        )
    if notes is not None:
        if not str(notes).strip():
            raise HTTPException(status_code=422, detail="Reservation notes cannot be blank")
        row.notes = optional_honest_narrative(notes, label="notes", max_length=500)
    await db.flush()
    return row, new_room, guest


async def confirm_reservation(
    db: AsyncSession, *, tenant_id: str, reservation_id: str
) -> tuple[m.HotelReservation, m.HotelRoom, m.HotelGuest]:
    row, room, guest = await _get_reservation(db, tenant_id, reservation_id)
    if row.status not in {"tentative", "waitlisted"}:
        raise HTTPException(
            status_code=400, detail="Only tentative or waiting-list reservations can be confirmed"
        )
    await _assert_room_available(
        db,
        tenant_id=tenant_id,
        room_id=room.id,
        check_in=row.check_in_date,
        check_out=row.check_out_date,
        exclude_id=row.id,
    )
    if room.status in {"maintenance", "out_of_order", "blocked"}:
        raise HTTPException(status_code=409, detail=f"Room is {room.status.replace('_', ' ')}")
    if room.status == "dirty":
        raise HTTPException(status_code=409, detail="Room is dirty — complete housekeeping first")
    row.status = "booked"
    row.updated_at = datetime.utcnow()
    if room.status in {"available", "clean", "inspected"}:
        room.status = "reserved"
        room.updated_at = datetime.utcnow()
    await db.flush()
    return row, room, guest


async def duplicate_reservation(
    db: AsyncSession,
    *,
    tenant_id: str,
    reservation_id: str,
    check_in_date: date,
    check_out_date: date,
    created_by: str | None = None,
) -> tuple[m.HotelReservation, m.HotelRoom, m.HotelGuest]:
    row, _room, _guest = await _get_reservation(db, tenant_id, reservation_id)
    return await create_reservation(
        db,
        tenant_id=tenant_id,
        room_id=row.room_id,
        guest_id=row.guest_id,
        check_in_date=check_in_date,
        check_out_date=check_out_date,
        adults=row.adults,
        children=row.children,
        nightly_rate=money_json(row.nightly_rate or 0),
        booking_source=row.booking_source,
        special_requests=row.special_requests,
        notes=row.notes,
        created_by=created_by,
        status="booked",
    )


async def transfer_folio_charge(
    db: AsyncSession,
    *,
    tenant_id: str,
    charge_id: str,
    target_folio_id: str,
    created_by: str | None = None,
) -> m.HotelFolioCharge:
    charge = (
        await db.execute(
            select(m.HotelFolioCharge).where(
                m.HotelFolioCharge.id == charge_id,
                m.HotelFolioCharge.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not charge or charge.is_void:
        raise HTTPException(status_code=404, detail="Charge not found")
    if charge.folio_id == target_folio_id:
        raise HTTPException(status_code=400, detail="Charge is already on that folio")
    target, _, _ = await get_folio_detail(db, tenant_id=tenant_id, folio_id=target_folio_id)
    if target.status != "open":
        raise HTTPException(status_code=400, detail="Target folio is closed")
    moved = await add_folio_charge(
        db,
        tenant_id=tenant_id,
        folio_id=target_folio_id,
        charge_type=charge.charge_type,
        description=f"Transfer: {charge.description}",
        quantity=money_json(charge.quantity or 1),
        unit_amount=money_json(charge.unit_amount or 0),
        tax_amount=money_json(charge.tax_amount or 0),
        discount_amount=money_json(charge.discount_amount or 0),
        created_by=created_by,
    )
    await void_folio_charge(
        db,
        tenant_id=tenant_id,
        charge_id=charge.id,
        void_reason="Transferred to another folio",
    )
    return moved


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
    guest = await _get_guest(db, tenant_id, row.guest_id, require_active=False)
    return row, room, guest


async def _get_or_create_folio(
    db: AsyncSession,
    *,
    tenant_id: str,
    reservation: m.HotelReservation,
    created_by: str | None = None,
) -> m.HotelFolio:
    existing = (
        await db.execute(
            select(m.HotelFolio).where(
                m.HotelFolio.tenant_id == tenant_id,
                m.HotelFolio.reservation_id == reservation.id,
            )
        )
    ).scalar_one_or_none()
    if existing:
        return existing
    folio = m.HotelFolio(
        tenant_id=tenant_id,
        reservation_id=reservation.id,
        guest_id=reservation.guest_id,
        folio_number=await _next_folio_number(db, tenant_id),
        status="open",
        opened_at=datetime.utcnow(),
    )
    db.add(folio)
    await db.flush()
    nights = max(1, (reservation.check_out_date - reservation.check_in_date).days)
    await add_folio_charge(
        db,
        tenant_id=tenant_id,
        folio_id=folio.id,
        charge_type="room",
        description=f"Room charge ({nights} night(s))",
        quantity=nights,
        unit_amount=money_json(reservation.nightly_rate or 0),
        created_by=created_by,
    )
    deposit = money_json(getattr(reservation, "deposit_amount", 0) or 0)
    if deposit > 0:
        await record_folio_payment(
            db,
            tenant_id=tenant_id,
            folio_id=folio.id,
            method=(getattr(reservation, "deposit_method", None) or "cash"),
            amount=deposit,
            reference="deposit",
            notes="Reservation deposit",
            recorded_by=created_by,
        )
    return folio


async def folio_totals(
    db: AsyncSession, *, tenant_id: str, folio_id: str
) -> tuple[float, float, float]:
    charges = (
        await db.execute(
            select(m.HotelFolioCharge).where(
                m.HotelFolioCharge.tenant_id == tenant_id,
                m.HotelFolioCharge.folio_id == folio_id,
                m.HotelFolioCharge.is_void.is_(False),
            )
        )
    ).scalars().all()
    payments = (
        await db.execute(
            select(m.HotelFolioPayment).where(
                m.HotelFolioPayment.tenant_id == tenant_id,
                m.HotelFolioPayment.folio_id == folio_id,
            )
        )
    ).scalars().all()
    charge_total = money_json(sum(money_json(c.line_total or 0) for c in charges))
    payment_total = money_json(sum(money_json(p.amount or 0) for p in payments))
    return charge_total, payment_total, money_json(charge_total - payment_total)


async def folio_balance(db: AsyncSession, *, tenant_id: str, folio_id: str) -> float:
    _, _, balance = await folio_totals(db, tenant_id=tenant_id, folio_id=folio_id)
    return balance


async def folio_map_for_reservations(
    db: AsyncSession, *, tenant_id: str, reservation_ids: list[str]
) -> dict[str, tuple[str, float]]:
    ids = [rid for rid in reservation_ids if rid]
    if not ids:
        return {}
    folios = (
        await db.execute(
            select(m.HotelFolio).where(
                m.HotelFolio.tenant_id == tenant_id,
                m.HotelFolio.reservation_id.in_(ids),
            )
        )
    ).scalars().all()
    if not folios:
        return {}
    folio_ids = [f.id for f in folios]
    charges = (
        await db.execute(
            select(m.HotelFolioCharge).where(
                m.HotelFolioCharge.tenant_id == tenant_id,
                m.HotelFolioCharge.folio_id.in_(folio_ids),
                m.HotelFolioCharge.is_void.is_(False),
            )
        )
    ).scalars().all()
    payments = (
        await db.execute(
            select(m.HotelFolioPayment).where(
                m.HotelFolioPayment.tenant_id == tenant_id,
                m.HotelFolioPayment.folio_id.in_(folio_ids),
            )
        )
    ).scalars().all()
    charge_by: dict[str, float] = {}
    pay_by: dict[str, float] = {}
    for c in charges:
        charge_by[c.folio_id] = money_json(
            charge_by.get(c.folio_id, 0) + money_json(c.line_total or 0)
        )
    for p in payments:
        pay_by[p.folio_id] = money_json(pay_by.get(p.folio_id, 0) + money_json(p.amount or 0))
    out: dict[str, tuple[str, float]] = {}
    for folio in folios:
        out[folio.reservation_id] = (
            folio.id,
            money_json(charge_by.get(folio.id, 0) - pay_by.get(folio.id, 0)),
        )
    return out


async def get_folio_for_reservation(
    db: AsyncSession, *, tenant_id: str, reservation_id: str
) -> m.HotelFolio | None:
    return (
        await db.execute(
            select(m.HotelFolio).where(
                m.HotelFolio.tenant_id == tenant_id,
                m.HotelFolio.reservation_id == reservation_id,
            )
        )
    ).scalar_one_or_none()


async def get_folio_detail(
    db: AsyncSession, *, tenant_id: str, folio_id: str
) -> tuple[m.HotelFolio, list[m.HotelFolioCharge], list[m.HotelFolioPayment]]:
    folio = (
        await db.execute(
            select(m.HotelFolio).where(m.HotelFolio.id == folio_id, m.HotelFolio.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if not folio:
        raise HTTPException(status_code=404, detail="Folio not found")
    charges = list(
        (
            await db.execute(
                select(m.HotelFolioCharge)
                .where(
                    m.HotelFolioCharge.tenant_id == tenant_id,
                    m.HotelFolioCharge.folio_id == folio_id,
                )
                .order_by(m.HotelFolioCharge.created_at.asc())
            )
        )
        .scalars()
        .all()
    )
    payments = list(
        (
            await db.execute(
                select(m.HotelFolioPayment)
                .where(
                    m.HotelFolioPayment.tenant_id == tenant_id,
                    m.HotelFolioPayment.folio_id == folio_id,
                )
                .order_by(m.HotelFolioPayment.created_at.asc())
            )
        )
        .scalars()
        .all()
    )
    return folio, charges, payments


async def add_folio_charge(
    db: AsyncSession,
    *,
    tenant_id: str,
    folio_id: str,
    charge_type: str = "extra",
    description: str,
    quantity: float = 1,
    unit_amount: float = 0,
    tax_amount: float = 0,
    discount_amount: float = 0,
    created_by: str | None = None,
) -> m.HotelFolioCharge:
    folio = (
        await db.execute(
            select(m.HotelFolio).where(m.HotelFolio.id == folio_id, m.HotelFolio.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if not folio:
        raise HTTPException(status_code=404, detail="Folio not found")
    if folio.status != "open":
        raise HTTPException(status_code=400, detail="Folio is closed")
    ctype = (charge_type or "extra").strip().lower()
    if ctype not in CHARGE_TYPES:
        raise HTTPException(status_code=422, detail="Invalid charge_type")
    qty = money_json(1 if quantity is None else quantity)
    if qty <= 0:
        raise HTTPException(status_code=422, detail="Folio charge quantity must be above zero")
    unit = money_json(unit_amount or 0)
    tax = money_json(tax_amount or 0)
    disc = money_json(discount_amount or 0)
    gross = money_json(qty * unit + tax)
    if disc > gross:
        raise HTTPException(status_code=422, detail="Folio charge discount cannot be above the line")
    line_total = money_json(gross - disc)
    row = m.HotelFolioCharge(
        tenant_id=tenant_id,
        folio_id=folio_id,
        charge_type=ctype,
        description=require_honest_narrative(description, label="description", max_length=255),
        quantity=qty,
        unit_amount=unit,
        tax_amount=tax,
        discount_amount=disc,
        line_total=line_total,
        created_by=created_by,
    )
    db.add(row)
    folio.updated_at = datetime.utcnow()
    await db.flush()
    return row


_TIMING_FEE_LABELS = {
    "early_checkin": ("Early check-in", "early_checkin_fee"),
    "late_checkout": ("Late check-out", "late_checkout_fee"),
}


async def _existing_open_charge(
    db: AsyncSession, *, tenant_id: str, folio_id: str, description: str
) -> m.HotelFolioCharge | None:
    return (
        await db.execute(
            select(m.HotelFolioCharge).where(
                m.HotelFolioCharge.tenant_id == tenant_id,
                m.HotelFolioCharge.folio_id == folio_id,
                m.HotelFolioCharge.description == description,
                m.HotelFolioCharge.is_void.is_(False),
            )
        )
    ).scalar_one_or_none()


async def post_timing_fee(
    db: AsyncSession,
    *,
    tenant_id: str,
    folio_id: str,
    kind: str,
    created_by: str | None = None,
) -> m.HotelFolioCharge:
    """Post the configured early or late fee once. A retry returns the same charge."""
    label_attr = _TIMING_FEE_LABELS.get((kind or "").strip().lower())
    if not label_attr:
        raise HTTPException(status_code=422, detail="kind must be early_checkin or late_checkout")
    label, attr = label_attr
    folio = (
        await db.execute(
            select(m.HotelFolio).where(m.HotelFolio.id == folio_id, m.HotelFolio.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if not folio:
        raise HTTPException(status_code=404, detail="Folio not found")
    if folio.status != "open":
        raise HTTPException(status_code=400, detail="Folio is closed")
    reservation = (
        await db.execute(
            select(m.HotelReservation).where(
                m.HotelReservation.id == folio.reservation_id,
                m.HotelReservation.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not reservation or reservation.status != "checked_in":
        raise HTTPException(status_code=400, detail="Only an in-house stay can take this fee")
    already = await _existing_open_charge(db, tenant_id=tenant_id, folio_id=folio.id, description=label)
    if already:
        return already
    settings = await get_or_create_settings(db, tenant_id=tenant_id)
    amount = money_json(getattr(settings, attr, 0) or 0)
    if amount <= 0:
        raise HTTPException(status_code=422, detail="This fee is not configured")
    return await add_folio_charge(
        db,
        tenant_id=tenant_id,
        folio_id=folio.id,
        charge_type="extra",
        description=label,
        quantity=1,
        unit_amount=amount,
        created_by=created_by,
    )


_SERVICE_CHARGE_LABEL = "Service charge"


async def post_service_charge(
    db: AsyncSession,
    *,
    tenant_id: str,
    folio_id: str,
    created_by: str | None = None,
) -> m.HotelFolioCharge:
    """Post the configured percent of room charges once. A retry returns the same line."""
    folio = (
        await db.execute(
            select(m.HotelFolio).where(m.HotelFolio.id == folio_id, m.HotelFolio.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if not folio:
        raise HTTPException(status_code=404, detail="Folio not found")
    if folio.status != "open":
        raise HTTPException(status_code=400, detail="Folio is closed")
    reservation = (
        await db.execute(
            select(m.HotelReservation).where(
                m.HotelReservation.id == folio.reservation_id,
                m.HotelReservation.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not reservation or reservation.status != "checked_in":
        raise HTTPException(status_code=400, detail="Only an in-house stay can take this fee")
    already = await _existing_open_charge(
        db, tenant_id=tenant_id, folio_id=folio.id, description=_SERVICE_CHARGE_LABEL
    )
    if already:
        return already
    settings = await get_or_create_settings(db, tenant_id=tenant_id)
    percent = money_json(getattr(settings, "service_charge_percent", 0) or 0)
    if percent <= 0:
        raise HTTPException(status_code=422, detail="This service charge is not configured")
    if percent > 100:
        raise HTTPException(status_code=422, detail="Service charge percent cannot exceed 100")
    room_lines = (
        await db.execute(
            select(m.HotelFolioCharge).where(
                m.HotelFolioCharge.tenant_id == tenant_id,
                m.HotelFolioCharge.folio_id == folio.id,
                m.HotelFolioCharge.charge_type == "room",
                m.HotelFolioCharge.is_void.is_(False),
            )
        )
    ).scalars().all()
    room_total = money_json(sum(money_json(line.line_total or 0) for line in room_lines))
    if room_total <= 0:
        raise HTTPException(status_code=422, detail="No room charge to apply a service charge to")
    amount = money_json(room_total * percent / 100.0)
    if amount <= 0:
        raise HTTPException(status_code=422, detail="This service charge is not configured")
    return await add_folio_charge(
        db,
        tenant_id=tenant_id,
        folio_id=folio.id,
        charge_type="service",
        description=_SERVICE_CHARGE_LABEL,
        quantity=1,
        unit_amount=amount,
        created_by=created_by,
    )


async def post_no_show_fee(
    db: AsyncSession,
    *,
    tenant_id: str,
    reservation_id: str,
    created_by: str | None = None,
) -> m.HotelFolio:
    """Post the configured no-show percent once, without a room-night charge."""
    row, _room, _guest = await _get_reservation(db, tenant_id, reservation_id)
    if row.status != "no_show":
        raise HTTPException(status_code=400, detail="No-show fee applies only after the stay is marked no-show")
    settings = await get_or_create_settings(db, tenant_id=tenant_id)
    percent = money_json(getattr(settings, "no_show_fee_percent", 0) or 0)
    nights = max(0, (row.check_out_date - row.check_in_date).days)
    amount = money_json(money_json(row.nightly_rate or 0) * nights * percent / 100.0)
    if amount <= 0:
        raise HTTPException(status_code=422, detail="No-show fee is not configured")
    folio = (
        await db.execute(
            select(m.HotelFolio).where(
                m.HotelFolio.tenant_id == tenant_id,
                m.HotelFolio.reservation_id == row.id,
            )
        )
    ).scalar_one_or_none()
    if folio and folio.status != "open":
        raise HTTPException(status_code=400, detail="Folio is closed")
    if not folio:
        folio = m.HotelFolio(
            tenant_id=tenant_id,
            reservation_id=row.id,
            guest_id=row.guest_id,
            folio_number=await _next_folio_number(db, tenant_id),
            status="open",
            opened_at=datetime.utcnow(),
        )
        db.add(folio)
        await db.flush()
    already = await _existing_open_charge(
        db, tenant_id=tenant_id, folio_id=folio.id, description="No-show fee"
    )
    if already:
        return folio
    await add_folio_charge(
        db,
        tenant_id=tenant_id,
        folio_id=folio.id,
        charge_type="extra",
        description="No-show fee",
        quantity=1,
        unit_amount=amount,
        created_by=created_by,
    )
    return folio


async def void_folio_charge(
    db: AsyncSession,
    *,
    tenant_id: str,
    charge_id: str,
    void_reason: str,
) -> m.HotelFolioCharge:
    row = (
        await db.execute(
            select(m.HotelFolioCharge).where(
                m.HotelFolioCharge.id == charge_id,
                m.HotelFolioCharge.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Charge not found")
    if row.is_void:
        raise HTTPException(status_code=400, detail="Charge already voided")
    row.is_void = True
    row.void_reason = require_honest_narrative(void_reason, label="void reason", max_length=255)
    await db.flush()
    return row


async def record_folio_payment(
    db: AsyncSession,
    *,
    tenant_id: str,
    folio_id: str,
    method: str = "cash",
    amount: float,
    reference: str | None = None,
    notes: str | None = None,
    recorded_by: str | None = None,
) -> m.HotelFolioPayment:
    folio = (
        await db.execute(
            select(m.HotelFolio).where(m.HotelFolio.id == folio_id, m.HotelFolio.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if not folio:
        raise HTTPException(status_code=404, detail="Folio not found")
    if folio.status != "open":
        raise HTTPException(status_code=400, detail="Folio is closed")
    method_key = (method or "cash").strip().lower()
    if method_key not in PAYMENT_METHODS:
        raise HTTPException(status_code=422, detail="Invalid payment method")
    amt = money_json(amount or 0)
    if amt <= 0:
        raise HTTPException(status_code=422, detail="Payment amount must be positive")
    if reference is not None and not str(reference).strip():
        raise HTTPException(status_code=422, detail="Folio payment reference cannot be blank")
    if notes is not None and not str(notes).strip():
        raise HTTPException(status_code=422, detail="Folio payment notes cannot be blank")
    row = m.HotelFolioPayment(
        tenant_id=tenant_id,
        folio_id=folio_id,
        method=method_key,
        amount=amt,
        reference=optional_honest_narrative(reference, label="reference", max_length=120),
        notes=optional_honest_narrative(notes, label="notes", max_length=500),
        recorded_by=recorded_by,
    )
    db.add(row)
    folio.updated_at = datetime.utcnow()
    await db.flush()
    return row


async def apply_event_deposit(
    db: AsyncSession,
    *,
    tenant_id: str,
    event_id: str,
    guest_id: str | None,
    amount: float,
    recorded_by: str | None = None,
) -> str | None:
    """Record an event deposit on the guest's open folio. Cash is a tender, not a card charge."""
    amt = money_json(amount or 0)
    if amt <= 0 or not guest_id:
        return None
    note = f"Event deposit {event_id}"
    already = await _optional_scalars(
        db,
        select(m.HotelFolioPayment).where(
            m.HotelFolioPayment.tenant_id == tenant_id,
            m.HotelFolioPayment.notes == note,
        ),
    )
    if already:
        return already[0].folio_id
    folios = await _optional_scalars(
        db,
        select(m.HotelFolio)
        .where(
            m.HotelFolio.tenant_id == tenant_id,
            m.HotelFolio.guest_id == guest_id,
            m.HotelFolio.status == "open",
        )
        .order_by(m.HotelFolio.opened_at.desc()),
    )
    if not folios:
        return None
    await record_folio_payment(
        db,
        tenant_id=tenant_id,
        folio_id=folios[0].id,
        method="cash",
        amount=amt,
        notes=note,
        recorded_by=recorded_by,
    )
    return folios[0].id


async def _post_overlapping_event_deposits(
    db: AsyncSession,
    *,
    tenant_id: str,
    guest_id: str,
    check_in: date,
    check_out: date,
    recorded_by: str | None,
) -> None:
    events = await _optional_scalars(
        db,
        select(m.HotelEvent).where(
            m.HotelEvent.tenant_id == tenant_id,
            m.HotelEvent.guest_id == guest_id,
            m.HotelEvent.status.in_(("inquiry", "confirmed")),
            m.HotelEvent.starts_on < check_out,
            m.HotelEvent.ends_on > check_in,
        ),
    )
    for event in events:
        await apply_event_deposit(
            db,
            tenant_id=tenant_id,
            event_id=event.id,
            guest_id=guest_id,
            amount=money_json(event.deposit_amount or 0),
            recorded_by=recorded_by,
        )


async def check_in(
    db: AsyncSession, *, tenant_id: str, reservation_id: str, created_by: str | None = None
) -> tuple[m.HotelReservation, m.HotelRoom, m.HotelGuest, m.HotelFolio]:
    row, room, guest = await _get_reservation(db, tenant_id, reservation_id)
    if row.status != "booked":
        raise HTTPException(status_code=400, detail=f"Cannot check in a reservation with status {row.status}")
    if room.status in {"maintenance", "out_of_order", "blocked"}:
        raise HTTPException(status_code=409, detail=f"Room is {room.status.replace('_', ' ')}")
    row.status = "checked_in"
    row.checked_in_at = datetime.utcnow()
    room.status = "occupied"
    room.housekeeping_status = "dirty"
    room.updated_at = datetime.utcnow()
    row.updated_at = datetime.utcnow()
    folio = await _get_or_create_folio(db, tenant_id=tenant_id, reservation=row, created_by=created_by)
    await _post_overlapping_event_deposits(
        db,
        tenant_id=tenant_id,
        guest_id=row.guest_id,
        check_in=row.check_in_date,
        check_out=row.check_out_date,
        recorded_by=created_by,
    )
    await db.flush()
    return row, room, guest, folio



async def _ensure_guest_party(db: AsyncSession, *, tenant_id: str, guest: m.HotelGuest) -> m.Party:
    """Link hotel guest to a tenant customer Party for invoicing (Payment Model 1)."""
    if guest.email:
        existing = (
            await db.execute(
                select(m.Party).where(
                    m.Party.tenant_id == tenant_id,
                    m.Party.kind == "customer",
                    m.Party.email == guest.email,
                )
            )
        ).scalar_one_or_none()
        if existing:
            return existing
    # Prefer exact name match among active customers when no email hit.
    by_name = (
        await db.execute(
            select(m.Party).where(
                m.Party.tenant_id == tenant_id,
                m.Party.kind == "customer",
                m.Party.name == guest.full_name,
                m.Party.status == "active",
            )
        )
    ).scalar_one_or_none()
    if by_name and not guest.email:
        return by_name
    party = m.Party(
        tenant_id=tenant_id,
        kind="customer",
        name=guest.full_name,
        email=guest.email,
        phone=guest.phone,
        profile_type="registered",
        status="active",
        credit_limit=0,
    )
    db.add(party)
    await db.flush()
    return party


async def create_invoice_from_folio(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str | None,
    folio: m.HotelFolio,
    guest: m.HotelGuest,
    reservation: m.HotelReservation,
) -> m.SalesInvoice | None:
    """Create a sales invoice from non-void folio charges (Payment Model 1 records only)."""
    if getattr(folio, "sales_invoice_id", None):
        from app.sales import get_invoice

        return await get_invoice(db, tenant_id, folio.sales_invoice_id)
    charges = (
        await db.execute(
            select(m.HotelFolioCharge).where(
                m.HotelFolioCharge.tenant_id == tenant_id,
                m.HotelFolioCharge.folio_id == folio.id,
                m.HotelFolioCharge.is_void.is_(False),
            )
        )
    ).scalars().all()
    if not charges:
        return None
    total = money_json(sum(money_json(c.line_total or 0) for c in charges))
    if total <= 0:
        return None
    party = await _ensure_guest_party(db, tenant_id=tenant_id, guest=guest)
    product = (
        await db.execute(
            select(m.Product).where(
                m.Product.tenant_id == tenant_id,
                m.Product.sku == "HOTEL-SERVICE",
            )
        )
    ).scalar_one_or_none()
    if not product:
        product = m.Product(
            tenant_id=tenant_id,
            name="Hotel services",
            sku="HOTEL-SERVICE",
            cost_price=0,
            selling_price=0,
            stock_qty=0,
            tracks_batches=False,
        )
        db.add(product)
        await db.flush()
    from app.doc_numbers import next_sales_invoice_number

    payments = (
        await db.execute(
            select(m.HotelFolioPayment).where(
                m.HotelFolioPayment.tenant_id == tenant_id,
                m.HotelFolioPayment.folio_id == folio.id,
            )
        )
    ).scalars().all()
    paid = money_json(sum(money_json(p.amount or 0) for p in payments))
    inv_number = await next_sales_invoice_number(db, tenant_id)
    status = "paid" if paid + 1e-9 >= total else ("partial" if paid > 0 else "posted")
    invoice = m.SalesInvoice(
        tenant_id=tenant_id,
        invoice_number=inv_number,
        customer_id=party.id,
        status=status,
        subtotal=total,
        tax_amount=money_json(0),
        discount_amount=money_json(0),
        total_amount=total,
        paid_amount=money_json(min(paid, total)),
        notes=(
            f"Hotel folio {folio.folio_number} / reservation {reservation.reservation_number}. "
            f"Payment information recorded on folio (not a payment gateway)."
        ),
        created_by=user_id,
        posted_at=datetime.utcnow(),
    )
    db.add(invoice)
    await db.flush()
    for charge in charges:
        db.add(
            m.SalesInvoiceItem(
                tenant_id=tenant_id,
                sales_invoice_id=invoice.id,
                product_id=product.id,
                quantity=money_json(charge.quantity or 1),
                unit_price=money_json(charge.unit_amount or 0),
                tax_rate=0,
                discount=money_json(charge.discount_amount or 0),
                line_total=money_json(charge.line_total or 0),
            )
        )
    folio.sales_invoice_id = invoice.id
    await db.flush()
    return invoice



async def check_out(
    db: AsyncSession,
    *,
    tenant_id: str,
    reservation_id: str,
    allow_balance: bool = False,
    user_id: str | None = None,
) -> tuple[m.HotelReservation, m.HotelRoom, m.HotelGuest, m.HotelFolio | None]:
    row, room, guest = await _get_reservation(db, tenant_id, reservation_id)
    if row.status != "checked_in":
        raise HTTPException(status_code=400, detail=f"Cannot check out a reservation with status {row.status}")
    folio = await get_folio_for_reservation(db, tenant_id=tenant_id, reservation_id=row.id)
    if folio:
        bal = await folio_balance(db, tenant_id=tenant_id, folio_id=folio.id)
        if bal > 0.009 and not allow_balance:
            raise HTTPException(
                status_code=400,
                detail=f"Folio balance outstanding ({money_json(bal)}). Record payment or allow_balance.",
            )
        await create_invoice_from_folio(
            db,
            tenant_id=tenant_id,
            user_id=user_id,
            folio=folio,
            guest=guest,
            reservation=row,
        )
        folio.status = "closed"
        folio.closed_at = datetime.utcnow()
        folio.updated_at = datetime.utcnow()
    row.status = "checked_out"
    row.checked_out_at = datetime.utcnow()
    room.status = "dirty"
    room.housekeeping_status = "dirty"
    room.updated_at = datetime.utcnow()
    row.updated_at = datetime.utcnow()
    # Auto-create housekeeping task after checkout
    db.add(
        m.HotelHousekeepingTask(
            tenant_id=tenant_id,
            room_id=room.id,
            task_type="cleaning",
            priority="high",
            status="pending",
            due_at=datetime.utcnow() + timedelta(hours=2),
            notes=f"Auto-created after checkout of {row.reservation_number}",
        )
    )
    await db.flush()
    return row, room, guest, folio


async def cancel_reservation(
    db: AsyncSession, *, tenant_id: str, reservation_id: str
) -> tuple[m.HotelReservation, m.HotelRoom, m.HotelGuest]:
    row, room, guest = await _get_reservation(db, tenant_id, reservation_id)
    if row.status not in {"tentative", "booked", "waitlisted"}:
        raise HTTPException(status_code=400, detail=f"Cannot cancel a reservation with status {row.status}")
    row.status = "cancelled"
    row.cancelled_at = datetime.utcnow()
    row.updated_at = datetime.utcnow()
    if room.status == "reserved":
        room.status = "available"
        room.updated_at = datetime.utcnow()
    await db.flush()
    return row, room, guest


async def mark_no_show(
    db: AsyncSession, *, tenant_id: str, reservation_id: str
) -> tuple[m.HotelReservation, m.HotelRoom, m.HotelGuest]:
    row, room, guest = await _get_reservation(db, tenant_id, reservation_id)
    if row.status != "booked":
        raise HTTPException(status_code=400, detail=f"Cannot mark no-show with status {row.status}")
    arrival = _as_date(row.check_in_date)
    if arrival is None or arrival > date.today():
        raise HTTPException(status_code=409, detail="No-show applies on the arrival date")
    row.status = "no_show"
    row.no_show_at = datetime.utcnow()
    row.updated_at = datetime.utcnow()
    if room.status == "reserved":
        room.status = "available"
        room.updated_at = datetime.utcnow()
    await db.flush()
    return row, room, guest


async def extend_stay(
    db: AsyncSession,
    *,
    tenant_id: str,
    reservation_id: str,
    new_check_out_date: date,
    created_by: str | None = None,
) -> tuple[m.HotelReservation, m.HotelRoom, m.HotelGuest]:
    row, room, guest = await _get_reservation(db, tenant_id, reservation_id)
    if row.status not in {"tentative", "booked", "checked_in"}:
        raise HTTPException(status_code=400, detail="Can only extend tentative, booked, or in-house stays")
    new_out = _as_date(new_check_out_date)
    if not new_out or new_out <= row.check_out_date:
        raise HTTPException(status_code=400, detail="new_check_out_date must be after current check_out_date")
    await _assert_room_available(
        db,
        tenant_id=tenant_id,
        room_id=row.room_id,
        check_in=row.check_out_date,
        check_out=new_out,
        exclude_id=row.id,
    )
    extra_nights = (new_out - row.check_out_date).days
    row.check_out_date = new_out
    row.updated_at = datetime.utcnow()
    if row.status == "checked_in":
        folio = await get_folio_for_reservation(db, tenant_id=tenant_id, reservation_id=row.id)
        if folio and folio.status == "open":
            await add_folio_charge(
                db,
                tenant_id=tenant_id,
                folio_id=folio.id,
                charge_type="room",
                description=f"Stay extension ({extra_nights} night(s))",
                quantity=extra_nights,
                unit_amount=money_json(row.nightly_rate or 0),
                created_by=created_by,
            )
    await db.flush()
    return row, room, guest


async def move_room(
    db: AsyncSession,
    *,
    tenant_id: str,
    reservation_id: str,
    new_room_id: str,
) -> tuple[m.HotelReservation, m.HotelRoom, m.HotelGuest]:
    row, old_room, guest = await _get_reservation(db, tenant_id, reservation_id)
    if row.status not in {"tentative", "booked", "checked_in"}:
        raise HTTPException(status_code=400, detail="Can only move tentative, booked, or in-house stays")
    new_room = await _get_room(db, tenant_id, new_room_id)
    if new_room.id == old_room.id:
        raise HTTPException(status_code=400, detail="New room is the same as current room")
    if new_room.status in {"maintenance", "out_of_order", "blocked", "occupied", "dirty"}:
        raise HTTPException(status_code=409, detail=f"Target room is {new_room.status.replace('_', ' ')}")
    await _assert_room_available(
        db,
        tenant_id=tenant_id,
        room_id=new_room.id,
        check_in=row.check_in_date,
        check_out=row.check_out_date,
        exclude_id=row.id,
    )
    row.room_id = new_room.id
    row.updated_at = datetime.utcnow()
    if row.status == "checked_in":
        old_room.status = "dirty"
        old_room.housekeeping_status = "dirty"
        new_room.status = "occupied"
        new_room.housekeeping_status = "dirty"
    else:
        if old_room.status == "reserved":
            old_room.status = "available"
        if new_room.status in {"available", "clean", "inspected"}:
            new_room.status = "reserved"
    old_room.updated_at = datetime.utcnow()
    new_room.updated_at = datetime.utcnow()
    await db.flush()
    return row, new_room, guest


async def list_housekeeping(
    db: AsyncSession, *, tenant_id: str, status: str | None = None
) -> list[tuple[m.HotelHousekeepingTask, m.HotelRoom | None]]:
    stmt = (
        select(m.HotelHousekeepingTask, m.HotelRoom)
        .outerjoin(m.HotelRoom, m.HotelRoom.id == m.HotelHousekeepingTask.room_id)
        .where(m.HotelHousekeepingTask.tenant_id == tenant_id)
        .options(undefer(m.HotelHousekeepingTask.due_at))
        .order_by(m.HotelHousekeepingTask.created_at.desc())
    )
    if status:
        stmt = stmt.where(m.HotelHousekeepingTask.status == status.strip().lower())
    return [(t, r) for t, r in await _optional_all(db, stmt)]


def _housekeeping_due(value: datetime | str | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo is not None else value
    text = str(value).strip()
    if not text:
        raise HTTPException(status_code=422, detail="Housekeeping due time cannot be blank")
    try:
        if len(text) == 10:
            return datetime.strptime(text, "%Y-%m-%d")
        return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="Housekeeping due time must be a date and time",
        ) from exc


async def create_housekeeping_task(
    db: AsyncSession,
    *,
    tenant_id: str,
    room_id: str,
    task_type: str = "cleaning",
    priority: str = "normal",
    assigned_to: str | None = None,
    notes: str | None = None,
    due_at: datetime | str | None = None,
    created_by: str | None = None,
) -> tuple[m.HotelHousekeepingTask, m.HotelRoom]:
    room = await _get_room(db, tenant_id, room_id)
    pri = (priority or "normal").strip().lower()
    if pri not in HK_PRIORITIES:
        raise HTTPException(status_code=422, detail="Invalid priority")
    if notes is not None and not str(notes).strip():
        raise HTTPException(status_code=422, detail="Housekeeping notes cannot be blank")
    due = _housekeeping_due(due_at)
    room.housekeeping_status = "dirty"
    if room.status not in {"occupied", "maintenance", "out_of_order", "blocked"}:
        room.status = "dirty"
    room.updated_at = datetime.utcnow()
    row = m.HotelHousekeepingTask(
        tenant_id=tenant_id,
        room_id=room.id,
        task_type=(task_type or "cleaning").strip().lower()[:40],
        priority=pri,
        status="pending",
        assigned_to=optional_honest_narrative(assigned_to, label="assigned to", max_length=150),
        notes=optional_honest_narrative(notes, label="notes", max_length=500),
        due_at=due or (datetime.utcnow() + timedelta(hours=2)),
        created_by=created_by,
    )
    db.add(row)
    await db.flush()
    return row, room


async def complete_housekeeping_task(
    db: AsyncSession,
    *,
    tenant_id: str,
    task_id: str,
    mark_inspected: bool = False,
) -> tuple[m.HotelHousekeepingTask, m.HotelRoom]:
    row = (
        await db.execute(
            select(m.HotelHousekeepingTask).where(
                m.HotelHousekeepingTask.id == task_id,
                m.HotelHousekeepingTask.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Housekeeping task not found")
    if row.status == "completed":
        raise HTTPException(status_code=400, detail="Task already completed")
    room = await _get_room(db, tenant_id, row.room_id)
    row.status = "completed"
    row.completed_at = datetime.utcnow()
    row.updated_at = datetime.utcnow()
    if not row.started_at:
        row.started_at = row.completed_at
    if mark_inspected:
        room.housekeeping_status = "inspected"
    else:
        room.housekeeping_status = "clean"
    reason = await _ready_block_reason(db, tenant_id=tenant_id, room_id=room.id)
    if not reason and room.status in {"dirty", "clean", "inspected", "available"}:
        room.status = "available"
    room.updated_at = datetime.utcnow()
    await db.flush()
    return row, room


async def list_maintenance(
    db: AsyncSession, *, tenant_id: str, status: str | None = None
) -> list[tuple[m.HotelMaintenanceTicket, m.HotelRoom | None]]:
    stmt = (
        select(m.HotelMaintenanceTicket, m.HotelRoom)
        .outerjoin(m.HotelRoom, m.HotelRoom.id == m.HotelMaintenanceTicket.room_id)
        .where(m.HotelMaintenanceTicket.tenant_id == tenant_id)
        .options(
            undefer(m.HotelMaintenanceTicket.ooo_starts_on),
            undefer(m.HotelMaintenanceTicket.ooo_ends_on),
        )
        .order_by(m.HotelMaintenanceTicket.created_at.desc())
    )
    if status:
        stmt = stmt.where(m.HotelMaintenanceTicket.status == status.strip().lower())
    return [(t, r) for t, r in await _optional_all(db, stmt)]


async def create_maintenance_ticket(
    db: AsyncSession,
    *,
    tenant_id: str,
    room_id: str,
    title: str,
    priority: str = "normal",
    block_room: bool = True,
    assigned_to: str | None = None,
    notes: str | None = None,
    created_by: str | None = None,
    ooo_starts_on: date | str | None = None,
    ooo_ends_on: date | str | None = None,
) -> tuple[m.HotelMaintenanceTicket, m.HotelRoom]:
    room = await _get_room(db, tenant_id, room_id)
    pri = (priority or "normal").strip().lower()
    if pri not in HK_PRIORITIES:
        raise HTTPException(status_code=422, detail="Invalid priority")
    start = _as_date(ooo_starts_on)
    end = _as_date(ooo_ends_on)
    if start and end and end < start:
        raise HTTPException(status_code=422, detail="ooo_ends_on must be on or after ooo_starts_on")
    if notes is not None and not str(notes).strip():
        raise HTTPException(status_code=422, detail="Maintenance notes cannot be blank")
    row = m.HotelMaintenanceTicket(
        tenant_id=tenant_id,
        room_id=room.id,
        title=require_honest_narrative(title, label="title", max_length=150),
        priority=pri,
        status="open",
        block_room=bool(block_room),
        assigned_to=optional_honest_narrative(assigned_to, label="assigned to", max_length=150),
        notes=optional_honest_narrative(notes, label="notes", max_length=500),
        created_by=created_by,
    )
    if start is not None:
        row.ooo_starts_on = start
    if end is not None:
        row.ooo_ends_on = end
    db.add(row)
    today = date.today()
    active_now = bool(block_room) and (start is None or start <= today) and (end is None or end >= today)
    if active_now and room.status != "occupied":
        room.status = "out_of_order" if pri in {"high", "urgent"} else "maintenance"
        room.updated_at = datetime.utcnow()
    try:
        await db.flush()
    except (ProgrammingError, OperationalError) as exc:
        _raise_schema_behind(exc)
    return row, room


async def complete_maintenance_ticket(
    db: AsyncSession, *, tenant_id: str, ticket_id: str
) -> tuple[m.HotelMaintenanceTicket, m.HotelRoom]:
    row = (
        await db.execute(
            select(m.HotelMaintenanceTicket).where(
                m.HotelMaintenanceTicket.id == ticket_id,
                m.HotelMaintenanceTicket.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Maintenance ticket not found")
    if row.status == "completed":
        raise HTTPException(status_code=400, detail="Ticket already completed")
    room = await _get_room(db, tenant_id, row.room_id)
    row.status = "completed"
    row.completed_at = datetime.utcnow()
    row.updated_at = datetime.utcnow()
    # Return to service if no other open blocking tickets
    open_other = (
        await db.execute(
            select(m.HotelMaintenanceTicket).where(
                m.HotelMaintenanceTicket.tenant_id == tenant_id,
                m.HotelMaintenanceTicket.room_id == room.id,
                m.HotelMaintenanceTicket.id != row.id,
                m.HotelMaintenanceTicket.status.in_(("open", "in_progress")),
                m.HotelMaintenanceTicket.block_room.is_(True),
            )
        )
    ).scalar_one_or_none()
    if not open_other and room.status in {"maintenance", "out_of_order", "blocked"}:
        room.status = "available"
        room.housekeeping_status = "clean"
        room.updated_at = datetime.utcnow()
    await db.flush()
    return row, room


async def availability(
    db: AsyncSession,
    *,
    tenant_id: str,
    check_in_date: date,
    check_out_date: date,
    room_type: str | None = None,
) -> list[m.HotelRoom]:
    check_in = _as_date(check_in_date)
    check_out = _as_date(check_out_date)
    if not check_in or not check_out or check_out <= check_in:
        raise HTTPException(status_code=400, detail="Invalid date range")
    rooms = await list_rooms(db, tenant_id=tenant_id, is_active=True)
    type_key = (room_type or "").strip().lower()
    available: list[m.HotelRoom] = []
    for room in rooms:
        if type_key and room.room_type != type_key:
            continue
        if room.status in {"maintenance", "out_of_order", "blocked", "dirty"}:
            continue
        try:
            await _assert_room_available(
                db,
                tenant_id=tenant_id,
                room_id=room.id,
                check_in=check_in,
                check_out=check_out,
            )
        except HTTPException:
            continue
        available.append(room)
    return available


async def summary(db: AsyncSession, *, tenant_id: str, on_date: date | None = None) -> dict:
    rooms = await list_rooms(db, tenant_id=tenant_id, is_active=True)
    reservations = await list_reservations(db, tenant_id=tenant_id)
    today = _as_date(on_date) or date.today()
    booked = sum(1 for r, _, _ in reservations if r.status == "booked")
    tentative = sum(1 for r, _, _ in reservations if r.status == "tentative")
    online_stay_requests = sum(
        1
        for r, _, _ in reservations
        if r.status == "tentative" and (getattr(r, "booking_source", None) or "") == "online"
    )
    in_house = sum(1 for r, _, _ in reservations if r.status == "checked_in")
    cancelled = sum(1 for r, _, _ in reservations if r.status == "cancelled")
    no_show = sum(1 for r, _, _ in reservations if r.status == "no_show")
    waitlisted = sum(1 for r, _, _ in reservations if r.status == "waitlisted")
    arrivals_today = sum(
        1
        for r, _, _ in reservations
        if _as_date(r.check_in_date) == today and r.status in {"tentative", "booked", "checked_in"}
    )
    expected_arrivals = sum(
        1 for r, _, _ in reservations if _as_date(r.check_in_date) == today and r.status in {"tentative", "booked"}
    )
    departures_today = sum(1 for r, _, _ in reservations if _departure_day(r) == today)
    occupied = sum(1 for r in rooms if r.status == "occupied")
    total = len(rooms) or 1

    def _sold_on(day: date) -> int:
        return sum(
            1
            for r, _, _ in reservations
            if r.status not in {"cancelled", "no_show", "waitlisted"}
            and (_as_date(r.check_in_date) or date.max) <= day < (_operational_checkout(r) or date.min)
        )
    open_folios = await _optional_scalars(
        db,
        select(m.HotelFolio).where(m.HotelFolio.tenant_id == tenant_id, m.HotelFolio.status == "open"),
    )
    outstanding = 0.0
    for f in open_folios:
        outstanding = money_json(
            outstanding + await folio_balance(db, tenant_id=tenant_id, folio_id=f.id)
        )
    today_charges = await _optional_scalars(
        db,
        select(m.HotelFolioCharge).where(
            m.HotelFolioCharge.tenant_id == tenant_id,
            m.HotelFolioCharge.is_void.is_(False),
        ),
    )
    revenue_today = 0.0
    room_revenue = 0.0
    service_revenue = 0.0
    meal_revenue = 0.0
    drink_revenue = 0.0
    for ch in today_charges:
        created = ch.created_at.date() if ch.created_at else None
        if created == today:
            amt = money_json(ch.line_total or 0)
            revenue_today = money_json(revenue_today + amt)
            if ch.charge_type == "room":
                room_revenue = money_json(room_revenue + amt)
            else:
                service_revenue = money_json(service_revenue + amt)
                if ch.charge_type == "restaurant":
                    meal_revenue = money_json(meal_revenue + amt)
                elif ch.charge_type == "bar":
                    drink_revenue = money_json(drink_revenue + amt)
    payments_today = 0.0
    pays = await _optional_scalars(
        db, select(m.HotelFolioPayment).where(m.HotelFolioPayment.tenant_id == tenant_id)
    )
    for p in pays:
        created = p.created_at.date() if p.created_at else None
        if created == today:
            payments_today = money_json(payments_today + money_json(p.amount or 0))
    recent = []
    folio_schema_ok = True
    for r, room, guest in reservations[:8]:
        bal = None
        if folio_schema_ok:
            try:
                async with db.begin_nested():
                    folio = await get_folio_for_reservation(
                        db, tenant_id=tenant_id, reservation_id=r.id
                    )
                    if folio:
                        bal = await folio_balance(db, tenant_id=tenant_id, folio_id=folio.id)
            except (ProgrammingError, OperationalError):
                logger.warning("hotel folio lookup skipped", exc_info=True)
                folio_schema_ok = False
                bal = None
        recent.append(serialize_reservation(r, room=room, guest=guest, folio_balance=bal))
    hk_rows = await list_housekeeping(db, tenant_id=tenant_id)
    overdue_hk = sum(
        1
        for t, _ in hk_rows
        if t.status not in {"completed", "cancelled"}
        and (_due := _opt(t, "due_at")) is not None
        and _due < datetime.utcnow()
    )
    pending_hk = sum(1 for t, _ in hk_rows if t.status in {"pending", "in_progress"})
    maint_count_rows = await _optional_all(
        db,
        select(func.count())
        .select_from(m.HotelMaintenanceTicket)
        .where(
            m.HotelMaintenanceTicket.tenant_id == tenant_id,
            m.HotelMaintenanceTicket.status.in_(("open", "in_progress")),
        ),
    )
    maint_open = int(maint_count_rows[0][0]) if maint_count_rows else 0
    from app.catalog_meta import qty_is_low_stock, qty_is_out_of_stock

    low_stock = []
    none_left = []
    products = await _optional_scalars(
        db, select(m.Product).where(m.Product.tenant_id == tenant_id).limit(200)
    )
    for prod in products:
        qty = money_json(getattr(prod, "stock_qty", 0) or 0)
        row = {"id": prod.id, "name": prod.name, "stock_qty": money_json(qty)}
        if qty_is_out_of_stock(qty):
            none_left.append(row)
        elif qty_is_low_stock(
            qty,
            minimum_stock=getattr(prod, "minimum_stock", 0),
            reorder_level=getattr(prod, "reorder_level", 0),
        ):
            low_stock.append(row)
    def _n(n: int, one: str, many: str) -> str:
        return f"{n} {one if int(n) == 1 else many}"

    alerts: list[dict] = []
    dirty_n = sum(1 for r in rooms if r.status == "dirty" or r.housekeeping_status == "dirty")
    sold_night = _sold_on(today)
    from datetime import timedelta as _td

    occupancy_trend = []
    for i in range(13, -1, -1):
        day = today - _td(days=i)
        sold_i = _sold_on(day)
        occupancy_trend.append(
            {
                "date": day.isoformat(),
                "sold": sold_i,
                "occupancy_rate": round(100.0 * sold_i / total, 2),
            }
        )
    active_ids = {room.id for room in rooms}
    sold_ids: set[str] = set()
    occupied_ids: set[str] = set()
    for row, room, _guest in reservations:
        if room is None or room.id not in active_ids:
            continue
        if row.status in {"cancelled", "no_show", "waitlisted"}:
            continue
        start = _as_date(row.check_in_date)
        end = _operational_checkout(row)
        if not start or not end or not (start <= today < end):
            continue
        sold_ids.add(room.id)
        if row.status == "checked_in":
            occupied_ids.add(room.id)
    reserved_ids = sold_ids - occupied_ids
    ooo_ids: set[str] = set()
    dirty_ids: set[str] = set()
    for room in rooms:
        if room.id in sold_ids:
            continue
        if room.status in {"maintenance", "out_of_order", "blocked"}:
            ooo_ids.add(room.id)
        elif room.status == "dirty" or getattr(room, "housekeeping_status", None) == "dirty":
            dirty_ids.add(room.id)
    free_tonight = len(rooms) - len(sold_ids) - len(ooo_ids) - len(dirty_ids)
    room_status_mix = {
        "available": free_tonight,
        "occupied": len(occupied_ids),
        "reserved": len(reserved_ids),
        "dirty": len(dirty_ids),
        "out_of_service": len(ooo_ids),
    }
    reservation_status_mix = {
        "tentative": tentative,
        "booked": booked,
        "checked_in": in_house,
        "cancelled": cancelled,
        "no_show": no_show,
        "waitlisted": waitlisted,
        "checked_out": sum(1 for r, _, _ in reservations if r.status == "checked_out"),
    }
    if dirty_n:
        alerts.append({"code": "dirty_rooms", "href": "/hotel?tab=housekeeping", "message": _n(dirty_n, "room needs housekeeping", "rooms need housekeeping")})
    maint_n = sum(1 for r in rooms if r.status in {"maintenance", "out_of_order", "blocked"})
    if maint_n:
        alerts.append({"code": "maintenance", "href": "/hotel?tab=maintenance", "message": _n(maint_n, "room is out of service", "rooms are out of service")})
    if outstanding > 0.009:
        alerts.append(
            {
                "code": "unpaid_balances",
                "href": "/hotel?tab=billing",
                "message": f"Unpaid guest balances: {money_json(outstanding)}",
            }
        )
    if expected_arrivals:
        alerts.append({"code": "arrivals", "href": "/hotel?tab=front-desk", "message": _n(expected_arrivals, "expected arrival", "expected arrivals")})
    if overdue_hk:
        alerts.append({"code": "overdue_hk", "href": "/hotel?tab=housekeeping", "message": _n(overdue_hk, "overdue housekeeping task", "overdue housekeeping tasks")})
    if low_stock:
        alerts.append(
            {
                "code": "low_stock",
                "href": "/inventory?tab=lowstock",
                "message": _n(len(low_stock), "supply is low", "supplies are low"),
            }
        )
    if none_left:
        alerts.append(
            {
                "code": "out_of_stock",
                "href": "/inventory?tab=products",
                "message": _n(len(none_left), "supply has none left", "supplies have none left"),
            }
        )
    return {
        "as_of": today.isoformat(),
        "rooms_total": len(rooms),
        "rooms_available": free_tonight,
        "rooms_occupied": len(occupied_ids),
        "rooms_sold_night": sold_night,
        "rooms_reserved": len(reserved_ids),
        "rooms_dirty": dirty_n,
        "rooms_maintenance": maint_n,
        "occupancy_rate": round(100.0 * sold_night / total, 2),
        "physical_occupancy_rate": round(100.0 * occupied / total, 2),
        "room_status_mix": room_status_mix,
        "reservation_status_mix": reservation_status_mix,
        "occupancy_trend": occupancy_trend,
        "reservations_booked": booked,
        "reservations_tentative": tentative,
        "online_stay_requests": online_stay_requests,
        "reservations_in_house": in_house,
        "reservations_cancelled": cancelled,
        "reservations_no_show": no_show,
        "arrivals_today": arrivals_today,
        "expected_arrivals": expected_arrivals,
        "departures_today": departures_today,
        "open_folio_count": len(open_folios),
        "outstanding_folio_balance": money_json(outstanding),
        "revenue_today": money_json(revenue_today),
        "room_revenue": money_json(room_revenue),
        "service_revenue": money_json(service_revenue),
        "meal_revenue": money_json(meal_revenue),
        "drink_revenue": money_json(drink_revenue),
        "payments_received": money_json(payments_today),
        "housekeeping_pending": pending_hk,
        "housekeeping_overdue": overdue_hk,
        "maintenance_open": int(maint_open or 0),
        "low_stock": low_stock[:20],
        "out_of_stock": none_left[:20],
        "guests_total": len(await list_guests(db, tenant_id=tenant_id, is_active=True)),
        "recent_reservations": recent,
        "alerts": alerts,
    }



# --- R3: settings, multi-room groups, calendar, reports, print ---


_FOOD_OUTLET_MODES = frozenset({"together", "separate"})


def split_food_outlet(notes: str | None) -> tuple[str | None, str]:
    """The outlet choice is stored with the property note. The note itself stays plain."""
    if not notes:
        return None, "together"
    kept: list[str] = []
    mode = "together"
    for line in str(notes).splitlines():
        stripped = line.strip()
        if stripped.startswith("[[food-outlet:") and stripped.endswith("]]"):
            raw = stripped[len("[[food-outlet:") : -2].strip().lower()
            if raw in _FOOD_OUTLET_MODES:
                mode = raw
            continue
        kept.append(line)
    text = "\n".join(kept).strip()
    return (text or None), mode


def join_food_outlet(notes: str | None, mode: str) -> str | None:
    clean, _stored = split_food_outlet(notes)
    if mode == "separate":
        mark = "[[food-outlet:separate]]"
        return f"{clean}\n{mark}" if clean else mark
    return clean


def serialize_settings(row: m.HotelSettings) -> dict:
    notes, food_outlet_mode = split_food_outlet(row.notes)
    return {
        "id": row.id,
        "property_name": _opt(row, "property_name"),
        "check_in_time": row.check_in_time,
        "check_out_time": row.check_out_time,
        "cancellation_hours": int(row.cancellation_hours or 24),
        "no_show_fee_percent": money_json(row.no_show_fee_percent or 0),
        "early_checkin_fee": money_json(row.early_checkin_fee or 0),
        "late_checkout_fee": money_json(row.late_checkout_fee or 0),
        "tax_percent": money_json(row.tax_percent or 0),
        "service_charge_percent": money_json(row.service_charge_percent or 0),
        "food_outlet_mode": food_outlet_mode,
        "notes": notes,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def default_settings_payload() -> dict:
    return {
        "id": None,
        "property_name": None,
        "check_in_time": "14:00",
        "check_out_time": "11:00",
        "cancellation_hours": 24,
        "no_show_fee_percent": 0,
        "early_checkin_fee": 0,
        "late_checkout_fee": 0,
        "tax_percent": 0,
        "service_charge_percent": 0,
        "food_outlet_mode": "together",
        "notes": None,
        "updated_at": None,
    }


async def settings_payload(db: AsyncSession, *, tenant_id: str) -> dict:
    try:
        async with db.begin_nested():
            row = await get_or_create_settings(db, tenant_id=tenant_id)
            return serialize_settings(row)
    except (ProgrammingError, OperationalError):
        logger.warning("hotel settings schema skipped", exc_info=True)
        return default_settings_payload()


async def get_or_create_settings(db: AsyncSession, *, tenant_id: str) -> m.HotelSettings:
    row = (
        await db.execute(
            select(m.HotelSettings)
            .where(m.HotelSettings.tenant_id == tenant_id)
            .options(undefer(m.HotelSettings.property_name))
        )
    ).scalar_one_or_none()
    if row:
        return row
    row = m.HotelSettings(tenant_id=tenant_id)
    db.add(row)
    await db.flush()
    return row


async def update_settings(
    db: AsyncSession,
    *,
    tenant_id: str,
    check_in_time: str | None = None,
    check_out_time: str | None = None,
    cancellation_hours: int | None = None,
    no_show_fee_percent: float | None = None,
    early_checkin_fee: float | None = None,
    late_checkout_fee: float | None = None,
    tax_percent: float | None = None,
    service_charge_percent: float | None = None,
    notes: str | None = None,
    property_name: str | None = None,
    food_outlet_mode: str | None = None,
) -> m.HotelSettings:
    row = await get_or_create_settings(db, tenant_id=tenant_id)
    if check_in_time is not None:
        row.check_in_time = require_honest_narrative(check_in_time, label="check_in_time", max_length=8)
    if check_out_time is not None:
        row.check_out_time = require_honest_narrative(check_out_time, label="check_out_time", max_length=8)
    if cancellation_hours is not None:
        row.cancellation_hours = max(0, int(cancellation_hours))
    if no_show_fee_percent is not None:
        row.no_show_fee_percent = money_json(no_show_fee_percent)
    if early_checkin_fee is not None:
        row.early_checkin_fee = money_json(early_checkin_fee)
    if late_checkout_fee is not None:
        row.late_checkout_fee = money_json(late_checkout_fee)
    if tax_percent is not None:
        row.tax_percent = money_json(tax_percent)
    if service_charge_percent is not None:
        row.service_charge_percent = money_json(service_charge_percent)
    if notes is not None or food_outlet_mode is not None:
        current_notes, current_mode = split_food_outlet(row.notes)
        if notes is not None:
            if not str(notes).strip():
                raise HTTPException(status_code=422, detail="Hotel settings notes cannot be blank")
            human, _ignored = split_food_outlet(notes)
            if not human:
                raise HTTPException(status_code=422, detail="Hotel settings notes cannot be blank")
            current_notes = optional_honest_narrative(human, label="notes", max_length=1000)
        mode = current_mode
        if food_outlet_mode is not None:
            mode = str(food_outlet_mode).strip().lower()
            if mode not in _FOOD_OUTLET_MODES:
                raise HTTPException(status_code=422, detail="Food outlet mode must be together or separate")
        row.notes = join_food_outlet(current_notes, mode)
    if property_name is not None:
        row.property_name = optional_honest_narrative(property_name, label="property name", max_length=150)
    row.updated_at = datetime.utcnow()
    await db.flush()
    return row


async def _next_group_number(db: AsyncSession, tenant_id: str) -> str:
    year = datetime.utcnow().year
    prefix = f"HG-{year}-"
    count = (
        await db.execute(
            select(func.count())
            .select_from(m.HotelReservationGroup)
            .where(
                m.HotelReservationGroup.tenant_id == tenant_id,
                m.HotelReservationGroup.group_number.like(f"{prefix}%"),
            )
        )
    ).scalar_one()
    return f"{prefix}{int(count or 0) + 1:04d}"


async def create_group_reservation(
    db: AsyncSession,
    *,
    tenant_id: str,
    guest_id: str,
    room_ids: list[str],
    check_in_date: date,
    check_out_date: date,
    adults: int = 1,
    children: int = 0,
    booking_source: str = "corporate",
    name: str | None = None,
    notes: str | None = None,
    discount_percent: float = 0,
    discount_authorized_by: str | None = None,
    created_by: str | None = None,
) -> tuple[m.HotelReservationGroup, list[tuple[m.HotelReservation, m.HotelRoom, m.HotelGuest]]]:
    if not room_ids:
        raise HTTPException(status_code=422, detail="At least one room_id is required")
    if len(set(room_ids)) != len(room_ids):
        raise HTTPException(status_code=400, detail="Duplicate room_ids in group booking")
    if name is not None and not str(name).strip():
        raise HTTPException(status_code=422, detail="Group name cannot be blank")
    if notes is not None and not str(notes).strip():
        raise HTTPException(status_code=422, detail="Group notes cannot be blank")
    guest = await _get_guest(db, tenant_id, guest_id)
    group = m.HotelReservationGroup(
        tenant_id=tenant_id,
        group_number=await _next_group_number(db, tenant_id),
        guest_id=guest.id,
        name=optional_honest_narrative(name, label="group name", max_length=150),
        booking_source=(booking_source or "corporate").strip().lower(),
        notes=optional_honest_narrative(notes, label="notes", max_length=500),
        created_by=created_by,
    )
    db.add(group)
    try:
        await db.flush()
    except (ProgrammingError, OperationalError) as exc:
        _raise_schema_behind(exc)
    created: list[tuple[m.HotelReservation, m.HotelRoom, m.HotelGuest]] = []
    for room_id in room_ids:
        row, room, g = await create_reservation(
            db,
            tenant_id=tenant_id,
            room_id=room_id,
            guest_id=guest_id,
            check_in_date=check_in_date,
            check_out_date=check_out_date,
            adults=adults,
            children=children,
            booking_source=booking_source,
            notes=notes,
            discount_percent=discount_percent,
            discount_authorized_by=discount_authorized_by,
            created_by=created_by,
        )
        row.group_id = group.id
        created.append((row, room, g))
    await db.flush()
    return group, created


def serialize_group(
    group: m.HotelReservationGroup,
    *,
    reservations: list[dict] | None = None,
) -> dict:
    return {
        "id": group.id,
        "group_number": group.group_number,
        "guest_id": group.guest_id,
        "name": group.name,
        "booking_source": group.booking_source,
        "notes": group.notes,
        "reservations": reservations or [],
        "created_at": group.created_at.isoformat() if group.created_at else None,
    }


async def calendar(
    db: AsyncSession,
    *,
    tenant_id: str,
    start_date: date,
    end_date: date,
) -> dict:
    start = _as_date(start_date)
    end = _as_date(end_date)
    if not start or not end or end < start:
        raise HTTPException(status_code=400, detail="Invalid calendar date range")
    if (end - start).days > 62:
        raise HTTPException(status_code=400, detail="Calendar range max 62 days")
    rooms = await list_rooms(db, tenant_id=tenant_id, is_active=True)
    reservations = await list_reservations(db, tenant_id=tenant_id)
    days = []
    d = start
    from datetime import timedelta as _td
    while d <= end:
        days.append(d.isoformat())
        d = d + _td(days=1)
    grid = []
    for room in rooms:
        cells = {}
        for r, _, guest in reservations:
            if r.room_id != room.id or r.status in {"cancelled", "no_show", "waitlisted"}:
                continue
            cur = _as_date(r.check_in_date)
            checkout = _operational_checkout(r)
            if not cur or not checkout:
                continue
            while cur < checkout:
                key = cur.isoformat()
                if start <= cur <= end:
                    cells[key] = {
                        "reservation_id": r.id,
                        "reservation_number": r.reservation_number,
                        "status": r.status,
                        "guest_name": guest.full_name if guest else None,
                    }
                cur = cur + _td(days=1)
        grid.append({"room": serialize_room(room), "days": cells})
    return {"start_date": start.isoformat(), "end_date": end.isoformat(), "days": days, "rooms": grid}


async def reports(
    db: AsyncSession,
    *,
    tenant_id: str,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict:
    start = _as_date(start_date) or date.today().replace(day=1)
    end = _as_date(end_date) or date.today()
    if end < start:
        raise HTTPException(status_code=400, detail="end_date must be on or after start_date")
    rooms = await list_rooms(db, tenant_id=tenant_id, is_active=True)
    reservations = await list_reservations(db, tenant_id=tenant_id)
    room_nights_available = max(1, len(rooms) * max(1, (end - start).days + 1))
    occupied_nights = 0
    room_revenue = 0.0
    by_source: dict[str, float] = {}
    by_type: dict[str, float] = {}
    cancellations = 0
    no_shows = 0
    for r, room, _guest in reservations:
        check_in = _as_date(r.check_in_date)
        check_out = _as_date(r.check_out_date)
        if not check_in or not check_out:
            continue
        if r.status == "cancelled":
            if start <= check_in <= end:
                cancellations += 1
            continue
        if r.status == "no_show":
            if start <= check_in <= end:
                no_shows += 1
            continue
        if r.status == "waitlisted":
            continue
        # Count nights overlapping report window for checked_in/out/booked.
        # Rooms and reservations stay separate rows; extras (folios) are optional below.
        night = max(check_in, start)
        last = min(check_out, end + timedelta(days=1))
        while night < last and night <= end:
            if night >= start:
                occupied_nights += 1
                rate = money_json(r.nightly_rate or 0)
                room_revenue = money_json(room_revenue + rate)
                src = getattr(r, "booking_source", None) or "direct"
                by_source[src] = money_json(by_source.get(src, 0) + rate)
                rtype = room.room_type if room else "unknown"
                by_type[rtype] = money_json(by_type.get(rtype, 0) + rate)
            night = night + timedelta(days=1)
    occupancy = round(100.0 * occupied_nights / room_nights_available, 2)
    adr = round(room_revenue / occupied_nights, 2) if occupied_nights else 0.0
    revpar = round(room_revenue / room_nights_available, 2)
    charges = await _optional_scalars(
        db,
        select(m.HotelFolioCharge).where(
            m.HotelFolioCharge.tenant_id == tenant_id,
            m.HotelFolioCharge.is_void.is_(False),
        ),
    )
    payments = await _optional_scalars(
        db, select(m.HotelFolioPayment).where(m.HotelFolioPayment.tenant_id == tenant_id)
    )
    service_sales: dict[str, float] = {}
    payments_total = 0.0
    for ch in charges:
        created = ch.created_at.date() if ch.created_at else None
        if created and start <= created <= end:
            service_sales[ch.charge_type] = money_json(
                service_sales.get(ch.charge_type, 0) + money_json(ch.line_total or 0)
            )
    for p in payments:
        created = p.created_at.date() if p.created_at else None
        if created and start <= created <= end:
            payments_total = money_json(payments_total + money_json(p.amount or 0))
    outstanding = 0.0
    open_folios = await _optional_scalars(
        db,
        select(m.HotelFolio).where(m.HotelFolio.tenant_id == tenant_id, m.HotelFolio.status == "open"),
    )
    for f in open_folios:
        outstanding = money_json(
            outstanding + await folio_balance(db, tenant_id=tenant_id, folio_id=f.id)
        )
    inventory_usage: list[dict] = []
    products = await _optional_scalars(
        db,
        select(m.Product)
        .where(m.Product.tenant_id == tenant_id)
        .order_by(m.Product.name.asc())
        .limit(40),
    )
    for prod in products:
        inventory_usage.append(
            {
                "id": prod.id,
                "sku": getattr(prod, "sku", None),
                "name": prod.name,
                "stock_qty": money_json(getattr(prod, "stock_qty", 0) or 0),
            }
        )
    return {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "rooms_total": len(rooms),
        "room_nights_available": room_nights_available,
        "occupied_nights": occupied_nights,
        "occupancy_rate": occupancy,
        "room_revenue": money_json(room_revenue),
        "adr": money_json(adr),
        "revpar": money_json(revpar),
        "cancellations": cancellations,
        "no_shows": no_shows,
        "payments_total": money_json(payments_total),
        "outstanding_guest_balances": money_json(outstanding),
        "service_sales": {k: money_json(v) for k, v in sorted(service_sales.items())},
        "inventory_usage": inventory_usage,
        "revenue_by_source": {k: money_json(v) for k, v in sorted(by_source.items())},
        "revenue_by_room_type": {k: money_json(v) for k, v in sorted(by_type.items())},
    }


_SOURCE_WORDS = {
    "direct": "Direct",
    "walk_in": "Walk-in",
    "phone": "Phone",
    "corporate": "Corporate",
    "group": "Group",
    "ota": "OTA",
    "staff": "Staff",
    "online": "Online",
    "other": "Other",
}


def _source_line(row: m.HotelReservation) -> str:
    key = (getattr(row, "booking_source", None) or "direct").strip().lower()
    return f"Source: {_SOURCE_WORDS.get(key, key.replace('_', ' ').title())}"


def _deposit_line(row: m.HotelReservation) -> str:
    amount = money_json(getattr(row, "deposit_amount", 0) or 0)
    method = (getattr(row, "deposit_method", None) or "").strip().lower()
    words = {
        "cash": "cash",
        "momo": "mobile money",
        "card": "card",
        "bank": "bank transfer",
        "credit": "credit",
        "other": "other",
    }
    tender = words.get(method)
    if amount > 0 and tender:
        return f"Deposit: {amount} by {tender}"
    return f"Deposit: {amount}"


async def reservation_confirmation(
    db: AsyncSession, *, tenant_id: str, reservation_id: str
) -> dict:
    row, room, guest = await _get_reservation(db, tenant_id, reservation_id)
    settings = await get_or_create_settings(db, tenant_id=tenant_id)
    nights = max(0, (row.check_out_date - row.check_in_date).days)
    total = money_json((row.nightly_rate or 0) * nights)
    lines = [
        "RESERVATION CONFIRMATION",
        f"Number: {row.reservation_number}",
        f"Guest: {guest.full_name}",
    ]
    if (guest.phone or "").strip():
        lines.append(f"Phone: {guest.phone.strip()}")
    lines.extend(
        [
        _source_line(row),
        f"Room: {room.code} — {room.name} ({room.room_type})",
        f"Check-in: {row.check_in_date.isoformat()} from {settings.check_in_time}",
        f"Check-out: {row.check_out_date.isoformat()} by {settings.check_out_time}",
        f"Nights: {nights}",
        f"Adults/Children: {row.adults}/{row.children}",
        f"Nightly rate: {money_json(row.nightly_rate or 0)}",
        f"Estimated total: {money_json(total)}",
        _deposit_line(row),
        f"Status: {row.status}",
        f"Cancellation: cancel at least {settings.cancellation_hours}h before check-in",
        ]
    )
    if row.status == "checked_out":
        left = _as_date(row.checked_out_at)
        planned = _as_date(row.check_out_date)
        if left and planned and left < planned:
            lines.append(f"Left: {left.isoformat()}")
    if row.special_requests:
        lines.append(f"Special requests: {row.special_requests}")
    return {
        "reservation": serialize_reservation(row, room=room, guest=guest),
        "settings": serialize_settings(settings),
        "text": "\n".join(lines),
    }


SERVICE_CATEGORIES = frozenset({"restaurant", "bar", "laundry", "transport", "spa", "extra", "service"})


def serialize_service(row: m.HotelService) -> dict:
    return {
        "id": row.id,
        "code": row.code,
        "name": row.name,
        "category": row.category,
        "unit_amount": money_json(row.unit_amount or 0),
        "tax_percent": money_json(row.tax_percent or 0),
        "is_active": bool(row.is_active),
        "notes": row.notes,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


async def list_services(
    db: AsyncSession, *, tenant_id: str, is_active: bool | None = None
) -> list[m.HotelService]:
    stmt = select(m.HotelService).where(m.HotelService.tenant_id == tenant_id).order_by(m.HotelService.name)
    if is_active is not None:
        stmt = stmt.where(m.HotelService.is_active.is_(bool(is_active)))
    return await _scalars_or_schema_behind(db, stmt)


async def create_service(
    db: AsyncSession,
    *,
    tenant_id: str,
    code: str,
    name: str,
    category: str = "extra",
    unit_amount: float = 0,
    tax_percent: float = 0,
    notes: str | None = None,
) -> m.HotelService:
    cat = (category or "extra").strip().lower()
    if cat not in SERVICE_CATEGORIES:
        raise HTTPException(
            status_code=422, detail=f"category must be one of: {', '.join(sorted(SERVICE_CATEGORIES))}"
        )
    code_clean = require_honest_narrative(code, label="service code", max_length=40).upper()
    exists = await _one_or_schema_behind(
        db,
        select(m.HotelService).where(
            m.HotelService.tenant_id == tenant_id, m.HotelService.code == code_clean
        ),
    )
    if exists:
        raise HTTPException(status_code=409, detail="Service code already exists")
    if notes is not None and not str(notes).strip():
        raise HTTPException(status_code=422, detail="Hotel service notes cannot be blank")
    row = m.HotelService(
        tenant_id=tenant_id,
        code=code_clean,
        name=require_honest_narrative(name, label="service name", max_length=150),
        category=cat,
        unit_amount=money_json(unit_amount or 0),
        tax_percent=money_json(tax_percent or 0),
        notes=optional_honest_narrative(notes, label="notes", max_length=500),
        is_active=True,
    )
    db.add(row)
    await _flush_extra(db)
    return row


async def update_service(
    db: AsyncSession,
    *,
    tenant_id: str,
    service_id: str,
    name: str | None = None,
    category: str | None = None,
    unit_amount: float | None = None,
    tax_percent: float | None = None,
    is_active: bool | None = None,
    notes: str | None = None,
) -> m.HotelService:
    row = await _one_or_schema_behind(
        db,
        select(m.HotelService).where(
            m.HotelService.id == service_id, m.HotelService.tenant_id == tenant_id
        ),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Hotel service not found")
    if name is not None:
        row.name = require_honest_narrative(name, label="service name", max_length=150)
    if category is not None:
        cat = category.strip().lower()
        if cat not in SERVICE_CATEGORIES:
            raise HTTPException(status_code=422, detail="Invalid service category")
        row.category = cat
    if unit_amount is not None:
        row.unit_amount = money_json(unit_amount)
    if tax_percent is not None:
        row.tax_percent = money_json(tax_percent)
    if is_active is not None:
        row.is_active = bool(is_active)
    if notes is not None:
        if not str(notes).strip():
            raise HTTPException(status_code=422, detail="Hotel service notes cannot be blank")
        row.notes = optional_honest_narrative(notes, label="notes", max_length=500)
    row.updated_at = datetime.utcnow()
    await _flush_extra(db)
    return row


async def post_service_to_folio(
    db: AsyncSession,
    *,
    tenant_id: str,
    folio_id: str,
    service_id: str,
    quantity: float = 1,
    created_by: str | None = None,
) -> m.HotelFolioCharge:
    svc = await _one_or_schema_behind(
        db,
        select(m.HotelService).where(
            m.HotelService.id == service_id,
            m.HotelService.tenant_id == tenant_id,
            m.HotelService.is_active.is_(True),
        ),
    )
    if not svc:
        raise HTTPException(status_code=404, detail="Hotel service not found")
    qty = money_json(quantity or 1)
    if qty <= 0:
        raise HTTPException(status_code=422, detail="quantity must be greater than 0")
    unit = money_json(svc.unit_amount or 0)
    tax = money_json(unit * qty * money_json(svc.tax_percent or 0) / 100.0)
    charge_type = svc.category if svc.category in CHARGE_TYPES else "extra"
    return await add_folio_charge(
        db,
        tenant_id=tenant_id,
        folio_id=folio_id,
        charge_type=charge_type,
        description=f"{svc.name} ({svc.code})",
        quantity=qty,
        unit_amount=unit,
        tax_amount=tax,
        created_by=created_by,
    )


async def list_folios(
    db: AsyncSession, *, tenant_id: str, status: str | None = None
) -> list[tuple[m.HotelFolio, m.HotelReservation | None, m.HotelGuest | None]]:
    stmt = (
        select(m.HotelFolio, m.HotelReservation, m.HotelGuest)
        .outerjoin(m.HotelReservation, m.HotelReservation.id == m.HotelFolio.reservation_id)
        .outerjoin(m.HotelGuest, m.HotelGuest.id == m.HotelFolio.guest_id)
        .where(m.HotelFolio.tenant_id == tenant_id)
        .order_by(m.HotelFolio.opened_at.desc())
    )
    if status:
        stmt = stmt.where(m.HotelFolio.status == status.strip().lower())
    return [(f, r, g) for f, r, g in (await db.execute(stmt)).all()]


async def guest_history(db: AsyncSession, *, tenant_id: str, guest_id: str) -> dict:
    guest = await _get_guest(db, tenant_id, guest_id, require_active=False)
    rows = await list_reservations(db, tenant_id=tenant_id)
    stays = [
        serialize_reservation(r, room=room, guest=g)
        for r, room, g in rows
        if r.guest_id == guest.id
    ]
    folios = await list_folios(db, tenant_id=tenant_id)
    folio_rows = []
    balances = 0.0
    for folio, _res, g in folios:
        if folio.guest_id != guest.id:
            continue
        _f, charges, payments = await get_folio_detail(db, tenant_id=tenant_id, folio_id=folio.id)
        payload = serialize_folio(folio, charges=charges, payments=payments)
        folio_rows.append(payload)
        balances = money_json(balances + money_json(payload["balance"] or 0))
    return {
        "guest": serialize_guest(guest),
        "reservations": stays,
        "folios": folio_rows,
        "outstanding_balance": money_json(balances),
    }


HOTEL_BOOKING_LINK_KINDS = {"existing", "new"}


async def _has_table(db: AsyncSession, table: str) -> bool:
    conn = await db.connection()
    return await conn.run_sync(lambda sync_conn: sa_inspect(sync_conn).has_table(table))


async def _hotel_booking_tenant(db: AsyncSession, *, tenant_id: str | None = None, slug: str | None = None) -> m.Tenant:
    from app import packages as packages_svc

    stmt = select(m.Tenant)
    if tenant_id:
        stmt = stmt.where(m.Tenant.id == tenant_id)
    else:
        stmt = stmt.where(m.Tenant.slug == (slug or "").strip().lower())
    tenant = (await db.execute(stmt)).scalar_one_or_none()
    industry = packages_svc.canonicalize_industry(getattr(tenant, "industry", None) if tenant else None)
    if tenant is None or industry != "hotel":
        raise HTTPException(status_code=404, detail="Hotel booking is not available")
    return tenant


def _serialize_hotel_booking_link(tenant: m.Tenant, row: m.HotelBookingLink | None, *, installed: bool) -> dict:
    return {
        "slug": tenant.slug,
        "company_name": tenant.company_name,
        "path": f"/stay/{tenant.slug}",
        "hostname": row.hostname if row else None,
        "link_kind": row.link_kind if row else None,
        "open": row is not None,
        "installed": installed,
    }


async def get_hotel_booking_link(db: AsyncSession, tenant_id: str) -> dict:
    tenant = await _hotel_booking_tenant(db, tenant_id=tenant_id)
    if not await _has_table(db, "hotel_booking_links"):
        return _serialize_hotel_booking_link(tenant, None, installed=False)
    row = (
        await db.execute(select(m.HotelBookingLink).where(m.HotelBookingLink.tenant_id == tenant.id))
    ).scalar_one_or_none()
    return _serialize_hotel_booking_link(tenant, row, installed=True)


async def save_hotel_booking_link(db: AsyncSession, tenant_id: str, *, hostname: str, link_kind: str) -> dict:
    tenant = await _hotel_booking_tenant(db, tenant_id=tenant_id)
    if not await _has_table(db, "hotel_booking_links"):
        raise HTTPException(status_code=404, detail="Hotel booking is not available")
    kind = (link_kind or "").strip().lower()
    if kind not in HOTEL_BOOKING_LINK_KINDS:
        raise HTTPException(status_code=422, detail="Booking link must be an existing website or a new domain")
    host = hostname.strip().lower().rstrip(".")
    if host.startswith("www."):
        host = host[4:]
    taken = (
        await db.execute(
            select(m.HotelBookingLink).where(
                m.HotelBookingLink.hostname == host,
                m.HotelBookingLink.tenant_id != tenant.id,
            )
        )
    ).scalar_one_or_none()
    if taken is not None:
        raise HTTPException(status_code=409, detail="That website is already linked to another hotel")
    if await _has_table(db, "restaurant_booking_links"):
        restaurant_taken = (
            await db.execute(select(m.RestaurantBookingLink).where(m.RestaurantBookingLink.hostname == host))
        ).scalar_one_or_none()
        if restaurant_taken is not None:
            raise HTTPException(status_code=409, detail="That website is already linked to a restaurant")
    row = (
        await db.execute(select(m.HotelBookingLink).where(m.HotelBookingLink.tenant_id == tenant.id))
    ).scalar_one_or_none()
    if row is None:
        row = m.HotelBookingLink(tenant_id=tenant.id, hostname=host, link_kind=kind)
        db.add(row)
    else:
        row.hostname = host
        row.link_kind = kind
        row.updated_at = datetime.utcnow()
    await db.flush()
    return _serialize_hotel_booking_link(tenant, row, installed=True)


async def hotel_booking_page(db: AsyncSession, slug: str) -> dict:
    tenant = await _hotel_booking_tenant(db, slug=slug)
    if not await _has_table(db, "hotel_booking_links"):
        raise HTTPException(status_code=404, detail="Hotel booking is not open")
    row = (
        await db.execute(select(m.HotelBookingLink).where(m.HotelBookingLink.tenant_id == tenant.id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Hotel booking is not open")
    return _serialize_hotel_booking_link(tenant, row, installed=True)


async def hotel_booking_page_for_host(db: AsyncSession, hostname: str) -> dict:
    host = (hostname or "").strip().lower().rstrip(".")
    if host.startswith("www."):
        host = host[4:]
    if not await _has_table(db, "hotel_booking_links"):
        raise HTTPException(status_code=404, detail="Hotel booking is not open")
    row = (
        await db.execute(select(m.HotelBookingLink).where(m.HotelBookingLink.hostname == host))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Hotel booking is not open")
    return await _hotel_booking_page_by_tenant(db, row.tenant_id)


async def _hotel_booking_page_by_tenant(db: AsyncSession, tenant_id: str) -> dict:
    tenant = await _hotel_booking_tenant(db, tenant_id=tenant_id)
    row = (
        await db.execute(select(m.HotelBookingLink).where(m.HotelBookingLink.tenant_id == tenant.id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Hotel booking is not open")
    return _serialize_hotel_booking_link(tenant, row, installed=True)


def _preview_nightly(room: m.HotelRoom, check_in: date, check_out: date, adults: int, children: int) -> float:
    rate = money_json(room.rate_amount or 0)
    weekend = getattr(room, "weekend_rate", None)
    if weekend is not None:
        night = check_in
        while night < check_out:
            if night.weekday() >= 5:
                rate = money_json(weekend)
                break
            night = night + timedelta(days=1)
    occ = max(1, int(adults or 1)) + max(0, int(children or 0))
    included = 1 if int(room.max_occupancy or 1) <= 1 else 2
    extra_people = max(0, occ - included)
    extra_each = money_json(getattr(room, "extra_person_charge", 0) or 0)
    if extra_people and extra_each > 0:
        rate = money_json(rate + (extra_people * extra_each))
    return rate


async def _room_free_for_stay(db: AsyncSession, tenant_id: str, room: m.HotelRoom, check_in: date, check_out: date) -> bool:
    if room.status in {"maintenance", "out_of_order", "blocked", "dirty"} or not room.is_active:
        return False
    clash = (
        await db.execute(
            select(m.HotelReservation.id).where(
                m.HotelReservation.tenant_id == tenant_id,
                m.HotelReservation.room_id == room.id,
                m.HotelReservation.status.in_(ACTIVE_BOOKING_STATUSES),
                m.HotelReservation.check_in_date < check_out,
                m.HotelReservation.check_out_date > check_in,
            ).limit(1)
        )
    ).scalar_one_or_none()
    if clash is not None:
        return False
    tickets = await _optional_scalars(
        db,
        select(m.HotelMaintenanceTicket).where(
            m.HotelMaintenanceTicket.tenant_id == tenant_id,
            m.HotelMaintenanceTicket.room_id == room.id,
            m.HotelMaintenanceTicket.block_room.is_(True),
            m.HotelMaintenanceTicket.status.in_(("open", "in_progress")),
        ),
    )
    return not list(tickets)


def _stay_dates(check_in_date: str, check_out_date: str) -> tuple[date, date]:
    check_in = _as_date(check_in_date)
    check_out = _as_date(check_out_date)
    if not check_in or not check_out:
        raise HTTPException(status_code=422, detail="check_in_date and check_out_date are required")
    if check_in < datetime.utcnow().date():
        raise HTTPException(status_code=422, detail="Check-in must be today or later")
    if check_out <= check_in:
        raise HTTPException(status_code=422, detail="Check-out must be after check-in")
    return check_in, check_out


async def public_available_rooms(
    db: AsyncSession,
    slug: str,
    *,
    check_in_date: str,
    check_out_date: str,
    adults: int,
    children: int,
) -> list[dict]:
    tenant = await _hotel_booking_tenant(db, slug=slug)
    await hotel_booking_page(db, slug)
    check_in, check_out = _stay_dates(check_in_date, check_out_date)
    occ = max(1, int(adults or 1)) + max(0, int(children or 0))
    rooms = await list_rooms(db, tenant_id=tenant.id, is_active=True)
    nights = max(1, (check_out - check_in).days)
    found = []
    for room in rooms:
        if occ > int(room.max_occupancy or 1):
            continue
        if not await _room_free_for_stay(db, tenant.id, room, check_in, check_out):
            continue
        nightly = _preview_nightly(room, check_in, check_out, adults, children)
        found.append(
            {
                "id": room.id,
                "code": room.code,
                "name": room.name,
                "room_type": room.room_type,
                "max_occupancy": int(room.max_occupancy or 1),
                "nightly_rate": nightly,
                "nights": nights,
            }
        )
    return found


async def create_public_stay(
    db: AsyncSession,
    slug: str,
    *,
    guest_name: str,
    phone: str,
    email: str | None,
    check_in_date: str,
    check_out_date: str,
    adults: int,
    children: int,
    room_id: str,
    notes: str | None,
) -> dict:
    tenant = await _hotel_booking_tenant(db, slug=slug)
    await hotel_booking_page(db, slug)
    check_in, check_out = _stay_dates(check_in_date, check_out_date)
    name = require_honest_narrative(guest_name, label="guest name", min_length=1, max_length=150)
    phone_clean = (phone or "").strip()
    existing = (
        await db.execute(
            select(m.HotelGuest).where(
                m.HotelGuest.tenant_id == tenant.id,
                m.HotelGuest.phone == phone_clean,
                func.lower(m.HotelGuest.full_name) == name.lower(),
                m.HotelGuest.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        guest = await create_guest(
            db,
            tenant_id=tenant.id,
            full_name=name,
            phone=phone_clean,
            email=(email or "").strip().lower() or None,
        )
    else:
        guest = existing
    reservation, room, guest = await create_reservation(
        db,
        tenant_id=tenant.id,
        room_id=room_id,
        guest_id=guest.id,
        check_in_date=check_in,
        check_out_date=check_out,
        adults=adults,
        children=children,
        booking_source="online",
        special_requests=notes,
        deposit_amount=0,
        status="tentative",
    )
    return serialize_reservation(reservation, room=room, guest=guest)

