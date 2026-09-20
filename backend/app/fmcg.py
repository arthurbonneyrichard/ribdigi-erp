"""FMCG module — trade schemes, distribution routes, delivery status, near-expiry."""

from __future__ import annotations

from datetime import date, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.honesty import money_json, optional_honest_narrative, require_honest_narrative

SCHEME_TYPES = frozenset({"percent", "fixed", "bxgy"})
VISIT_DAYS = frozenset({"mon", "tue", "wed", "thu", "fri", "sat", "sun"})
DELIVERY_STATUSES = frozenset({"pending", "delivered", "failed", "skipped"})


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
        "product_id": getattr(row, "product_id", None),
        "category_id": getattr(row, "category_id", None),
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
        "delivery_status": getattr(row, "delivery_status", None) or "pending",
        "delivered_at": row.delivered_at.isoformat() if getattr(row, "delivered_at", None) else None,
        "fail_reason": getattr(row, "fail_reason", None),
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
    product_id: str | None = None,
    category_id: str | None = None,
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
    if product_id:
        product = (
            await db.execute(
                select(m.Product).where(m.Product.id == product_id, m.Product.tenant_id == tenant_id)
            )
        ).scalar_one_or_none()
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
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
        product_id=product_id,
        category_id=category_id,
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


def preview_scheme_discount(
    scheme: m.FmcgTradeScheme, *, line_qty: float, line_amount: float
) -> dict:
    """Server-side discount preview (does not mutate sales documents)."""
    qty = float(line_qty or 0)
    amount = float(line_amount or 0)
    discount = 0.0
    bonus_qty = 0.0
    if scheme.scheme_type == "percent":
        discount = round(amount * float(scheme.value or 0) / 100.0, 2)
    elif scheme.scheme_type == "fixed":
        discount = min(amount, float(scheme.value or 0))
    elif scheme.scheme_type == "bxgy":
        buy = max(1, int(scheme.buy_qty or 1))
        get_q = max(0, int(scheme.get_qty or 0))
        if qty >= buy and get_q:
            sets = int(qty // buy)
            bonus_qty = float(sets * get_q)
            unit = amount / qty if qty else 0
            discount = round(bonus_qty * unit, 2)
    return {
        "scheme_id": scheme.id,
        "scheme_code": scheme.code,
        "scheme_type": scheme.scheme_type,
        "discount_amount": money_json(discount),
        "bonus_qty": money_json(bonus_qty),
        "net_amount": money_json(max(0.0, amount - discount)),
    }


async def preview_active_schemes(
    db: AsyncSession,
    *,
    tenant_id: str,
    line_qty: float,
    line_amount: float,
    product_id: str | None = None,
) -> list[dict]:
    today = date.today()
    schemes = await list_schemes(db, tenant_id=tenant_id, is_active=True)
    out: list[dict] = []
    for scheme in schemes:
        if scheme.starts_on and scheme.starts_on > today:
            continue
        if scheme.ends_on and scheme.ends_on < today:
            continue
        if scheme.product_id and product_id and scheme.product_id != product_id:
            continue
        if scheme.product_id and not product_id:
            continue
        out.append(preview_scheme_discount(scheme, line_qty=line_qty, line_amount=line_amount))
    return out


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
        delivery_status="pending",
        notes=optional_honest_narrative(notes, label="notes", max_length=500),
        is_active=True,
    )
    db.add(row)
    await db.flush()
    return row, customer.name


async def update_stop_delivery(
    db: AsyncSession,
    *,
    tenant_id: str,
    stop_id: str,
    delivery_status: str,
    fail_reason: str | None = None,
) -> tuple[m.FmcgRouteStop, str | None]:
    row = (
        await db.execute(
            select(m.FmcgRouteStop).where(
                m.FmcgRouteStop.id == stop_id,
                m.FmcgRouteStop.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Route stop not found")
    status = (delivery_status or "").strip().lower()
    if status not in DELIVERY_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=f"delivery_status must be one of: {', '.join(sorted(DELIVERY_STATUSES))}",
        )
    if status == "failed" and not (fail_reason or "").strip():
        raise HTTPException(status_code=422, detail="fail_reason is required when delivery fails")
    row.delivery_status = status
    row.fail_reason = (
        optional_honest_narrative(fail_reason, label="fail reason", max_length=255)
        if status == "failed"
        else None
    )
    row.delivered_at = datetime.utcnow() if status == "delivered" else None
    row.updated_at = datetime.utcnow()
    party = (
        await db.execute(
            select(m.Party).where(m.Party.id == row.customer_id, m.Party.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    await db.flush()
    return row, party.name if party else None


async def route_performance(db: AsyncSession, *, tenant_id: str) -> list[dict]:
    routes = await list_routes(db, tenant_id=tenant_id, is_active=True)
    out: list[dict] = []
    for route, stop_count in routes:
        stops = (
            await db.execute(
                select(m.FmcgRouteStop).where(
                    m.FmcgRouteStop.tenant_id == tenant_id,
                    m.FmcgRouteStop.route_id == route.id,
                    m.FmcgRouteStop.is_active.is_(True),
                )
            )
        ).scalars().all()
        delivered = sum(1 for s in stops if (s.delivery_status or "pending") == "delivered")
        failed = sum(1 for s in stops if (s.delivery_status or "") == "failed")
        pending = sum(1 for s in stops if (s.delivery_status or "pending") == "pending")
        out.append(
            {
                "route_id": route.id,
                "code": route.code,
                "name": route.name,
                "driver_name": route.driver_name,
                "vehicle": route.vehicle,
                "stops_total": stop_count,
                "delivered": delivered,
                "failed": failed,
                "pending": pending,
                "delivery_rate": round(100.0 * delivered / stop_count, 2) if stop_count else 0.0,
            }
        )
    return out


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
    all_stops = (
        await db.execute(
            select(m.FmcgRouteStop).where(
                m.FmcgRouteStop.tenant_id == tenant_id,
                m.FmcgRouteStop.is_active.is_(True),
            )
        )
    ).scalars().all()
    return {
        "schemes_active": len(schemes),
        "routes_active": len(routes),
        "route_stops": sum(count for _, count in routes),
        "customers_active": len(customers),
        "batches_expiring_30d": len(expiring),
        "deliveries_pending": sum(1 for s in all_stops if (s.delivery_status or "pending") == "pending"),
        "deliveries_completed": sum(1 for s in all_stops if (s.delivery_status or "") == "delivered"),
        "deliveries_failed": sum(1 for s in all_stops if (s.delivery_status or "") == "failed"),
    }


async def list_near_expiry(db: AsyncSession, *, tenant_id: str, within_days: int = 30) -> dict:
    from app import catalog as catalog_svc

    days = max(1, min(365, int(within_days or 30)))
    rows = await catalog_svc.list_expiring_batches(db, tenant_id, within_days=days)
    return {
        "within_days": days,
        "count": len(rows),
        "batches": [catalog_svc.serialize_batch(b) for b in rows],
    }
