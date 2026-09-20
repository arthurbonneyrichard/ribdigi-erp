"""FMCG module — trade schemes, distribution routes, and ops summary."""

from __future__ import annotations

from datetime import date, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.honesty import money_json, optional_honest_narrative, require_honest_narrative

SCHEME_TYPES = frozenset({"percent", "fixed", "bxgy"})
VISIT_DAYS = frozenset({"mon", "tue", "wed", "thu", "fri", "sat", "sun"})


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


def serialize_scheme(row: m.FmcgTradeScheme) -> dict:
    return {
        "id": row.id,
        "code": row.code,
        "name": row.name,
        "scheme_type": row.scheme_type,
        "value": money_json(row.value or 0),
        "buy_qty": int(row.buy_qty or 0),
        "get_qty": int(row.get_qty or 0),
        "starts_on": row.starts_on.isoformat() if row.starts_on else None,
        "ends_on": row.ends_on.isoformat() if row.ends_on else None,
        "notes": row.notes,
        "is_active": bool(row.is_active),
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def serialize_route(row: m.FmcgRoute, *, stop_count: int | None = None) -> dict:
    return {
        "id": row.id,
        "code": row.code,
        "name": row.name,
        "driver_name": row.driver_name,
        "vehicle": row.vehicle,
        "notes": row.notes,
        "is_active": bool(row.is_active),
        "stop_count": stop_count,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def serialize_stop(row: m.FmcgRouteStop, *, customer_name: str | None = None) -> dict:
    return {
        "id": row.id,
        "route_id": row.route_id,
        "customer_id": row.customer_id,
        "customer_name": customer_name,
        "sequence": int(row.sequence or 1),
        "visit_day": row.visit_day,
        "notes": row.notes,
        "is_active": bool(row.is_active),
    }


async def list_schemes(
    db: AsyncSession, *, tenant_id: str, is_active: bool | None = None
) -> list[m.FmcgTradeScheme]:
    stmt = (
        select(m.FmcgTradeScheme)
        .where(m.FmcgTradeScheme.tenant_id == tenant_id)
        .order_by(m.FmcgTradeScheme.code.asc())
    )
    if is_active is not None:
        stmt = stmt.where(m.FmcgTradeScheme.is_active.is_(bool(is_active)))
    return list((await db.execute(stmt)).scalars().all())


async def create_scheme(
    db: AsyncSession,
    *,
    tenant_id: str,
    code: str,
    name: str,
    scheme_type: str = "percent",
    value: float = 0,
    buy_qty: int = 0,
    get_qty: int = 0,
    starts_on: date | str | None = None,
    ends_on: date | str | None = None,
    notes: str | None = None,
) -> m.FmcgTradeScheme:
    code_clean = require_honest_narrative(code, label="scheme code", max_length=40).upper()
    name_clean = require_honest_narrative(name, label="scheme name", max_length=150)
    type_key = (scheme_type or "percent").strip().lower()
    if type_key not in SCHEME_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"scheme_type must be one of: {', '.join(sorted(SCHEME_TYPES))}",
        )
    exists = (
        await db.execute(
            select(m.FmcgTradeScheme).where(
                m.FmcgTradeScheme.tenant_id == tenant_id,
                m.FmcgTradeScheme.code == code_clean,
            )
        )
    ).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="Scheme code already exists")
    start = _as_date(starts_on)
    end = _as_date(ends_on)
    if start and end and end < start:
        raise HTTPException(status_code=400, detail="ends_on must be on or after starts_on")
    row = m.FmcgTradeScheme(
        tenant_id=tenant_id,
        code=code_clean,
        name=name_clean,
        scheme_type=type_key,
        value=value or 0,
        buy_qty=max(0, int(buy_qty or 0)),
        get_qty=max(0, int(get_qty or 0)),
        starts_on=start,
        ends_on=end,
        notes=optional_honest_narrative(notes, label="notes", max_length=500),
        is_active=True,
    )
    db.add(row)
    await db.flush()
    return row


