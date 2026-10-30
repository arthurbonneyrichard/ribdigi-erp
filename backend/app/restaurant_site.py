"""Restaurant public website: menu, online food orders (pickup or delivery) and table bookings.

One page per restaurant (/book/<slug> and /order/<slug>). Ordering follows the
restaurant's "online orders" switch; booking follows its saved booking link.
Orders land on restaurant_orders and bookings on restaurant_bookings, so the
restaurant sees them on its Orders board and booking desk. Nothing is charged
here: the guest pays when they collect, on delivery, or at the table.
"""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app import restaurant as rs
from app.honesty import money_json, optional_honest_narrative, require_honest_narrative

MAX_LINES = 30
SITE_PAY_METHODS = {"cash", "mobile_money", "card"}
TRACK_WORDS = {
    "open": "Received",
    "sent": "In the kitchen",
    "preparing": "Cooking",
    "ready": "Ready",
    "completed": "Done",
    "refunded": "Refunded",
    "cancelled": "Cancelled",
    "voided": "Cancelled",
}


async def _booking_link(db: AsyncSession, tenant_id: str) -> m.RestaurantBookingLink | None:
    return (
        await db.execute(select(m.RestaurantBookingLink).where(m.RestaurantBookingLink.tenant_id == tenant_id))
    ).scalar_one_or_none()


async def _site_tenant(db: AsyncSession, slug: str) -> tuple[m.Tenant, bool, bool]:
    tenant = await rs._restaurant_tenant(db, slug=slug)
    booking_open = await _booking_link(db, tenant.id) is not None
    ordering_open = rs._online_orders_open(tenant)
    if not booking_open and not ordering_open:
        raise HTTPException(status_code=404, detail="This restaurant is not taking orders or bookings online")
    return tenant, booking_open, ordering_open


async def _menu(db: AsyncSession, tenant: m.Tenant) -> list[dict]:
    rows = await rs.list_public_menu(db, tenant.id)
    if not rows:
        return []
    products = {
        p.id: p
        for p in (
            await db.execute(
                select(m.Product).where(m.Product.tenant_id == tenant.id, m.Product.id.in_([r["id"] for r in rows]))
            )
        ).scalars()
    }
    out = []
    for row in rows:
        product = products.get(row["id"])
        station = (getattr(product, "prep_station", None) or "").strip().lower()
        out.append({
            **row,
            "category": (getattr(product, "category", None) or ("Drinks" if station == "bar" else "Food")).strip(),
            "description": (getattr(product, "description", None) or "").strip() or None,
            "has_image": bool(getattr(product, "image_url", None)),
            "kind": "drink" if station == "bar" else "food",
        })
    return out


async def site_page(db: AsyncSession, slug: str) -> dict:
    tenant, booking_open, ordering_open = await _site_tenant(db, slug)
    return {
        "slug": tenant.slug,
        "company_name": tenant.company_name,
        "phone": tenant.phone,
        "email": tenant.email,
        "address": tenant.address,
        "currency": tenant.currency or "GHS",
        "has_logo": bool(getattr(tenant, "logo_url", None)),
        "booking_open": booking_open,
        "ordering_open": ordering_open,
        "delivery_zones": await rs.list_delivery_zones(db, tenant.id) if ordering_open else [],
        "service_percent": await rs.service_percent(db, tenant.id),
        "menu": await _menu(db, tenant),
    }


async def menu_image_key(db: AsyncSession, slug: str, product_id: str) -> tuple[m.Tenant, str]:
    tenant, _booking, _ordering = await _site_tenant(db, slug)
    product = await db.get(m.Product, product_id)
    if (
        product is None
        or product.tenant_id != tenant.id
        or not product.image_url
        or not await rs._is_public_menu_item(db, tenant.id, product)
    ):
        raise HTTPException(status_code=404, detail="Menu photo not found")
    return tenant, product.image_url


async def site_logo_tenant(db: AsyncSession, slug: str) -> m.Tenant:
    tenant, _booking, _ordering = await _site_tenant(db, slug)
    if not getattr(tenant, "logo_url", None):
        raise HTTPException(status_code=404, detail="No logo uploaded")
    return tenant


