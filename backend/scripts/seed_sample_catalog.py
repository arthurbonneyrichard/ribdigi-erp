"""Idempotent local SAMPLE catalog for retail/mart products and hotel rooms.

Does not create tenants or users, does not wipe data, and does not change
existing SKUs/rooms. Skips a row when the tenant already has that SKU or
room code.

Refuses to run unless APP_ENV is non-production and ALLOW_DEVELOPMENT_SEED=true.

Usage (from repo root, with Compose up):

  docker compose exec -e ALLOW_DEVELOPMENT_SEED=true backend python scripts/seed_sample_catalog.py

Optional: SEED_TENANT_SLUG=alpha to limit to one tenant.
"""
from __future__ import annotations

import asyncio
import os
from datetime import date, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app import catalog as catalog_svc
from app import hotel as hotel_svc
from app import models as m
from app import schema_compat
from app.config import settings
from app.db import SessionLocal
from app.honesty import money_json
from app.inventory import apply_stock_change
from app.models import uid
from app.tenants import VALID_INDUSTRIES

PLATFORM_SLUGS = frozenset({"platform", "ribdigi-platform"})
RETAIL_INDUSTRIES = frozenset({"retail", "mart"})
HOTEL_INDUSTRIES = frozenset({"hotel"})
SAMPLE_GUEST_EMAIL = "sample.guest@localhost"
SAMPLE_RESERVATION_NOTE = "SAMPLE stay overlapping tonight (local catalog seed)"

SAMPLE_PRODUCTS = (
    {
        "sku": "SAMPLE-RICE-5KG",
        "name": "Premium Rice 5kg",
        "cost_price": 32,
        "selling_price": 45,
        "stock_qty": 40,
        "reorder_level": 10,
        "category": "Groceries",
        "description": "SAMPLE retail SKU for POS and inventory tests",
    },
    {
        "sku": "SAMPLE-OIL-1L",
        "name": "Cooking Oil 1L",
        "cost_price": 18,
        "selling_price": 28,
        "stock_qty": 25,
        "reorder_level": 8,
        "category": "Groceries",
        "description": "SAMPLE retail SKU for POS and inventory tests",
    },
    {
        "sku": "SAMPLE-SOAP-BAR",
        "name": "Bar Soap",
        "cost_price": 4,
        "selling_price": 8,
        "stock_qty": 60,
        "reorder_level": 12,
        "category": "Household",
        "description": "SAMPLE retail SKU for POS and inventory tests",
    },
    {
        "sku": "SAMPLE-SUGAR-1KG",
        "name": "White Sugar 1kg",
        "cost_price": 8,
        "selling_price": 12,
        "stock_qty": 35,
        "reorder_level": 10,
        "category": "Groceries",
        "description": "SAMPLE retail SKU for POS and inventory tests",
    },
    {
        "sku": "SAMPLE-LOW-STOCK",
        "name": "Instant Noodles",
        "cost_price": 3.5,
        "selling_price": 6,
        "stock_qty": 2,
        "reorder_level": 15,
        "category": "Groceries",
        "description": "SAMPLE low-stock SKU for reorder and alerts",
    },
)

SAMPLE_ROOMS = (
    {
        "code": "SAMPLE-STD-101",
        "name": "Standard 101",
        "room_type": "standard",
        "floor": "1",
        "bed_type": "double",
        "max_occupancy": 2,
        "rate_amount": 280,
        "weekend_rate": 320,
        "status": "available",
    },
    {
        "code": "SAMPLE-STD-102",
        "name": "Standard 102",
        "room_type": "standard",
        "floor": "1",
        "bed_type": "twin",
        "max_occupancy": 2,
        "rate_amount": 280,
        "weekend_rate": 320,
        "status": "available",
    },
    {
        "code": "SAMPLE-DLX-201",
        "name": "Deluxe 201",
        "room_type": "deluxe",
        "floor": "2",
        "bed_type": "king",
        "max_occupancy": 3,
        "rate_amount": 420,
        "weekend_rate": 480,
        "status": "available",
    },
    {
        "code": "SAMPLE-DLX-202",
        "name": "Deluxe 202",
        "room_type": "deluxe",
        "floor": "2",
        "bed_type": "queen",
        "max_occupancy": 3,
        "rate_amount": 420,
        "weekend_rate": 480,
        "status": "available",
    },
    {
        "code": "SAMPLE-MNT-110",
        "name": "Standard 110 (maintenance)",
        "room_type": "standard",
        "floor": "1",
        "bed_type": "double",
        "max_occupancy": 2,
        "rate_amount": 280,
        "status": "maintenance",
    },
)


