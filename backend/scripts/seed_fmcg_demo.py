"""Seed a realistic local distributor for walking and recording the FMCG desk.

Run inside the backend container (local Docker only):
    PYTHONPATH=. python scripts/seed_fmcg_demo.py

Creates company `demo-fmcg-rec` (Northern Star Distributors, owner@northernstar.example.com,
plus a sales rep and a driver): products, a scheme, routes, outlets, orders at each stage,
collections and a return. Everything after the company itself goes through the API.
Refuses to run in production. Re-running reuses the company and skips the rest.
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

SLUG = "demo-fmcg-rec"
EMAIL = "owner@northernstar.example.com"
STAFF = [
    ("rep@northernstar.example.com", "Kofi Adu", "fmcg_rep"),
    ("driver@northernstar.example.com", "Issah Alhassan", "fmcg_driver"),
]
PASSWORD = os.environ.get("DEMO_PASSWORD", "NorthernStar-Video-2026!")
API = os.environ.get("DEMO_API", "http://localhost:8000/api/v1")

PRODUCTS = [
    ("Bar soap, carton of 48", 180, 240, 300),
    ("Cooking oil, 5 litre", 95, 125, 400),
    ("Tomato paste, carton of 24", 140, 190, 250),
    ("Bottled water, pack of 12", 18, 28, 800),
    ("Rice, 25 kg bag", 310, 380, 200),
]
OUTLETS = [
    ("Mama Esi Provisions", "+233244100201", "Madina Market", 3000, 14, "North"),
    ("Blessed Mini Mart", "+233244100202", "Adenta Barrier", 5000, 30, "North"),
    ("Akwaaba Wholesale", "+233244100203", "Kaneshie", 12000, 30, "West"),
    ("Corner Kiosk", "+233244100204", "Dansoman", 0, 7, "West"),
]


async def ensure_company() -> None:
    from app import tenants as tenants_svc
    from app.api import seed_tenant_defaults

    async with SessionLocal() as db:
        tenant = (await db.execute(select(m.Tenant).where(m.Tenant.slug == SLUG))).scalar_one_or_none()
        if tenant is not None:
            print("company exists", SLUG)
            return
        trial_end = tenants_svc.default_trial_ends_at()
        tenant = m.Tenant(
            slug=SLUG,
            company_name="Northern Star Distributors",
            industry="fmcg",
            currency="GHS",
            status="trial",
            trial_ends_at=trial_end,
            trial_notices={},
            package_code="trial",
            subscription_term_unit="months",
            subscription_term_value=1,
            subscription_ends_at=trial_end,
        )
        db.add(tenant)
        await db.flush()
        for email, name, role in [(EMAIL, "Abdul Rahman", "company_admin"), *STAFF]:
            db.add(
                m.User(
                    tenant_id=tenant.id,
                    email=email,
                    # Staff sign in on the User tab with this name, e.g. rep.ns.
                    username=None if role == "company_admin" else f"{email.split('@')[0]}.ns",
                    full_name=name,
                    password_hash=hash_password(PASSWORD),
                    role=role,
                    email_verified=True,
                    permissions=permissions_for_role(role),
                )
            )
        await db.flush()
        await seed_tenant_defaults(db, tenant.id)
        await db.commit()
        print("created company", SLUG)


async def post(client, h, path, body):
    r = await client.post(path, headers=h, json=body)
    if r.status_code >= 400:
        raise SystemExit(f"FAIL {path} {r.status_code} {r.text[:300]}")
    return r.json().get("data")


async def seed() -> None:
    async with httpx.AsyncClient(base_url=API, timeout=60) as c:
        r = await c.post("/auth/login", json={"tenant_id": SLUG, "email": EMAIL, "password": PASSWORD})
        r.raise_for_status()
        h = {"Authorization": f"Bearer {r.json()['data']['access_token']}"}
        if (await c.get("/fmcg/outlets", headers=h)).json().get("data"):
            print("already seeded")
            return

        products = {}
        for name, cost, price, stock in PRODUCTS:
            row = await post(c, h, "/products", {"name": name, "cost_price": cost, "selling_price": price, "stock_qty": stock, "category": "Trade goods"})
            products[name] = row["id"]
        await post(
            c, h, "/fmcg/schemes",
            {"code": "OIL5", "name": "5% off cooking oil", "scheme_type": "percent", "value": 5, "product_id": products["Cooking oil, 5 litre"]},
        )

        routes = {}
        for code, name, driver, vehicle in (("N1", "North", "Issah Alhassan", "GT-4471-22"), ("W1", "West", "Issah Alhassan", "GR-1190-23")):
            routes[name] = await post(c, h, "/fmcg/routes", {"code": code, "name": name, "driver_name": driver, "vehicle": vehicle})

        outlets = {}
        for name, phone, address, limit, days, route in OUTLETS:
            row = await post(
                c, h, "/fmcg/outlets",
                {
                    "name": name, "phone": phone, "address": address, "credit_limit": limit,
                    "payment_terms_days": days, "route_id": routes[route]["id"], "salesperson_name": "Kofi Adu",
                },
            )
            outlets[name] = row["id"]
            await post(c, h, f"/fmcg/routes/{routes[route]['id']}/stops", {"customer_id": row["id"]})

        dispatch = await post(c, h, "/fmcg/dispatches", {"route_id": routes["North"]["id"]})

        async def order(outlet, lines, terms="credit"):
            return await post(
                c, h, "/fmcg/orders",
                {"customer_id": outlets[outlet], "terms": terms, "lines": [{"product_id": products[n], "quantity": q} for n, q in lines]},
            )

        first = await order("Mama Esi Provisions", [("Bar soap, carton of 48", 3), ("Cooking oil, 5 litre", 6)])
        second = await order("Blessed Mini Mart", [("Rice, 25 kg bag", 5), ("Bottled water, pack of 12", 20)])
        third = await order("Akwaaba Wholesale", [("Tomato paste, carton of 24", 10), ("Cooking oil, 5 litre", 12)])
        fourth = await order("Corner Kiosk", [("Bottled water, pack of 12", 6)], terms="cash")
        await order("Akwaaba Wholesale", [("Rice, 25 kg bag", 8)])

        for row in (first, second, fourth):
            await post(c, h, f"/fmcg/orders/{row['id']}/load", {"dispatch_id": dispatch["id"]})
        done = await post(c, h, f"/fmcg/orders/{first['id']}/deliver", {})
        await post(c, h, f"/fmcg/orders/{fourth['id']}/deliver", {"payment_method": "cash"})
        await post(c, h, f"/fmcg/orders/{third['id']}/deliver", {})
        await post(
            c, h, "/fmcg/collections",
            {"customer_id": outlets["Mama Esi Provisions"], "amount": 500, "method": "mobile_money", "dispatch_id": dispatch["id"]},
        )
        await post(
            c, h, f"/fmcg/orders/{first['id']}/returns",
            {"lines": [{"line_id": done["lines"][0]["id"], "quantity": 1}], "reason": "damaged", "resaleable": False},
        )
        print("seeded", SLUG)


async def main() -> None:
    if (settings.APP_ENV or "").strip().lower() == "production":
        sys.exit("Refusing to seed demo data in production.")
    await ensure_company()
    await seed()


if __name__ == "__main__":
    asyncio.run(main())
