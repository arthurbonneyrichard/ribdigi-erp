"""HRM time: shifts, the roster, clocking in and out, the daily sheet and overtime.

- Clock times are stored in UTC; shifts are in the company's local time (Tenant.timezone).
- A clock-in from a phone can be required to happen at a work site: within the site's GPS
  radius (with a usable accuracy) or by scanning the site's QR code, which changes every
  five minutes. GPS can be faked on a rooted phone; the QR code and the stored distance
  and accuracy are the checks we have. Biometric devices are not connected.
- Clock events are never edited. HR entries and approved corrections void the day's events
  and add new ones, so the audit shows both.
- The daily sheet works out hours, lateness, leaving early, absence and overtime from the
  roster and the clock. A month's overtime is paid only after HR approves it.
"""

from __future__ import annotations

import hashlib
import hmac
import math
import secrets
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.honesty import money_json, optional_honest_narrative, require_honest_narrative

QR_WINDOW_SECONDS = 300
WORST_GPS_ACCURACY_M = 200


# --- Pure helpers --------------------------------------------------------------------------


def parse_hhmm(text: str) -> time:
    try:
        hh, mm = text.split(":")
        value = time(int(hh), int(mm))
    except (ValueError, AttributeError) as exc:
        raise HTTPException(status_code=422, detail="Times are HH:MM, 24-hour") from exc
    return value


def shift_window(starts_at: str, ends_at: str, day: date, zone: ZoneInfo) -> tuple[datetime, datetime]:
    """The shift's start and end in naive UTC. An end earlier than the start is the next day."""
    start_local = datetime.combine(day, parse_hhmm(starts_at), tzinfo=zone)
    end_local = datetime.combine(day, parse_hhmm(ends_at), tzinfo=zone)
    if end_local <= start_local:
        end_local += timedelta(days=1)
    to_utc = lambda d: d.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)  # noqa: E731
    return to_utc(start_local), to_utc(end_local)


def local_day_bounds(day: date, zone: ZoneInfo) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time(0, 0), tzinfo=zone).astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
    return start, start + timedelta(days=1)


def distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def qr_code(secret: str, at: datetime) -> str:
    window = int(at.timestamp()) // QR_WINDOW_SECONDS
    digest = hmac.new(secret.encode(), str(window).encode(), hashlib.sha256).hexdigest()
    return digest[:8].upper()


def qr_valid(secret: str, code: str, at: datetime) -> bool:
    code = (code or "").strip().upper()
    if len(code) != 8:
        return False
    return any(
        hmac.compare_digest(qr_code(secret, at - timedelta(seconds=QR_WINDOW_SECONDS * back)), code)
        for back in (0, 1)
    )


@dataclass
class DaySheet:
    status: str  # present | late | absent | on_leave | off | still_in
    first_in: datetime | None
    last_out: datetime | None
    worked_minutes: int
    late_minutes: int
    early_minutes: int
    overtime_minutes: int


