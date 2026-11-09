"""Seed a realistic local gym for walking and recording the gym desk.

Run inside the backend container (local Docker only):
    PYTHONPATH=. python scripts/seed_gym_demo.py

Creates company `demo-gym-rec` (Iron Peak Fitness, owner@ironpeak.example.com, plus a front
desk login and a trainer): plans, members, sales, visits and classes. Everything after the
company itself goes through the API. Refuses to run in production.
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timedelta

import httpx
from sqlalchemy import select

from app import models as m
from app.config import settings
from app.db import SessionLocal
from app.rbac import permissions_for_role
from app.security import hash_password

SLUG = "demo-gym-rec"
EMAIL = "owner@ironpeak.example.com"
STAFF = [
    ("desk@ironpeak.example.com", "Nana Ama", "gym_frontdesk"),
    ("trainer@ironpeak.example.com", "Kwesi Boakye", "gym_trainer"),
]
PASSWORD = os.environ.get("DEMO_PASSWORD", "IronPeak-Video-2026!")
API = os.environ.get("DEMO_API", "http://localhost:8000/api/v1")

PLANS = [("Day pass", 40, 1, None), ("Ten visits", 300, 90, 10), ("Monthly", 350, 30, None), ("Yearly", 3500, 365, None)]
MEMBERS = [
    ("Abena Owusu", "+233244200301"),
    ("Kwame Mensah", "+233244200302"),
    ("Chidi Okafor", "+233244200303"),
    ("Sarah Boateng", "+233244200304"),
    ("Daniel Asare", "+233244200305"),
    ("Fatima Diallo", "+233244200306"),
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
            slug=SLUG, company_name="Iron Peak Fitness", industry="gym", currency="GHS", status="trial",
            trial_ends_at=trial_end, trial_notices={}, package_code="trial", subscription_term_unit="months",
            subscription_term_value=1, subscription_ends_at=trial_end,
        )
        db.add(tenant)
        await db.flush()
        for email, name, role in [(EMAIL, "Yaw Darko", "company_admin"), *STAFF]:
            db.add(
                m.User(
                    tenant_id=tenant.id, email=email, full_name=name, password_hash=hash_password(PASSWORD),
                    role=role, email_verified=True, permissions=permissions_for_role(role),
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
        if (await c.get("/gym/plans", headers=h)).json().get("data"):
            print("already seeded")
            return
        plans = {}
        for name, price, days, visits in PLANS:
            plans[name] = await post(c, h, "/gym/plans", {"name": name, "price": price, "duration_days": days, "visit_limit": visits})
        await post(c, h, "/gym/till/shift/open", {"opening_cash": 150})
        members = [await post(c, h, "/gym/members", {"full_name": n, "phone": p}) for n, p in MEMBERS]
        sold = ["Monthly", "Monthly", "Yearly", "Ten visits", "Day pass"]
        methods = ["cash", "mobile_money", "card", "cash", "cash"]
        for member, plan, method in zip(members, sold, methods):
            await post(c, h, "/gym/memberships", {"member_id": member["id"], "plan_id": plans[plan]["id"], "method": method})
        for member in members[:3]:
            await post(c, h, "/gym/check-ins", {"member_id": member["id"]})
        await post(c, h, "/gym/check-ins", {"member_id": members[5]["id"]})
        now = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
        for name, hours, trainer in (("Morning spin", 20, "Kwesi Boakye"), ("Boxing basics", 26, "Kwesi Boakye")):
            row = await post(
                c, h, "/gym/classes",
                {"name": name, "trainer_name": trainer, "starts_at": (now + timedelta(hours=hours)).isoformat(), "capacity": 12},
            )
            await post(c, h, f"/gym/classes/{row['id']}/book", {"member_id": members[0]["id"]})
        print("seeded", SLUG)


async def main() -> None:
    if (settings.APP_ENV or "").strip().lower() == "production":
        sys.exit("Refusing to seed demo data in production.")
    await ensure_company()
    await seed()


if __name__ == "__main__":
    asyncio.run(main())
