"""Hotel PMS extensions — rate plans, requests, cashier, night audit."""

from __future__ import annotations

from datetime import date, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.honesty import money_json, optional_honest_narrative, require_honest_narrative


async def _pms_scalars(db: AsyncSession, stmt) -> list:
    try:
        async with db.begin_nested():
            return list((await db.execute(stmt)).scalars().all())
    except (ProgrammingError, OperationalError):
        return []


def serialize_rate_plan(row: m.HotelRatePlan) -> dict:
    return {
        "id": row.id,
        "code": row.code,
        "name": row.name,
        "room_type": row.room_type,
        "amount": money_json(row.amount or 0),
        "weekday_only": bool(row.weekday_only),
        "weekend_only": bool(row.weekend_only),
        "min_nights": int(row.min_nights or 1),
        "starts_on": row.starts_on.isoformat() if row.starts_on else None,
        "ends_on": row.ends_on.isoformat() if row.ends_on else None,
        "is_active": bool(row.is_active),
    }


async def list_rate_plans(db: AsyncSession, *, tenant_id: str, is_active: bool | None = None):
    stmt = select(m.HotelRatePlan).where(m.HotelRatePlan.tenant_id == tenant_id).order_by(m.HotelRatePlan.code)
    if is_active is not None:
        stmt = stmt.where(m.HotelRatePlan.is_active.is_(bool(is_active)))
    return await _pms_scalars(db, stmt)


async def create_rate_plan(
    db: AsyncSession,
    *,
    tenant_id: str,
    code: str,
    name: str,
    amount: float = 0,
    room_type: str | None = None,
    weekday_only: bool = False,
    weekend_only: bool = False,
    min_nights: int = 1,
    starts_on: date | None = None,
    ends_on: date | None = None,
) -> m.HotelRatePlan:
    row = m.HotelRatePlan(
        tenant_id=tenant_id,
        code=require_honest_narrative(code, label="code", max_length=40).upper(),
        name=require_honest_narrative(name, label="name", max_length=150),
        room_type=(room_type or "").strip().lower() or None,
        amount=float(amount or 0),
        weekday_only=bool(weekday_only),
        weekend_only=bool(weekend_only),
        min_nights=max(1, int(min_nights or 1)),
        starts_on=starts_on,
        ends_on=ends_on,
        is_active=True,
    )
    db.add(row)
    await db.flush()
    return row


