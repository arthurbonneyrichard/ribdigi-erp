"""Hotel module R2 — folio, housekeeping, maintenance, stay ops, isolation."""

from __future__ import annotations

from datetime import date, datetime, timedelta
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
    assert "['Company profile', '/company', 'company']" in nav or '["Company profile", "/company", "company"]' in nav
    assert "HOTEL_INVENTORY_PROCUREMENT_CHILDREN" in nav
    assert "Supplies" in nav
    assert "Low supplies" in nav
    assert "Purchase orders" in nav
    assert "Receive supplies" in nav
    page = (ROOT / "frontend/app/(dashboard)/hotel/page.tsx").read_text(encoding="utf-8")
    grid = (ROOT / "frontend/components/HotelRoomNightGrid.tsx").read_text(encoding="utf-8")
    assert "/hotel/rooms" in page
    assert "/hotel/reservations" in page
    assert 'href="/company"' in page
    assert "Company profile" in page
    assert "printDocumentHtml" in page
    assert "formatMoney" in page
    assert "allow_balance" in page
    assert "window.alert" not in page
    assert "Print slip" in page
    assert 'value="tentative"' in page
    assert "due_at" in page
    assert "Duplicate" in page
    assert "room.status === 'dirty' && day === localIso()" in grid
    assert "Next stay" in grid
    assert "nights × nightly rate" in page
    assert "Save hotel booking link" in page
    assert 'id="online-booking"' in page
    assert "stay requests are waiting." in page
    assert "mix.reserved ?? summary.rooms_reserved" in page
    assert "Rooms sold tonight are listed first." in page
    assert "r.can_no_show &&" in page
    assert "r.guest_phone" in page
    assert "Next stay" in page
    assert "nextStayAfter" in page
    assert "nextStayAfter(reservations, r.id, shiftIso(availForm.check_out_date, -1))" in page
    assert "function heldStay" in page
    assert "!resForm.waitlist && Boolean(heldStay(" in page
    assert page.count("leftEarlyWhen(r)") >= 5
    assert "folio.reservation_status" in page
    assert "Left: ${left}" in page
    assert "open_folio_count" in page
    hotel_src = (ROOT / "backend/app/hotel.py").read_text(encoding="utf-8")
    assert 'f"Left: {left.isoformat()}"' in hotel_src
    assert "def present_folio" in hotel_src
    stay_page = (ROOT / "frontend/app/stay/[slug]/page.tsx").read_text(encoding="utf-8")
    assert "setRooms((current) => current.filter((room) => room.id !== heldId))" in stay_page
    assert "setPhone('')" in stay_page
    assert "An early leave still counts" in page
    assert "ribdigi-onboarding-refresh" in page
    checklist = (ROOT / "frontend/components/OnboardingChecklist.tsx").read_text(encoding="utf-8")
    assert "ribdigi-onboarding-refresh" in checklist


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
    listed = await ac.get("/api/v1/hotel/folios", headers=admin)
    assert listed.status_code == 200, listed.text
    listed_row = next(f for f in listed.json()["data"] if f["id"] == folio_id)
    assert listed_row["charges_total"] == 500
    assert listed_row["payments_total"] == 100
    assert listed_row["balance"] == 400
    stays = await ac.get("/api/v1/hotel/reservations", headers=admin)
    assert stays.status_code == 200, stays.text
    stay_row = next(s for s in stays.json()["data"] if s["id"] == res_id)
    assert stay_row["folio_id"] == folio_id
    assert stay_row["folio_balance"] == 400
    assert stay_row["can_duplicate"] is True

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
    snap = audit.json()["data"]["snapshot"]
    assert snap["day_closed"] is True
    assert snap["room_charges_reposted"] is False
    assert "note" not in snap
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
    today = date.today()
    today_summary = await ac.get(
        f"/api/v1/hotel/summary?on_date={today.isoformat()}",
        headers=admin,
    )
    assert today_summary.status_code == 200, today_summary.text
    today_data = today_summary.json()["data"]
    assert today_data["rooms_sold_night"] == data["rooms_sold_night"] - 1
    assert today_data["rooms_available"] == data["rooms_available"] + 1
    assert data["room_status_mix"]["reserved"] == today_data["room_status_mix"]["reserved"] + 1
    assert today_data["room_status_mix"]["reserved"] == today_data["rooms_reserved"]
    listed = await ac.get("/api/v1/hotel/rooms", headers=admin)
    assert listed.status_code == 200, listed.text
    room_id = room.json()["data"]["id"]
    assert next(row for row in listed.json()["data"] if row["id"] == room_id)["status"] == "reserved"
    free_tonight = await ac.get(
        f"/api/v1/hotel/availability?check_in_date={today.isoformat()}&check_out_date={(today + timedelta(days=1)).isoformat()}",
        headers=admin,
    )
    assert free_tonight.status_code == 200, free_tonight.text
    assert any(row["id"] == room_id for row in free_tonight.json()["data"])
    held_night = await ac.get(
        f"/api/v1/hotel/availability?check_in_date={stay_night.isoformat()}&check_out_date={(stay_night + timedelta(days=1)).isoformat()}",
        headers=admin,
    )
    assert held_night.status_code == 200, held_night.text
    assert all(row["id"] != room_id for row in held_night.json()["data"])
    trend = data["occupancy_trend"]
    assert len(trend) == 14
    assert any(p["date"] == stay_night.isoformat() and p["sold"] >= 1 for p in trend)


@pytest.mark.asyncio
async def test_hotel_checkout_releases_remaining_nights(client, seeded, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:6]
    stay_in = date.today()
    room = await ac.post(
        "/api/v1/hotel/rooms",
        headers=admin,
        json={"code": f"L{suffix}", "name": f"Left {suffix}", "rate_amount": 80},
    )
    assert room.status_code == 200, room.text
    room_id = room.json()["data"]["id"]
    guest = await ac.post(
        "/api/v1/hotel/guests",
        headers=admin,
        json={"full_name": f"Left {suffix}"},
    )
    assert guest.status_code == 200, guest.text
    booked = await ac.post(
        "/api/v1/hotel/reservations",
        headers=admin,
        json={
            "room_id": room_id,
            "guest_id": guest.json()["data"]["id"],
            "check_in_date": stay_in.isoformat(),
            "check_out_date": (stay_in + timedelta(days=2)).isoformat(),
        },
    )
    assert booked.status_code == 200, booked.text
    res_id = booked.json()["data"]["id"]
    held = await ac.get(f"/api/v1/hotel/summary?on_date={stay_in.isoformat()}", headers=admin)
    assert held.json()["data"]["rooms_sold_night"] >= 1
    checked_in = await ac.post(f"/api/v1/hotel/reservations/{res_id}/check-in", headers=admin, json={})
    assert checked_in.status_code == 200, checked_in.text
    opened = await ac.get(f"/api/v1/hotel/summary?on_date={stay_in.isoformat()}", headers=admin)
    assert opened.status_code == 200, opened.text
    assert opened.json()["data"]["open_folio_count"] >= 1
    folio_id = checked_in.json()["data"]["folio_id"]
    paid = await ac.post(
        f"/api/v1/hotel/folios/{folio_id}/payments",
        headers=admin,
        json={"method": "cash", "amount": 160},
    )
    assert paid.status_code == 200, paid.text
    assert paid.json()["data"]["reservation_status"] == "checked_in"
    assert paid.json()["data"]["checked_out_at"] is None
    checked_out = await ac.post(
        f"/api/v1/hotel/reservations/{res_id}/check-out", headers=admin, json={}
    )
    assert checked_out.status_code == 200, checked_out.text
    free = await ac.get(f"/api/v1/hotel/summary?on_date={stay_in.isoformat()}", headers=admin)
    assert free.status_code == 200, free.text
    assert free.json()["data"]["rooms_sold_night"] == 0
    tomorrow = stay_in + timedelta(days=1)
    later = await ac.get(f"/api/v1/hotel/summary?on_date={tomorrow.isoformat()}", headers=admin)
    assert later.json()["data"]["rooms_sold_night"] == 0
    cal = await ac.get(
        f"/api/v1/hotel/calendar?start_date={stay_in.isoformat()}&end_date={tomorrow.isoformat()}",
        headers=admin,
    )
    assert cal.status_code == 200, cal.text
    row = next(item for item in cal.json()["data"]["rooms"] if item["room"]["id"] == room_id)
    assert row["days"] == {}
    assert free.json()["data"]["departures_today"] == 1
    assert free.json()["data"]["open_folio_count"] == 0
    planned_day = stay_in + timedelta(days=2)
    planned = await ac.get(
        f"/api/v1/hotel/summary?on_date={planned_day.isoformat()}",
        headers=admin,
    )
    assert planned.status_code == 200, planned.text
    assert planned.json()["data"]["departures_today"] == 0
    today_list = await ac.get(
        f"/api/v1/hotel/reservations?list_kind=departures&on_date={stay_in.isoformat()}",
        headers=admin,
    )
    assert today_list.status_code == 200, today_list.text
    assert any(item["id"] == res_id for item in today_list.json()["data"])
    planned_list = await ac.get(
        f"/api/v1/hotel/reservations?list_kind=departures&on_date={planned_day.isoformat()}",
        headers=admin,
    )
    assert planned_list.status_code == 200, planned_list.text
    assert all(item["id"] != res_id for item in planned_list.json()["data"])
    slip = await ac.get(f"/api/v1/hotel/reservations/{res_id}/confirmation", headers=admin)
    assert slip.status_code == 200, slip.text
    slip_text = slip.json()["data"]["text"]
    assert f"Check-out: {planned_day.isoformat()}" in slip_text
    assert f"Left: {stay_in.isoformat()}" in slip_text
    bill = await ac.get(f"/api/v1/hotel/folios/{folio_id}", headers=admin)
    assert bill.status_code == 200, bill.text
    bill_row = bill.json()["data"]
    assert bill_row["check_in_date"] == stay_in.isoformat()
    assert bill_row["check_out_date"] == planned_day.isoformat()
    assert str(bill_row["checked_out_at"]).startswith(stay_in.isoformat())
    assert bill_row["reservation_status"] == "checked_out"
    assert bill_row["guest_name"]
    assert bill_row["room_code"]
    listed_bills = await ac.get("/api/v1/hotel/folios", headers=admin)
    assert listed_bills.status_code == 200, listed_bills.text
    listed_bill = next(item for item in listed_bills.json()["data"] if item["id"] == folio_id)
    assert listed_bill["check_out_date"] == planned_day.isoformat()
    assert str(listed_bill["checked_out_at"]).startswith(stay_in.isoformat())
    report = await ac.get(
        f"/api/v1/hotel/reports?start_date={stay_in.isoformat()}&end_date={(stay_in + timedelta(days=1)).isoformat()}",
        headers=admin,
    )
    assert report.status_code == 200, report.text
    assert report.json()["data"]["occupied_nights"] == 2
    assert report.json()["data"]["room_revenue"] == 160


@pytest.mark.asyncio
async def test_hotel_empty_supply_is_not_called_low(client, seeded, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:6]
    empty = await ac.post(
        "/api/v1/products",
        headers=admin,
        json={"name": f"Towel {suffix}", "selling_price": 12},
    )
    assert empty.status_code == 200, empty.text
    summary = await ac.get("/api/v1/hotel/summary", headers=admin)
    assert summary.status_code == 200, summary.text
    data = summary.json()["data"]
    assert any(p["name"] == f"Towel {suffix}" for p in data["out_of_stock"])
    assert all(p["name"] != f"Towel {suffix}" for p in data["low_stock"])
    alert = next(a for a in data["alerts"] if a["code"] == "out_of_stock")
    assert alert["href"] == "/inventory?tab=products"
    assert "none left" in alert["message"]
    assert all(a["code"] != "low_stock" or "Towel" not in a["message"] for a in data["alerts"])


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


