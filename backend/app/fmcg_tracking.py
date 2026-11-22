"""FMCG staff location (field reps, drivers): where they are while they are on duty.

Not "real-time GPS". A web page can only read and send a phone's position while the ERP is open on the
screen; if the screen locks or the app is closed, updates stop and the map shows "last seen N min ago".

Privacy rules, all enforced here and not just on the screen:
- FMCG companies only.
- HR or an admin switches tracking on for each person. Nothing is read for anyone else.
- The person sees a notice and accepts it before anything is sent, and a banner while sharing.
- Positions are accepted only while the person is clocked in (no off-duty tracking).
- Admins, HR and the distribution manager see everyone; anyone else sees only the people who report to
  them in HR (their manager link). Someone out of scope gets 404.
- Each time a manager opens a trail it is written to the audit log. Staff can open their own trail.
- Points older than 30 days are deleted (the FMCG daily scan runs `purge_old`).
"""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit as audit_svc
from app import models as m
from app.honesty import money_json

RETENTION_DAYS = 30
WORST_ACCURACY_M = 200.0
MAX_BATCH = 100
MAX_AGE = timedelta(hours=12)
STALE_AFTER = timedelta(minutes=10)
STOP_MINUTES = 10
STOP_RADIUS_M = 50.0
WATCH_ROLES = frozenset({"company_admin", "super_admin", "hrm_manager", "fmcg_manager"})
NOTICE = (
    "While you are clocked in and this page is open, your phone's location is sent to your manager and HR. "
    "It stops when you clock out or close the page. Points are kept for 30 days."
)


def require_fmcg(claims: dict) -> None:
    from app import packages as packages_svc

    if packages_svc.canonicalize_industry(claims.get("industry")) != "fmcg":
        raise HTTPException(
            status_code=403,
            detail={"code": "FMCG_ONLY", "message": "Staff location is part of the FMCG desk."},
        )


def _now() -> datetime:
    return datetime.utcnow()


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() + "Z" if value else None


def distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


async def _state(db: AsyncSession, tenant_id: str, user_id: str, *, create: bool = False) -> m.FmcgTrackState | None:
    row = (
        await db.execute(
            select(m.FmcgTrackState).where(m.FmcgTrackState.tenant_id == tenant_id, m.FmcgTrackState.user_id == user_id)
        )
    ).scalar_one_or_none()
    if row is None and create:
        row = m.FmcgTrackState(tenant_id=tenant_id, user_id=user_id, enabled=False)
        db.add(row)
        await db.flush()
    return row


async def _employee_by_email(db: AsyncSession, tenant_id: str, email: str | None) -> m.HrmEmployee | None:
    key = (email or "").strip().lower()
    if not key:
        return None
    return (
        await db.execute(
            select(m.HrmEmployee).where(m.HrmEmployee.tenant_id == tenant_id, func.lower(m.HrmEmployee.email) == key)
        )
    ).scalars().first()


