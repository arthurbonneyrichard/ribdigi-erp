"""Hotel module MVP — rooms, guests, reservations, check-in/out."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4

import pyotp
import pytest

from app.packages import PACKAGEABLE_MODULES
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_hotel_module_registered():
    assert "hotel" in PACKAGEABLE_MODULES
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "['Hotel', '/hotel', 'hotel']" in shell or '["Hotel", "/hotel", "hotel"]' in shell
    page = (ROOT / "frontend/app/(dashboard)/hotel/page.tsx").read_text(encoding="utf-8")
    assert "/hotel/rooms" in page
    assert "/hotel/reservations" in page
    assert "Check in" in page


@pytest.mark.asyncio
async def test_hotel_room_guest_reservation_lifecycle(client, seeded):
    ac, seed = client
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
        },
    )
    assert booked.status_code == 200, booked.text
    res_id = booked.json()["data"]["id"]
    assert booked.json()["data"]["status"] == "booked"
    assert booked.json()["data"]["nights"] == 2
    assert booked.json()["data"]["estimated_total"] == 500

    checked_in = await ac.post(
        f"/api/v1/hotel/reservations/{res_id}/check-in",
        headers=admin,
        json={},
    )
    assert checked_in.status_code == 200, checked_in.text
    assert checked_in.json()["data"]["status"] == "checked_in"

    rooms = await ac.get("/api/v1/hotel/rooms", headers=admin)
    assert rooms.status_code == 200
    matched = next(r for r in rooms.json()["data"] if r["id"] == room_id)
    assert matched["status"] == "occupied"

    checked_out = await ac.post(
        f"/api/v1/hotel/reservations/{res_id}/check-out",
        headers=admin,
        json={},
    )
    assert checked_out.status_code == 200, checked_out.text
    assert checked_out.json()["data"]["status"] == "checked_out"

    summary = await ac.get("/api/v1/hotel/summary", headers=admin)
    assert summary.status_code == 200, summary.text
    assert summary.json()["data"]["rooms_total"] >= 1


@pytest.mark.asyncio
async def test_hotel_reservation_overlap_blocked(client, seeded):
    ac, seed = client
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
