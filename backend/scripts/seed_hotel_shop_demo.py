"""Seed a disposable local hotel company for checking the hotel shop till.

Run inside the backend container (local Docker only):
    PYTHONPATH=. python scripts/seed_hotel_shop_demo.py

Creates company `hotel-shop-demo` (admin owner@hotel-shop-demo.example) with shop
items, a room and a checked-in guest (open folio). Refuses to run when APP_ENV is
production. Re-running reuses the company.
"""

from __future__ import annotations

import asyncio
import os
import sys

import httpx
from sqlalchemy import select

from app import models as m
from app.config import settings
from app.db import SessionLocal
from app.rbac import permissions_for_role
from app.security import hash_password

SLUG = "hotel-shop-demo"
EMAIL = "owner@hotel-shop-demo.example"
PASSWORD = os.environ.get("DEMO_PASSWORD", "Demo-Till-2026!")
API = os.environ.get("DEMO_API", "http://localhost:8000/api/v1")

ITEMS = [
    ("Bottled water", 5, "Drinks"),
    ("Coca-Cola", 8, "Drinks"),
    ("Malt", 10, "Drinks"),
    ("Chocolate bar", 12, "Snacks"),
    ("Plantain chips", 6, "Snacks"),
    ("Toothbrush kit", 15, "Toiletries"),
    ("Phone charger", 45, "Travel"),
    ("Kente keyring", 25, "Gifts"),
]


async def ensure_company() -> None:
    from app.api import seed_tenant_defaults
    from app import tenants as tenants_svc

    async with SessionLocal() as db:
        tenant = (await db.execute(select(m.Tenant).where(m.Tenant.slug == SLUG))).scalar_one_or_none()
        if tenant is None:
            now = tenants_svc.datetime.utcnow() if hasattr(tenants_svc, "datetime") else None
            trial_end = tenants_svc.default_trial_ends_at()
            tenant = m.Tenant(
                slug=SLUG,
                company_name="Shop Demo Lodge",
                industry="hotel",
                currency="GHS",
                status="trial",
                trial_ends_at=trial_end,
                trial_notices={},
                package_code="trial",
                subscription_term_unit="months",
                subscription_term_value=1,
                subscription_ends_at=trial_end,
            )
            if now is not None:
                tenant.subscription_starts_at = now
                tenant.package_assigned_at = now
            db.add(tenant)
            await db.flush()
            db.add(
                m.User(
                    tenant_id=tenant.id,
                    email=EMAIL,
                    full_name="Demo Owner",
                    password_hash=hash_password(PASSWORD),
                    role="company_admin",
                    email_verified=True,
                    permissions=permissions_for_role("company_admin"),
                )
            )
            await db.flush()
            await seed_tenant_defaults(db, tenant.id)
            await db.commit()
            print("created company", SLUG)
        else:
            print("company exists", SLUG)


async def seed_shop_and_guest() -> None:
    from datetime import date, timedelta

    async with httpx.AsyncClient(base_url=API, timeout=60) as client:
        r = await client.post("/auth/login", json={"tenant_id": SLUG, "email": EMAIL, "password": PASSWORD})
        r.raise_for_status()
        h = {"Authorization": f"Bearer {r.json()['data']['access_token']}"}
        have = {p["name"] for p in ((await client.get("/products", headers=h)).json().get("data") or [])}
        for name, price, category in ITEMS:
            if name in have:
                continue
            r = await client.post(
                "/products",
                headers=h,
                json={"name": name, "selling_price": price, "cost_price": round(price * 0.5, 2), "category": category, "stock_qty": 50},
            )
            if r.status_code >= 400:
                print("product", name, r.status_code, r.text[:200])
        folios = (await client.get("/hotel/shop/rooms", headers=h)).json().get("data") or []
        if not folios:
            room = await client.post(
                "/hotel/rooms", headers=h,
                json={"code": "101", "name": "Garden room", "room_type": "standard", "rate_amount": 300, "max_occupancy": 2},
            )
            guest = await client.post("/hotel/guests", headers=h, json={"full_name": "Abena Owusu", "phone": "+233244123456"})
            start = date.today()
            booked = await client.post(
                "/hotel/reservations", headers=h,
                json={
                    "room_id": room.json()["data"]["id"], "guest_id": guest.json()["data"]["id"],
                    "check_in_date": start.isoformat(), "check_out_date": (start + timedelta(days=2)).isoformat(), "adults": 1,
                },
            )
            r = await client.post(f"/hotel/reservations/{booked.json()['data']['id']}/check-in", headers=h, json={})
            print("checked in", r.status_code)
        print("ready: sign in at /login with company", SLUG, "and", EMAIL)


async def main() -> None:
    if (settings.APP_ENV or "").strip().lower() == "production":
        sys.exit("refusing to seed a demo company in production")
    await ensure_company()
    await seed_shop_and_guest()


if __name__ == "__main__":
    asyncio.run(main())