def _assert_dev_seed_allowed() -> None:
    if settings.APP_ENV.lower() == "production":
        raise RuntimeError("Development sample catalog is forbidden in production")
    if not settings.ALLOW_DEVELOPMENT_SEED:
        raise RuntimeError("Set ALLOW_DEVELOPMENT_SEED=true explicitly to seed SAMPLE catalog data")


def _industry(tenant: m.Tenant) -> str:
    raw = (tenant.industry or "retail").strip().lower()
    return raw if raw in VALID_INDUSTRIES else "retail"


def _is_platform(tenant: m.Tenant) -> bool:
    slug = (tenant.slug or "").strip().lower()
    if slug in PLATFORM_SLUGS:
        return True
    name = (tenant.company_name or "").strip().lower()
    return name == "ribdigi house" or tenant.industry == "software"


async def _admin_user_id(db: AsyncSession, tenant_id: str) -> str | None:
    preferred = (
        await db.execute(
            select(m.User.id)
            .where(
                m.User.tenant_id == tenant_id,
                m.User.is_active.is_(True),
                m.User.role.in_(("company_admin", "super_admin", "store_manager")),
            )
            .order_by(m.User.created_at.asc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if preferred:
        return preferred
    return (
        await db.execute(
            select(m.User.id)
            .where(m.User.tenant_id == tenant_id, m.User.is_active.is_(True))
            .order_by(m.User.created_at.asc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def _login_emails(db: AsyncSession, tenant_id: str) -> list[str]:
    rows = (
        await db.execute(
            select(m.User.email, m.User.role)
            .where(m.User.tenant_id == tenant_id, m.User.is_active.is_(True))
            .order_by(m.User.role.asc(), m.User.email.asc())
        )
    ).all()
    return [f"{email} ({role})" for email, role in rows if email]


async def _seed_products(db: AsyncSession, tenant: m.Tenant) -> tuple[int, int]:
    created = skipped = 0
    user_id = await _admin_user_id(db, tenant.id)
    for spec in SAMPLE_PRODUCTS:
        sku = catalog_svc.normalize_sku(spec["sku"])
        if not sku:
            continue
        exists = (
            await db.execute(
                select(m.Product.id).where(m.Product.tenant_id == tenant.id, m.Product.sku == sku)
            )
        ).scalar_one_or_none()
        if exists:
            skipped += 1
            print(f"  skip product {sku} (already exists)")
            continue
        opening = money_json(spec["stock_qty"])
        payload = {
            "id": uid(),
            "tenant_id": tenant.id,
            "name": spec["name"],
            "sku": sku,
            "description": spec["description"],
            "category": spec["category"],
            "cost_price": spec["cost_price"],
            "selling_price": spec["selling_price"],
            "stock_qty": 0,
            "reorder_level": spec["reorder_level"],
            "minimum_stock": spec["reorder_level"],
            "reserved_qty": 0,
            "tax_supply_class": "standard",
            "tax_exempt": False,
            "is_active": True,
        }
        product = await schema_compat.insert_and_get(db, m.Product, payload)
        if product is None:
            raise RuntimeError(f"Failed to insert product {sku}")
        await db.flush()
        if opening > 0:
            await apply_stock_change(
                db,
                tenant_id=tenant.id,
                product_id=product.id,
                quantity_delta=opening,
                movement_type="opening_stock",
                user_id=user_id,
                reference_type="product",
                reference_id=product.id,
                notes="SAMPLE opening stock (local catalog seed)",
            )
        created += 1
        print(f"  created product {sku} qty={opening} price={spec['selling_price']}")
    return created, skipped


async def _seed_rooms(db: AsyncSession, tenant: m.Tenant) -> tuple[int, int]:
    created = skipped = 0
    for spec in SAMPLE_ROOMS:
        code = spec["code"].upper()
        exists = (
            await db.execute(
                select(m.HotelRoom.id).where(
                    m.HotelRoom.tenant_id == tenant.id,
                    m.HotelRoom.code == code,
                )
            )
        ).scalar_one_or_none()
        if exists:
            skipped += 1
            print(f"  skip room {code} (already exists)")
            continue
        try:
            room = await hotel_svc.create_room(
                db,
                tenant_id=tenant.id,
                code=spec["code"],
                name=spec["name"],
                room_type=spec["room_type"],
                floor=spec.get("floor"),
                bed_type=spec.get("bed_type"),
                max_occupancy=spec.get("max_occupancy", 2),
                rate_amount=spec["rate_amount"],
                weekend_rate=spec.get("weekend_rate"),
                status=spec["status"],
                description="SAMPLE hotel room for occupancy and Book a stay tests",
            )
        except HTTPException as exc:
            if exc.status_code == 409:
                skipped += 1
                print(f"  skip room {code} (already exists)")
                continue
            raise
        created += 1
        print(f"  created room {room.code} type={room.room_type} status={room.status} rate={spec['rate_amount']}")
    return created, skipped


async def _seed_tonight_stay(db: AsyncSession, tenant: m.Tenant) -> str:
    """Insert guest + stay using live table columns (older DBs omit later hotel extras)."""
    guest_row = (
        await db.execute(
            text(
                "SELECT id FROM hotel_guests WHERE tenant_id = :tid AND lower(email) = :em LIMIT 1"
            ),
            {"tid": tenant.id, "em": SAMPLE_GUEST_EMAIL},
        )
    ).first()
    if guest_row is None:
        guest_id = uid()
        now = datetime.utcnow()
        await schema_compat.insert_matching_row(
            db,
            "hotel_guests",
            {
                "id": guest_id,
                "tenant_id": tenant.id,
                "full_name": "SAMPLE Stay Guest",
                "email": SAMPLE_GUEST_EMAIL,
                "phone": "0200000001",
                "notes": "SAMPLE guest for occupancy infographics",
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            },
        )
        await db.flush()
        print(f"  created guest SAMPLE Stay Guest <{SAMPLE_GUEST_EMAIL}>")
    else:
        guest_id = str(guest_row[0])
        print(f"  skip guest {SAMPLE_GUEST_EMAIL} (already exists)")

    today = date.today()
    check_in = today
    check_out = today + timedelta(days=2)
    existing = (
        await db.execute(
            text(
                "SELECT reservation_number FROM hotel_reservations "
                "WHERE tenant_id = :tid AND guest_id = :gid AND notes = :notes LIMIT 1"
            ),
            {"tid": tenant.id, "gid": guest_id, "notes": SAMPLE_RESERVATION_NOTE},
        )
    ).first()
    if existing:
        print(f"  skip reservation {existing[0]} (already exists)")
        return str(existing[0])

    room_row = (
        await db.execute(
            select(m.HotelRoom.id, m.HotelRoom.rate_amount, m.HotelRoom.status).where(
                m.HotelRoom.tenant_id == tenant.id,
                m.HotelRoom.code == "SAMPLE-STD-101",
            )
        )
    ).first()
    if room_row is None:
        print("  skip tonight stay (SAMPLE-STD-101 missing)")
        return ""
    room_id, rate_amount, room_status = str(room_row[0]), float(room_row[1] or 0), str(room_row[2] or "")
    if room_status in {"maintenance", "out_of_order", "blocked", "dirty"}:
        print(f"  skip tonight stay (SAMPLE-STD-101 is {room_status})")
        return ""

    overlap = (
        await db.execute(
            text(
                """
                SELECT id FROM hotel_reservations
                WHERE tenant_id = :tid AND room_id = :rid
                  AND status IN ('tentative', 'booked', 'checked_in')
                  AND check_in_date < :co AND check_out_date > :ci
                LIMIT 1
                """
            ),
            {"tid": tenant.id, "rid": room_id, "ci": check_in, "co": check_out},
        )
    ).first()
    if overlap:
        print("  skip tonight stay (SAMPLE-STD-101 already booked in this window)")
        return ""

    year = datetime.utcnow().year
    prefix = f"HR-{year}-"
    count = (
        await db.execute(
            text(
                "SELECT count(*) FROM hotel_reservations "
                "WHERE tenant_id = :tid AND reservation_number LIKE :pfx"
            ),
            {"tid": tenant.id, "pfx": f"{prefix}%"},
        )
    ).scalar()
    reservation_number = f"{prefix}{int(count or 0) + 1:04d}"
    user_id = await _admin_user_id(db, tenant.id)
    now = datetime.utcnow()
    await schema_compat.insert_matching_row(
        db,
        "hotel_reservations",
        {
            "id": uid(),
            "tenant_id": tenant.id,
            "reservation_number": reservation_number,
            "room_id": room_id,
            "guest_id": guest_id,
            "check_in_date": check_in,
            "check_out_date": check_out,
            "adults": 1,
            "children": 0,
            "status": "booked",
            "booking_source": "direct",
            "nightly_rate": rate_amount,
            "deposit_amount": 0,
            "notes": SAMPLE_RESERVATION_NOTE,
            "created_by": user_id,
            "created_at": now,
            "updated_at": now,
        },
    )
    if room_status in {"available", "clean", "inspected", "reserved"}:
        await db.execute(
            text(
                "UPDATE hotel_rooms SET status = 'reserved', updated_at = :now "
                "WHERE id = :rid AND tenant_id = :tid"
            ),
            {"now": now, "rid": room_id, "tid": tenant.id},
        )
    await db.flush()
    print(
        f"  created reservation {reservation_number} "
        f"{check_in.isoformat()} → {check_out.isoformat()} room SAMPLE-STD-101"
    )
    return reservation_number


async def main() -> None:
    _assert_dev_seed_allowed()
    slug_filter = (os.environ.get("SEED_TENANT_SLUG") or "").strip().lower() or None

    async with SessionLocal() as db:
        tenants = list((await db.execute(select(m.Tenant).order_by(m.Tenant.created_at.asc()))).scalars().all())
        customers = [t for t in tenants if not _is_platform(t)]
        if slug_filter:
            customers = [t for t in customers if (t.slug or "").lower() == slug_filter]
        if not customers:
            print("No customer tenants found. Create a tenant (register UI) or run scripts/seed.py first.")
            print("Then re-run this script. Platform/House workspaces are skipped.")
            return

        print(f"Found {len(customers)} customer tenant(s). Seeding by industry (retail/mart → products, hotel → rooms).")
        for tenant in customers:
            industry = _industry(tenant)
            emails = await _login_emails(db, tenant.id)
            print(f"\nTenant slug={tenant.slug} industry={industry} name={tenant.company_name}")
            if emails:
                print("  existing logins (passwords are not printed; see seed.py / your own register):")
                for line in emails:
                    print(f"    {line}")
            else:
                print("  no users on this tenant — sign in with an account you already created")

            if industry in RETAIL_INDUSTRIES:
                created, skipped = await _seed_products(db, tenant)
                print(f"  products created={created} skipped={skipped}")
            elif industry in HOTEL_INDUSTRIES:
                created, skipped = await _seed_rooms(db, tenant)
                print(f"  rooms created={created} skipped={skipped}")
                await db.flush()
                await _seed_tonight_stay(db, tenant)
            else:
                print(f"  skip (industry {industry} is neither retail/mart nor hotel)")
            await db.commit()
            print("  committed")
        print("\nSAMPLE catalog seed finished. Re-run anytime; existing SKUs and room codes are left unchanged.")


if __name__ == "__main__":
    asyncio.run(main())
