"""Restaurant order and booking alerts: builds the message; ``online_alerts`` sends it."""

from __future__ import annotations

from app import models as m
from app import online_alerts as core
from app import restaurant as rs

alerts_of = core.alerts_of
serialize = core.serialize
ALERTS_KEY = core.ALERTS_KEY


async def save_alerts(db, tenant_id: str, payload, *, user_id: str | None) -> dict:
    tenant = await rs._restaurant_tenant(db, tenant_id=tenant_id)
    return await core.save_alerts(db, tenant, payload, user_id=user_id)


def compose(tenant: m.Tenant, kind: str, info: dict):
    return core.compose_restaurant(tenant, kind, info)


async def deliver(tenant: m.Tenant, kind: str, info: dict, *, only_test: bool = False) -> dict:
    title, lines, link = compose(tenant, kind, info)
    if only_test:
        title = "Test: " + title
    return await core.deliver(tenant, title, lines, link)


def schedule(background, tenant: m.Tenant, kind: str, info: dict) -> None:
    title, lines, link = compose(tenant, kind, info)
    core.schedule(
        background,
        tenant.id,
        kind=kind,
        title=title,
        lines=lines,
        link=link,
        entity_type="restaurant_order" if kind == "order" else "restaurant_booking",
        entity_id=info.get("id"),
    )


def order_info(order: m.RestaurantOrder, tracked: dict, *, name: str, phone: str, payload) -> dict:
    items = ", ".join(
        f"{int(i['quantity']) if float(i['quantity']).is_integer() else i['quantity']}× {i['name']}"
        for i in tracked.get("items", [])
    )
    return {
        "id": order.id,
        "number": order.order_number,
        "service": tracked.get("service"),
        "total": tracked.get("total_amount"),
        "name": name,
        "phone": phone,
        "items": items,
        "address": getattr(payload, "delivery_address", None) if tracked.get("service") == "delivery" else None,
        "ready_by": getattr(payload, "ready_by", None),
        "allergy": getattr(payload, "allergy", None),
        "notes": getattr(payload, "notes", None),
    }


def booking_info(row: m.RestaurantBooking) -> dict:
    return {
        "id": row.id,
        "name": row.guest_name,
        "phone": row.phone,
        "party": row.party_size,
        "when": row.booked_for.strftime("%a %d %b, %H:%M") if getattr(row, "booked_for", None) else "",
        "notes": row.notes,
    }