@pytest.mark.asyncio
async def test_hotel_tentative_cancel_and_unpaid_checkout(client, seeded, db_session):
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
        json={"code": f"C{suffix}", "name": f"Cancel {suffix}", "rate_amount": 80},
    )
    assert room.status_code == 200, room.text
    guest = await ac.post(
        "/api/v1/hotel/guests",
        headers=admin,
        json={"full_name": f"Cancel Guest {suffix}"},
    )
    assert guest.status_code == 200, guest.text
    check_in = date.today() + timedelta(days=3)
    tentative = await ac.post(
        "/api/v1/hotel/reservations",
        headers=admin,
        json={
            "room_id": room.json()["data"]["id"],
            "guest_id": guest.json()["data"]["id"],
            "check_in_date": check_in.isoformat(),
            "check_out_date": (check_in + timedelta(days=1)).isoformat(),
            "status": "tentative",
        },
    )
    assert tentative.status_code == 200, tentative.text
    assert tentative.json()["data"]["can_cancel"] is True
    assert tentative.json()["data"]["can_extend"] is True
    assert tentative.json()["data"]["can_move"] is True
    extended = await ac.post(
        f"/api/v1/hotel/reservations/{tentative.json()['data']['id']}/extend",
        headers=admin,
        json={"new_check_out_date": (check_in + timedelta(days=2)).isoformat()},
    )
    assert extended.status_code == 200, extended.text
    assert extended.json()["data"]["nights"] == 2
    cancelled = await ac.post(
        f"/api/v1/hotel/reservations/{tentative.json()['data']['id']}/cancel",
        headers=admin,
        json={},
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["data"]["status"] == "cancelled"

    stay = await ac.post(
        "/api/v1/hotel/reservations",
        headers=admin,
        json={
            "room_id": room.json()["data"]["id"],
            "guest_id": guest.json()["data"]["id"],
            "check_in_date": (date.today() + timedelta(days=8)).isoformat(),
            "check_out_date": (date.today() + timedelta(days=10)).isoformat(),
        },
    )
    assert stay.status_code == 200, stay.text
    checked_in = await ac.post(
        f"/api/v1/hotel/reservations/{stay.json()['data']['id']}/check-in",
        headers=admin,
        json={},
    )
    assert checked_in.status_code == 200, checked_in.text
    unpaid = await ac.post(
        f"/api/v1/hotel/reservations/{stay.json()['data']['id']}/check-out",
        headers=admin,
        json={},
    )
    assert unpaid.status_code == 400, unpaid.text
    allowed = await ac.post(
        f"/api/v1/hotel/reservations/{stay.json()['data']['id']}/check-out",
        headers=admin,
        json={"allow_balance": True},
    )
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["data"]["status"] == "checked_out"
    hk = await ac.get("/api/v1/hotel/housekeeping", headers=admin)
    assert hk.status_code == 200, hk.text
    auto = next(
        t
        for t in hk.json()["data"]
        if t["room_id"] == room.json()["data"]["id"] and t["status"] == "pending"
    )
    assert auto.get("due_at")


@pytest.mark.asyncio
async def test_hotel_guest_profile_keeps_company_and_loyalty(client, seeded, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:6]
    created = await ac.post(
        "/api/v1/hotel/guests",
        headers=admin,
        json={
            "full_name": f"Corp Guest {suffix}",
            "company_name": f"Coast Co {suffix}",
            "travel_agent": "Harbour Desk",
            "loyalty_tier": "Silver",
            "preferences": "High floor",
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()["data"]
    assert body["company_name"] == f"Coast Co {suffix}"
    assert body["travel_agent"] == "Harbour Desk"
    assert body["loyalty_tier"] == "Silver"
    patched = await ac.patch(
        f"/api/v1/hotel/guests/{body['id']}",
        headers=admin,
        json={"loyalty_tier": "Gold", "travel_agent": "Harbour Desk Gold"},
    )
    assert patched.status_code == 200, patched.text
    updated = patched.json()["data"]
    assert updated["loyalty_tier"] == "Gold"
    assert updated["travel_agent"] == "Harbour Desk Gold"
    assert updated["company_name"] == f"Coast Co {suffix}"


@pytest.mark.asyncio
async def test_hotel_waitlist_does_not_hold_the_room(client, seeded, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:6]
    start = date.today() + timedelta(days=12)
    end = start + timedelta(days=2)
    room = await ac.post(
        "/api/v1/hotel/rooms",
        headers=admin,
        json={"code": f"W{suffix}", "name": f"Wait {suffix}", "rate_amount": 80, "max_occupancy": 3},
    )
    assert room.status_code == 200, room.text
    room_id = room.json()["data"]["id"]
    first = await ac.post(
        "/api/v1/hotel/guests",
        headers=admin,
        json={"full_name": f"Held {suffix}"},
    )
    second = await ac.post(
        "/api/v1/hotel/guests",
        headers=admin,
        json={"full_name": f"Waiting {suffix}"},
    )
    assert first.status_code == 200 and second.status_code == 200
    held = await ac.post(
        "/api/v1/hotel/reservations",
        headers=admin,
        json={
            "room_id": room_id,
            "guest_id": first.json()["data"]["id"],
            "check_in_date": start.isoformat(),
            "check_out_date": end.isoformat(),
            "adults": 2,
            "children": 1,
            "special_requests": "Late arrival",
        },
    )
    assert held.status_code == 200, held.text
    assert held.json()["data"]["special_requests"] == "Late arrival"
    assert held.json()["data"]["adults"] == 2
    waiting = await ac.post(
        "/api/v1/hotel/reservations",
        headers=admin,
        json={
            "room_id": room_id,
            "guest_id": second.json()["data"]["id"],
            "check_in_date": start.isoformat(),
            "check_out_date": end.isoformat(),
            "status": "waitlisted",
            "special_requests": "Any floor",
        },
    )
    assert waiting.status_code == 200, waiting.text
    assert waiting.json()["data"]["status"] == "waitlisted"
    assert waiting.json()["data"]["can_confirm"] is True
    assert waiting.json()["data"]["can_check_in"] is False
    blocked = await ac.post(
        f"/api/v1/hotel/reservations/{waiting.json()['data']['id']}/confirm",
        headers=admin,
        json={},
    )
    assert blocked.status_code == 409, blocked.text
    listed = await ac.get("/api/v1/hotel/reservations?list_kind=waitlist", headers=admin)
    assert listed.status_code == 200, listed.text
    assert any(row["id"] == waiting.json()["data"]["id"] for row in listed.json()["data"])
    cancelled = await ac.post(
        f"/api/v1/hotel/reservations/{held.json()['data']['id']}/cancel",
        headers=admin,
        json={},
    )
    assert cancelled.status_code == 200, cancelled.text
    offered = await ac.post(
        f"/api/v1/hotel/reservations/{waiting.json()['data']['id']}/confirm",
        headers=admin,
        json={},
    )
    assert offered.status_code == 200, offered.text
    assert offered.json()["data"]["status"] == "booked"


@pytest.mark.asyncio
async def test_hotel_timing_and_no_show_fees_post_once(client, seeded, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:6]
    configured = await ac.patch(
        "/api/v1/hotel/settings",
        headers=admin,
        json={"early_checkin_fee": 40, "late_checkout_fee": 25, "no_show_fee_percent": 50, "tax_percent": 5},
    )
    assert configured.status_code == 200, configured.text
    start = date.today() + timedelta(days=3)
    end = start + timedelta(days=2)
    room = await ac.post(
        "/api/v1/hotel/rooms",
        headers=admin,
        json={"code": f"F{suffix}", "name": f"Fee {suffix}", "rate_amount": 250},
    )
    assert room.status_code == 200, room.text
    guest = await ac.post(
        "/api/v1/hotel/guests",
        headers=admin,
        json={"full_name": f"Fee Guest {suffix}"},
    )
    booked = await ac.post(
        "/api/v1/hotel/reservations",
        headers=admin,
        json={
            "room_id": room.json()["data"]["id"],
            "guest_id": guest.json()["data"]["id"],
            "check_in_date": start.isoformat(),
            "check_out_date": end.isoformat(),
        },
    )
    assert booked.status_code == 200, booked.text
    checked = await ac.post(
        f"/api/v1/hotel/reservations/{booked.json()['data']['id']}/check-in",
        headers=admin,
        json={},
    )
    assert checked.status_code == 200, checked.text
    folio_id = checked.json()["data"]["folio_id"]
    early = await ac.post(
        f"/api/v1/hotel/folios/{folio_id}/timing-fee",
        headers=admin,
        json={"kind": "early_checkin"},
    )
    assert early.status_code == 200, early.text
    assert early.json()["data"]["charges_total"] == 540
    again = await ac.post(
        f"/api/v1/hotel/folios/{folio_id}/timing-fee",
        headers=admin,
        json={"kind": "early_checkin"},
    )
    assert again.status_code == 200, again.text
    assert again.json()["data"]["charges_total"] == 540
    late = await ac.post(
        f"/api/v1/hotel/folios/{folio_id}/timing-fee",
        headers=admin,
        json={"kind": "late_checkout"},
    )
    assert late.status_code == 200, late.text
    assert late.json()["data"]["charges_total"] == 565
    labels = [c["description"] for c in late.json()["data"]["charges"] if not c["is_void"]]
    assert labels.count("Early check-in") == 1
    assert labels.count("Late check-out") == 1
    assert not any("tax" in c["description"].lower() for c in late.json()["data"]["charges"])

    other_room = await ac.post(
        "/api/v1/hotel/rooms",
        headers=admin,
        json={"code": f"N{suffix}", "name": f"No show {suffix}", "rate_amount": 100},
    )
    other_guest = await ac.post(
        "/api/v1/hotel/guests",
        headers=admin,
        json={"full_name": f"No Show {suffix}"},
    )
    missed = await ac.post(
        "/api/v1/hotel/reservations",
        headers=admin,
        json={
            "room_id": other_room.json()["data"]["id"],
            "guest_id": other_guest.json()["data"]["id"],
            "check_in_date": (date.today() + timedelta(days=20)).isoformat(),
            "check_out_date": (date.today() + timedelta(days=22)).isoformat(),
        },
    )
    assert missed.status_code == 200, missed.text
    assert missed.json()["data"]["can_no_show"] is False
    too_soon = await ac.post(
        f"/api/v1/hotel/reservations/{missed.json()['data']['id']}/no-show",
        headers=admin,
        json={},
    )
    assert too_soon.status_code == 409, too_soon.text
    assert too_soon.json()["detail"] == "No-show applies on the arrival date"
    due_room = await ac.post(
        "/api/v1/hotel/rooms",
        headers=admin,
        json={"code": f"D{suffix}", "name": f"Due {suffix}", "rate_amount": 100},
    )
    assert due_room.status_code == 200, due_room.text
    due_guest = await ac.post(
        "/api/v1/hotel/guests",
        headers=admin,
        json={"full_name": f"Due {suffix}"},
    )
    due = await ac.post(
        "/api/v1/hotel/reservations",
        headers=admin,
        json={
            "room_id": due_room.json()["data"]["id"],
            "guest_id": due_guest.json()["data"]["id"],
            "check_in_date": date.today().isoformat(),
            "check_out_date": (date.today() + timedelta(days=2)).isoformat(),
        },
    )
    assert due.status_code == 200, due.text
    assert due.json()["data"]["can_no_show"] is True
    marked = await ac.post(
        f"/api/v1/hotel/reservations/{due.json()['data']['id']}/no-show",
        headers=admin,
        json={},
    )
    assert marked.status_code == 200, marked.text
    fee = await ac.post(
        f"/api/v1/hotel/reservations/{due.json()['data']['id']}/no-show-fee",
        headers=admin,
        json={},
    )
    assert fee.status_code == 200, fee.text
    assert fee.json()["data"]["charges_total"] == 100
    open_labels = [c["description"] for c in fee.json()["data"]["charges"] if not c["is_void"]]
    assert open_labels == ["No-show fee"]
    fee_again = await ac.post(
        f"/api/v1/hotel/reservations/{due.json()['data']['id']}/no-show-fee",
        headers=admin,
        json={},
    )
    assert fee_again.status_code == 200, fee_again.text
    assert fee_again.json()["data"]["charges_total"] == 100


@pytest.mark.asyncio
async def test_hotel_extra_guest_and_weekend_rate(client, seeded, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:6]
    monday = date.today() + timedelta(days=1)
    while monday.weekday() != 0:
        monday += timedelta(days=1)
    saturday = monday + timedelta(days=5)
    room = await ac.post(
        "/api/v1/hotel/rooms",
        headers=admin,
        json={
            "code": f"X{suffix}",
            "name": f"Extra {suffix}",
            "room_type": "executive",
            "rate_amount": 100,
            "weekend_rate": 150,
            "extra_person_charge": 20,
            "max_occupancy": 4,
        },
    )
    assert room.status_code == 200, room.text
    assert room.json()["data"]["room_type"] == "executive"
    room_id = room.json()["data"]["id"]
    guest = await ac.post(
        "/api/v1/hotel/guests",
        headers=admin,
        json={"full_name": f"Extra Guest {suffix}"},
    )
    assert guest.status_code == 200, guest.text
    guest_id = guest.json()["data"]["id"]
    pair = await ac.post(
        "/api/v1/hotel/reservations",
        headers=admin,
        json={
            "room_id": room_id,
            "guest_id": guest_id,
            "check_in_date": monday.isoformat(),
            "check_out_date": (monday + timedelta(days=1)).isoformat(),
            "adults": 2,
        },
    )
    assert pair.status_code == 200, pair.text
    assert pair.json()["data"]["nightly_rate"] == 100
    third = await ac.post(
        "/api/v1/hotel/guests",
        headers=admin,
        json={"full_name": f"Third Guest {suffix}"},
    )
    crowded = await ac.post(
        "/api/v1/hotel/reservations",
        headers=admin,
        json={
            "room_id": room_id,
            "guest_id": third.json()["data"]["id"],
            "check_in_date": (monday + timedelta(days=1)).isoformat(),
            "check_out_date": (monday + timedelta(days=2)).isoformat(),
            "adults": 2,
            "children": 1,
        },
    )
    assert crowded.status_code == 200, crowded.text
    assert crowded.json()["data"]["nightly_rate"] == 120
    assert crowded.json()["data"]["estimated_total"] == 120
    weekend_guest = await ac.post(
        "/api/v1/hotel/guests",
        headers=admin,
        json={"full_name": f"Weekend Guest {suffix}"},
    )
    weekend = await ac.post(
        "/api/v1/hotel/reservations",
        headers=admin,
        json={
            "room_id": room_id,
            "guest_id": weekend_guest.json()["data"]["id"],
            "check_in_date": saturday.isoformat(),
            "check_out_date": (saturday + timedelta(days=1)).isoformat(),
            "adults": 3,
        },
    )
    assert weekend.status_code == 200, weekend.text
    assert weekend.json()["data"]["nightly_rate"] == 170
    too_many = await ac.post(
        "/api/v1/hotel/reservations",
        headers=admin,
        json={
            "room_id": room_id,
            "guest_id": guest_id,
            "check_in_date": (monday + timedelta(days=8)).isoformat(),
            "check_out_date": (monday + timedelta(days=9)).isoformat(),
            "adults": 5,
        },
    )
    assert too_many.status_code == 409, too_many.text


@pytest.mark.asyncio
async def test_hotel_room_stays_out_of_service_until_maintenance_ends(client, seeded, db_session):
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
        json={"code": f"M{suffix}", "name": f"Maint {suffix}", "rate_amount": 80},
    )
    assert room.status_code == 200, room.text
    room_id = room.json()["data"]["id"]
    ticket = await ac.post(
        "/api/v1/hotel/maintenance",
        headers=admin,
        json={"room_id": room_id, "title": f"Leak {suffix}", "priority": "high", "block_room": True},
    )
    assert ticket.status_code == 200, ticket.text
    forced = await ac.patch(
        f"/api/v1/hotel/rooms/{room_id}",
        headers=admin,
        json={"status": "available"},
    )
    assert forced.status_code == 409, forced.text
    task = await ac.post(
        "/api/v1/hotel/housekeeping",
        headers=admin,
        json={"room_id": room_id, "task_type": "cleaning"},
    )
    assert task.status_code == 200, task.text
    done = await ac.post(
        f"/api/v1/hotel/housekeeping/{task.json()['data']['id']}/complete",
        headers=admin,
        json={"mark_inspected": True},
    )
    assert done.status_code == 200, done.text
    listed = await ac.get("/api/v1/hotel/rooms", headers=admin)
    blocked = next(r for r in listed.json()["data"] if r["id"] == room_id)
    assert blocked["status"] in {"maintenance", "out_of_order"}
    closed = await ac.post(
        f"/api/v1/hotel/maintenance/{ticket.json()['data']['id']}/complete",
        headers=admin,
        json={},
    )
    assert closed.status_code == 200, closed.text
    released = await ac.get("/api/v1/hotel/rooms", headers=admin)
    ready = next(r for r in released.json()["data"] if r["id"] == room_id)
    assert ready["status"] == "available"


@pytest.mark.asyncio
async def test_hotel_maintenance_ticket_can_leave_the_room_in_service(client, seeded, db_session):
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
        json={"code": f"N{suffix}", "name": f"Note {suffix}", "rate_amount": 80},
    )
    assert room.status_code == 200, room.text
    room_id = room.json()["data"]["id"]
    logged = await ac.post(
        "/api/v1/hotel/maintenance",
        headers=admin,
        json={"room_id": room_id, "title": f"Dripping tap {suffix}", "block_room": False},
    )
    assert logged.status_code == 200, logged.text
    assert logged.json()["data"]["block_room"] is False
    listed = await ac.get("/api/v1/hotel/rooms", headers=admin)
    still = next(r for r in listed.json()["data"] if r["id"] == room_id)
    assert still["status"] == "available"
    blocking = await ac.post(
        "/api/v1/hotel/maintenance",
        headers=admin,
        json={"room_id": room_id, "title": f"Leak {suffix}"},
    )
    assert blocking.status_code == 200, blocking.text
    assert blocking.json()["data"]["block_room"] is True
    after = await ac.get("/api/v1/hotel/rooms", headers=admin)
    taken = next(r for r in after.json()["data"] if r["id"] == room_id)
    assert taken["status"] == "maintenance"


@pytest.mark.asyncio
async def test_hotel_task_priority_is_stored(client, seeded, db_session):
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
        json={"code": f"P{suffix}", "name": f"Priority {suffix}", "rate_amount": 80},
    )
    assert room.status_code == 200, room.text
    room_id = room.json()["data"]["id"]
    urgent = await ac.post(
        "/api/v1/hotel/housekeeping",
        headers=admin,
        json={"room_id": room_id, "task_type": "cleaning", "priority": "urgent"},
    )
    assert urgent.status_code == 200, urgent.text
    assert urgent.json()["data"]["priority"] == "urgent"
    plain = await ac.post(
        "/api/v1/hotel/housekeeping",
        headers=admin,
        json={"room_id": room_id, "task_type": "linen"},
    )
    assert plain.status_code == 200, plain.text
    assert plain.json()["data"]["priority"] == "normal"
    bad = await ac.post(
        "/api/v1/hotel/housekeeping",
        headers=admin,
        json={"room_id": room_id, "task_type": "cleaning", "priority": "nope"},
    )
    assert bad.status_code == 422, bad.text
    other = await ac.post(
        "/api/v1/hotel/rooms",
        headers=admin,
        json={"code": f"Q{suffix}", "name": f"Quiet {suffix}", "rate_amount": 80},
    )
    assert other.status_code == 200, other.text
    other_id = other.json()["data"]["id"]
    logged = await ac.post(
        "/api/v1/hotel/maintenance",
        headers=admin,
        json={"room_id": other_id, "title": f"Tap {suffix}", "priority": "urgent", "block_room": False},
    )
    assert logged.status_code == 200, logged.text
    assert logged.json()["data"]["priority"] == "urgent"
    listed = await ac.get("/api/v1/hotel/rooms", headers=admin)
    still = next(r for r in listed.json()["data"] if r["id"] == other_id)
    assert still["status"] == "available"


