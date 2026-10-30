"""Seed a disposable local restaurant company for checking the restaurant till.

Run inside the backend container (local Docker only):
    PYTHONPATH=. python scripts/seed_restaurant_till_demo.py

Creates company `rest-till-demo` (admin owner@rest-till-demo.example) with a branch,
tables, a menu with kitchen and bar items, and an extras group. Refuses to run
when APP_ENV is production. Re-running reuses the company.
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

SLUG = "rest-till-demo"
EMAIL = "owner@rest-till-demo.example"
PASSWORD = os.environ.get("DEMO_PASSWORD", "Demo-Till-2026!")
API = os.environ.get("DEMO_API", "http://localhost:8000/api/v1")

MENU = [
    ("Jollof rice and chicken", 65, "Mains", "kitchen"),
    ("Banku and tilapia", 80, "Mains", "kitchen"),
    ("Waakye special", 45, "Mains", "kitchen"),
    ("Fried rice and beef", 60, "Mains", "kitchen"),
    ("Kelewele", 20, "Sides", "kitchen"),
    ("Fried plantain", 15, "Sides", "kitchen"),
    ("Garden salad", 25, "Sides", "kitchen"),
    ("Light soup and fufu", 70, "Soups", "kitchen"),
    ("Groundnut soup", 70, "Soups", "kitchen"),
    ("Sobolo", 12, "Drinks", "bar"),
    ("Fresh pineapple juice", 18, "Drinks", "bar"),
    ("Malt", 10, "Drinks", "bar"),
    ("Bottled water", 5, "Drinks", "bar"),
    ("Coconut ice cream", 22, "Desserts", "kitchen"),
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
                company_name="Till Demo Kitchen",
                industry="restaurant",
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


async def seed_floor_and_menu() -> None:
    async with httpx.AsyncClient(base_url=API, timeout=60) as client:
        r = await client.post("/auth/login", json={"tenant_id": SLUG, "email": EMAIL, "password": PASSWORD})
        r.raise_for_status()
        token = r.json()["data"]["access_token"]
        h = {"Authorization": f"Bearer {token}"}

        stores = (await client.get("/stores", headers=h)).json().get("data") or []
        if not stores:
            r = await client.post("/stores", headers=h, json={"name": "Osu branch", "code": "OSU"})
            r.raise_for_status()
            stores = [r.json()["data"]]
        store_id = stores[0]["id"]

        tables = (await client.get("/restaurant/tables", headers=h)).json().get("data") or []
        if not tables:
            for n in range(1, 9):
                r = await client.post(
                    "/restaurant/tables",
                    headers=h,
                    json={"code": f"T{n}", "name": str(n), "seats": 4 if n % 3 else 6, "store_id": store_id},
                )
                if r.status_code >= 400:
                    print("table", n, r.status_code, r.text[:200])

        have = {p["name"] for p in ((await client.get("/products", headers=h)).json().get("data") or [])}
        for name, price, category, station in MENU:
            if name in have:
                continue
            r = await client.post(
                "/products",
                headers=h,
                json={
                    "name": name,
                    "selling_price": price,
                    "cost_price": round(price * 0.4, 2),
                    "category": category,
                    "prep_station": station,
                    "stock_qty": 200,
                },
            )
            if r.status_code >= 400:
                print("product", name, r.status_code, r.text[:200])

        groups = (await client.get("/restaurant/modifiers", headers=h)).json().get("data") or []
        if not groups:
            r = await client.post("/restaurant/modifier-groups", headers=h, json={"name": "Extras"})
            if r.status_code < 400:
                gid = r.json()["data"]["id"]
                for mod, price in [("Extra chicken", 15), ("Extra shito", 3), ("Extra pepper", 0), ("No onions", 0)]:
                    await client.post(
                        f"/restaurant/modifier-groups/{gid}/modifiers",
                        headers=h,
                        json={"name": mod, "price": price},
                    )
            else:
                print("modifier group", r.status_code, r.text[:200])
        print("ready: sign in at /login with company", SLUG, "and", EMAIL)


async def main() -> None:
    if (settings.APP_ENV or "").strip().lower() == "production":
        sys.exit("refusing to seed a demo company in production")
    await ensure_company()
    await seed_floor_and_menu()


if __name__ == "__main__":
    asyncio.run(main())
