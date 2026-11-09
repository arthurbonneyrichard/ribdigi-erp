"""Seed a realistic local bakery for walking and recording the bakery desk.

Run inside the backend container (local Docker only):
    PYTHONPATH=. python scripts/seed_bakery_demo.py

Creates company `demo-bakery-rec` (Golden Crust Bakery, owner@goldencrust.example.com,
plus a cashier, a baker and a driver): ingredients, items for sale, recipes, a morning's baking,
counter sales, pre-orders with deposits and some waste. Everything after the company
itself goes through the API, so the demo obeys the same rules a customer does.
Refuses to run in production. Re-running reuses the company and skips the rest.
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import date, timedelta

import httpx
from sqlalchemy import select

from app import models as m
from app.config import settings
from app.db import SessionLocal
from app.rbac import permissions_for_role
from app.security import hash_password

SLUG = "demo-bakery-rec"
EMAIL = "owner@goldencrust.example.com"
STAFF = [
    ("cashier@goldencrust.example.com", "Esi Boateng", "bakery_cashier"),
    ("baker@goldencrust.example.com", "Kojo Asante", "bakery_baker"),
    ("driver@goldencrust.example.com", "Yaw Boateng", "bakery_driver"),
]
PASSWORD = os.environ.get("DEMO_PASSWORD", "GoldenCrust-Video-2026!")
API = os.environ.get("DEMO_API", "http://localhost:8000/api/v1")

# name, cost per unit, opening stock
INGREDIENTS = [
    ("Flour (kg)", 9.5, 200),
    ("Sugar (kg)", 12, 80),
    ("Butter (kg)", 48, 40),
    ("Eggs (each)", 2, 300),
    ("Yeast (kg)", 60, 10),
    ("Milk (litre)", 14, 50),
]
# name, price, recipe name, yield, [(ingredient, quantity)]
ITEMS = [
    ("Sugar bread", 12, "Sugar bread", 20, [("Flour (kg)", 5), ("Sugar (kg)", 1), ("Yeast (kg)", 0.1), ("Butter (kg)", 0.4)]),
    ("Meat pie", 15, "Meat pie", 24, [("Flour (kg)", 3), ("Butter (kg)", 1.2), ("Eggs (each)", 6)]),
    ("Chocolate cake", 180, "Chocolate cake", 2, [("Flour (kg)", 1), ("Sugar (kg)", 1), ("Butter (kg)", 0.5), ("Eggs (each)", 8), ("Milk (litre)", 0.5)]),
    ("Doughnut", 6, "Doughnut", 30, [("Flour (kg)", 3), ("Sugar (kg)", 0.5), ("Yeast (kg)", 0.08), ("Milk (litre)", 1)]),
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
            company_name="Golden Crust Bakery",
            industry="bakery",
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
        for email, name, role in [(EMAIL, "Adwoa Mensah", "company_admin"), *STAFF]:
            db.add(
                m.User(
                    tenant_id=tenant.id,
                    email=email,
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
    today = date.today()
    async with httpx.AsyncClient(base_url=API, timeout=60) as c:
        r = await c.post("/auth/login", json={"tenant_id": SLUG, "email": EMAIL, "password": PASSWORD})
        r.raise_for_status()
        h = {"Authorization": f"Bearer {r.json()['data']['access_token']}"}
        if (await c.get("/bakery/recipes", headers=h)).json().get("data"):
            print("already seeded")
            return

        ingredient = {}
        for name, cost, stock in INGREDIENTS:
            row = await post(c, h, "/products", {"name": name, "cost_price": cost, "selling_price": 0, "stock_qty": stock, "category": "Ingredients"})
            ingredient[name] = row["id"]

        recipes = {}
        for name, price, recipe, makes, lines in ITEMS:
            item = await post(c, h, "/products", {"name": name, "cost_price": 0, "selling_price": price, "stock_qty": 0, "category": "Baked goods"})
            row = await post(
                c, h, "/bakery/recipes",
                {
                    "product_id": item["id"],
                    "name": recipe,
                    "yield_qty": makes,
                    "lines": [{"ingredient_id": ingredient[i], "quantity": q} for i, q in lines],
                },
            )
            recipes[name] = (row["id"], item["id"])

        for name, batches in (("Sugar bread", 2), ("Meat pie", 2), ("Doughnut", 2), ("Chocolate cake", 2)):
            await post(c, h, "/bakery/batches", {"recipe_id": recipes[name][0], "batches": batches})

        await post(c, h, "/bakery/till/shift/open", {"opening_cash": 200})
        for method, lines in (
            ("cash", [("Sugar bread", 3), ("Doughnut", 4)]),
            ("mobile_money", [("Meat pie", 6)]),
            ("card", [("Chocolate cake", 1)]),
            ("cash", [("Doughnut", 10), ("Meat pie", 2)]),
        ):
            await post(
                c, h, "/bakery/sales",
                {"payment_method": method, "lines": [{"product_id": recipes[n][1], "quantity": q} for n, q in lines]},
            )

        for customer, phone, days, item, qty, note, deposit in (
            ("Abena Owusu", "+233244123456", 2, "Chocolate cake", 1, "Happy birthday Ama", 90),
            ("Grace Adjei", "+233501234987", 1, "Meat pie", 40, "Office meeting", 200),
            ("Yaw Darko", "+233557001122", 0, "Sugar bread", 10, None, 0),
        ):
            await post(
                c, h, "/bakery/orders",
                {
                    "customer_name": customer,
                    "phone": phone,
                    "due_date": (today + timedelta(days=days)).isoformat(),
                    "lines": [{"product_id": recipes[item][1], "quantity": qty, "note": note}],
                    "deposit": deposit,
                    "deposit_method": "mobile_money" if deposit else None,
                },
            )

        await post(c, h, "/bakery/waste", {"product_id": recipes["Doughnut"][1], "quantity": 3, "reason": "burnt"})
        drivers = (await c.get("/bakery/drivers", headers=h)).json()["data"]
        for customer, phone, address, item, qty in (
            ("Hope Academy canteen", "+233244998877", "Hope Academy, East Legon", "Meat pie", 30),
            ("Mrs Adjoa Quaye", "+233208765432", "14 Palm Street, Dzorwulu", "Chocolate cake", 1),
        ):
            await post(
                c, h, "/bakery/orders",
                {
                    "customer_name": customer, "phone": phone, "due_date": today.isoformat(),
                    "lines": [{"product_id": recipes[item][1], "quantity": qty}],
                    "delivery": True, "address": address, "driver_id": next((d["id"] for d in drivers if d.get("is_driver")), None),
                },
            )
        await post(
            c, h, "/bakery/expenses",
            {"category": "gas", "description": "Oven gas refill", "amount": 120, "paid_with": "cash", "spent_on": today.isoformat(), "from_till": True},
        )
        await post(
            c, h, "/bakery/stock/receive",
            {"product_id": ingredient["Flour (kg)"], "quantity": 50, "unit_cost": 9.5, "paid_with": "credit", "supplier": "Golden Mills"},
        )
        print("seeded", SLUG)


async def main() -> None:
    if (settings.APP_ENV or "").strip().lower() == "production":
        sys.exit("Refusing to seed demo data in production.")
    await ensure_company()
    await seed()


if __name__ == "__main__":
    asyncio.run(main())