async def set_scheme_active(
    db: AsyncSession, *, tenant_id: str, scheme_id: str, is_active: bool
) -> m.FmcgTradeScheme:
    row = (
        await db.execute(
            select(m.FmcgTradeScheme).where(
                m.FmcgTradeScheme.id == scheme_id,
                m.FmcgTradeScheme.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Trade scheme not found")
    row.is_active = bool(is_active)
    row.updated_at = datetime.utcnow()
    await db.flush()
    return row


async def list_routes(
    db: AsyncSession, *, tenant_id: str, is_active: bool | None = None
) -> list[tuple[m.FmcgRoute, int]]:
    stmt = select(m.FmcgRoute).where(m.FmcgRoute.tenant_id == tenant_id).order_by(m.FmcgRoute.code)
    if is_active is not None:
        stmt = stmt.where(m.FmcgRoute.is_active.is_(bool(is_active)))
    routes = list((await db.execute(stmt)).scalars().all())
    out: list[tuple[m.FmcgRoute, int]] = []
    for route in routes:
        count = (
            await db.execute(
                select(m.FmcgRouteStop).where(
                    m.FmcgRouteStop.tenant_id == tenant_id,
                    m.FmcgRouteStop.route_id == route.id,
                    m.FmcgRouteStop.is_active.is_(True),
                )
            )
        ).scalars().all()
        out.append((route, len(count)))
    return out


async def create_route(
    db: AsyncSession,
    *,
    tenant_id: str,
    code: str,
    name: str,
    driver_name: str | None = None,
    vehicle: str | None = None,
    notes: str | None = None,
) -> m.FmcgRoute:
    code_clean = require_honest_narrative(code, label="route code", max_length=40).upper()
    name_clean = require_honest_narrative(name, label="route name", max_length=150)
    exists = (
        await db.execute(
            select(m.FmcgRoute).where(
                m.FmcgRoute.tenant_id == tenant_id,
                m.FmcgRoute.code == code_clean,
            )
        )
    ).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="Route code already exists")
    row = m.FmcgRoute(
        tenant_id=tenant_id,
        code=code_clean,
        name=name_clean,
        driver_name=optional_honest_narrative(driver_name, label="driver name", max_length=150),
        vehicle=optional_honest_narrative(vehicle, label="vehicle", max_length=80),
        notes=optional_honest_narrative(notes, label="notes", max_length=500),
        is_active=True,
    )
    db.add(row)
    await db.flush()
    return row


async def _get_route(db: AsyncSession, tenant_id: str, route_id: str) -> m.FmcgRoute:
    row = (
        await db.execute(
            select(m.FmcgRoute).where(m.FmcgRoute.id == route_id, m.FmcgRoute.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if not row or not row.is_active:
        raise HTTPException(status_code=404, detail="Route not found")
    return row


async def list_stops(
    db: AsyncSession, *, tenant_id: str, route_id: str
) -> list[tuple[m.FmcgRouteStop, str | None]]:
    await _get_route(db, tenant_id, route_id)
    rows = (
        await db.execute(
            select(m.FmcgRouteStop, m.Party)
            .outerjoin(m.Party, m.Party.id == m.FmcgRouteStop.customer_id)
            .where(
                m.FmcgRouteStop.tenant_id == tenant_id,
                m.FmcgRouteStop.route_id == route_id,
            )
            .order_by(m.FmcgRouteStop.sequence.asc(), m.FmcgRouteStop.created_at.asc())
        )
    ).all()
    return [(stop, party.name if party else None) for stop, party in rows]


async def add_stop(
    db: AsyncSession,
    *,
    tenant_id: str,
    route_id: str,
    customer_id: str,
    sequence: int = 1,
    visit_day: str | None = None,
    notes: str | None = None,
) -> tuple[m.FmcgRouteStop, str | None]:
    await _get_route(db, tenant_id, route_id)
    customer = (
        await db.execute(
            select(m.Party).where(
                m.Party.id == customer_id,
                m.Party.tenant_id == tenant_id,
                m.Party.kind == "customer",
            )
        )
    ).scalar_one_or_none()
    if not customer or (customer.status or "active").lower() != "active":
        raise HTTPException(status_code=404, detail="Customer not found")
    day = (visit_day or "").strip().lower() or None
    if day and day not in VISIT_DAYS:
        raise HTTPException(
            status_code=422,
            detail=f"visit_day must be one of: {', '.join(sorted(VISIT_DAYS))}",
        )
    exists = (
        await db.execute(
            select(m.FmcgRouteStop).where(
                m.FmcgRouteStop.tenant_id == tenant_id,
                m.FmcgRouteStop.route_id == route_id,
                m.FmcgRouteStop.customer_id == customer_id,
            )
        )
    ).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="Customer already on this route")
    row = m.FmcgRouteStop(
        tenant_id=tenant_id,
        route_id=route_id,
        customer_id=customer_id,
        sequence=max(1, int(sequence or 1)),
        visit_day=day,
        notes=optional_honest_narrative(notes, label="notes", max_length=500),
        is_active=True,
    )
    db.add(row)
    await db.flush()
    return row, customer.name


async def summary(db: AsyncSession, *, tenant_id: str) -> dict:
    from app import catalog as catalog_svc

    schemes = await list_schemes(db, tenant_id=tenant_id, is_active=True)
    routes = await list_routes(db, tenant_id=tenant_id, is_active=True)
    expiring = await catalog_svc.list_expiring_batches(db, tenant_id, within_days=30)
    customers = (
        await db.execute(
            select(m.Party).where(
                m.Party.tenant_id == tenant_id,
                m.Party.kind == "customer",
                m.Party.status == "active",
            )
        )
    ).scalars().all()
    return {
        "schemes_active": len(schemes),
        "routes_active": len(routes),
        "route_stops": sum(count for _, count in routes),
        "customers_active": len(customers),
        "batches_expiring_30d": len(expiring),
    }
