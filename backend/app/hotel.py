"""Hotel module — rooms, guests, reservations, folio, housekeeping, maintenance."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.honesty import money_json, optional_honest_narrative, require_honest_narrative

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
RESERVATION_STATUSES = frozenset({"booked", "checked_in", "checked_out", "cancelled", "no_show"})
ROOM_TYPES = frozenset({"standard", "deluxe", "suite", "family", "other"})
BOOKING_SOURCES = frozenset({"direct", "walk_in", "ota", "corporate", "phone", "other"})
CHARGE_TYPES = frozenset(
    {"room", "restaurant", "laundry", "service", "damage", "extra", "tax", "discount", "adjustment"}
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
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def serialize_reservation(
    row: m.HotelReservation,
    *,
    room: m.HotelRoom | None = None,
    guest: m.HotelGuest | None = None,
    folio_id: str | None = None,
    folio_balance: float | None = None,
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
        "booking_source": getattr(row, "booking_source", None) or "direct",
        "special_requests": getattr(row, "special_requests", None),
        "nightly_rate": money_json(row.nightly_rate or 0),
        "deposit_amount": money_json(getattr(row, "deposit_amount", 0) or 0),
        "deposit_method": getattr(row, "deposit_method", None),
        "group_id": getattr(row, "group_id", None),
        "estimated_total": money_json(Decimal(str(row.nightly_rate or 0)) * nights),
        "notes": row.notes,
        "folio_id": folio_id,
        "folio_balance": money_json(folio_balance) if folio_balance is not None else None,
        "checked_in_at": row.checked_in_at.isoformat() if row.checked_in_at else None,
        "checked_out_at": row.checked_out_at.isoformat() if row.checked_out_at else None,
        "cancelled_at": row.cancelled_at.isoformat() if row.cancelled_at else None,
        "no_show_at": row.no_show_at.isoformat() if getattr(row, "no_show_at", None) else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "can_check_in": row.status == "booked",
        "can_check_out": row.status == "checked_in",
        "can_cancel": row.status == "booked",
        "can_no_show": row.status == "booked",
        "can_extend": row.status in {"booked", "checked_in"},
        "can_move": row.status in {"booked", "checked_in"},
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
    charge_total = sum(float(c.line_total or 0) for c in charge_rows if not c.is_void)
    payment_total = sum(float(p.amount or 0) for p in payment_rows)
    return {
        "id": row.id,
        "reservation_id": row.reservation_id,
        "guest_id": row.guest_id,
        "folio_number": row.folio_number,
        "status": row.status,
        "notes": row.notes,
        "charges_total": money_json(charge_total),
        "payments_total": money_json(payment_total),
        "balance": money_json(charge_total - payment_total),
        "charges": [serialize_charge(c) for c in charge_rows],
        "payments": [serialize_payment(p) for p in payment_rows],
        "opened_at": row.opened_at.isoformat() if row.opened_at else None,
        "closed_at": row.closed_at.isoformat() if row.closed_at else None,
    }


def serialize_hk_task(row: m.HotelHousekeepingTask, *, room_code: str | None = None) -> dict:
    return {
        "id": row.id,
        "room_id": row.room_id,
        "room_code": room_code,
        "task_type": row.task_type,
        "priority": row.priority,
        "status": row.status,
        "assigned_to": row.assigned_to,
        "notes": row.notes,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def serialize_maint(row: m.HotelMaintenanceTicket, *, room_code: str | None = None) -> dict:
    return {
        "id": row.id,
        "room_id": row.room_id,
        "room_code": room_code,
        "title": row.title,
        "priority": row.priority,
        "status": row.status,
        "block_room": bool(row.block_room),
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
    row = m.HotelRoom(
        tenant_id=tenant_id,
        code=code_clean.upper(),
        name=name_clean,
        room_type=type_key,
        floor=optional_honest_narrative(floor, label="floor", max_length=40),
        bed_type=optional_honest_narrative(bed_type, label="bed type", max_length=40),
        max_occupancy=max(1, int(max_occupancy or 1)),
        rate_amount=rate_amount or 0,
        weekend_rate=weekend_rate,
        extra_person_charge=extra_person_charge or 0,
        amenities=amenities or {},
        description=optional_honest_narrative(description, label="description", max_length=2000),
        status=status_key,
        housekeeping_status="clean",
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
        row.rate_amount = rate_amount
    if weekend_rate is not None:
        row.weekend_rate = weekend_rate
    if extra_person_charge is not None:
        row.extra_person_charge = extra_person_charge
    if amenities is not None:
        row.amenities = amenities
    if description is not None:
        row.description = optional_honest_narrative(description, label="description", max_length=2000)
    if status is not None:
        status_key = status.strip().lower()
        if status_key not in ROOM_STATUSES:
            raise HTTPException(status_code=422, detail="Invalid room status")
        row.status = status_key
    if housekeeping_status is not None:
        hk = housekeeping_status.strip().lower()
        if hk not in HOUSEKEEPING_STATUSES:
            raise HTTPException(status_code=422, detail="Invalid housekeeping_status")
        row.housekeeping_status = hk
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
    db.add(row)
    await db.flush()
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
    if is_active is not None:
        row.is_active = bool(is_active)
    row.updated_at = datetime.utcnow()
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


async def _get_room(db: AsyncSession, tenant_id: str, room_id: str) -> m.HotelRoom:
    row = (
        await db.execute(
            select(m.HotelRoom).where(m.HotelRoom.id == room_id, m.HotelRoom.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
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
    day = on_date or date.today()
    kind = (list_kind or "").strip().lower()
    if kind == "arrivals":
        stmt = stmt.where(
            m.HotelReservation.check_in_date == day,
            m.HotelReservation.status.in_(("booked", "checked_in")),
        )
    elif kind == "departures":
        stmt = stmt.where(
            m.HotelReservation.check_out_date == day,
            m.HotelReservation.status.in_(("checked_in", "checked_out")),
        )
    elif kind == "in_house":
        stmt = stmt.where(m.HotelReservation.status == "checked_in")
    elif kind == "upcoming":
        stmt = stmt.where(
            m.HotelReservation.status == "booked",
            m.HotelReservation.check_in_date >= day,
        )
    elif kind == "cancelled":
        stmt = stmt.where(m.HotelReservation.status == "cancelled")
    elif kind == "no_show":
        stmt = stmt.where(m.HotelReservation.status == "no_show")
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
    booking_source: str = "direct",
    special_requests: str | None = None,
    deposit_amount: float = 0,
    deposit_method: str | None = None,
    notes: str | None = None,
    created_by: str | None = None,
    walk_in: bool = False,
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
    if room.status in {"maintenance", "out_of_order", "blocked"}:
        raise HTTPException(status_code=409, detail=f"Room is {room.status.replace('_', ' ')}")
    if room.status == "dirty":
        raise HTTPException(status_code=409, detail="Room is dirty — complete housekeeping first")
    source = (booking_source or ("walk_in" if walk_in else "direct")).strip().lower()
    if source not in BOOKING_SOURCES:
        raise HTTPException(status_code=422, detail="Invalid booking_source")
    if deposit_method and deposit_method.strip().lower() not in PAYMENT_METHODS:
        raise HTTPException(status_code=422, detail="Invalid deposit_method")
    if nightly_rate is not None:
        rate = float(nightly_rate)
    else:
        # Prefer weekend rate for stays that include Sat/Sun nights when configured.
        rate = float(room.rate_amount or 0)
        weekend = getattr(room, "weekend_rate", None)
        if weekend is not None:
            d = check_in
            while d < check_out:
                if d.weekday() >= 5:  # Sat/Sun
                    rate = float(weekend)
                    break
                from datetime import timedelta as _td
                d = d + _td(days=1)
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
        booking_source=source,
        special_requests=optional_honest_narrative(
            special_requests, label="special requests", max_length=1000
        ),
        nightly_rate=rate,
        deposit_amount=deposit_amount or 0,
        deposit_method=(deposit_method or "").strip().lower() or None,
        notes=optional_honest_narrative(notes, label="notes", max_length=500),
        created_by=created_by,
    )
    db.add(row)
    if room.status in {"available", "clean", "inspected"}:
        room.status = "reserved"
        room.updated_at = datetime.utcnow()
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
        unit_amount=float(reservation.nightly_rate or 0),
        created_by=created_by,
    )
    deposit = float(getattr(reservation, "deposit_amount", 0) or 0)
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


async def folio_balance(db: AsyncSession, *, tenant_id: str, folio_id: str) -> float:
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
    return sum(float(c.line_total or 0) for c in charges) - sum(float(p.amount or 0) for p in payments)


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
    qty = float(quantity or 1)
    unit = float(unit_amount or 0)
    tax = float(tax_amount or 0)
    disc = float(discount_amount or 0)
    line_total = round(qty * unit + tax - disc, 2)
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
    if float(amount or 0) <= 0:
        raise HTTPException(status_code=422, detail="Payment amount must be positive")
    row = m.HotelFolioPayment(
        tenant_id=tenant_id,
        folio_id=folio_id,
        method=method_key,
        amount=float(amount),
        reference=optional_honest_narrative(reference, label="reference", max_length=120),
        notes=optional_honest_narrative(notes, label="notes", max_length=500),
        recorded_by=recorded_by,
    )
    db.add(row)
    folio.updated_at = datetime.utcnow()
    await db.flush()
    return row


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
    await db.flush()
    return row, room, guest, folio


async def check_out(
    db: AsyncSession,
    *,
    tenant_id: str,
    reservation_id: str,
    allow_balance: bool = False,
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
            notes=f"Auto-created after checkout of {row.reservation_number}",
        )
    )
    await db.flush()
    return row, room, guest, folio


async def cancel_reservation(
    db: AsyncSession, *, tenant_id: str, reservation_id: str
) -> tuple[m.HotelReservation, m.HotelRoom, m.HotelGuest]:
    row, room, guest = await _get_reservation(db, tenant_id, reservation_id)
    if row.status != "booked":
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
    if row.status not in {"booked", "checked_in"}:
        raise HTTPException(status_code=400, detail="Can only extend booked or in-house stays")
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
                unit_amount=float(row.nightly_rate or 0),
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
    if row.status not in {"booked", "checked_in"}:
        raise HTTPException(status_code=400, detail="Can only move booked or in-house stays")
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
        .order_by(m.HotelHousekeepingTask.created_at.desc())
    )
    if status:
        stmt = stmt.where(m.HotelHousekeepingTask.status == status.strip().lower())
    return [(t, r) for t, r in (await db.execute(stmt)).all()]


async def create_housekeeping_task(
    db: AsyncSession,
    *,
    tenant_id: str,
    room_id: str,
    task_type: str = "cleaning",
    priority: str = "normal",
    assigned_to: str | None = None,
    notes: str | None = None,
    created_by: str | None = None,
) -> tuple[m.HotelHousekeepingTask, m.HotelRoom]:
    room = await _get_room(db, tenant_id, room_id)
    pri = (priority or "normal").strip().lower()
    if pri not in HK_PRIORITIES:
        raise HTTPException(status_code=422, detail="Invalid priority")
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
    if room.status in {"dirty", "clean", "inspected", "available"}:
        room.status = "available" if mark_inspected or room.housekeeping_status == "clean" else room.status
        if room.housekeeping_status in {"clean", "inspected"} and room.status == "dirty":
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
        .order_by(m.HotelMaintenanceTicket.created_at.desc())
    )
    if status:
        stmt = stmt.where(m.HotelMaintenanceTicket.status == status.strip().lower())
    return [(t, r) for t, r in (await db.execute(stmt)).all()]


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
) -> tuple[m.HotelMaintenanceTicket, m.HotelRoom]:
    room = await _get_room(db, tenant_id, room_id)
    pri = (priority or "normal").strip().lower()
    if pri not in HK_PRIORITIES:
        raise HTTPException(status_code=422, detail="Invalid priority")
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
    db.add(row)
    if block_room and room.status != "occupied":
        room.status = "out_of_order" if pri in {"high", "urgent"} else "maintenance"
        room.updated_at = datetime.utcnow()
    await db.flush()
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
) -> list[m.HotelRoom]:
    check_in = _as_date(check_in_date)
    check_out = _as_date(check_out_date)
    if not check_in or not check_out or check_out <= check_in:
        raise HTTPException(status_code=400, detail="Invalid date range")
    rooms = await list_rooms(db, tenant_id=tenant_id, is_active=True)
    available: list[m.HotelRoom] = []
    for room in rooms:
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


async def summary(db: AsyncSession, *, tenant_id: str) -> dict:
    rooms = await list_rooms(db, tenant_id=tenant_id, is_active=True)
    reservations = await list_reservations(db, tenant_id=tenant_id)
    today = date.today()
    booked = sum(1 for r, _, _ in reservations if r.status == "booked")
    in_house = sum(1 for r, _, _ in reservations if r.status == "checked_in")
    arrivals_today = sum(
        1 for r, _, _ in reservations if r.check_in_date == today and r.status in {"booked", "checked_in"}
    )
    departures_today = sum(
        1
        for r, _, _ in reservations
        if r.check_out_date == today and r.status in {"checked_in", "checked_out"}
    )
    occupied = sum(1 for r in rooms if r.status == "occupied")
    total = len(rooms) or 1
    open_folios = (
        await db.execute(
            select(m.HotelFolio).where(
                m.HotelFolio.tenant_id == tenant_id, m.HotelFolio.status == "open"
            )
        )
    ).scalars().all()
    outstanding = 0.0
    for f in open_folios:
        outstanding += await folio_balance(db, tenant_id=tenant_id, folio_id=f.id)
    return {
        "rooms_total": len(rooms),
        "rooms_available": sum(1 for r in rooms if r.status in {"available", "clean", "inspected"}),
        "rooms_occupied": occupied,
        "rooms_reserved": sum(1 for r in rooms if r.status == "reserved"),
        "rooms_dirty": sum(1 for r in rooms if r.status == "dirty" or r.housekeeping_status == "dirty"),
        "rooms_maintenance": sum(1 for r in rooms if r.status in {"maintenance", "out_of_order", "blocked"}),
        "reservations_booked": booked,
        "reservations_in_house": in_house,
        "arrivals_today": arrivals_today,
        "departures_today": departures_today,
        "occupancy_rate": round(100.0 * occupied / total, 2),
        "outstanding_folio_balance": money_json(outstanding),
        "guests_total": len(await list_guests(db, tenant_id=tenant_id, is_active=True)),
    }



# --- R3: settings, multi-room groups, calendar, reports, print ---


def serialize_settings(row: m.HotelSettings) -> dict:
    return {
        "id": row.id,
        "check_in_time": row.check_in_time,
        "check_out_time": row.check_out_time,
        "cancellation_hours": int(row.cancellation_hours or 24),
        "no_show_fee_percent": money_json(row.no_show_fee_percent or 0),
        "early_checkin_fee": money_json(row.early_checkin_fee or 0),
        "late_checkout_fee": money_json(row.late_checkout_fee or 0),
        "tax_percent": money_json(row.tax_percent or 0),
        "service_charge_percent": money_json(row.service_charge_percent or 0),
        "notes": row.notes,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


async def get_or_create_settings(db: AsyncSession, *, tenant_id: str) -> m.HotelSettings:
    row = (
        await db.execute(select(m.HotelSettings).where(m.HotelSettings.tenant_id == tenant_id))
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
) -> m.HotelSettings:
    row = await get_or_create_settings(db, tenant_id=tenant_id)
    if check_in_time is not None:
        row.check_in_time = require_honest_narrative(check_in_time, label="check_in_time", max_length=8)
    if check_out_time is not None:
        row.check_out_time = require_honest_narrative(check_out_time, label="check_out_time", max_length=8)
    if cancellation_hours is not None:
        row.cancellation_hours = max(0, int(cancellation_hours))
    if no_show_fee_percent is not None:
        row.no_show_fee_percent = float(no_show_fee_percent)
    if early_checkin_fee is not None:
        row.early_checkin_fee = float(early_checkin_fee)
    if late_checkout_fee is not None:
        row.late_checkout_fee = float(late_checkout_fee)
    if tax_percent is not None:
        row.tax_percent = float(tax_percent)
    if service_charge_percent is not None:
        row.service_charge_percent = float(service_charge_percent)
    if notes is not None:
        row.notes = optional_honest_narrative(notes, label="notes", max_length=1000)
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
    created_by: str | None = None,
) -> tuple[m.HotelReservationGroup, list[tuple[m.HotelReservation, m.HotelRoom, m.HotelGuest]]]:
    if not room_ids:
        raise HTTPException(status_code=422, detail="At least one room_id is required")
    if len(set(room_ids)) != len(room_ids):
        raise HTTPException(status_code=400, detail="Duplicate room_ids in group booking")
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
    await db.flush()
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
            if r.room_id != room.id or r.status in {"cancelled", "no_show"}:
                continue
            cur = r.check_in_date
            while cur < r.check_out_date:
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
        if r.status == "cancelled":
            if start <= r.check_in_date <= end:
                cancellations += 1
            continue
        if r.status == "no_show":
            if start <= r.check_in_date <= end:
                no_shows += 1
            continue
        # Count nights overlapping report window for checked_in/out/booked
        night = max(r.check_in_date, start)
        last = min(r.check_out_date, end + __import__("datetime").timedelta(days=1))
        while night < last and night <= end:
            if night >= start:
                occupied_nights += 1
                room_revenue += float(r.nightly_rate or 0)
                src = getattr(r, "booking_source", None) or "direct"
                by_source[src] = by_source.get(src, 0) + float(r.nightly_rate or 0)
                rtype = room.room_type if room else "unknown"
                by_type[rtype] = by_type.get(rtype, 0) + float(r.nightly_rate or 0)
            night = night + __import__("datetime").timedelta(days=1)
    occupancy = round(100.0 * occupied_nights / room_nights_available, 2)
    adr = round(room_revenue / occupied_nights, 2) if occupied_nights else 0.0
    revpar = round(room_revenue / room_nights_available, 2)
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
        "revenue_by_source": {k: money_json(v) for k, v in sorted(by_source.items())},
        "revenue_by_room_type": {k: money_json(v) for k, v in sorted(by_type.items())},
    }


async def reservation_confirmation(
    db: AsyncSession, *, tenant_id: str, reservation_id: str
) -> dict:
    row, room, guest = await _get_reservation(db, tenant_id, reservation_id)
    settings = await get_or_create_settings(db, tenant_id=tenant_id)
    nights = max(0, (row.check_out_date - row.check_in_date).days)
    total = float(row.nightly_rate or 0) * nights
    lines = [
        f"RESERVATION CONFIRMATION",
        f"Number: {row.reservation_number}",
        f"Guest: {guest.full_name}",
        f"Room: {room.code} — {room.name} ({room.room_type})",
        f"Check-in: {row.check_in_date.isoformat()} from {settings.check_in_time}",
        f"Check-out: {row.check_out_date.isoformat()} by {settings.check_out_time}",
        f"Nights: {nights}",
        f"Adults/Children: {row.adults}/{row.children}",
        f"Nightly rate: {money_json(row.nightly_rate or 0)}",
        f"Estimated total: {money_json(total)}",
        f"Deposit: {money_json(getattr(row, 'deposit_amount', 0) or 0)}",
        f"Status: {row.status}",
        f"Cancellation: cancel at least {settings.cancellation_hours}h before check-in",
    ]
    if row.special_requests:
        lines.append(f"Special requests: {row.special_requests}")
    return {
        "reservation": serialize_reservation(row, room=room, guest=guest),
        "settings": serialize_settings(settings),
        "text": "\n".join(lines),
    }

