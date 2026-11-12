"""FMCG field work: territories and outlet visits tracked with the rep's phone location.

- A territory is a set of routes (each route in one territory) and the reps who work it.
  A rep's outlets are the outlets on those routes.
- A visit is checked in and out from the rep's phone. The phone's location and its stated
  accuracy are stored at both ends. Visits are not refused for distance (field reality: weak
  signal indoors); instead they are flagged for the manager: far from the outlet, rough GPS,
  no GPS, or an outlet with no saved location.
- An outlet with no saved location takes it from the first check-in with a close fix
  (accuracy 50 m or better). After that it changes only when a manager edits the outlet.
- Location on a tampered phone can be faked; the stored accuracy, distance and timestamps
  are the checks available.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit as audit_svc
from app import models as m
from app.honesty import money_json, optional_honest_narrative, require_honest_narrative
from app.hrm_time import distance_m

FAR_M = 300
ROUGH_ACCURACY_M = 200
SET_LOCATION_ACCURACY_M = 50
OUTCOMES = frozenset({"order", "no_order", "closed", "not_found"})
NO_ORDER_REASONS = frozenset({"has_stock", "no_money", "owner_away", "price", "competitor", "other"})
WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


async def _audit(db, tenant_id, user_id, action, entity_id, details):
    await audit_svc.record_event(
        db, tenant_id=tenant_id, user_id=user_id, module="fmcg", action=action,
        entity="fmcg_field", entity_id=entity_id, details=details,
    )


async def _zone(db: AsyncSession, tenant_id: str) -> ZoneInfo:
    from app import hrm_time

    return await hrm_time._zone(db, tenant_id)


def _day_bounds(day: date, zone: ZoneInfo) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time(0, 0), tzinfo=zone).astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
    return start, start + timedelta(days=1)


def _local(at: datetime | None, zone: ZoneInfo) -> str | None:
    return at.replace(tzinfo=ZoneInfo("UTC")).astimezone(zone).strftime("%H:%M") if at else None


# --- Territories ---------------------------------------------------------------------------


async def serialize_territory(db: AsyncSession, row: m.FmcgTerritory) -> dict:
    routes = (
        await db.execute(
            select(m.FmcgRoute.id, m.FmcgRoute.name)
            .join(m.FmcgTerritoryRoute, m.FmcgTerritoryRoute.route_id == m.FmcgRoute.id)
            .where(m.FmcgTerritoryRoute.territory_id == row.id)
            .order_by(m.FmcgRoute.name)
        )
    ).all()
    reps = (
        await db.execute(
            select(m.User.id, m.User.full_name, m.User.email)
            .join(m.FmcgTerritoryRep, m.FmcgTerritoryRep.user_id == m.User.id)
            .where(m.FmcgTerritoryRep.territory_id == row.id)
            .order_by(m.User.full_name)
        )
    ).all()
    return {
        "id": row.id, "code": row.code, "name": row.name, "notes": row.notes,
        "daily_visit_target": int(row.daily_visit_target or 0), "is_active": bool(row.is_active),
        "routes": [{"id": r, "name": n} for r, n in routes],
        "reps": [{"id": u, "name": n or e} for u, n, e in reps],
    }


async def list_territories(db: AsyncSession, tenant_id: str) -> list[dict]:
    rows = (
        await db.execute(select(m.FmcgTerritory).where(m.FmcgTerritory.tenant_id == tenant_id).order_by(m.FmcgTerritory.name))
    ).scalars().all()
    return [await serialize_territory(db, r) for r in rows]


async def save_territory(db: AsyncSession, tenant_id: str, payload, *, territory_id: str | None, user_id) -> m.FmcgTerritory:
    if territory_id:
        row = await db.get(m.FmcgTerritory, territory_id)
        if row is None or row.tenant_id != tenant_id:
            raise HTTPException(status_code=404, detail="Territory not found")
    else:
        clash = (
            await db.execute(
                select(m.FmcgTerritory.id).where(m.FmcgTerritory.tenant_id == tenant_id, m.FmcgTerritory.code == payload.code.strip().upper())
            )
        ).first()
        if clash:
            raise HTTPException(status_code=409, detail="That territory code is taken")
        row = m.FmcgTerritory(tenant_id=tenant_id, code=payload.code.strip().upper())
        db.add(row)
    row.name = require_honest_narrative(payload.name, label="territory name", max_length=150)
    row.notes = optional_honest_narrative(payload.notes, label="notes", max_length=2000)
    row.daily_visit_target = payload.daily_visit_target
    row.is_active = payload.is_active
    await db.flush()
    # Routes: each route sits in one territory, so moving a route here takes it from its old one.
    for route_id in payload.route_ids:
        route = await db.get(m.FmcgRoute, route_id)
        if route is None or route.tenant_id != tenant_id:
            raise HTTPException(status_code=404, detail="Route not found")
    for link in (await db.execute(select(m.FmcgTerritoryRoute).where(m.FmcgTerritoryRoute.territory_id == row.id))).scalars():
        await db.delete(link)
    for link in (
        await db.execute(
            select(m.FmcgTerritoryRoute).where(
                m.FmcgTerritoryRoute.tenant_id == tenant_id, m.FmcgTerritoryRoute.route_id.in_(payload.route_ids or [""])
            )
        )
    ).scalars():
        await db.delete(link)
    await db.flush()
    for route_id in dict.fromkeys(payload.route_ids):
        db.add(m.FmcgTerritoryRoute(tenant_id=tenant_id, territory_id=row.id, route_id=route_id))
    for link in (await db.execute(select(m.FmcgTerritoryRep).where(m.FmcgTerritoryRep.territory_id == row.id))).scalars():
        await db.delete(link)
    await db.flush()
    for rep_id in dict.fromkeys(payload.rep_user_ids):
        user = await db.get(m.User, rep_id)
        if user is None or user.tenant_id != tenant_id or not user.is_active:
            raise HTTPException(status_code=404, detail="Rep not found")
        db.add(m.FmcgTerritoryRep(tenant_id=tenant_id, territory_id=row.id, user_id=user.id))
    await db.flush()
    await _audit(db, tenant_id, user_id, "fmcg_territory_saved", row.id, {"code": row.code, "routes": len(payload.route_ids), "reps": len(payload.rep_user_ids)})
    return row


async def _territory_of_route(db: AsyncSession, tenant_id: str, route_id: str | None) -> str | None:
    if not route_id:
        return None
    return (
        await db.execute(
            select(m.FmcgTerritoryRoute.territory_id).where(m.FmcgTerritoryRoute.tenant_id == tenant_id, m.FmcgTerritoryRoute.route_id == route_id)
        )
    ).scalar_one_or_none()


async def my_route_ids(db: AsyncSession, tenant_id: str, user_id: str) -> set[str]:
    rows = (
        await db.execute(
            select(m.FmcgTerritoryRoute.route_id)
            .join(m.FmcgTerritoryRep, m.FmcgTerritoryRep.territory_id == m.FmcgTerritoryRoute.territory_id)
            .join(m.FmcgTerritory, m.FmcgTerritory.id == m.FmcgTerritoryRoute.territory_id)
            .where(m.FmcgTerritoryRep.user_id == user_id, m.FmcgTerritoryRep.tenant_id == tenant_id, m.FmcgTerritory.is_active.is_(True))
        )
    ).scalars().all()
    return set(rows)


async def outlets_for(db: AsyncSession, tenant_id: str, *, user_id: str | None, everyone: bool, day: date | None = None) -> list[dict]:
    """Outlets with their route, location and today's visit. A rep sees their territories' outlets."""
    zone = await _zone(db, tenant_id)
    day = day or datetime.now(zone).date()
    start, end = _day_bounds(day, zone)
    stmt = (
        select(m.Party, m.FmcgCustomerAssignment)
        .outerjoin(
            m.FmcgCustomerAssignment,
            (m.FmcgCustomerAssignment.customer_id == m.Party.id) & (m.FmcgCustomerAssignment.tenant_id == tenant_id),
        )
        .where(m.Party.tenant_id == tenant_id, m.Party.kind == "customer", m.Party.status == "active")
        .order_by(m.Party.name)
    )
    rows = (await db.execute(stmt)).all()
    mine = None if everyone else await my_route_ids(db, tenant_id, user_id)
    visits = {
        v.outlet_id: v
        for v in (
            await db.execute(
                select(m.FmcgVisit).where(m.FmcgVisit.tenant_id == tenant_id, m.FmcgVisit.checked_in_at >= start, m.FmcgVisit.checked_in_at < end)
                .order_by(m.FmcgVisit.checked_in_at)
            )
        ).scalars()
    }
    out = []
    for party, assignment in rows:
        route_id = assignment.route_id if assignment else None
        if mine is not None and route_id not in mine:
            continue
        visit = visits.get(party.id)
        out.append(
            {
                "id": party.id, "name": party.name, "address": party.address, "phone": party.phone, "route_id": route_id,
                "latitude": money_json(party.latitude) if party.latitude is not None else None,
                "longitude": money_json(party.longitude) if party.longitude is not None else None,
                "visited_today": bool(visit),
                "visit_open": bool(visit and visit.checked_out_at is None),
            }
        )
    return out


# --- Visits --------------------------------------------------------------------------------


def _serialize_visit(v: m.FmcgVisit, zone: ZoneInfo, *, outlet: str | None = None, rep: str | None = None) -> dict:
    minutes = int((v.checked_out_at - v.checked_in_at).total_seconds() // 60) if v.checked_out_at else None
    return {
        "id": v.id, "outlet_id": v.outlet_id, "outlet_name": outlet, "user_id": v.user_id, "rep_name": rep,
        "day": v.checked_in_at.replace(tzinfo=ZoneInfo("UTC")).astimezone(zone).date().isoformat(),
        "checked_in": _local(v.checked_in_at, zone), "checked_out": _local(v.checked_out_at, zone),
        "minutes": minutes, "distance_m": money_json(v.distance_m) if v.distance_m is not None else None,
        "accuracy_m": money_json(v.in_accuracy_m) if v.in_accuracy_m is not None else None,
        "outcome": v.outcome, "no_order_reason": v.no_order_reason, "order_id": v.order_id, "notes": v.notes,
        "flags": v.flags or [], "set_outlet_location": bool(v.set_outlet_location),
    }


async def check_in(db: AsyncSession, tenant_id: str, payload, *, user_id: str, may_visit_any: bool, device: str | None) -> dict:
    outlet = await db.get(m.Party, payload.outlet_id)
    if outlet is None or outlet.tenant_id != tenant_id or outlet.kind != "customer":
        raise HTTPException(status_code=404, detail="Outlet not found")
    assignment = (
        await db.execute(
            select(m.FmcgCustomerAssignment).where(m.FmcgCustomerAssignment.tenant_id == tenant_id, m.FmcgCustomerAssignment.customer_id == outlet.id)
        )
    ).scalar_one_or_none()
    route_id = assignment.route_id if assignment else None
    if not may_visit_any:
        mine = await my_route_ids(db, tenant_id, user_id)
        if route_id not in mine:
            raise HTTPException(status_code=403, detail={"code": "OUTSIDE_TERRITORY", "message": "That outlet is not in your territory."})
    open_visit = (
        await db.execute(
            select(m.FmcgVisit).where(m.FmcgVisit.user_id == user_id, m.FmcgVisit.checked_out_at.is_(None)).limit(1)
        )
    ).scalar_one_or_none()
    if open_visit is not None:
        raise HTTPException(status_code=409, detail="Finish your current visit first")
    flags: list[str] = []
    dist = None
    lat, lon, acc = payload.latitude, payload.longitude, payload.accuracy_m
    if lat is None or lon is None:
        flags.append("no_gps")
    else:
        if acc is not None and acc > ROUGH_ACCURACY_M:
            flags.append("rough_gps")
        if outlet.latitude is not None and outlet.longitude is not None:
            dist = round(distance_m(float(lat), float(lon), float(outlet.latitude), float(outlet.longitude)), 1)
            if dist > FAR_M:
                flags.append("far")
        else:
            flags.append("outlet_unmapped")
    set_location = False
    if "outlet_unmapped" in flags and acc is not None and acc <= SET_LOCATION_ACCURACY_M:
        outlet.latitude, outlet.longitude = lat, lon
        set_location = True
        flags.remove("outlet_unmapped")
    visit = m.FmcgVisit(
        tenant_id=tenant_id, outlet_id=outlet.id, user_id=user_id, route_id=route_id,
        territory_id=await _territory_of_route(db, tenant_id, route_id), checked_in_at=datetime.utcnow(),
        in_latitude=lat, in_longitude=lon, in_accuracy_m=acc, distance_m=dist, flags=flags,
        set_outlet_location=set_location, device=(device or "")[:160] or None,
    )
    db.add(visit)
    await db.flush()
    if set_location:
        await _audit(db, tenant_id, user_id, "fmcg_outlet_located", outlet.id, {"latitude": lat, "longitude": lon, "accuracy_m": acc})
    return _serialize_visit(visit, await _zone(db, tenant_id), outlet=outlet.name)


async def check_out(db: AsyncSession, tenant_id: str, visit_id: str, payload, *, user_id: str) -> dict:
    visit = await db.get(m.FmcgVisit, visit_id)
    if visit is None or visit.tenant_id != tenant_id or visit.user_id != user_id:
        raise HTTPException(status_code=404, detail="Visit not found")
    if visit.checked_out_at is not None:
        raise HTTPException(status_code=409, detail="This visit is already finished")
    if payload.outcome == "no_order" and payload.no_order_reason not in NO_ORDER_REASONS:
        raise HTTPException(status_code=422, detail="Say why there was no order")
    visit.checked_out_at = datetime.utcnow()
    visit.out_latitude, visit.out_longitude, visit.out_accuracy_m = payload.latitude, payload.longitude, payload.accuracy_m
    visit.outcome = payload.outcome
    visit.no_order_reason = payload.no_order_reason if payload.outcome == "no_order" else None
    visit.notes = optional_honest_narrative(payload.notes, label="notes", max_length=500)
    if payload.outcome == "order":
        # Link the order this rep booked for this outlet during the visit, if there is one.
        order = (
            await db.execute(
                select(m.FmcgOrder.id)
                .where(
                    m.FmcgOrder.tenant_id == tenant_id, m.FmcgOrder.customer_id == visit.outlet_id,
                    m.FmcgOrder.created_by == user_id, m.FmcgOrder.created_at >= visit.checked_in_at - timedelta(minutes=5),
                )
                .order_by(m.FmcgOrder.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        visit.order_id = order
        if order is None:
            visit.flags = list(visit.flags or []) + ["order_not_booked"]
    await db.flush()
    outlet = await db.get(m.Party, visit.outlet_id)
    return _serialize_visit(visit, await _zone(db, tenant_id), outlet=outlet.name if outlet else None)


async def list_visits(db: AsyncSession, tenant_id: str, *, day: date, user_id: str | None) -> list[dict]:
    zone = await _zone(db, tenant_id)
    start, end = _day_bounds(day, zone)
    stmt = (
        select(m.FmcgVisit, m.Party.name, m.User.full_name)
        .join(m.Party, m.Party.id == m.FmcgVisit.outlet_id)
        .join(m.User, m.User.id == m.FmcgVisit.user_id)
        .where(m.FmcgVisit.tenant_id == tenant_id, m.FmcgVisit.checked_in_at >= start, m.FmcgVisit.checked_in_at < end)
        .order_by(m.FmcgVisit.checked_in_at)
    )
    if user_id:
        stmt = stmt.where(m.FmcgVisit.user_id == user_id)
    return [_serialize_visit(v, zone, outlet=o, rep=r) for v, o, r in (await db.execute(stmt)).all()]


# --- Coverage and territory reports --------------------------------------------------------


async def coverage(db: AsyncSession, tenant_id: str, day: date) -> dict:
    """Per rep: visits, orders, strike rate, time in the market, flags; per route: planned outlets missed."""
    zone = await _zone(db, tenant_id)
    visits = await list_visits(db, tenant_id, day=day, user_id=None)
    by_rep: dict[str, dict] = {}
    for v in visits:
        row = by_rep.setdefault(
            v["user_id"], {"user_id": v["user_id"], "rep_name": v["rep_name"], "visits": 0, "orders": 0, "flagged": 0, "first_in": None, "last_out": None}
        )
        row["visits"] += 1
        row["orders"] += 1 if v["outcome"] == "order" else 0
        row["flagged"] += 1 if v["flags"] else 0
        row["first_in"] = row["first_in"] or v["checked_in"]
        row["last_out"] = v["checked_out"] or row["last_out"]
    for row in by_rep.values():
        row["strike_rate"] = round(100 * row["orders"] / row["visits"]) if row["visits"] else 0
    weekday = WEEKDAYS[day.weekday()]
    visited = {v["outlet_id"] for v in visits}
    routes = []
    for route in (await db.execute(select(m.FmcgRoute).where(m.FmcgRoute.tenant_id == tenant_id, m.FmcgRoute.is_active.is_(True)))).scalars():
        stops = (
            await db.execute(
                select(m.FmcgRouteStop, m.Party.name)
                .join(m.Party, m.Party.id == m.FmcgRouteStop.customer_id)
                .where(m.FmcgRouteStop.route_id == route.id)
                .order_by(m.FmcgRouteStop.sequence)
            )
        ).all()
        planned = [(s, n) for s, n in stops if not s.visit_day or s.visit_day.strip().lower()[:3] == weekday]
        if not planned:
            continue
        missed = [n for s, n in planned if s.customer_id not in visited]
        routes.append(
            {"route_id": route.id, "route": route.name, "planned": len(planned), "visited": len(planned) - len(missed), "missed": missed}
        )
    return {"day": day.isoformat(), "reps": sorted(by_rep.values(), key=lambda r: r["rep_name"] or ""), "routes": routes, "visits": visits}


async def territory_report(db: AsyncSession, tenant_id: str, period: str) -> list[dict]:
    """Per territory for a month: outlets, outlets visited at least once, visits, delivered sales."""
    import calendar

    year, month = int(period[:4]), int(period[5:7])
    start = datetime(year, month, 1)
    end = datetime(year, month, calendar.monthrange(year, month)[1]) + timedelta(days=1)
    out = []
    for terr in (await db.execute(select(m.FmcgTerritory).where(m.FmcgTerritory.tenant_id == tenant_id).order_by(m.FmcgTerritory.name))).scalars():
        route_ids = (await db.execute(select(m.FmcgTerritoryRoute.route_id).where(m.FmcgTerritoryRoute.territory_id == terr.id))).scalars().all()
        outlet_ids = (
            await db.execute(
                select(m.FmcgCustomerAssignment.customer_id).where(
                    m.FmcgCustomerAssignment.tenant_id == tenant_id, m.FmcgCustomerAssignment.route_id.in_(route_ids or [""])
                )
            )
        ).scalars().all()
        visits = (
            await db.execute(
                select(func.count(), func.count(func.distinct(m.FmcgVisit.outlet_id))).where(
                    m.FmcgVisit.territory_id == terr.id, m.FmcgVisit.checked_in_at >= start, m.FmcgVisit.checked_in_at < end
                )
            )
        ).one()
        sales = (
            await db.execute(
                select(func.coalesce(func.sum(m.FmcgOrder.total - m.FmcgOrder.returned), 0)).where(
                    m.FmcgOrder.tenant_id == tenant_id, m.FmcgOrder.customer_id.in_(outlet_ids or [""]),
                    m.FmcgOrder.status.in_(("delivered", "closed")), m.FmcgOrder.delivered_at >= start, m.FmcgOrder.delivered_at < end,
                )
            )
        ).scalar_one()
        outlets = len(outlet_ids)
        reached = int(visits[1] or 0)
        out.append(
            {
                "territory_id": terr.id, "code": terr.code, "name": terr.name, "outlets": outlets,
                "outlets_visited": reached, "coverage_pct": round(100 * reached / outlets) if outlets else 0,
                "visits": int(visits[0] or 0), "sales": money_json(sales),
            }
        )
    return out