def compute_day(
    *,
    events: list[tuple[str, datetime]],
    window: tuple[datetime, datetime] | None,
    break_minutes: int,
    grace_minutes: int,
    hours_per_day: float,
    on_leave: bool,
    now: datetime,
) -> DaySheet:
    """events: (kind, utc) in time order, voided ones already left out."""
    worked = 0
    open_in: datetime | None = None
    first_in = last_out = None
    for kind, at in events:
        if kind == "in":
            if open_in is None:
                open_in = at
                first_in = first_in or at
        elif kind == "out" and open_in is not None:
            worked += int((at - open_in).total_seconds() // 60)
            last_out = at
            open_in = None
    still_in = open_in is not None
    if window is not None and worked > 0:
        worked = max(worked - int(break_minutes or 0), 0)
    late = early = overtime = 0
    if window is not None:
        start, end = window
        if first_in and first_in > start + timedelta(minutes=int(grace_minutes or 0)):
            late = int((first_in - start).total_seconds() // 60)
        if last_out and not still_in and last_out < end:
            early = int((end - last_out).total_seconds() // 60)
        expected = int((end - start).total_seconds() // 60) - int(break_minutes or 0)
        overtime = max(worked - expected, 0)
    else:
        overtime = max(worked - int(float(hours_per_day) * 60), 0) if worked else 0
    if on_leave and not first_in:
        status = "on_leave"
    elif still_in:
        status = "still_in"
    elif first_in:
        status = "late" if late else "present"
    elif window is not None and now > window[0] + timedelta(minutes=int(grace_minutes or 0)):
        status = "absent"
    elif window is not None:
        status = "due"
    else:
        status = "off"
    return DaySheet(status, first_in, last_out, worked, late, early, overtime)


# --- Database work -------------------------------------------------------------------------


async def _hrm():
    from app import hrm

    return hrm


async def _zone(db: AsyncSession, tenant_id: str) -> ZoneInfo:
    tenant = await db.get(m.Tenant, tenant_id)
    try:
        return ZoneInfo((tenant.timezone if tenant else None) or "Africa/Accra")
    except Exception:  # noqa: BLE001 - a bad stored zone falls back to Accra (UTC+0)
        return ZoneInfo("Africa/Accra")


async def _audit(db, tenant_id, user_id, action, entity, entity_id, details):
    hrm = await _hrm()
    await hrm._audit(db, tenant_id, user_id, action, entity, entity_id, details)


def serialize_shift(row: m.HrmShift) -> dict:
    return {
        "id": row.id, "name": row.name, "starts_at": row.starts_at, "ends_at": row.ends_at,
        "break_minutes": row.break_minutes, "grace_minutes": row.grace_minutes, "is_active": bool(row.is_active),
    }


async def list_shifts(db: AsyncSession, tenant_id: str) -> list[m.HrmShift]:
    return list((await db.execute(select(m.HrmShift).where(m.HrmShift.tenant_id == tenant_id).order_by(m.HrmShift.starts_at))).scalars())


async def add_shift(db: AsyncSession, tenant_id: str, payload, *, user_id) -> m.HrmShift:
    start, end = parse_hhmm(payload.starts_at), parse_hhmm(payload.ends_at)
    length = (datetime.combine(date.today(), end) - datetime.combine(date.today(), start)).total_seconds() // 60
    if length <= 0:
        length += 24 * 60
    if payload.break_minutes >= length:
        raise HTTPException(status_code=422, detail="The break is as long as the shift")
    row = m.HrmShift(
        tenant_id=tenant_id, name=require_honest_narrative(payload.name, label="shift name", max_length=80),
        starts_at=start.strftime("%H:%M"), ends_at=end.strftime("%H:%M"),
        break_minutes=payload.break_minutes, grace_minutes=payload.grace_minutes, is_active=True,
    )
    db.add(row)
    await db.flush()
    await _audit(db, tenant_id, user_id, "hrm_shift_added", "hrm_shift", row.id, serialize_shift(row))
    return row


async def retire_shift(db: AsyncSession, tenant_id: str, shift_id: str, *, user_id) -> m.HrmShift:
    row = await db.get(m.HrmShift, shift_id)
    if row is None or row.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Shift not found")
    row.is_active = False
    await _audit(db, tenant_id, user_id, "hrm_shift_retired", "hrm_shift", row.id, {})
    await db.flush()
    return row


async def set_roster(db: AsyncSession, tenant_id: str, payload, *, user_id) -> int:
    """Put people on a shift (or take them off) for each chosen weekday between two dates."""
    hrm = await _hrm()
    if payload.end < payload.start:
        raise HTTPException(status_code=422, detail="The end date is before the start")
    if (payload.end - payload.start).days > 92:
        raise HTTPException(status_code=422, detail="Roster up to three months at a time")
    shift = None
    if payload.shift_id:
        shift = await db.get(m.HrmShift, payload.shift_id)
        if shift is None or shift.tenant_id != tenant_id or not shift.is_active:
            raise HTTPException(status_code=404, detail="Shift not found")
    people = [await hrm._employee(db, tenant_id, eid) for eid in payload.employee_ids]
    weekdays = set(payload.weekdays)
    count = 0
    day = payload.start
    while day <= payload.end:
        if day.weekday() in weekdays:
            for person in people:
                row = (
                    await db.execute(
                        select(m.HrmRoster).where(m.HrmRoster.employee_id == person.id, m.HrmRoster.day == day)
                    )
                ).scalar_one_or_none()
                if shift is None:
                    if row is not None:
                        await db.delete(row)
                        count += 1
                    continue
                if row is None:
                    db.add(m.HrmRoster(tenant_id=tenant_id, employee_id=person.id, day=day, shift_id=shift.id, created_by=user_id))
                else:
                    row.shift_id = shift.id
                count += 1
        day += timedelta(days=1)
    await db.flush()
    await _audit(
        db, tenant_id, user_id, "hrm_roster_set", "hrm_roster", payload.shift_id or "off",
        {"start": payload.start.isoformat(), "end": payload.end.isoformat(), "people": len(people), "days": count},
    )
    return count


async def roster_between(db: AsyncSession, tenant_id: str, start: date, end: date) -> list[dict]:
    rows = (
        await db.execute(
            select(m.HrmRoster, m.HrmShift, m.HrmEmployee)
            .join(m.HrmShift, m.HrmShift.id == m.HrmRoster.shift_id)
            .join(m.HrmEmployee, m.HrmEmployee.id == m.HrmRoster.employee_id)
            .where(m.HrmRoster.tenant_id == tenant_id, m.HrmRoster.day >= start, m.HrmRoster.day <= end)
            .order_by(m.HrmRoster.day, m.HrmEmployee.full_name)
        )
    ).all()
    return [
        {"day": r.day.isoformat(), "employee_id": e.id, "employee_name": e.full_name, "shift_id": s.id, "shift": s.name, "starts_at": s.starts_at, "ends_at": s.ends_at}
        for r, s, e in rows
    ]


# --- Sites ---------------------------------------------------------------------------------


def serialize_site(row: m.HrmSite) -> dict:
    return {
        "id": row.id, "name": row.name,
        "latitude": money_json(row.latitude) if row.latitude is not None else None,
        "longitude": money_json(row.longitude) if row.longitude is not None else None,
        "radius_m": row.radius_m, "is_active": bool(row.is_active),
    }


async def list_sites(db: AsyncSession, tenant_id: str) -> list[m.HrmSite]:
    return list((await db.execute(select(m.HrmSite).where(m.HrmSite.tenant_id == tenant_id).order_by(m.HrmSite.name))).scalars())


async def add_site(db: AsyncSession, tenant_id: str, payload, *, user_id) -> m.HrmSite:
    if (payload.latitude is None) != (payload.longitude is None):
        raise HTTPException(status_code=422, detail="Give both latitude and longitude, or neither")
    row = m.HrmSite(
        tenant_id=tenant_id, name=require_honest_narrative(payload.name, label="site name", max_length=120),
        latitude=payload.latitude, longitude=payload.longitude, radius_m=payload.radius_m,
        qr_secret=secrets.token_hex(24), is_active=True,
    )
    db.add(row)
    await db.flush()
    await _audit(db, tenant_id, user_id, "hrm_site_added", "hrm_site", row.id, serialize_site(row))
    return row


async def site_qr(db: AsyncSession, tenant_id: str, site_id: str) -> dict:
    row = await db.get(m.HrmSite, site_id)
    if row is None or row.tenant_id != tenant_id or not row.is_active:
        raise HTTPException(status_code=404, detail="Site not found")
    now = datetime.utcnow()
    window = int(now.timestamp()) // QR_WINDOW_SECONDS
    changes_at = datetime.utcfromtimestamp((window + 1) * QR_WINDOW_SECONDS)
    import base64

    from app.barcodes import render_qr_png

    code = qr_code(row.qr_secret, now)
    # Drawn here, so the code never goes to an outside QR service.
    image = "data:image/png;base64," + base64.b64encode(render_qr_png(code, box_size=8)).decode("ascii")
    return {"site_id": row.id, "site": row.name, "code": code, "image": image, "changes_at": changes_at.isoformat()}


# --- Clocking ------------------------------------------------------------------------------


def serialize_event(row: m.HrmClockEvent) -> dict:
    return {
        "id": row.id, "employee_id": row.employee_id, "kind": row.kind, "at": row.at.isoformat() + "Z",
        "source": row.source, "site_id": row.site_id,
        "distance_m": money_json(row.distance_m) if row.distance_m is not None else None,
        "accuracy_m": money_json(row.accuracy_m) if row.accuracy_m is not None else None,
        "note": row.note, "voided": bool(row.voided),
    }


async def _events(db: AsyncSession, employee_id: str, start: datetime, end: datetime) -> list[m.HrmClockEvent]:
    return list(
        (
            await db.execute(
                select(m.HrmClockEvent)
                .where(
                    m.HrmClockEvent.employee_id == employee_id,
                    m.HrmClockEvent.voided.is_(False),
                    m.HrmClockEvent.at >= start,
                    m.HrmClockEvent.at < end,
                )
                .order_by(m.HrmClockEvent.at)
            )
        ).scalars()
    )


async def _last_event(db: AsyncSession, employee_id: str) -> m.HrmClockEvent | None:
    return (
        await db.execute(
            select(m.HrmClockEvent)
            .where(m.HrmClockEvent.employee_id == employee_id, m.HrmClockEvent.voided.is_(False))
            .order_by(m.HrmClockEvent.at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def clock(db: AsyncSession, tenant_id: str, employee: m.HrmEmployee, payload, *, user_id, device: str | None) -> m.HrmClockEvent:
    hrm = await _hrm()
    settings = await hrm.get_settings(db, tenant_id)
    if employee.status != "active":
        raise HTTPException(status_code=409, detail="This person has left")
    now = datetime.utcnow()
    last = await _last_event(db, employee.id)
    # An 'in' left open for more than a day does not block a new start.
    open_in = last is not None and last.kind == "in" and (now - last.at) < timedelta(hours=20)
    if payload.kind == "in" and open_in:
        raise HTTPException(status_code=409, detail="You are already clocked in")
    if payload.kind == "out" and not open_in:
        raise HTTPException(status_code=409, detail="You are not clocked in")
    sites = [s for s in await list_sites(db, tenant_id) if s.is_active]
    site_id = None
    dist = None
    source = "self"
    if payload.qr_code:
        match = next((s for s in sites if qr_valid(s.qr_secret, payload.qr_code, now)), None)
        if match is None:
            raise HTTPException(status_code=422, detail="That QR code is old or not ours. Scan the code on the screen again.")
        site_id, source = match.id, "qr"
    if payload.latitude is not None and payload.longitude is not None:
        placed = [
            (distance_m(float(payload.latitude), float(payload.longitude), float(s.latitude), float(s.longitude)), s)
            for s in sites
            if s.latitude is not None and s.longitude is not None
        ]
        if placed:
            dist, nearest = min(placed, key=lambda x: x[0])
            if site_id is None and dist <= nearest.radius_m and (payload.accuracy_m or 0) <= WORST_GPS_ACCURACY_M:
                site_id = nearest.id
    if settings.clock_needs_site and site_id is None:
        if payload.latitude is not None and (payload.accuracy_m or 0) > WORST_GPS_ACCURACY_M:
            raise HTTPException(status_code=422, detail="Your phone's location is too rough. Step outside or scan the site QR code.")
        raise HTTPException(status_code=422, detail="Clock in at a work site: be within its area or scan its QR code.")
    row = m.HrmClockEvent(
        tenant_id=tenant_id, employee_id=employee.id, kind=payload.kind, at=now, source=source, site_id=site_id,
        latitude=payload.latitude, longitude=payload.longitude, accuracy_m=payload.accuracy_m,
        distance_m=round(dist, 1) if dist is not None else None, device=(device or "")[:160] or None,
        created_by=user_id,
    )
    db.add(row)
    await db.flush()
    return row


async def _replace_day(db: AsyncSession, tenant_id: str, employee_id: str, day: date, in_at, out_at, *, source: str, note: str, user_id) -> None:
    zone = await _zone(db, tenant_id)
    start, end = local_day_bounds(day, zone)
    for ev in await _events(db, employee_id, start, end + timedelta(hours=12)):
        if ev.at < end or ev.kind == "out":
            ev.voided = True
    for kind, at in (("in", in_at), ("out", out_at)):
        if at is not None:
            db.add(m.HrmClockEvent(tenant_id=tenant_id, employee_id=employee_id, kind=kind, at=at, source=source, note=note, created_by=user_id))
    await db.flush()


def _to_utc(value: datetime | None, zone: ZoneInfo) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=zone)
    return value.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)


async def hr_record(db: AsyncSession, tenant_id: str, payload, *, user_id) -> None:
    hrm = await _hrm()
    employee = await hrm._employee(db, tenant_id, payload.employee_id)
    zone = await _zone(db, tenant_id)
    in_at, out_at = _to_utc(payload.in_at, zone), _to_utc(payload.out_at, zone)
    if in_at and out_at and out_at <= in_at:
        raise HTTPException(status_code=422, detail="Out must be after in")
    note = require_honest_narrative(payload.note, label="why", max_length=255)
    await _replace_day(db, tenant_id, employee.id, payload.day, in_at, out_at, source="hr", note=note, user_id=user_id)
    await _audit(db, tenant_id, user_id, "hrm_clock_entered", "hrm_employee", employee.id, {"day": payload.day.isoformat(), "note": note})


async def request_correction(db: AsyncSession, tenant_id: str, employee: m.HrmEmployee, payload, *, user_id) -> m.HrmClockCorrection:
    zone = await _zone(db, tenant_id)
    if payload.day > date.today():
        raise HTTPException(status_code=422, detail="That day has not happened yet")
    in_at, out_at = _to_utc(payload.in_at, zone), _to_utc(payload.out_at, zone)
    if not in_at and not out_at:
        raise HTTPException(status_code=422, detail="Give the time in, the time out, or both")
    if in_at and out_at and out_at <= in_at:
        raise HTTPException(status_code=422, detail="Out must be after in")
    row = m.HrmClockCorrection(
        tenant_id=tenant_id, employee_id=employee.id, day=payload.day, in_at=in_at, out_at=out_at,
        reason=require_honest_narrative(payload.reason, label="reason", max_length=255), status="pending", requested_by=user_id,
    )
    db.add(row)
    await db.flush()
    return row


async def serialize_correction(db: AsyncSession, row: m.HrmClockCorrection) -> dict:
    person = await db.get(m.HrmEmployee, row.employee_id)
    return {
        "id": row.id, "employee_id": row.employee_id, "employee_name": person.full_name if person else None,
        "day": row.day.isoformat(), "in_at": row.in_at.isoformat() + "Z" if row.in_at else None,
        "out_at": row.out_at.isoformat() + "Z" if row.out_at else None, "reason": row.reason,
        "status": row.status, "decision_note": row.decision_note,
    }


async def list_corrections(db: AsyncSession, tenant_id: str, *, employee_id: str | None = None) -> list[m.HrmClockCorrection]:
    stmt = select(m.HrmClockCorrection).where(m.HrmClockCorrection.tenant_id == tenant_id).order_by(m.HrmClockCorrection.created_at.desc())
    if employee_id:
        stmt = stmt.where(m.HrmClockCorrection.employee_id == employee_id)
    return list((await db.execute(stmt)).scalars())


async def decide_correction(db: AsyncSession, tenant_id: str, correction_id: str, *, approve: bool, note: str | None, user_id) -> m.HrmClockCorrection:
    hrm = await _hrm()
    row = await db.get(m.HrmClockCorrection, correction_id)
    if row is None or row.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Request not found")
    if row.status != "pending":
        raise HTTPException(status_code=409, detail=f"This request is already {row.status}")
    me = await hrm._user_employee(db, tenant_id, user_id)
    if (me is not None and me.id == row.employee_id) or row.requested_by == user_id:
        raise HTTPException(status_code=403, detail="Someone else must decide your own request")
    row.decided_by = user_id
    row.decided_at = datetime.utcnow()
    row.decision_note = optional_honest_narrative(note, label="note", max_length=255)
    if not approve:
        if not row.decision_note:
            raise HTTPException(status_code=422, detail="Say why it was turned down")
        row.status = "rejected"
    else:
        zone = await _zone(db, tenant_id)
        start, end = local_day_bounds(row.day, zone)
        kept = await _events(db, row.employee_id, start, end + timedelta(hours=12))
        in_at = row.in_at or next((e.at for e in kept if e.kind == "in" and e.at < end), None)
        out_at = row.out_at or next((e.at for e in reversed(kept) if e.kind == "out"), None)
        await _replace_day(db, tenant_id, row.employee_id, row.day, in_at, out_at, source="correction", note=row.reason, user_id=user_id)
        row.status = "approved"
    await _audit(db, tenant_id, user_id, f"hrm_clock_correction_{row.status}", "hrm_clock_correction", row.id, {"day": row.day.isoformat()})
    await db.flush()
    return row


# --- Daily sheet and overtime --------------------------------------------------------------


async def _on_leave(db: AsyncSession, tenant_id: str, employee_id: str, day: date) -> bool:
    hit = (
        await db.execute(
            select(m.HrmLeaveRequest.id).where(
                m.HrmLeaveRequest.tenant_id == tenant_id,
                m.HrmLeaveRequest.employee_id == employee_id,
                m.HrmLeaveRequest.status == "approved",
                m.HrmLeaveRequest.starts_on <= day,
                m.HrmLeaveRequest.ends_on >= day,
            ).limit(1)
        )
    ).first()
    return hit is not None


async def sheet_for(db: AsyncSession, tenant_id: str, employee: m.HrmEmployee, day: date, *, zone=None, settings=None) -> dict:
    hrm = await _hrm()
    zone = zone or await _zone(db, tenant_id)
    settings = settings or await hrm.get_settings(db, tenant_id)
    roster = (
        await db.execute(
            select(m.HrmRoster, m.HrmShift)
            .join(m.HrmShift, m.HrmShift.id == m.HrmRoster.shift_id)
            .where(m.HrmRoster.employee_id == employee.id, m.HrmRoster.day == day)
        )
    ).first()
    shift = roster[1] if roster else None
    window = shift_window(shift.starts_at, shift.ends_at, day, zone) if shift else None
    start, end = local_day_bounds(day, zone)
    # A night shift's clock-out lands the next day; look a little past midnight for it.
    reach_end = max(end, window[1] + timedelta(hours=6)) if window else end
    events = [(e.kind, e.at) for e in await _events(db, employee.id, start, reach_end)]
    if not window:
        # Without a shift, do not borrow tomorrow morning's clock-in.
        events = [(k, a) for k, a in events if k == "out" or a < end]
    sheet = compute_day(
        events=events, window=window, break_minutes=shift.break_minutes if shift else 0,
        grace_minutes=shift.grace_minutes if shift else 0, hours_per_day=float(settings.hours_per_day or 8),
        on_leave=await _on_leave(db, tenant_id, employee.id, day), now=datetime.utcnow(),
    )
    as_local = lambda d: d.replace(tzinfo=ZoneInfo("UTC")).astimezone(zone).strftime("%H:%M") if d else None  # noqa: E731
    return {
        "employee_id": employee.id, "employee_name": employee.full_name, "day": day.isoformat(),
        "shift": shift.name if shift else None, "shift_time": f"{shift.starts_at}–{shift.ends_at}" if shift else None,
        "status": sheet.status, "first_in": as_local(sheet.first_in), "last_out": as_local(sheet.last_out),
        "worked_minutes": sheet.worked_minutes, "late_minutes": sheet.late_minutes,
        "early_minutes": sheet.early_minutes, "overtime_minutes": sheet.overtime_minutes,
    }


async def day_board(db: AsyncSession, tenant_id: str, day: date) -> list[dict]:
    hrm = await _hrm()
    zone = await _zone(db, tenant_id)
    settings = await hrm.get_settings(db, tenant_id)
    return [await sheet_for(db, tenant_id, p, day, zone=zone, settings=settings) for p in await hrm.list_employees(db, tenant_id)]


def _period_days(period: str) -> list[date]:
    import calendar

    year, month = int(period[:4]), int(period[5:7])
    last = min(date(year, month, calendar.monthrange(year, month)[1]), date.today())
    first = date(year, month, 1)
    return [first + timedelta(days=i) for i in range(max((last - first).days + 1, 0))]


async def month_summary(db: AsyncSession, tenant_id: str, period: str) -> list[dict]:
    hrm = await _hrm()
    zone = await _zone(db, tenant_id)
    settings = await hrm.get_settings(db, tenant_id)
    out = []
    for person in await hrm.list_employees(db, tenant_id):
        totals = {"worked_minutes": 0, "late_minutes": 0, "early_minutes": 0, "overtime_minutes": 0, "late_days": 0, "absent_days": 0}
        for day in _period_days(period):
            sheet = await sheet_for(db, tenant_id, person, day, zone=zone, settings=settings)
            for key in ("worked_minutes", "late_minutes", "early_minutes", "overtime_minutes"):
                totals[key] += sheet[key]
            totals["late_days"] += 1 if sheet["status"] == "late" else 0
            totals["absent_days"] += 1 if sheet["status"] == "absent" else 0
        approved = (
            await db.execute(select(m.HrmOvertime).where(m.HrmOvertime.employee_id == person.id, m.HrmOvertime.period == period))
        ).scalar_one_or_none()
        out.append(
            {
                "employee_id": person.id, "employee_name": person.full_name, "period": period, **totals,
                "overtime_approved": (
                    {"minutes": approved.minutes, "amount": money_json(approved.amount), "status": approved.status} if approved else None
                ),
            }
        )
    return out


def overtime_pay(basic, working_days: int, hours_per_day, rate, minutes: int) -> tuple[Decimal, Decimal]:
    """Hourly = basic / (working days x hours a day); pay = hourly x rate x hours. Decimal throughout."""
    hours = Decimal(str(hours_per_day or 8))
    days = Decimal(max(int(working_days or 22), 1))
    hourly = (Decimal(str(basic or 0)) / (days * hours)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    amount = (hourly * Decimal(str(rate or 1)) * Decimal(int(minutes)) / Decimal(60)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return hourly, amount


async def approve_overtime(db: AsyncSession, tenant_id: str, payload, *, user_id) -> m.HrmOvertime:
    """HR approves a month's overtime minutes (no more than the clock shows). Paid on that month's payroll."""
    hrm = await _hrm()
    from app import hrm_pay_changes

    employee = await hrm._employee(db, tenant_id, payload.employee_id)
    me = await hrm._user_employee(db, tenant_id, user_id)
    if me is not None and me.id == employee.id:
        raise HTTPException(status_code=403, detail="Someone else must approve your own overtime")
    zone = await _zone(db, tenant_id)
    settings = await hrm.get_settings(db, tenant_id)
    clocked = 0
    for day in _period_days(payload.period):
        clocked += (await sheet_for(db, tenant_id, employee, day, zone=zone, settings=settings))["overtime_minutes"]
    if payload.minutes > clocked:
        raise HTTPException(status_code=422, detail=f"The clock shows {clocked} minutes of overtime this month")
    basic, _allow = await hrm_pay_changes.salary_for(db, employee, hrm_pay_changes._first(payload.period))
    hourly, amount = overtime_pay(basic, settings.working_days_per_month, settings.hours_per_day, settings.overtime_rate, payload.minutes)
    row = (
        await db.execute(select(m.HrmOvertime).where(m.HrmOvertime.employee_id == employee.id, m.HrmOvertime.period == payload.period))
    ).scalar_one_or_none()
    if row is not None and (row.status != "approved" or row.run_id):
        raise HTTPException(status_code=409, detail="This month's overtime is already on a payroll")
    if row is None:
        row = m.HrmOvertime(tenant_id=tenant_id, employee_id=employee.id, period=payload.period)
        db.add(row)
    row.minutes, row.amount, row.hourly_rate, row.rate = payload.minutes, amount, hourly, Decimal(str(settings.overtime_rate))
    row.status, row.approved_by = "approved", user_id
    await db.flush()
    await _audit(
        db, tenant_id, user_id, "hrm_overtime_approved", "hrm_overtime", row.id,
        {"employee_id": employee.id, "period": payload.period, "minutes": payload.minutes, "amount": money_json(amount)},
    )
    return row


async def take_overtime(db: AsyncSession, employee_id: str, period: str, run_id: str) -> Decimal:
    row = (
        await db.execute(
            select(m.HrmOvertime).where(
                m.HrmOvertime.employee_id == employee_id, m.HrmOvertime.period == period,
                m.HrmOvertime.status == "approved", m.HrmOvertime.run_id.is_(None),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        return Decimal("0")
    row.run_id = run_id
    return Decimal(str(row.amount))


async def release_overtime(db: AsyncSession, run_id: str) -> None:
    for row in (await db.execute(select(m.HrmOvertime).where(m.HrmOvertime.run_id == run_id))).scalars():
        if row.status == "approved":
            row.run_id = None


async def settle_overtime(db: AsyncSession, run_id: str) -> None:
    for row in (await db.execute(select(m.HrmOvertime).where(m.HrmOvertime.run_id == run_id))).scalars():
        row.status = "paid"
