"""A stay discount must be signed by an active user of the same company."""

from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

import pyotp
import pytest

from tests.conftest import auth_headers, set_tenant_industry


async def _setup(ac, seed, db_session):
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    h = await auth_headers(ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code)
    suffix = uuid4().hex[:6]
    room = await ac.post(
        "/api/v1/hotel/rooms",
        headers=h,
        json={"code": f"S{suffix}", "name": f"Room {suffix}", "rate_amount": 400, "max_occupancy": 2},
    )
    assert room.status_code == 200, room.text
    guest = await ac.post("/api/v1/hotel/guests", headers=h, json={"full_name": f"Signer Guest {suffix}"})
    assert guest.status_code == 200, guest.text
    arrive = date.today() + timedelta(days=30)
    stay = {
        "room_id": room.json()["data"]["id"],
        "guest_id": guest.json()["data"]["id"],
        "check_in_date": arrive.isoformat(),
        "check_out_date": (arrive + timedelta(days=2)).isoformat(),
        "adults": 1,
        "children": 0,
        "discount_percent": 10,
    }
    return h, stay


@pytest.mark.asyncio
async def test_discount_signed_by_another_company_user_is_refused(client, seeded, db_session):
    ac, seed = client
    h, stay = await _setup(ac, seed, db_session)
    res = await ac.post(
        "/api/v1/hotel/reservations", headers=h, json={**stay, "discount_authorized_by": seed["u2"].id}
    )
    assert res.status_code == 422, res.text


@pytest.mark.asyncio
async def test_discount_signed_by_deactivated_user_is_refused(client, seeded, db_session):
    ac, seed = client
    h, stay = await _setup(ac, seed, db_session)
    seed["mgr1"].is_active = False
    db_session.add(seed["mgr1"])
    await db_session.commit()
    res = await ac.post(
        "/api/v1/hotel/reservations", headers=h, json={**stay, "discount_authorized_by": seed["mgr1"].id}
    )
    assert res.status_code == 422, res.text


@pytest.mark.asyncio
async def test_discount_signed_by_active_company_user_is_accepted(client, seeded, db_session):
    ac, seed = client
    h, stay = await _setup(ac, seed, db_session)
    res = await ac.post(
        "/api/v1/hotel/reservations", headers=h, json={**stay, "discount_authorized_by": seed["mgr1"].id}
    )
    assert res.status_code == 200, res.text