def serialize_guest_request(row: m.HotelGuestRequest) -> dict:
    return {
        "id": row.id,
        "reservation_id": row.reservation_id,
        "room_id": row.room_id,
        "kind": row.kind,
        "title": row.title,
        "status": row.status,
        "due_at": getattr(row, "due_at", None).isoformat() if getattr(row, "due_at", None) else None,
        "notes": row.notes,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


async def list_guest_requests(db: AsyncSession, *, tenant_id: str, status: str | None = None):
    stmt = (
        select(m.HotelGuestRequest)
        .where(m.HotelGuestRequest.tenant_id == tenant_id)
        .order_by(m.HotelGuestRequest.created_at.desc())
    )
    if status:
        stmt = stmt.where(m.HotelGuestRequest.status == status.strip().lower())
    return await _pms_scalars(db, stmt)


async def create_guest_request(
    db: AsyncSession,
    *,
    tenant_id: str,
    title: str,
    kind: str = "service",
    reservation_id: str | None = None,
    room_id: str | None = None,
    notes: str | None = None,
    created_by: str | None = None,
) -> m.HotelGuestRequest:
    kind_key = (kind or "service").strip().lower()
    if kind_key not in {"service", "wake_up", "note", "complaint"}:
        raise HTTPException(status_code=422, detail="Invalid request kind")
    row = m.HotelGuestRequest(
        tenant_id=tenant_id,
        reservation_id=reservation_id,
        room_id=room_id,
        kind=kind_key,
        title=require_honest_narrative(title, label="title", max_length=150),
        status="open",
        notes=optional_honest_narrative(notes, label="notes", max_length=500),
        created_by=created_by,
    )
    db.add(row)
    await db.flush()
    return row


async def complete_guest_request(db: AsyncSession, *, tenant_id: str, request_id: str) -> m.HotelGuestRequest:
    row = (
        await db.execute(
            select(m.HotelGuestRequest).where(
                m.HotelGuestRequest.id == request_id, m.HotelGuestRequest.tenant_id == tenant_id
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Guest request not found")
    row.status = "completed"
    row.updated_at = datetime.utcnow()
    await db.flush()
    return row


def serialize_lost_found(row: m.HotelLostFound) -> dict:
    return {
        "id": row.id,
        "room_id": row.room_id,
        "kind": row.kind,
        "description": row.description,
        "status": row.status,
        "notes": row.notes,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


async def list_lost_found(db: AsyncSession, *, tenant_id: str):
    stmt = (
        select(m.HotelLostFound)
        .where(m.HotelLostFound.tenant_id == tenant_id)
        .order_by(m.HotelLostFound.created_at.desc())
    )
    return await _pms_scalars(db, stmt)


async def create_lost_found(
    db: AsyncSession,
    *,
    tenant_id: str,
    description: str,
    kind: str = "lost",
    room_id: str | None = None,
    notes: str | None = None,
    created_by: str | None = None,
) -> m.HotelLostFound:
    kind_key = (kind or "lost").strip().lower()
    if kind_key not in {"lost", "found", "damage"}:
        raise HTTPException(status_code=422, detail="kind must be lost, found, or damage")
    row = m.HotelLostFound(
        tenant_id=tenant_id,
        room_id=room_id,
        kind=kind_key,
        description=require_honest_narrative(description, label="description", max_length=500),
        status="open",
        notes=optional_honest_narrative(notes, label="notes", max_length=500),
        created_by=created_by,
    )
    db.add(row)
    await db.flush()
    return row


def serialize_shift(row: m.HotelCashierShift) -> dict:
    return {
        "id": row.id,
        "opened_by": row.opened_by,
        "opened_at": row.opened_at.isoformat() if row.opened_at else None,
        "opening_float": money_json(row.opening_float or 0),
        "closed_by": row.closed_by,
        "closed_at": row.closed_at.isoformat() if row.closed_at else None,
        "closing_float": money_json(row.closing_float) if row.closing_float is not None else None,
        "payments_total": money_json(row.payments_total or 0),
        "notes": row.notes,
        "status": row.status,
    }


async def current_shift(db: AsyncSession, *, tenant_id: str) -> m.HotelCashierShift | None:
    rows = await _pms_scalars(
        db,
        select(m.HotelCashierShift)
        .where(m.HotelCashierShift.tenant_id == tenant_id, m.HotelCashierShift.status == "open")
        .order_by(m.HotelCashierShift.opened_at.desc()),
    )
    return rows[0] if rows else None


async def open_shift(
    db: AsyncSession, *, tenant_id: str, user_id: str, opening_float: float = 0
) -> m.HotelCashierShift:
    existing = await current_shift(db, tenant_id=tenant_id)
    if existing:
        raise HTTPException(status_code=409, detail="A cashier shift is already open")
    row = m.HotelCashierShift(
        tenant_id=tenant_id,
        opened_by=user_id,
        opening_float=float(opening_float or 0),
        status="open",
    )
    db.add(row)
    await db.flush()
    return row


async def close_shift(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    closing_float: float = 0,
    notes: str | None = None,
) -> m.HotelCashierShift:
    row = await current_shift(db, tenant_id=tenant_id)
    if not row:
        raise HTTPException(status_code=404, detail="No open cashier shift")
    payments = (
        await db.execute(
            select(m.HotelFolioPayment).where(
                m.HotelFolioPayment.tenant_id == tenant_id,
                m.HotelFolioPayment.created_at >= row.opened_at,
            )
        )
    ).scalars().all()
    total = sum(float(p.amount or 0) for p in payments)
    row.closed_by = user_id
    row.closed_at = datetime.utcnow()
    row.closing_float = float(closing_float or 0)
    row.payments_total = total
    row.notes = optional_honest_narrative(notes, label="notes", max_length=500)
    row.status = "closed"
    await db.flush()
    return row


def serialize_night_audit(row: m.HotelNightAudit) -> dict:
    return {
        "id": row.id,
        "business_date": row.business_date.isoformat(),
        "snapshot": row.snapshot or {},
        "created_by": row.created_by,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


async def list_night_audits(db: AsyncSession, *, tenant_id: str, limit: int = 30):
    stmt = (
        select(m.HotelNightAudit)
        .where(m.HotelNightAudit.tenant_id == tenant_id)
        .order_by(m.HotelNightAudit.business_date.desc())
        .limit(limit)
    )
    return await _pms_scalars(db, stmt)


async def run_night_audit(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str | None,
    snapshot: dict,
    business_date: date | None = None,
) -> m.HotelNightAudit:
    day = business_date or date.today()
    existing = (
        await db.execute(
            select(m.HotelNightAudit).where(
                m.HotelNightAudit.tenant_id == tenant_id,
                m.HotelNightAudit.business_date == day,
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Night audit already posted for this business date")
    row = m.HotelNightAudit(
        tenant_id=tenant_id,
        business_date=day,
        snapshot=snapshot,
        created_by=user_id,
    )
    db.add(row)
    await db.flush()
    return row


EVENT_STATUSES = frozenset({"inquiry", "confirmed", "cancelled", "completed"})


def serialize_event(row: m.HotelEvent) -> dict:
    return {
        "id": row.id,
        "title": row.title,
        "space_name": row.space_name,
        "starts_on": row.starts_on.isoformat() if row.starts_on else None,
        "ends_on": row.ends_on.isoformat() if row.ends_on else None,
        "expected_guests": int(row.expected_guests or 1),
        "status": row.status,
        "room_id": row.room_id,
        "guest_id": row.guest_id,
        "deposit_amount": money_json(row.deposit_amount or 0),
        "notes": row.notes,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


async def list_events(db: AsyncSession, *, tenant_id: str, status: str | None = None):
    stmt = (
        select(m.HotelEvent)
        .where(m.HotelEvent.tenant_id == tenant_id)
        .order_by(m.HotelEvent.starts_on.desc(), m.HotelEvent.created_at.desc())
    )
    if status:
        stmt = stmt.where(m.HotelEvent.status == status.strip().lower())
    return await _pms_scalars(db, stmt)


async def create_event(
    db: AsyncSession,
    *,
    tenant_id: str,
    title: str,
    space_name: str,
    starts_on: date | str,
    ends_on: date | str,
    expected_guests: int = 1,
    room_id: str | None = None,
    guest_id: str | None = None,
    deposit_amount: float = 0,
    notes: str | None = None,
    status: str = "inquiry",
    created_by: str | None = None,
) -> m.HotelEvent:
    st = (status or "inquiry").strip().lower()
    if st not in {"inquiry", "confirmed"}:
        raise HTTPException(status_code=422, detail="Invalid event status")
    from app.hotel import HOTEL_FEATURE_UNAVAILABLE, _as_date, _assert_room_available

    start = _as_date(starts_on)
    end = _as_date(ends_on)
    if not start or not end or end <= start:
        raise HTTPException(status_code=400, detail="Event end date must be after start date")
    if room_id:
        await _assert_room_available(
            db,
            tenant_id=tenant_id,
            room_id=room_id,
            check_in=start,
            check_out=end,
        )
    row = m.HotelEvent(
        tenant_id=tenant_id,
        title=require_honest_narrative(title, label="event title", max_length=150),
        space_name=require_honest_narrative(space_name, label="space name", max_length=120),
        starts_on=start,
        ends_on=end,
        expected_guests=max(1, int(expected_guests or 1)),
        status=st,
        room_id=room_id or None,
        guest_id=guest_id or None,
        deposit_amount=float(deposit_amount or 0),
        notes=optional_honest_narrative(notes, label="notes", max_length=500),
        created_by=created_by,
    )
    db.add(row)
    try:
        await db.flush()
    except (ProgrammingError, OperationalError) as exc:
        raise HTTPException(status_code=503, detail=HOTEL_FEATURE_UNAVAILABLE) from exc
    return row


async def set_event_status(
    db: AsyncSession, *, tenant_id: str, event_id: str, status: str
) -> m.HotelEvent:
    row = (
        await db.execute(
            select(m.HotelEvent).where(
                m.HotelEvent.id == event_id, m.HotelEvent.tenant_id == tenant_id
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Event not found")
    st = (status or "").strip().lower()
    if st not in EVENT_STATUSES:
        raise HTTPException(status_code=422, detail="Invalid event status")
    row.status = st
    row.updated_at = datetime.utcnow()
    await db.flush()
    return row