async def _clocked_in(db: AsyncSession, employee: m.HrmEmployee | None) -> bool:
    if employee is None or employee.status != "active":
        return False
    last = (
        await db.execute(
            select(m.HrmClockEvent)
            .where(m.HrmClockEvent.employee_id == employee.id, m.HrmClockEvent.voided.is_(False))
            .order_by(m.HrmClockEvent.at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    return last is not None and last.kind == "in" and (_now() - last.at) < timedelta(hours=20)


# ------------------------------------------------------------------ the person's own side


async def me_status(db: AsyncSession, tenant_id: str, user_id: str) -> dict:
    user = await db.get(m.User, user_id)
    state = await _state(db, tenant_id, user_id)
    employee = await _employee_by_email(db, tenant_id, user.email if user else None)
    clocked = await _clocked_in(db, employee)
    enabled = bool(state and state.enabled)
    acknowledged = bool(state and state.notice_ack_at)
    return {
        "enabled": enabled,
        "notice": NOTICE,
        "notice_accepted": acknowledged,
        "has_hr_record": employee is not None,
        "clocked_in": clocked,
        # The page may send positions only when all of these hold.
        "sharing": bool(enabled and acknowledged and clocked),
        "last_at": _iso(state.last_at) if state else None,
    }


async def accept_notice(db: AsyncSession, tenant_id: str, user_id: str) -> dict:
    state = await _state(db, tenant_id, user_id)
    if state is None or not state.enabled:
        raise HTTPException(status_code=409, detail="Location sharing is not switched on for you")
    if state.notice_ack_at is None:
        state.notice_ack_at = _now()
        await db.flush()
        await audit_svc.record_event(
            db, tenant_id=tenant_id, user_id=user_id, module="fmcg", action="fmcg_tracking_notice_accepted",
            entity="user", entity_id=user_id, details={},
        )
    return await me_status(db, tenant_id, user_id)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is not None:
        from datetime import timezone

        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


async def record_pings(db: AsyncSession, tenant_id: str, user_id: str, points: list) -> dict:
    """Store a batch (a phone that lost signal sends its queue). Refused unless sharing is allowed right now."""
    status = await me_status(db, tenant_id, user_id)
    if not status["enabled"]:
        raise HTTPException(status_code=403, detail={"code": "TRACKING_OFF", "message": "Location sharing is not switched on for you."})
    if not status["notice_accepted"]:
        raise HTTPException(status_code=409, detail={"code": "NOTICE_NEEDED", "message": "Read and accept the location notice first."})
    if not status["clocked_in"]:
        raise HTTPException(status_code=409, detail={"code": "NOT_CLOCKED_IN", "message": "Clock in first. Your location is only shared while you are clocked in."})
    if len(points) > MAX_BATCH:
        raise HTTPException(status_code=422, detail=f"Send at most {MAX_BATCH} points at a time")
    now = _now()
    kept: dict[datetime, dict] = {}
    dropped = 0
    for p in points:
        at = _utc(p.captured_at).replace(microsecond=0)
        acc = float(p.accuracy_m) if p.accuracy_m is not None else None
        if at > now + timedelta(minutes=2) or now - at > MAX_AGE:
            dropped += 1
            continue
        if acc is not None and acc > WORST_ACCURACY_M:
            dropped += 1  # too rough to trust: a fix this poor can put someone in the wrong street
            continue
        kept[at] = {"lat": float(p.latitude), "lon": float(p.longitude), "acc": acc, "speed": float(p.speed_kmh) if p.speed_kmh is not None else None}
    if not kept:
        return {"saved": 0, "dropped": dropped, "duplicates": 0}
    have = set(
        (
            await db.execute(
                select(m.FmcgTrackPing.captured_at).where(
                    m.FmcgTrackPing.tenant_id == tenant_id,
                    m.FmcgTrackPing.user_id == user_id,
                    m.FmcgTrackPing.captured_at.in_(list(kept)),
                )
            )
        ).scalars()
    )
    saved = 0
    for at, v in sorted(kept.items()):
        if at in have:
            continue
        db.add(
            m.FmcgTrackPing(
                tenant_id=tenant_id, user_id=user_id, latitude=v["lat"], longitude=v["lon"],
                accuracy_m=v["acc"], speed_kmh=v["speed"], captured_at=at, received_at=now,
            )
        )
        saved += 1
    state = await _state(db, tenant_id, user_id, create=True)
    newest_at = max(kept)
    if state.last_at is None or newest_at >= state.last_at:
        v = kept[newest_at]
        state.last_latitude, state.last_longitude = v["lat"], v["lon"]
        state.last_accuracy_m, state.last_speed_kmh, state.last_at = v["acc"], v["speed"], newest_at
    await db.flush()
    return {"saved": saved, "dropped": dropped, "duplicates": len(kept) - saved}


# ------------------------------------------------------------------ who may see whom


async def _reports_of(db: AsyncSession, tenant_id: str, employee: m.HrmEmployee) -> list[m.HrmEmployee]:
    seen = {employee.id}
    found: list[m.HrmEmployee] = []
    frontier = [employee.id]
    while frontier:
        rows = (
            await db.execute(
                select(m.HrmEmployee).where(
                    m.HrmEmployee.tenant_id == tenant_id, m.HrmEmployee.manager_id.in_(frontier), m.HrmEmployee.status == "active"
                )
            )
        ).scalars().all()
        frontier = []
        for r in rows:
            if r.id not in seen:
                seen.add(r.id)
                found.append(r)
                frontier.append(r.id)
    return found


async def scope_user_ids(db: AsyncSession, claims: dict) -> set[str] | None:
    """None means everyone in the company; otherwise the people who report to this manager."""
    role = str(claims.get("role") or "")
    tenant_id = claims["tenant_id"]
    if role in WATCH_ROLES:
        return None
    user = await db.get(m.User, claims.get("sub")) if claims.get("sub") else None
    me = await _employee_by_email(db, tenant_id, user.email if user else None)
    reports = await _reports_of(db, tenant_id, me) if me is not None else []
    emails = [r.email.strip().lower() for r in reports if r.email]
    if not emails:
        raise HTTPException(
            status_code=403,
            detail={"code": "TRACKING_NOT_YOURS", "message": "You can see the live map when people report to you in HR. Ask HR to assign them to you."},
        )
    ids = (
        await db.execute(
            select(m.User.id).where(m.User.tenant_id == tenant_id, func.lower(m.User.email).in_(emails), m.User.is_active.is_(True))
        )
    ).scalars().all()
    return set(ids)


# ------------------------------------------------------------------ the manager's side


async def people(db: AsyncSession, claims: dict) -> list[dict]:
    """Everyone the viewer may see, with whether sharing is on and where they last were."""
    tenant_id = claims["tenant_id"]
    scope = await scope_user_ids(db, claims)
    stmt = select(m.User).where(m.User.tenant_id == tenant_id, m.User.is_active.is_(True))
    if scope is not None:
        stmt = stmt.where(m.User.id.in_(scope or {"-"}))
    users = (await db.execute(stmt.order_by(m.User.full_name).limit(500))).scalars().all()
    states = {
        s.user_id: s
        for s in (await db.execute(select(m.FmcgTrackState).where(m.FmcgTrackState.tenant_id == tenant_id))).scalars()
    }
    now = _now()
    out = []
    for u in users:
        if u.role in {"super_admin"} or str(u.role).startswith("platform"):
            continue
        s = states.get(u.id)
        employee = await _employee_by_email(db, tenant_id, u.email)
        on_duty = await _clocked_in(db, employee)
        at = s.last_at if s else None
        out.append(
            {
                "user_id": u.id,
                "name": u.full_name,
                "role": u.role,
                "enabled": bool(s and s.enabled),
                "notice_accepted": bool(s and s.notice_ack_at),
                "has_hr_record": employee is not None,
                "on_duty": on_duty,
                "latitude": money_json(s.last_latitude) if s and s.last_latitude is not None else None,
                "longitude": money_json(s.last_longitude) if s and s.last_longitude is not None else None,
                "accuracy_m": money_json(s.last_accuracy_m) if s and s.last_accuracy_m is not None else None,
                "speed_kmh": money_json(s.last_speed_kmh) if s and s.last_speed_kmh is not None else None,
                "last_at": _iso(at),
                "minutes_ago": int((now - at).total_seconds() // 60) if at else None,
                "stale": bool(at is None or (now - at) > STALE_AFTER or not on_duty),
            }
        )
    return out


async def set_enabled(db: AsyncSession, claims: dict, user_id: str, enabled: bool) -> dict:
    """HR or an admin switches location sharing on or off for one person."""
    if str(claims.get("role") or "") not in WATCH_ROLES:
        raise HTTPException(status_code=403, detail={"code": "TRACKING_SWITCH", "message": "Only HR or an admin can switch location sharing on."})
    tenant_id = claims["tenant_id"]
    user = await db.get(m.User, user_id)
    if user is None or user.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Person not found")
    state = await _state(db, tenant_id, user_id, create=True)
    state.enabled = bool(enabled)
    state.enabled_by = claims.get("sub")
    state.enabled_at = _now()
    if not enabled:
        state.notice_ack_at = None  # switching back on later asks for acceptance again
    await db.flush()
    await audit_svc.record_event(
        db, tenant_id=tenant_id, user_id=claims.get("sub"), module="fmcg",
        action="fmcg_tracking_on" if enabled else "fmcg_tracking_off", entity="user", entity_id=user_id,
        details={"person": user.full_name},
    )
    return {"user_id": user_id, "enabled": state.enabled}


def _stops(points: list[m.FmcgTrackPing]) -> list[dict]:
    stops: list[dict] = []
    if not points:
        return stops
    anchor = points[0]
    last = points[0]

    def close():
        minutes = (last.captured_at - anchor.captured_at).total_seconds() / 60
        if minutes >= STOP_MINUTES:
            stops.append(
                {
                    "latitude": money_json(anchor.latitude), "longitude": money_json(anchor.longitude),
                    "from": _iso(anchor.captured_at), "to": _iso(last.captured_at), "minutes": int(minutes),
                }
            )

    for p in points[1:]:
        if distance_m(float(anchor.latitude), float(anchor.longitude), float(p.latitude), float(p.longitude)) <= STOP_RADIUS_M:
            last = p
            continue
        close()
        anchor = last = p
    close()
    return stops


async def trail(db: AsyncSession, claims: dict, user_id: str, day: date | None) -> dict:
    """One person's day: the line they walked or drove, the distance, and where they stopped."""
    from app import hrm_time

    tenant_id = claims["tenant_id"]
    viewer = claims.get("sub")
    own = viewer == user_id
    if not own:
        scope = await scope_user_ids(db, claims)
        if scope is not None and user_id not in scope:
            raise HTTPException(status_code=404, detail="Person not found")
    user = await db.get(m.User, user_id)
    if user is None or user.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Person not found")
    zone = await hrm_time._zone(db, tenant_id)
    today = datetime.now(zone).date()
    day = day or today
    start, end = hrm_time.local_day_bounds(day, zone)
    pts = (
        await db.execute(
            select(m.FmcgTrackPing)
            .where(
                m.FmcgTrackPing.tenant_id == tenant_id, m.FmcgTrackPing.user_id == user_id,
                m.FmcgTrackPing.captured_at >= start, m.FmcgTrackPing.captured_at < end,
            )
            .order_by(m.FmcgTrackPing.captured_at)
            .limit(5000)
        )
    ).scalars().all()
    metres = 0.0
    for a, b in zip(pts, pts[1:]):
        step = distance_m(float(a.latitude), float(a.longitude), float(b.latitude), float(b.longitude))
        if step >= 15:  # smaller moves are GPS jitter, not travel
            metres += step
    if not own:
        await audit_svc.record_event(
            db, tenant_id=tenant_id, user_id=viewer, module="fmcg", action="fmcg_tracking_trail_viewed",
            entity="user", entity_id=user_id, details={"person": user.full_name, "day": day.isoformat(), "points": len(pts)},
        )
    return {
        "user_id": user_id,
        "name": user.full_name,
        "day": day.isoformat(),
        "distance_km": round(metres / 1000, 2),
        "points": [
            {"latitude": money_json(p.latitude), "longitude": money_json(p.longitude), "at": _iso(p.captured_at),
             "accuracy_m": money_json(p.accuracy_m) if p.accuracy_m is not None else None}
            for p in pts
        ],
        "stops": _stops(list(pts)),
    }


async def purge_old(db: AsyncSession, tenant_id: str, days: int = RETENTION_DAYS) -> int:
    cutoff = _now() - timedelta(days=days)
    res = await db.execute(
        delete(m.FmcgTrackPing).where(m.FmcgTrackPing.tenant_id == tenant_id, m.FmcgTrackPing.captured_at < cutoff)
    )
    return int(res.rowcount or 0)