async def _public_lines(db: AsyncSession, tenant: m.Tenant, lines: list) -> list[tuple[m.Product, float]]:
    if not lines or len(lines) > MAX_LINES:
        raise HTTPException(status_code=422, detail=f"Choose from 1 to {MAX_LINES} dishes or drinks.")
    sold_out = set(rs._stored_sold_out(tenant))
    out = []
    for line in lines:
        product = await rs._product(db, tenant.id, line.product_id)
        if not await rs._is_public_menu_item(db, tenant.id, product):
            raise HTTPException(status_code=422, detail="Choose from the menu.")
        if product.id in sold_out:
            raise HTTPException(status_code=409, detail=f"{product.name} is sold out today.")
        out.append((product, float(line.quantity)))
    return out


class _SiteOrder:
    """The shape rs.create_order reads."""

    def __init__(self, **fields):
        self.store_id = None
        self.table_id = None
        self.delivery_zone = None
        self.delivery_address = None
        for key, value in fields.items():
            setattr(self, key, value)


async def create_site_order(db: AsyncSession, slug: str, payload) -> m.RestaurantOrder:
    tenant, _booking, ordering_open = await _site_tenant(db, slug)
    if not ordering_open:
        raise HTTPException(status_code=404, detail="Online food orders are closed")
    name = require_honest_narrative(payload.customer_name, label="name", max_length=180)
    picked = await _public_lines(db, tenant, payload.lines)
    service = "delivery" if payload.service == "delivery" else "takeaway"
    address = None
    if service == "delivery":
        address = optional_honest_narrative(payload.delivery_address, label="delivery address")
        if not address:
            raise HTTPException(status_code=422, detail="Add the delivery address.")
    method = payload.pay_with if payload.pay_with in SITE_PAY_METHODS else "cash"
    order = await rs.create_order(
        db,
        tenant.id,
        _SiteOrder(
            service_mode=service,
            payment_method=method,
            customer_name=name,
            notes=payload.notes,
            delivery_address=address,
            delivery_zone=payload.delivery_zone if service == "delivery" else None,
            phone=payload.phone,
            guest_email=payload.email,
            allergy=payload.allergy,
            ready_by=payload.ready_by if service == "takeaway" else None,
            lines=[rs._GuestLine(product.id, qty) for product, qty in picked],
        ),
        user_id=None,
    )
    order.notes = rs.write_order_channel(order.notes)
    await db.flush()
    return order


async def create_site_booking(db: AsyncSession, slug: str, payload) -> m.RestaurantBooking:
    tenant, booking_open, _ordering = await _site_tenant(db, slug)
    if not booking_open:
        raise HTTPException(status_code=404, detail="Restaurant booking is not open")
    note = optional_honest_narrative(payload.notes, label="booking note", max_length=300)
    if payload.pre_order:
        # Dishes to have ready: kept on the booking for staff, rung on the till when the party sits.
        picked = await _public_lines(db, tenant, payload.pre_order)
        words = ", ".join(f"{int(qty) if qty == int(qty) else qty}× {product.name}" for product, qty in picked)
        pre = f"Pre-order: {words}"
        note = f"{note}. {pre}" if note else pre
        if len(note) > 500:
            raise HTTPException(status_code=422, detail="That pre-order is too long. Order fewer dishes, or order at the table.")
    return await rs._new_booking(
        db,
        tenant.id,
        guest_name=payload.guest_name,
        phone=payload.phone,
        party_size=payload.party_size,
        booked_for=payload.booked_for,
        notes=note,
    )


async def track_order(db: AsyncSession, slug: str, order_id: str) -> dict:
    tenant, _booking, _ordering = await _site_tenant(db, slug)
    order = await db.get(m.RestaurantOrder, order_id)
    if order is None or order.tenant_id != tenant.id or not rs.channel_for_order(order.notes):
        raise HTTPException(status_code=404, detail="Order not found")
    presented = (await rs.present_orders(db, tenant.id, [order]))[0]
    return {
        "id": order.id,
        "order_number": order.order_number,
        "status": order.status,
        "status_words": TRACK_WORDS.get(order.status, order.status),
        "service": "delivery" if order.service_mode == "delivery" else "pickup",
        "total_amount": money_json(order.total_amount),
        "items": [
            {"name": item["name"], "quantity": item["quantity"], "line_total": item["line_total"]}
            for item in presented["items"]
        ],
    }
