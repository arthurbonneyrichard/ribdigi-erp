"""Hotel module R2 — folio, housekeeping, maintenance, stay ops, isolation."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4

import pyotp
import pytest

from app.packages import PACKAGEABLE_MODULES
from tests.conftest import auth_headers, set_tenant_industry

ROOT = Path(__file__).resolve().parents[2]


def test_hotel_module_registered():
    assert "hotel" in PACKAGEABLE_MODULES
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    nav = (ROOT / "frontend/lib/tenantNav.ts").read_text(encoding="utf-8")
    assert "HOTEL_NAV_ITEMS" in shell
    assert "['Hotel Dashboard', '/hotel', 'hotel']" in nav or '["Hotel Dashboard", "/hotel", "hotel"]' in nav
    page = (ROOT / "frontend/app/(dashboard)/hotel/page.tsx").read_text(encoding="utf-8")
    assert "/hotel/rooms" in page
    assert "/hotel/reservations" in page


@pytest.mark.asyncio
async def test_hotel_room_guest_reservation_lifecycle(client, seeded, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:6]

    room = await ac.post(
        "/api/v1/hotel/rooms",
        headers=admin,
        json={
            "code": f"R{suffix}",
            "name": f"Room {suffix}",
            "room_type": "deluxe",
            "rate_amount": 250,
            "max_occupancy": 2,
            "bed_type": "king",
        },
    )
    assert room.status_code == 200, room.text
    room_id = room.json()["data"]["id"]
    assert room.json()["data"]["code"] == f"R{suffix}".upper()

    guest = await ac.post(
        "/api/v1/hotel/guests",
        headers=admin,
        json={
            "full_name": f"Guest {suffix}",
            "email": f"guest-{suffix}@example.com",
            "nationality": "GH",
            "id_type": "passport",
        },
    )
    assert guest.status_code == 200, guest.text
    guest_id = guest.json()["data"]["id"]

    check_in = date.today() + timedelta(days=1)
    check_out = check_in + timedelta(days=2)
    booked = await ac.post(
        "/api/v1/hotel/reservations",
        headers=admin,
        json={
            "room_id": room_id,
            "guest_id": guest_id,
            "check_in_date": check_in.isoformat(),
            "check_out_date": check_out.isoformat(),
            "adults": 2,
            "deposit_amount": 100,
            "deposit_method": "cash",
        },
    )
    assert booked.status_code == 200, booked.text
    res_id = booked.json()["data"]["id"]
    assert booked.json()["data"]["status"] == "booked"
    assert booked.json()["data"]["nights"] == 2
    assert booked.json()["data"]["estimated_total"] == 500

    rooms = await ac.get("/api/v1/hotel/rooms", headers=admin)
    matched = next(r for r in rooms.json()["data"] if r["id"] == room_id)
    assert matched["status"] == "reserved"

    checked_in = await ac.post(
        f"/api/v1/hotel/reservations/{res_id}/check-in",
        headers=admin,
        json={},
    )
    assert checked_in.status_code == 200, checked_in.text
    assert checked_in.json()["data"]["status"] == "checked_in"
    folio_id = checked_in.json()["data"]["folio_id"]
    assert folio_id

    folio = await ac.get(f"/api/v1/hotel/folios/{folio_id}", headers=admin)
    assert folio.status_code == 200, folio.text
    assert folio.json()["data"]["charges_total"] == 500
    # deposit applied
    assert folio.json()["data"]["payments_total"] == 100
    assert folio.json()["data"]["balance"] == 400

    pay = await ac.post(
        f"/api/v1/hotel/folios/{folio_id}/payments",
        headers=admin,
        json={"method": "momo", "amount": 400, "reference": "MOMO-1"},
    )
    assert pay.status_code == 200, pay.text
    assert pay.json()["data"]["balance"] == 0

    checked_out = await ac.post(
        f"/api/v1/hotel/reservations/{res_id}/check-out",
        headers=admin,
        json={},
    )
    assert checked_out.status_code == 200, checked_out.text
    assert checked_out.json()["data"]["status"] == "checked_out"

    rooms = await ac.get("/api/v1/hotel/rooms", headers=admin)
    matched = next(r for r in rooms.json()["data"] if r["id"] == room_id)
    assert matched["status"] == "dirty"
    assert matched["housekeeping_status"] == "dirty"

    hk = await ac.get("/api/v1/hotel/housekeeping", headers=admin)
    assert hk.status_code == 200
    assert any(t["room_id"] == room_id and t["status"] == "pending" for t in hk.json()["data"])

    summary = await ac.get("/api/v1/hotel/summary", headers=admin)
    assert summary.status_code == 200, summary.text
    assert summary.json()["data"]["rooms_total"] >= 1
    assert "occupancy_rate" in summary.json()["data"]


@pytest.mark.asyncio
async def test_hotel_reservation_overlap_blocked(client, seeded, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:6]
    room = await ac.post(
        "/api/v1/hotel/rooms",
        headers=admin,
        json={"code": f"O{suffix}", "name": f"Overlap {suffix}", "rate_amount": 100},
    )
    assert room.status_code == 200, room.text
    guest = await ac.post(
        "/api/v1/hotel/guests",
        headers=admin,
        json={"full_name": f"Overlap Guest {suffix}"},
    )
    assert guest.status_code == 200, guest.text
    check_in = date.today() + timedelta(days=5)
    check_out = check_in + timedelta(days=3)
    first = await ac.post(
        "/api/v1/hotel/reservations",
        headers=admin,
        json={
            "room_id": room.json()["data"]["id"],
            "guest_id": guest.json()["data"]["id"],
            "check_in_date": check_in.isoformat(),
            "check_out_date": check_out.isoformat(),
        },
    )
    assert first.status_code == 200, first.text
    clash = await ac.post(
        "/api/v1/hotel/reservations",
        headers=admin,
        json={
            "room_id": room.json()["data"]["id"],
            "guest_id": guest.json()["data"]["id"],
            "check_in_date": (check_in + timedelta(days=1)).isoformat(),
            "check_out_date": (check_out + timedelta(days=1)).isoformat(),
        },
    )
    assert clash.status_code == 409, clash.text

    other_room = await ac.post(
        "/api/v1/hotel/rooms",
        headers=admin,
        json={"code": f"X{suffix}", "name": f"Other {suffix}", "rate_amount": 80, "room_type": "deluxe"},
    )
    assert other_room.status_code == 200, other_room.text
    avail = await ac.get(
        "/api/v1/hotel/availability",
        headers=admin,
        params={
            "check_in_date": check_in.isoformat(),
            "check_out_date": check_out.isoformat(),
            "room_type": "deluxe",
        },
    )
    assert avail.status_code == 200, avail.text
    ids = {r["id"] for r in avail.json()["data"]}
    assert other_room.json()["data"]["id"] in ids
    assert room.json()["data"]["id"] not in ids

    moved = await ac.patch(
        f"/api/v1/hotel/reservations/{first.json()['data']['id']}",
        headers=admin,
        json={"room_id": other_room.json()["data"]["id"]},
    )
    assert moved.status_code == 200, moved.text

    recrash = await ac.post(
        "/api/v1/hotel/reservations",
        headers=admin,
        json={
            "room_id": other_room.json()["data"]["id"],
            "guest_id": guest.json()["data"]["id"],
            "check_in_date": check_in.isoformat(),
            "check_out_date": check_out.isoformat(),
        },
    )
    assert recrash.status_code == 409, recrash.text


@pytest.mark.asyncio
async def test_hotel_extend_move_maintenance_housekeeping(client, seeded, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:6]
    r1 = await ac.post(
        "/api/v1/hotel/rooms",
        headers=admin,
        json={"code": f"A{suffix}", "name": f"A {suffix}", "rate_amount": 100},
    )
    r2 = await ac.post(
        "/api/v1/hotel/rooms",
        headers=admin,
        json={"code": f"B{suffix}", "name": f"B {suffix}", "rate_amount": 120},
    )
    guest = await ac.post(
        "/api/v1/hotel/guests",
        headers=admin,
        json={"full_name": f"Ops Guest {suffix}"},
    )
    assert r1.status_code == 200 and r2.status_code == 200 and guest.status_code == 200
    check_in = date.today()
    check_out = check_in + timedelta(days=1)
    booked = await ac.post(
        "/api/v1/hotel/reservations",
        headers=admin,
        json={
            "room_id": r1.json()["data"]["id"],
            "guest_id": guest.json()["data"]["id"],
            "check_in_date": check_in.isoformat(),
            "check_out_date": check_out.isoformat(),
            "booking_source": "walk_in",
            "walk_in": True,
        },
    )
    assert booked.status_code == 200, booked.text
    res_id = booked.json()["data"]["id"]
    cin = await ac.post(f"/api/v1/hotel/reservations/{res_id}/check-in", headers=admin, json={})
    assert cin.status_code == 200, cin.text

    ext = await ac.post(
        f"/api/v1/hotel/reservations/{res_id}/extend",
        headers=admin,
        json={"new_check_out_date": (check_out + timedelta(days=2)).isoformat()},
    )
    assert ext.status_code == 200, ext.text
    assert ext.json()["data"]["nights"] == 3

    moved = await ac.post(
        f"/api/v1/hotel/reservations/{res_id}/move",
        headers=admin,
        json={"new_room_id": r2.json()["data"]["id"]},
    )
    assert moved.status_code == 200, moved.text
    assert moved.json()["data"]["room_id"] == r2.json()["data"]["id"]

    # Settle folio and checkout
    folio_id = cin.json()["data"]["folio_id"]
    folio = await ac.get(f"/api/v1/hotel/folios/{folio_id}", headers=admin)
    bal = folio.json()["data"]["balance"]
    if bal > 0:
        await ac.post(
            f"/api/v1/hotel/folios/{folio_id}/payments",
            headers=admin,
            json={"method": "cash", "amount": bal},
        )
    cout = await ac.post(
        f"/api/v1/hotel/reservations/{res_id}/check-out", headers=admin, json={}
    )
    assert cout.status_code == 200, cout.text

    maint = await ac.post(
        "/api/v1/hotel/maintenance",
        headers=admin,
        json={
            "room_id": r1.json()["data"]["id"],
            "title": f"AC fix {suffix}",
            "priority": "high",
            "block_room": True,
        },
    )
    assert maint.status_code == 200, maint.text
    rooms = await ac.get("/api/v1/hotel/rooms", headers=admin)
    blocked = next(r for r in rooms.json()["data"] if r["id"] == r1.json()["data"]["id"])
    assert blocked["status"] in {"maintenance", "out_of_order"}

    done = await ac.post(
        f"/api/v1/hotel/maintenance/{maint.json()['data']['id']}/complete",
        headers=admin,
        json={},
    )
    assert done.status_code == 200, done.text

    hk_list = await ac.get("/api/v1/hotel/housekeeping?status=pending", headers=admin)
    assert hk_list.status_code == 200
    pending = [t for t in hk_list.json()["data"] if t["status"] == "pending"]
    if pending:
        complete = await ac.post(
            f"/api/v1/hotel/housekeeping/{pending[0]['id']}/complete",
            headers=admin,
            json={"mark_inspected": True},
        )
        assert complete.status_code == 200, complete.text


@pytest.mark.asyncio
async def test_hotel_tenant_isolation(client, seeded, db_session):
    """Cross-tenant room id must 404."""
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:6]
    room = await ac.post(
        "/api/v1/hotel/rooms",
        headers=admin,
        json={"code": f"T{suffix}", "name": f"Iso {suffix}", "rate_amount": 50},
    )
    assert room.status_code == 200
    fake = await ac.patch(
        f"/api/v1/hotel/rooms/{uuid4()}",
        headers=admin,
        json={"name": "Stolen"},
    )
    assert fake.status_code == 404


@pytest.mark.asyncio
async def test_hotel_services_folios_guest_history(client, seeded, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:6]
    svc = await ac.post(
        "/api/v1/hotel/services",
        headers=admin,
        json={
            "code": f"LND{suffix}",
            "name": "Laundry bag",
            "category": "laundry",
            "unit_amount": 25,
            "tax_percent": 0,
        },
    )
    assert svc.status_code == 200, svc.text
    room = await ac.post(
        "/api/v1/hotel/rooms",
        headers=admin,
        json={"code": f"S{suffix}", "name": f"Svc {suffix}", "rate_amount": 50},
    )
    guest = await ac.post(
        "/api/v1/hotel/guests",
        headers=admin,
        json={"full_name": f"Bill Guest {suffix}"},
    )
    assert room.status_code == 200 and guest.status_code == 200
    check_in = date.today()
    booked = await ac.post(
        "/api/v1/hotel/reservations",
        headers=admin,
        json={
            "room_id": room.json()["data"]["id"],
            "guest_id": guest.json()["data"]["id"],
            "check_in_date": check_in.isoformat(),
            "check_out_date": (check_in + timedelta(days=1)).isoformat(),
            "walk_in": True,
            "booking_source": "walk_in",
        },
    )
    assert booked.status_code == 200, booked.text
    cin = await ac.post(
        f"/api/v1/hotel/reservations/{booked.json()['data']['id']}/check-in",
        headers=admin,
        json={},
    )
    assert cin.status_code == 200, cin.text
    folio_id = cin.json()["data"]["folio_id"]
    posted = await ac.post(
        f"/api/v1/hotel/folios/{folio_id}/service-charges",
        headers=admin,
        json={"service_id": svc.json()["data"]["id"], "quantity": 2},
    )
    assert posted.status_code == 200, posted.text
    assert posted.json()["data"]["charges_total"] >= 50 + 50
    listed = await ac.get("/api/v1/hotel/folios", headers=admin)
    assert listed.status_code == 200, listed.text
    assert any(f["id"] == folio_id for f in listed.json()["data"])
    hist = await ac.get(
        f"/api/v1/hotel/guests/{guest.json()['data']['id']}/history", headers=admin
    )
    assert hist.status_code == 200, hist.text
    assert hist.json()["data"]["guest"]["id"] == guest.json()["data"]["id"]
    reports = await ac.get("/api/v1/hotel/reports", headers=admin)
    assert reports.status_code == 200, reports.text
    assert "payments_total" in reports.json()["data"]
    assert "inventory_usage" in reports.json()["data"]
    summary = await ac.get("/api/v1/hotel/summary", headers=admin)
    assert "revenue_today" in summary.json()["data"]
    assert "alerts" in summary.json()["data"]


@pytest.mark.asyncio
async def test_hotel_overlap_and_ooo_block(client, seeded, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:6]
    room = await ac.post(
        "/api/v1/hotel/rooms",
        headers=admin,
        json={"code": f"X{suffix}", "name": f"Overlap {suffix}", "rate_amount": 80},
    )
    assert room.status_code == 200, room.text
    guest = await ac.post(
        "/api/v1/hotel/guests",
        headers=admin,
        json={"full_name": f"Overlap Guest {suffix}"},
    )
    assert guest.status_code == 200, guest.text
    check_in = date.today() + timedelta(days=10)
    check_out = check_in + timedelta(days=2)
    first = await ac.post(
        "/api/v1/hotel/reservations",
        headers=admin,
        json={
            "room_id": room.json()["data"]["id"],
            "guest_id": guest.json()["data"]["id"],
            "check_in_date": check_in.isoformat(),
            "check_out_date": check_out.isoformat(),
            "status": "tentative",
        },
    )
    assert first.status_code == 200, first.text
    clash = await ac.post(
        "/api/v1/hotel/reservations",
        headers=admin,
        json={
            "room_id": room.json()["data"]["id"],
            "guest_id": guest.json()["data"]["id"],
            "check_in_date": (check_in + timedelta(days=1)).isoformat(),
            "check_out_date": (check_out + timedelta(days=1)).isoformat(),
        },
    )
    assert clash.status_code == 409, clash.text
    confirmed = await ac.post(
        f"/api/v1/hotel/reservations/{first.json()['data']['id']}/confirm",
        headers=admin,
        json={},
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["data"]["status"] == "booked"

    room2 = await ac.post(
        "/api/v1/hotel/rooms",
        headers=admin,
        json={"code": f"Y{suffix}", "name": f"OOO {suffix}", "rate_amount": 70},
    )
    assert room2.status_code == 200, room2.text
    ticket = await ac.post(
        "/api/v1/hotel/maintenance",
        headers=admin,
        json={
            "room_id": room2.json()["data"]["id"],
            "title": "Air conditioner repair",
            "priority": "urgent",
            "block_room": True,
        },
    )
    assert ticket.status_code == 200, ticket.text
    blocked = await ac.post(
        "/api/v1/hotel/reservations",
        headers=admin,
        json={
            "room_id": room2.json()["data"]["id"],
            "guest_id": guest.json()["data"]["id"],
            "check_in_date": (date.today() + timedelta(days=20)).isoformat(),
            "check_out_date": (date.today() + timedelta(days=22)).isoformat(),
        },
    )
    assert blocked.status_code == 409, blocked.text

    audit = await ac.post("/api/v1/hotel/night-audits", headers=admin, json={})
    assert audit.status_code == 200, audit.text
    again = await ac.post("/api/v1/hotel/night-audits", headers=admin, json={})
    assert again.status_code == 409, again.text


@pytest.mark.asyncio
async def test_hotel_occupancy_uses_sold_nights_for_selected_date(client, seeded, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:6]
    stay_night = date.today() + timedelta(days=5)
    room = await ac.post(
        "/api/v1/hotel/rooms",
        headers=admin,
        json={"code": f"O{suffix}", "name": f"Occ {suffix}", "rate_amount": 90},
    )
    assert room.status_code == 200, room.text
    guest = await ac.post(
        "/api/v1/hotel/guests",
        headers=admin,
        json={"full_name": f"Stay {suffix}"},
    )
    assert guest.status_code == 200, guest.text
    booked = await ac.post(
        "/api/v1/hotel/reservations",
        headers=admin,
        json={
            "room_id": room.json()["data"]["id"],
            "guest_id": guest.json()["data"]["id"],
            "check_in_date": stay_night.isoformat(),
            "check_out_date": (stay_night + timedelta(days=1)).isoformat(),
        },
    )
    assert booked.status_code == 200, booked.text
    assert booked.json()["data"]["status"] == "booked"
    summary = await ac.get(
        f"/api/v1/hotel/summary?on_date={stay_night.isoformat()}",
        headers=admin,
    )
    assert summary.status_code == 200, summary.text
    data = summary.json()["data"]
    assert data["as_of"] == stay_night.isoformat()
    assert data["rooms_sold_night"] >= 1
    assert data["occupancy_rate"] > 0
    assert data["physical_occupancy_rate"] == 0
    trend = data["occupancy_trend"]
    assert len(trend) == 14
    assert any(p["date"] == stay_night.isoformat() and p["sold"] >= 1 for p in trend)


@pytest.mark.asyncio
async def test_hotel_ooo_dates_block_only_overlapping_nights(client, seeded, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:6]
    ooo_start = date.today() + timedelta(days=10)
    ooo_end = date.today() + timedelta(days=12)
    room = await ac.post(
        "/api/v1/hotel/rooms",
        headers=admin,
        json={"code": f"M{suffix}", "name": f"Maint {suffix}", "rate_amount": 80},
    )
    assert room.status_code == 200, room.text
    room_id = room.json()["data"]["id"]
    guest = await ac.post(
        "/api/v1/hotel/guests",
        headers=admin,
        json={"full_name": f"OOO {suffix}"},
    )
    assert guest.status_code == 200, guest.text
    ticket = await ac.post(
        "/api/v1/hotel/maintenance",
        headers=admin,
        json={
            "room_id": room_id,
            "title": "Scheduled floor work",
            "priority": "normal",
            "block_room": True,
            "ooo_starts_on": ooo_start.isoformat(),
            "ooo_ends_on": ooo_end.isoformat(),
        },
    )
    assert ticket.status_code == 200, ticket.text
    assert ticket.json()["data"]["ooo_starts_on"] == ooo_start.isoformat()
    listing = await ac.get("/api/v1/hotel/rooms?is_active=true", headers=admin)
    row = next(r for r in listing.json()["data"] if r["id"] == room_id)
    assert row["status"] not in {"maintenance", "out_of_order", "blocked"}
    before = await ac.post(
        "/api/v1/hotel/reservations",
        headers=admin,
        json={
            "room_id": room_id,
            "guest_id": guest.json()["data"]["id"],
            "check_in_date": (date.today() + timedelta(days=2)).isoformat(),
            "check_out_date": (date.today() + timedelta(days=3)).isoformat(),
        },
    )
    assert before.status_code == 200, before.text
    overlap = await ac.post(
        "/api/v1/hotel/reservations",
        headers=admin,
        json={
            "room_id": room_id,
            "guest_id": guest.json()["data"]["id"],
            "check_in_date": ooo_start.isoformat(),
            "check_out_date": (ooo_end + timedelta(days=1)).isoformat(),
        },
    )
    assert overlap.status_code == 409, overlap.text


@pytest.mark.asyncio
async def test_hotel_event_holds_room_and_lists(client, seeded, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:6]
    start = date.today() + timedelta(days=8)
    end = start + timedelta(days=1)
    room = await ac.post(
        "/api/v1/hotel/rooms",
        headers=admin,
        json={"code": f"E{suffix}", "name": f"Event {suffix}", "rate_amount": 120},
    )
    assert room.status_code == 200, room.text
    guest = await ac.post(
        "/api/v1/hotel/guests",
        headers=admin,
        json={"full_name": f"Host {suffix}", "consent_marketing": True},
    )
    assert guest.status_code == 200, guest.text
    booked = await ac.post(
        "/api/v1/hotel/events",
        headers=admin,
        json={
            "title": f"Wedding {suffix}",
            "space_name": "Ballroom A",
            "starts_on": start.isoformat(),
            "ends_on": end.isoformat(),
            "expected_guests": 80,
            "room_id": room.json()["data"]["id"],
            "guest_id": guest.json()["data"]["id"],
            "status": "confirmed",
        },
    )
    assert booked.status_code == 200, booked.text
    assert booked.json()["data"]["status"] == "confirmed"
    clash = await ac.post(
        "/api/v1/hotel/reservations",
        headers=admin,
        json={
            "room_id": room.json()["data"]["id"],
            "guest_id": guest.json()["data"]["id"],
            "check_in_date": start.isoformat(),
            "check_out_date": end.isoformat(),
        },
    )
    assert clash.status_code == 409, clash.text
    listed = await ac.get("/api/v1/hotel/events", headers=admin)
    assert listed.status_code == 200, listed.text
    assert any(e["title"] == f"Wedding {suffix}" for e in listed.json()["data"])