async def test_hotel_rate_plan_rules_apply_on_booking(client, seeded, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:6]
    monday = date.today() + timedelta(days=1)
    while monday.weekday() != 0:
        monday += timedelta(days=1)
    saturday = monday + timedelta(days=5)
    room = await ac.post(
        "/api/v1/hotel/rooms",
        headers=admin,
        json={"code": f"P{suffix}", "name": f"Plan {suffix}", "room_type": "executive", "rate_amount": 200},
    )
    assert room.status_code == 200, room.text
    room_id = room.json()["data"]["id"]
    other = await ac.post(
        "/api/v1/hotel/rooms",
        headers=admin,
        json={"code": f"S{suffix}", "name": f"Std {suffix}", "room_type": "standard", "rate_amount": 90},
    )
    assert other.status_code == 200, other.text
    guest = await ac.post(
        "/api/v1/hotel/guests",
        headers=admin,
        json={"full_name": f"Plan Guest {suffix}"},
    )
    assert guest.status_code == 200, guest.text
    guest_id = guest.json()["data"]["id"]
    both = await ac.post(
        "/api/v1/hotel/rate-plans",
        headers=admin,
        json={"code": f"BOTH{suffix}", "name": "Both", "amount": 10, "weekday_only": True, "weekend_only": True},
    )
    assert both.status_code == 422, both.text
    plan = await ac.post(
        "/api/v1/hotel/rate-plans",
        headers=admin,
        json={
            "code": f"WK{suffix}",
            "name": "Weekday executive",
            "amount": 80,
            "room_type": "executive",
            "min_nights": 2,
            "weekday_only": True,
            "starts_on": monday.isoformat(),
            "ends_on": (monday + timedelta(days=20)).isoformat(),
        },
    )
    assert plan.status_code == 200, plan.text
    plan_id = plan.json()["data"]["id"]
    short = await ac.post(
        "/api/v1/hotel/reservations",
        headers=admin,
        json={
            "room_id": room_id,
            "guest_id": guest_id,
            "check_in_date": monday.isoformat(),
            "check_out_date": (monday + timedelta(days=1)).isoformat(),
            "rate_plan_id": plan_id,
        },
    )
    assert short.status_code == 409, short.text
    weekend = await ac.post(
        "/api/v1/hotel/reservations",
        headers=admin,
        json={
            "room_id": room_id,
            "guest_id": guest_id,
            "check_in_date": saturday.isoformat(),
            "check_out_date": (saturday + timedelta(days=2)).isoformat(),
            "rate_plan_id": plan_id,
        },
    )
    assert weekend.status_code == 409, weekend.text
    wrong_type = await ac.post(
        "/api/v1/hotel/reservations",
        headers=admin,
        json={
            "room_id": other.json()["data"]["id"],
            "guest_id": guest_id,
            "check_in_date": monday.isoformat(),
            "check_out_date": (monday + timedelta(days=2)).isoformat(),
            "rate_plan_id": plan_id,
        },
    )
    assert wrong_type.status_code == 409, wrong_type.text
    booked = await ac.post(
        "/api/v1/hotel/reservations",
        headers=admin,
        json={
            "room_id": room_id,
            "guest_id": guest_id,
            "check_in_date": monday.isoformat(),
            "check_out_date": (monday + timedelta(days=2)).isoformat(),
            "adults": 1,
            "rate_plan_id": plan_id,
        },
    )
    assert booked.status_code == 200, booked.text
    assert booked.json()["data"]["nightly_rate"] == 80


