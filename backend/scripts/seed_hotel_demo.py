"""Seed a realistic local hotel company for walking and recording the hotel desk.

Run inside the backend container (local Docker only):
    PYTHONPATH=. python scripts/seed_hotel_demo.py

Creates company `demo-hotel-rec` (Palm Court Hotel, admin owner@palmcourt.example.com):
24 rooms on three floors, rate plans, services, guests, and stays spread over
in-house, arriving and future dates. Everything goes through the API, so the demo
obeys the same rules a customer does. Refuses to run in production. Re-running
reuses the company and skips the stays.
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

SLUG = "demo-hotel-rec"
EMAIL = "owner@palmcourt.example.com"
PASSWORD = os.environ.get("DEMO_PASSWORD", "PalmCourt-Video-2026!")
API = os.environ.get("DEMO_API", "http://localhost:8000/api/v1")

ROOM_TYPES = [
    ("1", "standard", "Garden standard", "Queen", 2, 420),
    ("2", "deluxe", "Deluxe balcony", "King", 2, 620),
    ("3", "suite", "Palm suite", "King", 3, 1150),
]
GUESTS = [
    ("Abena Owusu", "+233244123456", "Ghanaian", "Ghana Card", "GHA-712345678-1"),
    ("Kwame Mensah", "+233201112233", "Ghanaian", "Ghana Card", "GHA-700112233-4"),
    ("Chidi Okafor", "+2348031234567", "Nigerian", "Passport", "A09876543"),
    ("Sarah Boateng", "+233277654321", "Ghanaian", "Ghana Card", "GHA-705554443-2"),
    ("Daniel Asare", "+233246778899", "Ghanaian", "Ghana Card", "GHA-701239876-5"),
    ("Fatima Diallo", "+221771234567", "Senegalese", "Passport", "SN1234567"),
    ("James Whitfield", "+447700900123", "British", "Passport", "533112288"),
    ("Akosua Frimpong", "+233208889900", "Ghanaian", "Ghana Card", "GHA-709988776-3"),
    ("Yaw Darko", "+233557001122", "Ghanaian", "Ghana Card", "GHA-703322110-7"),
    ("Ama Serwaa", "+233244556677", "Ghanaian", "Ghana Card", "GHA-706677889-9"),
    ("Michael Tetteh", "+233265443322", "Ghanaian", "Ghana Card", "GHA-702233445-6"),
    ("Grace Adjei", "+233501234987", "Ghanaian", "Ghana Card", "GHA-708765432-1"),
]
SERVICES = [
    ("BRK", "Breakfast buffet", "restaurant", 85),
    ("JOL", "Jollof with chicken", "restaurant", 95),
    ("BEER", "Club beer", "bar", 25),
    ("COCK", "House cocktail", "bar", 55),
    ("LAUN", "Laundry per bag", "laundry", 60),
    ("AIRP", "Airport pick-up", "transport", 180),
    ("SPA", "Massage, 60 minutes", "spa", 250),
]
PLANS = [
    ("RACK", "Rack rate", 420, "standard", 1),
    ("WEEK", "Stay 3 nights or more", 380, "standard", 3),
    ("CORP", "Corporate deluxe", 550, "deluxe", 1),
]


async def ensure_company() -> None:
    from app.api import seed_tenant_defaults
    from app import tenants as tenants_svc

    async with SessionLocal() as db:
        tenant = (await db.execute(select(m.Tenant).where(m.Tenant.slug == SLUG))).scalar_one_or_none()
        if tenant is not None:
            print("company exists", SLUG)
            return
        trial_end = tenants_svc.default_trial_ends_at()
        tenant = m.Tenant(
            slug=SLUG,
            company_name="Palm Court Hotel",
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
        db.add(tenant)
        await db.flush()
        db.add(
            m.User(
                tenant_id=tenant.id,
                email=EMAIL,
                full_name="Efua Ansah",
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


async def post(client, h, path, body, label=""):
    r = await client.post(path, headers=h, json=body)
    if r.status_code >= 400:
        print("FAIL", path, label, r.status_code, r.text[:300])
        return None
    return r.json().get("data")


async def seed() -> None:
    today = date.today()
    async with httpx.AsyncClient(base_url=API, timeout=60) as c:
        r = await c.post("/auth/login", json={"tenant_id": SLUG, "email": EMAIL, "password": PASSWORD})
        r.raise_for_status()
        h = {"Authorization": f"Bearer {r.json()['data']['access_token']}"}
        if (await c.get("/hotel/rooms", headers=h)).json().get("data"):
            print("rooms exist, nothing to do")
            return
        rooms = []
        for floor, rtype, label, bed, occ, rate in ROOM_TYPES:
            for n in range(1, 9):
                rooms.append(await post(c, h, "/hotel/rooms", {
                    "code": f"{floor}0{n}", "name": f"{label} {floor}0{n}", "room_type": rtype,
                    "floor": f"Floor {floor}", "bed_type": bed, "max_occupancy": occ, "rate_amount": rate,
                    "weekend_rate": round(rate * 1.15), "extra_person_charge": 60,
                }))
        guests = []
        for name, phone, nat, idt, idn in GUESTS:
            email = name.lower().replace(" ", ".") + "@example.com"
            guests.append(await post(c, h, "/hotel/guests", {
                "full_name": name, "phone": phone, "email": email, "nationality": nat,
                "id_type": idt, "id_document": idn,
            }))
        for code, name, cat, amount in SERVICES:
            await post(c, h, "/hotel/services", {"code": code, "name": name, "category": cat, "unit_amount": amount})
        for code, name, amount, rtype, nights in PLANS:
            await post(c, h, "/hotel/rate-plans", {
                "code": code, "name": name, "amount": amount, "room_type": rtype, "min_nights": nights,
            })

        async def stay(room, guest, start, nights, check_in=False, **extra):
            res = await post(c, h, "/hotel/reservations", {
                "room_id": rooms[room]["id"], "guest_id": guests[guest]["id"],
                "check_in_date": (today + timedelta(days=start)).isoformat(),
                "check_out_date": (today + timedelta(days=start + nights)).isoformat(),
                "adults": 1, **extra,
            }, f"room {room}")
            if res and check_in:
                await post(c, h, f"/hotel/reservations/{res['id']}/check-in", {}, f"room {room}")
            return res

        in_house = [
            await stay(room, guest, 0, nights, check_in=True)
            for guest, (room, nights) in enumerate([(0, 2), (1, 3), (8, 2), (9, 1), (16, 4), (17, 2)])
        ]
        await stay(2, 6, 0, 2, booking_source="phone")
        await stay(10, 7, 0, 3, booking_source="online", deposit_amount=300, deposit_method="momo")
        await stay(18, 8, 0, 1)
        await stay(3, 9, 1, 2, booking_source="ota")
        await stay(11, 10, 2, 3, booking_source="phone")
        await stay(19, 11, 3, 2, status="tentative")
        await stay(4, 6, 5, 4)
        await stay(12, 7, 7, 2)
        for res, amount in zip(in_house[:3], (200, 620, 150)):
            if not res:
                continue
            full = (await c.get(f"/hotel/reservations/{res['id']}/folio", headers=h)).json().get("data") or {}
            folio = full.get("id") or (full.get("folio") or {}).get("id")
            if folio:
                await post(c, h, f"/hotel/folios/{folio}/payments", {
                    "method": "momo", "amount": amount, "reference": "MOMO-DEMO",
                })
        await post(c, h, "/hotel/housekeeping", {"room_id": rooms[5]["id"], "task_type": "cleaning", "priority": "high", "assigned_to": "Esi"})
        await post(c, h, "/hotel/housekeeping", {"room_id": rooms[13]["id"], "task_type": "inspection", "assigned_to": "Adwoa"})
        await post(c, h, "/hotel/maintenance", {
            "room_id": rooms[7]["id"], "title": "Air conditioner not cooling", "priority": "high", "block_room": True,
            "ooo_starts_on": today.isoformat(), "ooo_ends_on": (today + timedelta(days=2)).isoformat(), "assigned_to": "Kofi",
        })
        if in_house[0]:
            await post(c, h, "/hotel/guest-requests", {"title": "Extra towels", "kind": "service", "reservation_id": in_house[0]["id"]})
        if in_house[2]:
            await post(c, h, "/hotel/guest-requests", {"title": "Wake-up call at 6:00", "kind": "wake_up", "reservation_id": in_house[2]["id"]})
        await post(c, h, "/hotel/lost-found", {"description": "Black phone charger", "kind": "found", "room_id": rooms[6]["id"]})
        await post(c, h, "/hotel/events", {
            "title": "Boateng wedding reception", "space_name": "Palm Hall", "expected_guests": 120,
            "starts_on": (today + timedelta(days=9)).isoformat(), "ends_on": (today + timedelta(days=10)).isoformat(),
            "deposit_amount": 2000, "status": "confirmed",
        })
        print("ready: sign in at /login with company", SLUG, "and", EMAIL)


async def main() -> None:
    if (settings.APP_ENV or "").strip().lower() == "production":
        sys.exit("refusing to seed a demo company in production")
    await ensure_company()
    await seed()


if __name__ == "__main__":
    asyncio.run(main())
