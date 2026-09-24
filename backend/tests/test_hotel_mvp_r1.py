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
    assert "['Hotel', '/hotel', 'hotel']" in shell or '["Hotel", "/hotel", "hotel"]' in shell
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