async def test_hotel_room_amenities_and_description(client, seeded, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:6]
    blank = await ac.post(
        "/api/v1/hotel/rooms",
        headers=admin,
        json={"code": f"B{suffix}", "name": f"Blank {suffix}", "description": "   "},
    )
    assert blank.status_code == 422, blank.text
    junk = await ac.post(
        "/api/v1/hotel/rooms",
        headers=admin,
        json={"code": f"J{suffix}", "name": f"Junk {suffix}", "amenities": {"http://x": True}},
    )
    assert junk.status_code == 422, junk.text
    room = await ac.post(
        "/api/v1/hotel/rooms",
        headers=admin,
        json={
            "code": f"A{suffix}",
            "name": f"Amenity {suffix}",
            "rate_amount": 100,
            "description": "Quiet room",
            "amenities": {"wifi": True, "breakfast": True, "minibar": False},
        },
    )
    assert room.status_code == 200, room.text
    data = room.json()["data"]
    assert data["description"] == "Quiet room"
    assert data["amenities"] == {"wifi": True, "breakfast": True}
    listed = await ac.get("/api/v1/hotel/rooms", headers=admin)
    row = next(r for r in listed.json()["data"] if r["id"] == data["id"])
    assert row["amenities"] == {"wifi": True, "breakfast": True}
    assert row["description"] == "Quiet room"


