"""Seed a realistic local HR company for walking and recording the HRM desk.

Run inside the backend container (local Docker only):
    PYTHONPATH=. python scripts/seed_hrm_demo.py

Creates company `demo-hrm-rec` (Bright Path Services, owner@brightpath.example.com, plus an
HR officer and an employee login): staff, leave, attendance and a paid payroll. Everything
after the company itself goes through the API. Refuses to run in production.
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

SLUG = "demo-hrm-rec"
EMAIL = "owner@brightpath.example.com"
STAFF = [
    ("hr@brightpath.example.com", "Akosua Frimpong", "hrm_officer"),
    ("employee@brightpath.example.com", "Michael Tetteh", "hrm_employee"),
]
PASSWORD = os.environ.get("DEMO_PASSWORD", "BrightPath-Video-2026!")
API = os.environ.get("DEMO_API", "http://localhost:8000/api/v1")

PEOPLE = [
    ("Michael Tetteh", "employee@brightpath.example.com", "Accounts Officer", "Finance", 3200, 400),
    ("Grace Adjei", None, "Operations Lead", "Operations", 5200, 800),
    ("Daniel Asare", None, "Driver", "Operations", 1800, 200),
    ("Ama Serwaa", None, "Receptionist", "Admin", 1600, 150),
    ("Akosua Frimpong", "hr@brightpath.example.com", "HR Officer", "Admin", 3600, 400),
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
            slug=SLUG, company_name="Bright Path Services", industry="hrm", currency="GHS", status="trial",
            trial_ends_at=trial_end, trial_notices={}, package_code="trial", subscription_term_unit="months",
            subscription_term_value=1, subscription_ends_at=trial_end,
        )
        db.add(tenant)
        await db.flush()
        for email, name, role in [(EMAIL, "Sarah Boateng", "company_admin"), *STAFF]:
            db.add(
                m.User(
                    tenant_id=tenant.id, email=email, full_name=name, password_hash=hash_password(PASSWORD),
                    role=role, email_verified=True, permissions=permissions_for_role(role),
                    username=None if role == "company_admin" else f"{email.split('@')[0]}.bp",
                )
            )
        await db.flush()
        await seed_tenant_defaults(db, tenant.id)
        await db.commit()
        print("created company", SLUG)


async def post(client, h, path, body=None):
    r = await client.post(path, headers=h, json=body or {})
    if r.status_code >= 400:
        raise SystemExit(f"FAIL {path} {r.status_code} {r.text[:300]}")
    return r.json().get("data")


async def seed() -> None:
    today = date.today()
    async with httpx.AsyncClient(base_url=API, timeout=60) as c:
        r = await c.post("/auth/login", json={"tenant_id": SLUG, "email": EMAIL, "password": PASSWORD})
        r.raise_for_status()
        h = {"Authorization": f"Bearer {r.json()['data']['access_token']}"}
        if (await c.get("/hrm/employees", headers=h)).json().get("data"):
            print("already seeded")
            return
        people = []
        for name, email, title, department, basic, allowances in PEOPLE:
            people.append(
                await post(
                    c, h, "/hrm/employees",
                    {
                        "full_name": name, "email": email, "job_title": title, "department": department,
                        "hired_on": "2024-02-01", "basic_salary": basic, "allowances": allowances,
                    },
                )
            )
        monday = today + timedelta(days=7 - today.weekday())
        first = await post(
            c, h, "/hrm/leave",
            {"employee_id": people[1]["id"], "leave_type": "annual", "starts_on": monday.isoformat(), "ends_on": (monday + timedelta(days=4)).isoformat(), "reason": "Family visit"},
        )
        await post(c, h, f"/hrm/leave/{first['id']}/decide", {"approve": True})
        await post(
            c, h, "/hrm/leave",
            {"employee_id": people[2]["id"], "leave_type": "sick", "starts_on": monday.isoformat(), "ends_on": monday.isoformat()},
        )
        await post(
            c, h, "/hrm/attendance",
            {
                "day": today.isoformat(),
                "marks": [{"employee_id": p["id"], "status": "late" if i == 3 else "present"} for i, p in enumerate(people)],
            },
        )
        last_month = (today.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
        run = await post(c, h, "/hrm/payroll", {"period": last_month})
        await post(c, h, f"/hrm/payroll/{run['id']}/approve")
        for what in ("staff", "paye", "ssnit"):
            await post(c, h, f"/hrm/payroll/{run['id']}/pay", {"what": what, "method": "bank_transfer"})
        await post(c, h, "/hrm/payroll", {"period": today.strftime("%Y-%m")})
        print("seeded", SLUG)


async def main() -> None:
    if (settings.APP_ENV or "").strip().lower() == "production":
        sys.exit("Refusing to seed demo data in production.")
    await ensure_company()
    await seed()


if __name__ == "__main__":
    asyncio.run(main())
