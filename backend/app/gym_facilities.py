"""Gym facilities (sauna, pool, studio, court) and member bookings by the slot.

Rules: a booking is inside the facility's opening hours (company local time), in the future, no
longer than the facility allows, only for a member with an active membership, never overlapping
another live booking of the same member, and never above the facility's capacity for any moment.
The facility row is locked while booking so two desks cannot take the last place together.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import gym as base
from app import models as m
from app.gym import _audit, _member
from app.gym_access import _HHMM, usable_branch
from app.honesty import require_honest_narrative
from app.hotel import hotel_zone

LIVE = ("booked", "attended")


def present_facility(row: m.GymFacility) -> dict:
    return {
        "id": row.id, "name": row.name, "kind": row.kind, "capacity": int(row.capacity), "open_time": row.open_time, "close_time": row.close_time,
        "max_minutes": int(row.max_minutes), "branch_id": row.branch_id, "is_active": bool(row.is_active),
    }


async def create_facility(db: AsyncSession, tenant_id: str, payload, *, user_id) -> dict:
    if not _HHMM.match(payload.open_time) or not _HHMM.match(payload.close_time) or payload.open_time >= payload.close_time:
        raise HTTPException(status_code=422, detail="Opening time must be before closing time, like 06:00 and 22:00")
    if payload.branch_id:
        await usable_branch(db, tenant_id, payload.branch_id)
    name = require_honest_narrative(payload.name, label="facility name", max_length=120)
    if (await db.execute(select(m.GymFacility.id).where(m.GymFacility.tenant_id == tenant_id, m.GymFacility.name == name))).first():
        raise HTTPException(status_code=409, detail="A facility with this name already exists")
    row = m.GymFacility(
        tenant_id=tenant_id, name=name, kind=payload.kind, capacity=payload.capacity, open_time=payload.open_time, close_time=payload.close_time,
        max_minutes=payload.max_minutes, branch_id=payload.branch_id,
    )
    db.add(row)
    await db.flush()
    await _audit(db, tenant_id, user_id, "gym_facility_created", "gym_facility", row.id, {"name": name})
    return present_facility(row)


async def list_facilities(db: AsyncSession, tenant_id: str, *, active_only: bool = False) -> list[dict]:
    stmt = select(m.GymFacility).where(m.GymFacility.tenant_id == tenant_id).order_by(m.GymFacility.name)
    if active_only:
        stmt = stmt.where(m.GymFacility.is_active.is_(True))
    return [present_facility(r) for r in (await db.execute(stmt)).scalars().all()]


async def set_active(db: AsyncSession, tenant_id: str, facility_id: str, *, active: bool, user_id) -> dict:
    row = await db.get(m.GymFacility, facility_id)
    if row is None or row.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Facility not found")
    row.is_active = active
    await db.flush()
    await _audit(db, tenant_id, user_id, "gym_facility_active" if active else "gym_facility_inactive", "gym_facility", row.id, {})
    return present_facility(row)


def present_booking(b: m.GymFacilityBooking, facility: m.GymFacility, member: m.GymMember) -> dict:
    return {
        "id": b.id, "facility_id": facility.id, "facility": facility.name, "member_id": member.id, "member_name": member.full_name,
        "starts_at": b.starts_at.isoformat(), "ends_at": b.ends_at.isoformat(), "status": b.status,
    }


async def book(db: AsyncSession, tenant_id: str, facility_id: str, *, member_id: str, starts_at: datetime, minutes: int, user_id) -> dict:
    facility = (
        await db.execute(select(m.GymFacility).where(m.GymFacility.id == facility_id, m.GymFacility.tenant_id == tenant_id).with_for_update())
    ).scalar_one_or_none()
    if facility is None:
        raise HTTPException(status_code=404, detail="Facility not found")
    if not facility.is_active:
        raise HTTPException(status_code=409, detail=f"{facility.name} is closed for booking")
    if minutes < 15 or minutes > int(facility.max_minutes):
        raise HTTPException(status_code=422, detail=f"A booking runs 15 to {facility.max_minutes} minutes here")
    start = starts_at.astimezone(timezone.utc).replace(tzinfo=None) if starts_at.tzinfo else starts_at
    end = start + timedelta(minutes=minutes)
    if start < datetime.utcnow() - timedelta(minutes=5):
        raise HTTPException(status_code=422, detail="Choose a time that has not passed")
    zone = await hotel_zone(db, tenant_id)
    ls, le = start.replace(tzinfo=timezone.utc).astimezone(zone), end.replace(tzinfo=timezone.utc).astimezone(zone)
    if ls.date() != le.date() or ls.strftime("%H:%M") < facility.open_time or le.strftime("%H:%M") > facility.close_time:
        raise HTTPException(status_code=409, detail=f"{facility.name} is open {facility.open_time} to {facility.close_time}")
    member = await _member(db, tenant_id, member_id)
    if base._state(await base._latest(db, tenant_id, member.id), date.today()) != "active":
        raise HTTPException(status_code=409, detail=f"{member.full_name} has no active membership")
    live = (
        await db.execute(
            select(m.GymFacilityBooking).where(
                m.GymFacilityBooking.tenant_id == tenant_id, m.GymFacilityBooking.status.in_(LIVE),
                m.GymFacilityBooking.starts_at < end, m.GymFacilityBooking.ends_at > start,
            )
        )
    ).scalars().all()
    if any(b.member_id == member.id for b in live):
        raise HTTPException(status_code=409, detail=f"{member.full_name} already has a booking at that time")
    same = [b for b in live if b.facility_id == facility.id]
    # The busiest moment inside the slot decides whether there is still a place.
    points = sorted({start, *[b.starts_at for b in same if b.starts_at > start]})
    busiest = max((sum(1 for b in same if b.starts_at <= t < b.ends_at) for t in points), default=0)
    if busiest >= int(facility.capacity):
        raise HTTPException(status_code=409, detail=f"{facility.name} is full at that time")
    row = m.GymFacilityBooking(tenant_id=tenant_id, facility_id=facility.id, member_id=member.id, starts_at=start, ends_at=end, created_by=user_id)
    db.add(row)
    await db.flush()
    await _audit(db, tenant_id, user_id, "gym_facility_booked", "gym_facility", facility.id, {"member_id": member.id})
    return present_booking(row, facility, member)


async def list_bookings(db: AsyncSession, tenant_id: str, *, day: date | None = None, member_id: str | None = None) -> list[dict]:
    stmt = (
        select(m.GymFacilityBooking, m.GymFacility, m.GymMember)
        .join(m.GymFacility, m.GymFacility.id == m.GymFacilityBooking.facility_id)
        .join(m.GymMember, m.GymMember.id == m.GymFacilityBooking.member_id)
        .where(m.GymFacilityBooking.tenant_id == tenant_id)
        .order_by(m.GymFacilityBooking.starts_at)
        .limit(500)
    )
    if day:
        lo = datetime.combine(day, datetime.min.time())
        stmt = stmt.where(m.GymFacilityBooking.starts_at >= lo, m.GymFacilityBooking.starts_at < lo + timedelta(days=1))
    else:
        stmt = stmt.where(m.GymFacilityBooking.starts_at >= datetime.combine(date.today(), datetime.min.time()))
    if member_id:
        stmt = stmt.where(m.GymFacilityBooking.member_id == member_id)
    return [present_booking(b, f, mem) for b, f, mem in (await db.execute(stmt)).all()]


async def set_booking(db: AsyncSession, tenant_id: str, booking_id: str, *, status: str, user_id, member_id: str | None = None) -> dict:
    row = (
        await db.execute(select(m.GymFacilityBooking).where(m.GymFacilityBooking.id == booking_id, m.GymFacilityBooking.tenant_id == tenant_id).with_for_update())
    ).scalar_one_or_none()
    if row is None or (member_id is not None and row.member_id != member_id):
        raise HTTPException(status_code=404, detail="Booking not found")
    if row.status != "booked":
        raise HTTPException(status_code=409, detail=f"This booking is already {row.status.replace('_', ' ')}")
    row.status = status
    await db.flush()
    await _audit(db, tenant_id, user_id, f"gym_facility_booking_{status}", "gym_facility", row.facility_id, {"booking_id": row.id})
    return present_booking(row, await db.get(m.GymFacility, row.facility_id), await db.get(m.GymMember, row.member_id))