async def test_hotel_cancel_inside_window_adds_no_fee(client, seeded, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    saved = await ac.patch(
        "/api/v1/hotel/settings",
        headers=admin,
        json={"cancellation_hours": 72},
    )
    assert saved.status_code == 200, saved.text
    suffix = uuid4().hex[:6]
    room = await ac.post(
        "/api/v1/hotel/rooms",
        headers=admin,
        json={"code": f"W{suffix}", "name": f"Window {suffix}", "rate_amount": 100},
    )
    assert room.status_code == 200, room.text
    guest = await ac.post(
        "/api/v1/hotel/guests",
        headers=admin,
        json={"full_name": f"Window Guest {suffix}"},
    )
    assert guest.status_code == 200, guest.text
    today = datetime.utcnow().date()
    near_in = today + timedelta(days=1)
    far_in = today + timedelta(days=10)
    near = await ac.post(
        "/api/v1/hotel/reservations",
        headers=admin,
        json={
            "room_id": room.json()["data"]["id"],
            "guest_id": guest.json()["data"]["id"],
            "check_in_date": near_in.isoformat(),
            "check_out_date": (near_in + timedelta(days=1)).isoformat(),
        },
    )
    assert near.status_code == 200, near.text
    near_body = near.json()["data"]
    assert near_body["cancellation_hours"] == 72
    assert near_body["inside_cancellation_window"] is True
    far = await ac.post(
        "/api/v1/hotel/reservations",
        headers=admin,
        json={
            "room_id": room.json()["data"]["id"],
            "guest_id": guest.json()["data"]["id"],
            "check_in_date": far_in.isoformat(),
            "check_out_date": (far_in + timedelta(days=1)).isoformat(),
        },
    )
    assert far.status_code == 200, far.text
    assert far.json()["data"]["inside_cancellation_window"] is False
    cancelled = await ac.post(
        f"/api/v1/hotel/reservations/{near_body['id']}/cancel",
        headers=admin,
        json={},
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["data"]["status"] == "cancelled"
    folios = await ac.get("/api/v1/hotel/folios", headers=admin)
    assert folios.status_code == 200, folios.text
    assert all(row.get("reservation_id") != near_body["id"] for row in folios.json()["data"])


async def test_hotel_service_charge_posts_once_off_the_room_line(client, seeded, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:6]
    too_high = await ac.patch(
        "/api/v1/hotel/settings",
        headers=admin,
        json={"service_charge_percent": 150},
    )
    assert too_high.status_code == 422, too_high.text
    start = date.today() + timedelta(days=4)
    room = await ac.post(
        "/api/v1/hotel/rooms",
        headers=admin,
        json={"code": f"C{suffix}", "name": f"Charge {suffix}", "rate_amount": 250},
    )
    assert room.status_code == 200, room.text
    guest = await ac.post(
        "/api/v1/hotel/guests",
        headers=admin,
        json={"full_name": f"Charge Guest {suffix}"},
    )
    booked = await ac.post(
        "/api/v1/hotel/reservations",
        headers=admin,
        json={
            "room_id": room.json()["data"]["id"],
            "guest_id": guest.json()["data"]["id"],
            "check_in_date": start.isoformat(),
            "check_out_date": (start + timedelta(days=2)).isoformat(),
        },
    )
    assert booked.status_code == 200, booked.text
    checked = await ac.post(
        f"/api/v1/hotel/reservations/{booked.json()['data']['id']}/check-in",
        headers=admin,
        json={},
    )
    assert checked.status_code == 200, checked.text
    folio_id = checked.json()["data"]["folio_id"]
    missing = await ac.post(
        f"/api/v1/hotel/folios/{folio_id}/service-charge",
        headers=admin,
        json={},
    )
    assert missing.status_code == 422, missing.text
    configured = await ac.patch(
        "/api/v1/hotel/settings",
        headers=admin,
        json={"service_charge_percent": 10, "tax_percent": 5},
    )
    assert configured.status_code == 200, configured.text
    posted = await ac.post(
        f"/api/v1/hotel/folios/{folio_id}/service-charge",
        headers=admin,
        json={},
    )
    assert posted.status_code == 200, posted.text
    body = posted.json()["data"]
    assert body["charges_total"] == 550
    labels = [c for c in body["charges"] if not c["is_void"]]
    room_lines = [c for c in labels if c["description"].startswith("Room charge")]
    service_lines = [c for c in labels if c["description"] == "Service charge"]
    assert len(room_lines) == 1
    assert room_lines[0]["line_total"] == 500
    assert len(service_lines) == 1
    assert service_lines[0]["line_total"] == 50
    again = await ac.post(
        f"/api/v1/hotel/folios/{folio_id}/service-charge",
        headers=admin,
        json={},
    )
    assert again.status_code == 200, again.text
    assert again.json()["data"]["charges_total"] == 550
    assert sum(1 for c in again.json()["data"]["charges"] if c["description"] == "Service charge" and not c["is_void"]) == 1


async def test_hotel_deposit_keeps_the_tender(client, seeded, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:6]
    start = date.today() + timedelta(days=6)
    room = await ac.post(
        "/api/v1/hotel/rooms",
        headers=admin,
        json={"code": f"D{suffix}", "name": f"Deposit {suffix}", "rate_amount": 100},
    )
    assert room.status_code == 200, room.text
    guest = await ac.post(
        "/api/v1/hotel/guests",
        headers=admin,
        json={"full_name": f"Deposit Guest {suffix}"},
    )
    assert guest.status_code == 200, guest.text
    bad = await ac.post(
        "/api/v1/hotel/reservations",
        headers=admin,
        json={
            "room_id": room.json()["data"]["id"],
            "guest_id": guest.json()["data"]["id"],
            "check_in_date": start.isoformat(),
            "check_out_date": (start + timedelta(days=1)).isoformat(),
            "deposit_amount": 40,
            "deposit_method": "!!!",
        },
    )
    assert bad.status_code == 422, bad.text
    booked = await ac.post(
        "/api/v1/hotel/reservations",
        headers=admin,
        json={
            "room_id": room.json()["data"]["id"],
            "guest_id": guest.json()["data"]["id"],
            "check_in_date": start.isoformat(),
            "check_out_date": (start + timedelta(days=1)).isoformat(),
            "deposit_amount": 40,
            "deposit_method": "momo",
        },
    )
    assert booked.status_code == 200, booked.text
    body = booked.json()["data"]
    assert body["deposit_amount"] == 40
    assert body["deposit_method"] == "momo"
    checked = await ac.post(
        f"/api/v1/hotel/reservations/{body['id']}/check-in",
        headers=admin,
        json={},
    )
    assert checked.status_code == 200, checked.text
    folio = await ac.get(f"/api/v1/hotel/folios/{checked.json()['data']['folio_id']}", headers=admin)
    assert folio.status_code == 200, folio.text
    data = folio.json()["data"]
    room_lines = [c for c in data["charges"] if not c["is_void"] and c["description"].startswith("Room charge")]
    assert len(room_lines) == 1
    assert room_lines[0]["line_total"] == 100
    payments = data["payments"]
    assert len(payments) == 1
    assert payments[0]["method"] == "momo"
    assert payments[0]["amount"] == 40
    assert data["balance"] == 60
    slip = await ac.get(f"/api/v1/hotel/reservations/{body['id']}/confirmation", headers=admin)
    assert slip.status_code == 200, slip.text
    assert "Deposit: 40.0 by mobile money" in slip.json()["data"]["text"] or "Deposit: 40 by mobile money" in slip.json()["data"]["text"]


async def test_hotel_event_keeps_deposit_and_notes(client, seeded, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:6]
    start = date.today() + timedelta(days=8)
    blank = await ac.post(
        "/api/v1/hotel/events",
        headers=admin,
        json={
            "title": f"Blank {suffix}",
            "space_name": "Garden",
            "starts_on": start.isoformat(),
            "ends_on": (start + timedelta(days=1)).isoformat(),
            "notes": "   ",
        },
    )
    assert blank.status_code == 422, blank.text
    junk = await ac.post(
        "/api/v1/hotel/events",
        headers=admin,
        json={
            "title": f"Junk {suffix}",
            "space_name": "Garden",
            "starts_on": start.isoformat(),
            "ends_on": (start + timedelta(days=1)).isoformat(),
            "notes": "!!!",
        },
    )
    assert junk.status_code == 400, junk.text
    created = await ac.post(
        "/api/v1/hotel/events",
        headers=admin,
        json={
            "title": f"Lunch {suffix}",
            "space_name": "Garden",
            "starts_on": start.isoformat(),
            "ends_on": (start + timedelta(days=1)).isoformat(),
            "deposit_amount": 150,
            "notes": "Anniversary lunch",
            "status": "confirmed",
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()["data"]
    assert body["deposit_amount"] == 150
    assert body["notes"] == "Anniversary lunch"
    listed = await ac.get("/api/v1/hotel/events", headers=admin)
    assert listed.status_code == 200, listed.text
    row = next(item for item in listed.json()["data"] if item["id"] == body["id"])
    assert row["deposit_amount"] == 150
    assert row["notes"] == "Anniversary lunch"


async def test_hotel_task_notes_and_assignee(client, seeded, db_session):
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
        json={"code": f"M{suffix}", "name": f"Maint {suffix}", "rate_amount": 80},
    )
    assert room.status_code == 200, room.text
    room_id = room.json()["data"]["id"]
    blank = await ac.post(
        "/api/v1/hotel/maintenance",
        headers=admin,
        json={"room_id": room_id, "title": f"Leak {suffix}", "notes": "   "},
    )
    assert blank.status_code == 422, blank.text
    junk = await ac.post(
        "/api/v1/hotel/housekeeping",
        headers=admin,
        json={"room_id": room_id, "notes": "!!!"},
    )
    assert junk.status_code == 400, junk.text
    start = date.today() + timedelta(days=9)
    ticket = await ac.post(
        "/api/v1/hotel/maintenance",
        headers=admin,
        json={
            "room_id": room_id,
            "title": f"Leak {suffix}",
            "assigned_to": "Kofi Mensah",
            "notes": "Leak under the sink",
            "ooo_starts_on": start.isoformat(),
            "ooo_ends_on": (start + timedelta(days=1)).isoformat(),
        },
    )
    assert ticket.status_code == 200, ticket.text
    saved = ticket.json()["data"]
    assert saved["assigned_to"] == "Kofi Mensah"
    assert saved["notes"] == "Leak under the sink"
    task = await ac.post(
        "/api/v1/hotel/housekeeping",
        headers=admin,
        json={"room_id": room_id, "notes": "Extra towels", "assigned_to": "Ama Clean"},
    )
    assert task.status_code == 200, task.text
    assert task.json()["data"]["notes"] == "Extra towels"
    listed = await ac.get("/api/v1/hotel/housekeeping", headers=admin)
    assert listed.status_code == 200, listed.text
    row = next(item for item in listed.json()["data"] if item["id"] == task.json()["data"]["id"])
    assert row["notes"] == "Extra towels"
    assert row["assigned_to"] == "Ama Clean"


async def test_hotel_guest_request_keeps_due_time_and_notes(client, seeded, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    blank = await ac.post(
        "/api/v1/hotel/guest-requests",
        headers=admin,
        json={"title": "Extra towels", "notes": "   "},
    )
    assert blank.status_code == 422, blank.text
    junk = await ac.post(
        "/api/v1/hotel/guest-requests",
        headers=admin,
        json={"title": "Extra towels", "notes": "!!!"},
    )
    assert junk.status_code == 400, junk.text
    bad = await ac.post(
        "/api/v1/hotel/guest-requests",
        headers=admin,
        json={"title": "Wake-up call", "due_at": "not-a-date"},
    )
    assert bad.status_code == 422, bad.text
    when = (datetime.utcnow() + timedelta(days=1)).replace(hour=6, minute=30, second=0, microsecond=0)
    saved = await ac.post(
        "/api/v1/hotel/guest-requests",
        headers=admin,
        json={
            "title": "Wake-up call",
            "kind": "wake_up",
            "due_at": when.isoformat(timespec="seconds"),
            "notes": "Knock softly",
        },
    )
    assert saved.status_code == 200, saved.text
    data = saved.json()["data"]
    assert data["kind"] == "wake_up"
    assert data["notes"] == "Knock softly"
    assert data["due_at"].startswith(when.strftime("%Y-%m-%dT06:30"))
    plain = await ac.post(
        "/api/v1/hotel/guest-requests",
        headers=admin,
        json={"title": "Extra pillow"},
    )
    assert plain.status_code == 200, plain.text
    assert plain.json()["data"]["due_at"] is None
    assert plain.json()["data"]["notes"] is None
    listed = await ac.get("/api/v1/hotel/guest-requests", headers=admin)
    assert listed.status_code == 200, listed.text
    row = next(item for item in listed.json()["data"] if item["id"] == data["id"])
    assert row["notes"] == "Knock softly"
    assert row["due_at"].startswith(when.strftime("%Y-%m-%dT06:30"))


@pytest.mark.asyncio
async def test_hotel_guest_request_can_name_a_room(client, seeded, db_session):
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
        json={"code": f"R{suffix}", "name": f"Request {suffix}", "rate_amount": 80},
    )
    assert room.status_code == 200, room.text
    room_id = room.json()["data"]["id"]
    blank = await ac.post(
        "/api/v1/hotel/guest-requests",
        headers=admin,
        json={"title": "Towels", "room_id": "   "},
    )
    assert blank.status_code == 422, blank.text
    missing = await ac.post(
        "/api/v1/hotel/guest-requests",
        headers=admin,
        json={"title": "Towels", "room_id": str(uuid4())},
    )
    assert missing.status_code == 404, missing.text
    saved = await ac.post(
        "/api/v1/hotel/guest-requests",
        headers=admin,
        json={"title": "Towels", "room_id": room_id, "kind": "service"},
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["data"]["room_id"] == room_id
    plain = await ac.post(
        "/api/v1/hotel/guest-requests",
        headers=admin,
        json={"title": "Late breakfast"},
    )
    assert plain.status_code == 200, plain.text
    assert plain.json()["data"]["room_id"] is None


async def test_hotel_lost_found_keeps_notes(client, seeded, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    blank = await ac.post(
        "/api/v1/hotel/lost-found",
        headers=admin,
        json={"description": "Blue scarf", "notes": "   "},
    )
    assert blank.status_code == 422, blank.text
    junk = await ac.post(
        "/api/v1/hotel/lost-found",
        headers=admin,
        json={"description": "Blue scarf", "notes": "!!!"},
    )
    assert junk.status_code == 400, junk.text
    saved = await ac.post(
        "/api/v1/hotel/lost-found",
        headers=admin,
        json={"description": "Blue scarf", "kind": "found", "notes": "Found in the wardrobe"},
    )
    assert saved.status_code == 200, saved.text
    data = saved.json()["data"]
    assert data["kind"] == "found"
    assert data["description"] == "Blue scarf"
    assert data["notes"] == "Found in the wardrobe"
    plain = await ac.post(
        "/api/v1/hotel/lost-found",
        headers=admin,
        json={"description": "Black umbrella"},
    )
    assert plain.status_code == 200, plain.text
    assert plain.json()["data"]["notes"] is None
    listed = await ac.get("/api/v1/hotel/lost-found", headers=admin)
    assert listed.status_code == 200, listed.text
    row = next(item for item in listed.json()["data"] if item["id"] == data["id"])
    assert row["notes"] == "Found in the wardrobe"


async def test_hotel_reservation_desk_note_stays_off_the_confirmation(client, seeded, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:6]
    start = date.today() + timedelta(days=14)
    room = await ac.post(
        "/api/v1/hotel/rooms",
        headers=admin,
        json={"code": f"N{suffix}", "name": f"Note {suffix}", "rate_amount": 90},
    )
    assert room.status_code == 200, room.text
    guest = await ac.post(
        "/api/v1/hotel/guests",
        headers=admin,
        json={"full_name": f"Note Guest {suffix}"},
    )
    assert guest.status_code == 200, guest.text
    stay = {
        "room_id": room.json()["data"]["id"],
        "guest_id": guest.json()["data"]["id"],
        "check_in_date": start.isoformat(),
        "check_out_date": (start + timedelta(days=1)).isoformat(),
    }
    blank = await ac.post(
        "/api/v1/hotel/reservations",
        headers=admin,
        json={**stay, "notes": "   "},
    )
    assert blank.status_code == 422, blank.text
    junk = await ac.post(
        "/api/v1/hotel/reservations",
        headers=admin,
        json={**stay, "notes": "!!!"},
    )
    assert junk.status_code == 400, junk.text
    booked = await ac.post(
        "/api/v1/hotel/reservations",
        headers=admin,
        json={**stay, "special_requests": "Late arrival", "notes": "VIP arrival, do not print"},
    )
    assert booked.status_code == 200, booked.text
    body = booked.json()["data"]
    assert body["special_requests"] == "Late arrival"
    assert body["notes"] == "VIP arrival, do not print"
    slip = await ac.get(f"/api/v1/hotel/reservations/{body['id']}/confirmation", headers=admin)
    assert slip.status_code == 200, slip.text
    text = slip.json()["data"]["text"]
    assert "Special requests: Late arrival" in text
    assert "Source: Direct" in text
    assert "Phone:" not in text
    assert "Left:" not in text
    assert "VIP arrival, do not print" not in text
    assert "do not print" not in text.lower()


async def test_hotel_front_desk_float_keeps_close_notes(client, seeded, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    opened = await ac.post(
        "/api/v1/hotel/cashier/shift/open",
        headers=admin,
        json={"opening_float": 25},
    )
    assert opened.status_code == 200, opened.text
    shift_id = opened.json()["data"]["id"]
    blank = await ac.post(
        "/api/v1/hotel/cashier/shift/close",
        headers=admin,
        json={"closing_float": 25, "notes": "   "},
    )
    assert blank.status_code == 422, blank.text
    junk = await ac.post(
        "/api/v1/hotel/cashier/shift/close",
        headers=admin,
        json={"closing_float": 25, "notes": "!!!"},
    )
    assert junk.status_code == 400, junk.text
    still = await ac.get("/api/v1/hotel/cashier/shift", headers=admin)
    assert still.status_code == 200, still.text
    assert still.json()["data"]["id"] == shift_id
    assert still.json()["data"]["status"] == "open"
    closed = await ac.post(
        "/api/v1/hotel/cashier/shift/close",
        headers=admin,
        json={"closing_float": 25, "notes": "Counted with the night manager"},
    )
    assert closed.status_code == 200, closed.text
    body = closed.json()["data"]
    assert body["status"] == "closed"
    assert body["closing_float"] == 25
    assert body["notes"] == "Counted with the night manager"
    current = await ac.get("/api/v1/hotel/cashier/shift", headers=admin)
    assert current.status_code == 200, current.text
    assert current.json()["data"] is None
    listed = await ac.get("/api/v1/hotel/cashier/shifts", headers=admin)
    assert listed.status_code == 200, listed.text
    row = next(item for item in listed.json()["data"] if item["id"] == shift_id)
    assert row["notes"] == "Counted with the night manager"


async def test_hotel_folio_payment_keeps_reference_and_notes(client, seeded, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:6]
    start = date.today() + timedelta(days=18)
    room = await ac.post(
        "/api/v1/hotel/rooms",
        headers=admin,
        json={"code": f"P{suffix}", "name": f"Pay {suffix}", "rate_amount": 100},
    )
    assert room.status_code == 200, room.text
    guest = await ac.post(
        "/api/v1/hotel/guests",
        headers=admin,
        json={"full_name": f"Pay Guest {suffix}"},
    )
    assert guest.status_code == 200, guest.text
    booked = await ac.post(
        "/api/v1/hotel/reservations",
        headers=admin,
        json={
            "room_id": room.json()["data"]["id"],
            "guest_id": guest.json()["data"]["id"],
            "check_in_date": start.isoformat(),
            "check_out_date": (start + timedelta(days=1)).isoformat(),
        },
    )
    assert booked.status_code == 200, booked.text
    checked = await ac.post(
        f"/api/v1/hotel/reservations/{booked.json()['data']['id']}/check-in",
        headers=admin,
        json={},
    )
    assert checked.status_code == 200, checked.text
    folio_id = checked.json()["data"]["folio_id"]
    blank = await ac.post(
        f"/api/v1/hotel/folios/{folio_id}/payments",
        headers=admin,
        json={"method": "momo", "amount": 40, "reference": "   "},
    )
    assert blank.status_code == 422, blank.text
    junk = await ac.post(
        f"/api/v1/hotel/folios/{folio_id}/payments",
        headers=admin,
        json={"method": "momo", "amount": 40, "reference": "!!!"},
    )
    assert junk.status_code == 400, junk.text
    paid = await ac.post(
        f"/api/v1/hotel/folios/{folio_id}/payments",
        headers=admin,
        json={
            "method": "momo",
            "amount": 40,
            "reference": "MM-20481",
            "notes": "Paid at the desk",
        },
    )
    assert paid.status_code == 200, paid.text
    data = paid.json()["data"]
    room_lines = [c for c in data["charges"] if not c["is_void"] and c["description"].startswith("Room charge")]
    assert len(room_lines) == 1
    assert room_lines[0]["line_total"] == 100
    assert len(data["payments"]) == 1
    assert data["payments"][0]["method"] == "momo"
    assert data["payments"][0]["amount"] == 40
    assert data["payments"][0]["reference"] == "MM-20481"
    assert data["payments"][0]["notes"] == "Paid at the desk"
    assert data["balance"] == 60


async def test_hotel_group_keeps_name_and_notes(client, seeded, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:6]
    start = date.today() + timedelta(days=22)
    guest = await ac.post(
        "/api/v1/hotel/guests",
        headers=admin,
        json={"full_name": f"Group Guest {suffix}"},
    )
    assert guest.status_code == 200, guest.text
    first = await ac.post(
        "/api/v1/hotel/rooms",
        headers=admin,
        json={"code": f"A{suffix}", "name": f"Group A {suffix}", "rate_amount": 80},
    )
    second = await ac.post(
        "/api/v1/hotel/rooms",
        headers=admin,
        json={"code": f"B{suffix}", "name": f"Group B {suffix}", "rate_amount": 90},
    )
    assert first.status_code == 200 and second.status_code == 200
    stay = {
        "guest_id": guest.json()["data"]["id"],
        "room_ids": [first.json()["data"]["id"], second.json()["data"]["id"]],
        "check_in_date": start.isoformat(),
        "check_out_date": (start + timedelta(days=2)).isoformat(),
        "booking_source": "group",
    }
    blank = await ac.post(
        "/api/v1/hotel/reservation-groups",
        headers=admin,
        json={**stay, "name": "   "},
    )
    assert blank.status_code == 422, blank.text
    junk = await ac.post(
        "/api/v1/hotel/reservation-groups",
        headers=admin,
        json={**stay, "notes": "!!!"},
    )
    assert junk.status_code == 400, junk.text
    booked = await ac.post(
        "/api/v1/hotel/reservation-groups",
        headers=admin,
        json={**stay, "name": "Conference block", "notes": "Bill the company"},
    )
    assert booked.status_code == 200, booked.text
    body = booked.json()["data"]
    assert body["name"] == "Conference block"
    assert body["notes"] == "Bill the company"
    assert len(body["reservations"]) == 2
    assert {row["group_name"] for row in body["reservations"]} == {"Conference block"}
    assert {row["notes"] for row in body["reservations"]} == {"Bill the company"}
    slip = await ac.get(
        f"/api/v1/hotel/reservations/{body['reservations'][0]['id']}/confirmation",
        headers=admin,
    )
    assert slip.status_code == 200, slip.text
    assert "Bill the company" not in slip.json()["data"]["text"]
    listed = await ac.get("/api/v1/hotel/reservations", headers=admin)
    assert listed.status_code == 200, listed.text
    saved = [row for row in listed.json()["data"] if row["id"] in {item["id"] for item in body["reservations"]}]
    assert len(saved) == 2
    assert {row["group_name"] for row in saved} == {"Conference block"}


async def test_hotel_service_keeps_notes(client, seeded, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:6]
    blank = await ac.post(
        "/api/v1/hotel/services",
        headers=admin,
        json={"code": f"LD{suffix}", "name": "Laundry", "notes": "   "},
    )
    assert blank.status_code == 422, blank.text
    junk = await ac.post(
        "/api/v1/hotel/services",
        headers=admin,
        json={"code": f"LD{suffix}", "name": "Laundry", "notes": "!!!"},
    )
    assert junk.status_code == 400, junk.text
    saved = await ac.post(
        "/api/v1/hotel/services",
        headers=admin,
        json={
            "code": f"LD{suffix}",
            "name": "Same-day laundry",
            "category": "laundry",
            "unit_amount": 15,
            "notes": "Same-day if in by noon",
        },
    )
    assert saved.status_code == 200, saved.text
    data = saved.json()["data"]
    assert data["code"] == f"LD{suffix}".upper()
    assert data["unit_amount"] == 15
    assert data["tax_percent"] == 0
    assert data["notes"] == "Same-day if in by noon"
    plain = await ac.post(
        "/api/v1/hotel/services",
        headers=admin,
        json={"code": f"SP{suffix}", "name": "Airport transfer", "category": "transport", "unit_amount": 40},
    )
    assert plain.status_code == 200, plain.text
    assert plain.json()["data"]["notes"] is None
    listed = await ac.get("/api/v1/hotel/services", headers=admin)
    assert listed.status_code == 200, listed.text
    row = next(item for item in listed.json()["data"] if item["id"] == data["id"])
    assert row["notes"] == "Same-day if in by noon"


async def test_hotel_housekeeping_keeps_a_chosen_due_time(client, seeded, db_session):
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
        json={"code": f"H{suffix}", "name": f"House {suffix}", "rate_amount": 70},
    )
    assert room.status_code == 200, room.text
    room_id = room.json()["data"]["id"]
    bad = await ac.post(
        "/api/v1/hotel/housekeeping",
        headers=admin,
        json={"room_id": room_id, "due_at": "not-a-date"},
    )
    assert bad.status_code == 422, bad.text
    when = (datetime.utcnow() + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
    chosen = await ac.post(
        "/api/v1/hotel/housekeeping",
        headers=admin,
        json={"room_id": room_id, "due_at": when.isoformat(timespec="seconds"), "notes": "Before arrival"},
    )
    assert chosen.status_code == 200, chosen.text
    assert chosen.json()["data"]["due_at"].startswith(when.strftime("%Y-%m-%dT09:00"))
    assert chosen.json()["data"]["notes"] == "Before arrival"
    plain = await ac.post(
        "/api/v1/hotel/housekeeping",
        headers=admin,
        json={"room_id": room_id},
    )
    assert plain.status_code == 200, plain.text
    default_due = datetime.fromisoformat(plain.json()["data"]["due_at"])
    gap = default_due - datetime.utcnow()
    assert timedelta(hours=1) < gap < timedelta(hours=3)


async def test_hotel_room_keeps_notes(client, seeded, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:6]
    blank = await ac.post(
        "/api/v1/hotel/rooms",
        headers=admin,
        json={"code": f"R{suffix}", "name": f"Room {suffix}", "notes": "   "},
    )
    assert blank.status_code == 422, blank.text
    junk = await ac.post(
        "/api/v1/hotel/rooms",
        headers=admin,
        json={"code": f"R{suffix}", "name": f"Room {suffix}", "notes": "!!!"},
    )
    assert junk.status_code == 400, junk.text
    saved = await ac.post(
        "/api/v1/hotel/rooms",
        headers=admin,
        json={
            "code": f"R{suffix}",
            "name": f"Room {suffix}",
            "rate_amount": 120,
            "description": "Garden view",
            "notes": "Quiet room, away from the lift",
        },
    )
    assert saved.status_code == 200, saved.text
    data = saved.json()["data"]
    assert data["rate_amount"] == 120
    assert data["description"] == "Garden view"
    assert data["notes"] == "Quiet room, away from the lift"
    plain = await ac.post(
        "/api/v1/hotel/rooms",
        headers=admin,
        json={"code": f"S{suffix}", "name": f"Plain {suffix}", "rate_amount": 80},
    )
    assert plain.status_code == 200, plain.text
    assert plain.json()["data"]["notes"] is None
    listed = await ac.get("/api/v1/hotel/rooms", headers=admin)
    assert listed.status_code == 200, listed.text
    row = next(item for item in listed.json()["data"] if item["id"] == data["id"])
    assert row["notes"] == "Quiet room, away from the lift"


async def test_hotel_settings_keeps_notes(client, seeded, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    blank = await ac.patch(
        "/api/v1/hotel/settings",
        headers=admin,
        json={"notes": "   "},
    )
    assert blank.status_code == 422, blank.text
    junk = await ac.patch(
        "/api/v1/hotel/settings",
        headers=admin,
        json={"notes": "!!!"},
    )
    assert junk.status_code == 400, junk.text
    saved = await ac.patch(
        "/api/v1/hotel/settings",
        headers=admin,
        json={"notes": "Front desk closes at 22:00", "tax_percent": 12.5},
    )
    assert saved.status_code == 200, saved.text
    data = saved.json()["data"]
    assert data["notes"] == "Front desk closes at 22:00"
    assert data["tax_percent"] == 12.5
    kept = await ac.patch(
        "/api/v1/hotel/settings",
        headers=admin,
        json={"check_in_time": "15:00"},
    )
    assert kept.status_code == 200, kept.text
    assert kept.json()["data"]["notes"] == "Front desk closes at 22:00"
    assert kept.json()["data"]["tax_percent"] == 12.5
    listed = await ac.get("/api/v1/hotel/settings", headers=admin)
    assert listed.status_code == 200, listed.text
    assert listed.json()["data"]["notes"] == "Front desk closes at 22:00"


async def test_hotel_stay_discount_lowers_the_nightly_rate(client, seeded, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:6]
    check_in = date.today() + timedelta(days=3)
    check_out = check_in + timedelta(days=1)
    room = await ac.post(
        "/api/v1/hotel/rooms",
        headers=admin,
        json={"code": f"D{suffix}", "name": f"Discount {suffix}", "rate_amount": 200},
    )
    assert room.status_code == 200, room.text
    room_id = room.json()["data"]["id"]
    guest = await ac.post(
        "/api/v1/hotel/guests",
        headers=admin,
        json={"full_name": f"Discount guest {suffix}"},
    )
    assert guest.status_code == 200, guest.text
    guest_id = guest.json()["data"]["id"]
    body = {
        "room_id": room_id,
        "guest_id": guest_id,
        "check_in_date": check_in.isoformat(),
        "check_out_date": check_out.isoformat(),
        "adults": 1,
    }
    missing = await ac.post(
        "/api/v1/hotel/reservations",
        headers=admin,
        json={**body, "discount_percent": 10},
    )
    assert missing.status_code == 422, missing.text
    high = await ac.post(
        "/api/v1/hotel/reservations",
        headers=admin,
        json={**body, "discount_percent": 150, "discount_authorized_by": seed["super"].id},
    )
    assert high.status_code == 422, high.text
    plain = await ac.post("/api/v1/hotel/reservations", headers=admin, json=body)
    assert plain.status_code == 200, plain.text
    assert plain.json()["data"]["nightly_rate"] == 200
    assert plain.json()["data"]["discount_percent"] == 0
    other = await ac.post(
        "/api/v1/hotel/rooms",
        headers=admin,
        json={"code": f"E{suffix}", "name": f"Full {suffix}", "rate_amount": 200},
    )
    assert other.status_code == 200, other.text
    saved = await ac.post(
        "/api/v1/hotel/reservations",
        headers=admin,
        json={
            **body,
            "room_id": other.json()["data"]["id"],
            "discount_percent": 10,
            "discount_authorized_by": seed["super"].id,
        },
    )
    assert saved.status_code == 200, saved.text
    data = saved.json()["data"]
    assert data["nightly_rate"] == 180
    assert data["discount_percent"] == 10
    assert data["estimated_total"] == 180
    checked_in = await ac.post(
        f"/api/v1/hotel/reservations/{data['id']}/check-in",
        headers=admin,
        json={},
    )
    assert checked_in.status_code == 200, checked_in.text
    folio = await ac.get(f"/api/v1/hotel/folios/{checked_in.json()['data']['folio_id']}", headers=admin)
    assert folio.status_code == 200, folio.text
    charges = folio.json()["data"]["charges"]
    assert len(charges) == 1
    assert charges[0]["line_total"] == 180
    assert charges[0]["tax_amount"] == 0
    assert folio.json()["data"]["charges_total"] == 180


async def test_hotel_folio_charge_keeps_quantity(client, seeded, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:6]
    check_in = date.today() + timedelta(days=4)
    check_out = check_in + timedelta(days=1)
    room = await ac.post(
        "/api/v1/hotel/rooms",
        headers=admin,
        json={"code": f"Q{suffix}", "name": f"Qty {suffix}", "rate_amount": 100},
    )
    assert room.status_code == 200, room.text
    guest = await ac.post(
        "/api/v1/hotel/guests",
        headers=admin,
        json={"full_name": f"Qty guest {suffix}"},
    )
    assert guest.status_code == 200, guest.text
    booked = await ac.post(
        "/api/v1/hotel/reservations",
        headers=admin,
        json={
            "room_id": room.json()["data"]["id"],
            "guest_id": guest.json()["data"]["id"],
            "check_in_date": check_in.isoformat(),
            "check_out_date": check_out.isoformat(),
            "adults": 1,
        },
    )
    assert booked.status_code == 200, booked.text
    checked_in = await ac.post(
        f"/api/v1/hotel/reservations/{booked.json()['data']['id']}/check-in",
        headers=admin,
        json={},
    )
    assert checked_in.status_code == 200, checked_in.text
    folio_id = checked_in.json()["data"]["folio_id"]
    zero = await ac.post(
        f"/api/v1/hotel/folios/{folio_id}/charges",
        headers=admin,
        json={"description": "Laundry", "unit_amount": 15, "quantity": 0},
    )
    assert zero.status_code == 422, zero.text
    posted = await ac.post(
        f"/api/v1/hotel/folios/{folio_id}/charges",
        headers=admin,
        json={"description": "Laundry", "unit_amount": 15, "quantity": 2, "charge_type": "laundry"},
    )
    assert posted.status_code == 200, posted.text
    plain = await ac.post(
        f"/api/v1/hotel/folios/{folio_id}/charges",
        headers=admin,
        json={"description": "Water", "unit_amount": 8},
    )
    assert plain.status_code == 200, plain.text
    folio = await ac.get(f"/api/v1/hotel/folios/{folio_id}", headers=admin)
    assert folio.status_code == 200, folio.text
    charges = folio.json()["data"]["charges"]
    room_line = next(c for c in charges if c["description"] != "Laundry" and c["description"] != "Water")
    laundry = next(c for c in charges if c["description"] == "Laundry")
    water = next(c for c in charges if c["description"] == "Water")
    assert room_line["line_total"] == 100
    assert room_line["tax_amount"] == 0
    assert laundry["quantity"] == 2
    assert laundry["unit_amount"] == 15
    assert laundry["line_total"] == 30
    assert laundry["tax_amount"] == 0
    assert laundry["discount_amount"] == 0
    assert water["quantity"] == 1
    assert water["line_total"] == 8
    assert folio.json()["data"]["charges_total"] == 138


async def test_hotel_folio_charge_keeps_discount(client, seeded, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:6]
    check_in = date.today() + timedelta(days=5)
    check_out = check_in + timedelta(days=1)
    room = await ac.post(
        "/api/v1/hotel/rooms",
        headers=admin,
        json={"code": f"Z{suffix}", "name": f"Disc {suffix}", "rate_amount": 100},
    )
    assert room.status_code == 200, room.text
    guest = await ac.post(
        "/api/v1/hotel/guests",
        headers=admin,
        json={"full_name": f"Disc guest {suffix}"},
    )
    assert guest.status_code == 200, guest.text
    booked = await ac.post(
        "/api/v1/hotel/reservations",
        headers=admin,
        json={
            "room_id": room.json()["data"]["id"],
            "guest_id": guest.json()["data"]["id"],
            "check_in_date": check_in.isoformat(),
            "check_out_date": check_out.isoformat(),
            "adults": 1,
        },
    )
    assert booked.status_code == 200, booked.text
    checked_in = await ac.post(
        f"/api/v1/hotel/reservations/{booked.json()['data']['id']}/check-in",
        headers=admin,
        json={},
    )
    assert checked_in.status_code == 200, checked_in.text
    folio_id = checked_in.json()["data"]["folio_id"]
    high = await ac.post(
        f"/api/v1/hotel/folios/{folio_id}/charges",
        headers=admin,
        json={"description": "Laundry", "unit_amount": 15, "quantity": 2, "discount_amount": 40},
    )
    assert high.status_code == 422, high.text
    posted = await ac.post(
        f"/api/v1/hotel/folios/{folio_id}/charges",
        headers=admin,
        json={
            "description": "Laundry",
            "unit_amount": 15,
            "quantity": 2,
            "discount_amount": 5,
            "charge_type": "laundry",
        },
    )
    assert posted.status_code == 200, posted.text
    folio = await ac.get(f"/api/v1/hotel/folios/{folio_id}", headers=admin)
    assert folio.status_code == 200, folio.text
    charges = folio.json()["data"]["charges"]
    room_line = next(c for c in charges if c["description"] != "Laundry")
    laundry = next(c for c in charges if c["description"] == "Laundry")
    assert room_line["line_total"] == 100
    assert room_line["tax_amount"] == 0
    assert laundry["quantity"] == 2
    assert laundry["discount_amount"] == 5
    assert laundry["line_total"] == 25
    assert laundry["tax_amount"] == 0
    assert folio.json()["data"]["charges_total"] == 125


async def test_hotel_folio_note_is_stored_and_blank_is_refused(client, seeded, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:6]
    check_in = date.today() + timedelta(days=6)
    check_out = check_in + timedelta(days=1)
    room = await ac.post(
        "/api/v1/hotel/rooms",
        headers=admin,
        json={"code": f"N{suffix}", "name": f"Note {suffix}", "rate_amount": 100},
    )
    assert room.status_code == 200, room.text
    guest = await ac.post(
        "/api/v1/hotel/guests",
        headers=admin,
        json={"full_name": f"Note guest {suffix}"},
    )
    assert guest.status_code == 200, guest.text
    booked = await ac.post(
        "/api/v1/hotel/reservations",
        headers=admin,
        json={
            "room_id": room.json()["data"]["id"],
            "guest_id": guest.json()["data"]["id"],
            "check_in_date": check_in.isoformat(),
            "check_out_date": check_out.isoformat(),
            "adults": 1,
        },
    )
    assert booked.status_code == 200, booked.text
    checked_in = await ac.post(
        f"/api/v1/hotel/reservations/{booked.json()['data']['id']}/check-in",
        headers=admin,
        json={},
    )
    assert checked_in.status_code == 200, checked_in.text
    folio_id = checked_in.json()["data"]["folio_id"]
    opened = await ac.get(f"/api/v1/hotel/folios/{folio_id}", headers=admin)
    assert opened.status_code == 200, opened.text
    assert opened.json()["data"]["notes"] is None
    blank = await ac.patch(
        f"/api/v1/hotel/folios/{folio_id}",
        headers=admin,
        json={"notes": "   "},
    )
    assert blank.status_code == 422, blank.text
    saved = await ac.patch(
        f"/api/v1/hotel/folios/{folio_id}",
        headers=admin,
        json={"notes": "Late arrival after 21:00"},
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["data"]["notes"] == "Late arrival after 21:00"
    kept = await ac.patch(f"/api/v1/hotel/folios/{folio_id}", headers=admin, json={})
    assert kept.status_code == 200, kept.text
    body = kept.json()["data"]
    assert body["notes"] == "Late arrival after 21:00"
    room_line = next(c for c in body["charges"] if c["charge_type"] == "room")
    assert room_line["line_total"] == 100
    assert room_line["tax_amount"] == 0
    assert body["charges_total"] == 100


def test_cancellation_deadline_uses_the_check_in_clock():
    from app.hotel import cancellation_deadline

    day = date(2026, 11, 2)
    assert cancellation_deadline(day, 24, "14:00") == datetime(2026, 11, 1, 14, 0)
    assert cancellation_deadline(day, 24, "00:00") == datetime(2026, 11, 1, 0, 0)


@pytest.mark.asyncio
async def test_hotel_group_discount_lowers_each_room(client, seeded, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:6]
    start = date.today() + timedelta(days=30)
    guest = await ac.post(
        "/api/v1/hotel/guests",
        headers=admin,
        json={"full_name": f"Group Discount {suffix}"},
    )
    assert guest.status_code == 200, guest.text
    rooms = []
    for label, rate in (("C", 200), ("D", 200)):
        created = await ac.post(
            "/api/v1/hotel/rooms",
            headers=admin,
            json={"code": f"{label}{suffix}", "name": f"Group {label} {suffix}", "rate_amount": rate},
        )
        assert created.status_code == 200, created.text
        rooms.append(created.json()["data"]["id"])
    stay = {
        "guest_id": guest.json()["data"]["id"],
        "room_ids": rooms,
        "check_in_date": start.isoformat(),
        "check_out_date": (start + timedelta(days=1)).isoformat(),
        "booking_source": "group",
        "discount_percent": 10,
    }
    refused = await ac.post("/api/v1/hotel/reservation-groups", headers=admin, json=stay)
    assert refused.status_code == 422, refused.text
    booked = await ac.post(
        "/api/v1/hotel/reservation-groups",
        headers=admin,
        json={**stay, "discount_authorized_by": seed["super"].id},
    )
    assert booked.status_code == 200, booked.text
    rows = booked.json()["data"]["reservations"]
    assert len(rows) == 2
    assert all(row["nightly_rate"] == 180 for row in rows)
    assert all(row["discount_percent"] == 10 for row in rows)


@pytest.mark.asyncio
async def test_hotel_event_deposit_posts_on_an_open_folio(client, seeded, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:6]
    start = date.today() + timedelta(days=12)
    guest = await ac.post(
        "/api/v1/hotel/guests",
        headers=admin,
        json={"full_name": f"Event Guest {suffix}"},
    )
    assert guest.status_code == 200, guest.text
    room = await ac.post(
        "/api/v1/hotel/rooms",
        headers=admin,
        json={"code": f"E{suffix}", "name": f"Event room {suffix}", "rate_amount": 100},
    )
    assert room.status_code == 200, room.text
    waiting = await ac.post(
        "/api/v1/hotel/events",
        headers=admin,
        json={
            "title": f"Lunch {suffix}",
            "space_name": "Garden",
            "starts_on": start.isoformat(),
            "ends_on": (start + timedelta(days=1)).isoformat(),
            "guest_id": guest.json()["data"]["id"],
            "deposit_amount": 40,
            "status": "confirmed",
        },
    )
    assert waiting.status_code == 200, waiting.text
    assert waiting.json()["data"]["deposit_amount"] == 40
    assert waiting.json()["data"]["deposit_folio_id"] is None
    booked = await ac.post(
        "/api/v1/hotel/reservations",
        headers=admin,
        json={
            "room_id": room.json()["data"]["id"],
            "guest_id": guest.json()["data"]["id"],
            "check_in_date": start.isoformat(),
            "check_out_date": (start + timedelta(days=1)).isoformat(),
        },
    )
    assert booked.status_code == 200, booked.text
    checked_in = await ac.post(
        f"/api/v1/hotel/reservations/{booked.json()['data']['id']}/check-in",
        headers=admin,
        json={},
    )
    assert checked_in.status_code == 200, checked_in.text
    folio_id = checked_in.json()["data"]["folio_id"]
    opened = await ac.get(f"/api/v1/hotel/folios/{folio_id}", headers=admin)
    assert opened.status_code == 200, opened.text
    body = opened.json()["data"]
    room_line = next(c for c in body["charges"] if c["charge_type"] == "room")
    assert room_line["line_total"] == 100
    assert room_line["tax_amount"] == 0
    payment = next(p for p in body["payments"] if p["notes"] == f"Event deposit {waiting.json()['data']['id']}")
    assert payment["amount"] == 40
    assert payment["method"] == "cash"


@pytest.mark.asyncio
async def test_hotel_restaurant_meal_posts_on_the_folio(client, seeded, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:6]
    start = date.today() + timedelta(days=14)
    guest = await ac.post(
        "/api/v1/hotel/guests",
        headers=admin,
        json={"full_name": f"Diner {suffix}"},
    )
    room = await ac.post(
        "/api/v1/hotel/rooms",
        headers=admin,
        json={"code": f"R{suffix}", "name": f"Dine {suffix}", "rate_amount": 100},
    )
    assert guest.status_code == 200 and room.status_code == 200
    service = await ac.post(
        "/api/v1/hotel/services",
        headers=admin,
        json={
            "code": f"MEAL{suffix}",
            "name": f"Jollof {suffix}",
            "category": "restaurant",
            "unit_amount": 20,
            "tax_percent": 10,
        },
    )
    assert service.status_code == 200, service.text
    booked = await ac.post(
        "/api/v1/hotel/reservations",
        headers=admin,
        json={
            "room_id": room.json()["data"]["id"],
            "guest_id": guest.json()["data"]["id"],
            "check_in_date": start.isoformat(),
            "check_out_date": (start + timedelta(days=1)).isoformat(),
        },
    )
    assert booked.status_code == 200, booked.text
    checked_in = await ac.post(
        f"/api/v1/hotel/reservations/{booked.json()['data']['id']}/check-in",
        headers=admin,
        json={},
    )
    folio_id = checked_in.json()["data"]["folio_id"]
    posted = await ac.post(
        f"/api/v1/hotel/folios/{folio_id}/service-charges",
        headers=admin,
        json={"service_id": service.json()["data"]["id"], "quantity": 2},
    )
    assert posted.status_code == 200, posted.text
    one_off = await ac.post(
        f"/api/v1/hotel/folios/{folio_id}/charges",
        headers=admin,
        json={
            "charge_type": "restaurant",
            "description": f"Grill {suffix}",
            "quantity": 1,
            "unit_amount": 25,
            "discount_amount": 0,
        },
    )
    assert one_off.status_code == 200, one_off.text
    body = one_off.json()["data"]
    room_line = next(c for c in body["charges"] if c["charge_type"] == "room")
    meal = next(c for c in body["charges"] if c["description"].startswith("Jollof"))
    grill = next(c for c in body["charges"] if c["description"].startswith("Grill"))
    assert room_line["line_total"] == 100
    assert room_line["tax_amount"] == 0
    assert meal["tax_amount"] == 4
    assert meal["line_total"] == 44
    assert grill["charge_type"] == "restaurant"
    assert grill["tax_amount"] == 0
    assert grill["line_total"] == 25
    desk = await ac.get("/api/v1/hotel/summary", headers=admin)
    assert desk.status_code == 200, desk.text
    today = desk.json()["data"]
    assert today["meal_revenue"] == 69
    assert today["drink_revenue"] == 0
    assert today["room_revenue"] == 100
    assert today["service_revenue"] == 69


@pytest.mark.asyncio
async def test_hotel_night_audit_keeps_a_note(client, seeded, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    blank = await ac.post("/api/v1/hotel/night-audits", headers=admin, json={"notes": "   "})
    assert blank.status_code == 422, blank.text
    junk = await ac.post("/api/v1/hotel/night-audits", headers=admin, json={"notes": "!!!"})
    assert junk.status_code == 400, junk.text
    posted = await ac.post(
        "/api/v1/hotel/night-audits",
        headers=admin,
        json={"notes": "Closed with the night manager"},
    )
    assert posted.status_code == 200, posted.text
    snap = posted.json()["data"]["snapshot"]
    assert snap["note"] == "Closed with the night manager"
    assert snap["day_closed"] is True
    assert snap["room_charges_reposted"] is False
    again = await ac.post("/api/v1/hotel/night-audits", headers=admin, json={})
    assert again.status_code == 409, again.text


@pytest.mark.asyncio
async def test_hotel_bar_runs_together_or_separate(client, seeded, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    listed = await ac.get("/api/v1/hotel/settings", headers=admin)
    assert listed.status_code == 200, listed.text
    assert listed.json()["data"]["food_outlet_mode"] == "together"
    assert "food-outlet" not in str(listed.json()["data"].get("notes") or "")
    bad = await ac.patch(
        "/api/v1/hotel/settings",
        headers=admin,
        json={"food_outlet_mode": "side"},
    )
    assert bad.status_code == 422, bad.text
    separate = await ac.patch(
        "/api/v1/hotel/settings",
        headers=admin,
        json={"food_outlet_mode": "separate"},
    )
    assert separate.status_code == 200, separate.text
    assert separate.json()["data"]["food_outlet_mode"] == "separate"
    assert separate.json()["data"]["notes"] is None
    noted = await ac.patch(
        "/api/v1/hotel/settings",
        headers=admin,
        json={"notes": "Kitchen closes at 22:00"},
    )
    assert noted.status_code == 200, noted.text
    assert noted.json()["data"]["notes"] == "Kitchen closes at 22:00"
    assert noted.json()["data"]["food_outlet_mode"] == "separate"
    assert "food-outlet" not in noted.json()["data"]["notes"]
    kept = await ac.patch(
        "/api/v1/hotel/settings",
        headers=admin,
        json={"check_in_time": "15:00"},
    )
    assert kept.status_code == 200, kept.text
    assert kept.json()["data"]["food_outlet_mode"] == "separate"
    assert kept.json()["data"]["notes"] == "Kitchen closes at 22:00"
    together = await ac.patch(
        "/api/v1/hotel/settings",
        headers=admin,
        json={"food_outlet_mode": "together"},
    )
    assert together.status_code == 200, together.text
    assert together.json()["data"]["food_outlet_mode"] == "together"
    assert together.json()["data"]["notes"] == "Kitchen closes at 22:00"
    suffix = uuid4().hex[:6]
    start = date.today() + timedelta(days=16)
    guest = await ac.post(
        "/api/v1/hotel/guests",
        headers=admin,
        json={"full_name": f"Bar guest {suffix}"},
    )
    room = await ac.post(
        "/api/v1/hotel/rooms",
        headers=admin,
        json={"code": f"B{suffix}", "name": f"Bar {suffix}", "rate_amount": 100},
    )
    assert guest.status_code == 200 and room.status_code == 200
    service = await ac.post(
        "/api/v1/hotel/services",
        headers=admin,
        json={
            "code": f"BAR{suffix}",
            "name": f"Club soda {suffix}",
            "category": "bar",
            "unit_amount": 15,
            "tax_percent": 10,
        },
    )
    assert service.status_code == 200, service.text
    booked = await ac.post(
        "/api/v1/hotel/reservations",
        headers=admin,
        json={
            "room_id": room.json()["data"]["id"],
            "guest_id": guest.json()["data"]["id"],
            "check_in_date": start.isoformat(),
            "check_out_date": (start + timedelta(days=1)).isoformat(),
        },
    )
    assert booked.status_code == 200, booked.text
    checked_in = await ac.post(
        f"/api/v1/hotel/reservations/{booked.json()['data']['id']}/check-in",
        headers=admin,
        json={},
    )
    folio_id = checked_in.json()["data"]["folio_id"]
    posted = await ac.post(
        f"/api/v1/hotel/folios/{folio_id}/service-charges",
        headers=admin,
        json={"service_id": service.json()["data"]["id"], "quantity": 2},
    )
    assert posted.status_code == 200, posted.text
    one_off = await ac.post(
        f"/api/v1/hotel/folios/{folio_id}/charges",
        headers=admin,
        json={
            "charge_type": "bar",
            "description": f"Tonic {suffix}",
            "quantity": 1,
            "unit_amount": 18,
            "discount_amount": 0,
        },
    )
    assert one_off.status_code == 200, one_off.text
    body = one_off.json()["data"]
    room_line = next(c for c in body["charges"] if c["charge_type"] == "room")
    drink = next(c for c in body["charges"] if c["description"].startswith("Club soda"))
    tonic = next(c for c in body["charges"] if c["description"].startswith("Tonic"))
    assert room_line["line_total"] == 100
    assert room_line["tax_amount"] == 0
    assert drink["charge_type"] == "bar"
    assert drink["tax_amount"] == 3
    assert drink["line_total"] == 33
    assert tonic["charge_type"] == "bar"
    assert tonic["tax_amount"] == 0
    assert tonic["line_total"] == 18
    desk = await ac.get("/api/v1/hotel/summary", headers=admin)
    assert desk.status_code == 200, desk.text
    today = desk.json()["data"]
    assert today["drink_revenue"] == 51
    assert today["meal_revenue"] == 0
    assert today["room_revenue"] == 100
    assert today["service_revenue"] == 51


@pytest.mark.asyncio
async def test_hotel_online_booking_holds_a_room_without_payment(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    closed = await ac.get("/api/v1/public/hotel-booking/alpha")
    assert closed.status_code == 404, closed.text
    suffix = uuid4().hex[:6]
    room = await ac.post(
        "/api/v1/hotel/rooms",
        headers=admin,
        json={
            "code": f"OL{suffix}",
            "name": f"Online {suffix}",
            "room_type": "standard",
            "rate_amount": 250,
            "max_occupancy": 2,
        },
    )
    assert room.status_code == 200, room.text
    room_id = room.json()["data"]["id"]
    junk = await ac.put(
        "/api/v1/hotel/booking-link",
        headers=admin,
        json={"hostname": "!!!", "link_kind": "existing"},
    )
    assert junk.status_code == 422, junk.text
    existing = await ac.put(
        "/api/v1/hotel/booking-link",
        headers=admin,
        json={"hostname": "https://www.inn.example/stay", "link_kind": "existing"},
    )
    assert existing.status_code == 200, existing.text
    assert existing.json()["data"]["hostname"] == "inn.example"
    assert existing.json()["data"]["path"] == "/stay/alpha"
    newer = await ac.put(
        "/api/v1/hotel/booking-link",
        headers=admin,
        json={"hostname": "stay.example", "link_kind": "new"},
    )
    assert newer.status_code == 200, newer.text
    page = await ac.get("/api/v1/public/hotel-booking/alpha")
    assert page.status_code == 200, page.text
    assert page.json()["data"]["open"] is True
    by_host = await ac.get("/api/v1/public/hotel-booking/by-host", params={"host": "www.stay.example"})
    assert by_host.status_code == 200, by_host.text
    assert by_host.json()["data"]["slug"] == "alpha"
    arrival = date.today() + timedelta(days=2)
    depart = arrival + timedelta(days=2)
    charged = await ac.post(
        "/api/v1/public/hotel-booking/alpha",
        json={
            "guest_name": "Ama Boateng",
            "phone": "+233241234567",
            "check_in_date": arrival.isoformat(),
            "check_out_date": depart.isoformat(),
            "adults": 2,
            "room_id": room_id,
            "payment_method": "card",
        },
    )
    assert charged.status_code == 422, charged.text
    past = await ac.post(
        "/api/v1/public/hotel-booking/alpha",
        json={
            "guest_name": "Ama Boateng",
            "phone": "+233241234567",
            "check_in_date": (date.today() - timedelta(days=1)).isoformat(),
            "check_out_date": date.today().isoformat(),
            "adults": 1,
            "room_id": room_id,
        },
    )
    assert past.status_code == 422, past.text
    crowded = await ac.get(
        "/api/v1/public/hotel-booking/alpha/rooms",
        params={"check_in": arrival.isoformat(), "check_out": depart.isoformat(), "adults": 3},
    )
    assert crowded.status_code == 200, crowded.text
    assert all(row["id"] != room_id for row in crowded.json()["data"])
    free = await ac.get(
        "/api/v1/public/hotel-booking/alpha/rooms",
        params={"check_in": arrival.isoformat(), "check_out": depart.isoformat(), "adults": 2},
    )
    assert free.status_code == 200, free.text
    offered = next(row for row in free.json()["data"] if row["id"] == room_id)
    assert offered["nightly_rate"] == 250
    assert offered["nights"] == 2
    booked = await ac.post(
        "/api/v1/public/hotel-booking/alpha",
        json={
            "guest_name": "Ama Boateng",
            "phone": "+233241234567",
            "check_in_date": arrival.isoformat(),
            "check_out_date": depart.isoformat(),
            "adults": 2,
            "room_id": room_id,
            "notes": "Late arrival",
        },
    )
    assert booked.status_code == 200, booked.text
    stay = booked.json()["data"]
    assert stay["status"] == "tentative"
    assert stay["booking_source"] == "online"
    assert stay["deposit_amount"] == 0
    assert stay["nightly_rate"] == 250
    assert stay["folio_id"] is None
    assert stay["special_requests"] == "Late arrival"
    assert stay["guest_phone"] == "+233241234567"
    assert stay["can_check_in"] is False
    waiting = await ac.get("/api/v1/hotel/summary", headers=admin)
    assert waiting.status_code == 200, waiting.text
    assert waiting.json()["data"]["online_stay_requests"] == 1
    overlap = await ac.post(
        "/api/v1/public/hotel-booking/alpha",
        json={
            "guest_name": "Kofi Mensah",
            "phone": "+233201112233",
            "check_in_date": arrival.isoformat(),
            "check_out_date": depart.isoformat(),
            "adults": 1,
            "room_id": room_id,
        },
    )
    assert overlap.status_code == 409, overlap.text
    confirmed = await ac.post(f"/api/v1/hotel/reservations/{stay['id']}/confirm", headers=admin)
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["data"]["status"] == "booked"
    cleared = await ac.get("/api/v1/hotel/summary", headers=admin)
    assert cleared.json()["data"]["online_stay_requests"] == 0
    rooms = await ac.get("/api/v1/hotel/rooms", headers=admin)
    assert next(row for row in rooms.json()["data"] if row["id"] == room_id)["status"] == "reserved"
    slip = await ac.get(f"/api/v1/hotel/reservations/{stay['id']}/confirmation", headers=admin)
    assert slip.status_code == 200, slip.text
    slip_text = slip.json()["data"]["text"]
    assert "Phone: +233241234567" in slip_text
    assert "Source: Online" in slip_text
    assert "Special requests: Late arrival" in slip_text
    assert "Status: booked" in slip_text
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    restaurant = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    denied = await ac.get("/api/v1/hotel/booking-link", headers=restaurant)
    assert denied.status_code == 404, denied.text
    gone = await ac.get("/api/v1/public/hotel-booking/alpha")
    assert gone.status_code == 404, gone.text

