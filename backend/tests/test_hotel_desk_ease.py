"""Hotel desk ease of use: price before booking, later bookings on rooms being cleaned, closing records."""

from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

import pyotp
import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app import hotel_jobs
from app import models as m
from tests.conftest import auth_headers, set_tenant_industry


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code)


async def _room(ac, h, **fields):
    suffix = uuid4().hex[:6]
    body = {"code": f"E{suffix}", "name": f"Room {suffix}", "rate_amount": 400, "max_occupancy": 2, **fields}
    res = await ac.post("/api/v1/hotel/rooms", headers=h, json=body)
    assert res.status_code == 200, res.text
    return res.json()["data"]


async def _guest(ac, h):
    res = await ac.post("/api/v1/hotel/guests", headers=h, json={"full_name": f"Ease Guest {uuid4().hex[:6]}"})
    assert res.status_code == 200, res.text
    return res.json()["data"]


def _saturday_after(day: date) -> date:
    return day + timedelta(days=(5 - day.weekday()) % 7 or 7)


@pytest.mark.asyncio
async def test_quote_matches_what_the_booking_charges(client, seeded, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    h = await _admin(ac, seed)
    room = await _room(ac, h, weekend_rate=600, max_occupancy=3, extra_person_charge=50)
    guest = await _guest(ac, h)
    arrive = _saturday_after(date.today()) - timedelta(days=1)
    leave = arrive + timedelta(days=3)
    stay = {
        "room_id": room["id"],
        "check_in_date": arrive.isoformat(),
        "check_out_date": leave.isoformat(),
        "adults": 3,
        "children": 0,
    }

    quote = await ac.get("/api/v1/hotel/quote", headers=h, params={**stay, "discount_percent": 10})
    assert quote.status_code == 200, quote.text
    priced = quote.json()["data"]
    assert priced["nights"] == 3
    assert priced["over_capacity"] is False

    me = await ac.get("/api/v1/me", headers=h)
    booked = await ac.post(
        "/api/v1/hotel/reservations",
        headers=h,
        json={**stay, "guest_id": guest["id"], "discount_percent": 10, "discount_authorized_by": me.json()["data"]["id"]},
    )
    assert booked.status_code == 200, booked.text
    assert priced["nightly_rate"] == pytest.approx(booked.json()["data"]["nightly_rate"])
    assert priced["total"] == pytest.approx(booked.json()["data"]["estimated_total"])


@pytest.mark.asyncio
async def test_quote_flags_too_many_people_and_a_plan_that_does_not_fit(client, seeded, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    h = await _admin(ac, seed)
    room = await _room(ac, h, max_occupancy=2)
    plan = await ac.post(
        "/api/v1/hotel/rate-plans",
        headers=h,
        json={"code": f"L{uuid4().hex[:6]}", "name": "Long stay", "amount": 300, "min_nights": 5},
    )
    assert plan.status_code == 200, plan.text
    start = date.today() + timedelta(days=2)
    params = {
        "room_id": room["id"],
        "check_in_date": start.isoformat(),
        "check_out_date": (start + timedelta(days=2)).isoformat(),
    }

    crowded = await ac.get("/api/v1/hotel/quote", headers=h, params={**params, "adults": 4})
    assert crowded.json()["data"]["over_capacity"] is True

    short = await ac.get("/api/v1/hotel/quote", headers=h, params={**params, "rate_plan_id": plan.json()["data"]["id"]})
    assert short.status_code == 409

    backwards = await ac.get(
        "/api/v1/hotel/quote",
        headers=h,
        params={**params, "check_out_date": start.isoformat()},
    )
    assert backwards.status_code == 400


@pytest.mark.asyncio
async def test_room_being_cleaned_can_be_booked_for_later_but_not_today(client, seeded, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    h = await _admin(ac, seed)
    room = await _room(ac, h)
    guest = await _guest(ac, h)
    row = (await db_session.execute(select(m.HotelRoom).where(m.HotelRoom.id == room["id"]))).scalar_one()
    row.status = "dirty"
    await db_session.commit()

    today = date.today()
    tomorrow = today + timedelta(days=1)
    later = today + timedelta(days=5)

    free_today = await ac.get(
        "/api/v1/hotel/availability",
        headers=h,
        params={"check_in_date": today.isoformat(), "check_out_date": tomorrow.isoformat()},
    )
    assert room["id"] not in {r["id"] for r in free_today.json()["data"]}
    free_later = await ac.get(
        "/api/v1/hotel/availability",
        headers=h,
        params={"check_in_date": later.isoformat(), "check_out_date": (later + timedelta(days=1)).isoformat()},
    )
    assert room["id"] in {r["id"] for r in free_later.json()["data"]}

    stay = {"room_id": room["id"], "guest_id": guest["id"], "adults": 1}
    refused = await ac.post(
        "/api/v1/hotel/reservations",
        headers=h,
        json={**stay, "check_in_date": today.isoformat(), "check_out_date": tomorrow.isoformat()},
    )
    assert refused.status_code == 409

    booked = await ac.post(
        "/api/v1/hotel/reservations",
        headers=h,
        json={**stay, "check_in_date": later.isoformat(), "check_out_date": (later + timedelta(days=2)).isoformat()},
    )
    assert booked.status_code == 200, booked.text


@pytest.mark.asyncio
async def test_lost_item_closes_and_stays_in_the_company(client, seeded, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    h = await _admin(ac, seed)
    item = await ac.post("/api/v1/hotel/lost-found", headers=h, json={"description": "Blue umbrella", "kind": "found"})
    assert item.status_code == 200, item.text
    item_id = item.json()["data"]["id"]
    assert item.json()["data"]["status"] == "open"

    closed = await ac.post(f"/api/v1/hotel/lost-found/{item_id}/close", headers=h, json={})
    assert closed.status_code == 200, closed.text
    assert closed.json()["data"]["status"] == "closed"

    missing = await ac.post(f"/api/v1/hotel/lost-found/{uuid4()}/close", headers=h, json={})
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_rate_plan_turned_off_cannot_be_booked_and_comes_back(client, seeded, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    h = await _admin(ac, seed)
    room = await _room(ac, h)
    made = await ac.post(
        "/api/v1/hotel/rate-plans",
        headers=h,
        json={"code": f"C{uuid4().hex[:6]}", "name": "Corporate", "amount": 350},
    )
    plan_id = made.json()["data"]["id"]
    start = date.today() + timedelta(days=3)
    params = {
        "room_id": room["id"],
        "check_in_date": start.isoformat(),
        "check_out_date": (start + timedelta(days=1)).isoformat(),
        "rate_plan_id": plan_id,
    }

    edited = await ac.patch(f"/api/v1/hotel/rate-plans/{plan_id}", headers=h, json={"amount": 325, "name": "Corporate 2026"})
    assert edited.status_code == 200, edited.text
    assert edited.json()["data"]["amount"] == 325
    assert (await ac.get("/api/v1/hotel/quote", headers=h, params=params)).json()["data"]["nightly_rate"] == 325

    off = await ac.patch(f"/api/v1/hotel/rate-plans/{plan_id}", headers=h, json={"is_active": False})
    assert off.json()["data"]["is_active"] is False
    assert (await ac.get("/api/v1/hotel/quote", headers=h, params=params)).status_code == 404

    on = await ac.patch(f"/api/v1/hotel/rate-plans/{plan_id}", headers=h, json={"is_active": True})
    assert on.json()["data"]["is_active"] is True
    assert (await ac.get("/api/v1/hotel/quote", headers=h, params=params)).status_code == 200


@pytest.mark.asyncio
async def test_room_charge_reads_in_plain_words(client, seeded, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    h = await _admin(ac, seed)
    room = await _room(ac, h)
    guest = await _guest(ac, h)
    today = date.today()
    booked = await ac.post(
        "/api/v1/hotel/reservations",
        headers=h,
        json={
            "room_id": room["id"],
            "guest_id": guest["id"],
            "check_in_date": today.isoformat(),
            "check_out_date": (today + timedelta(days=1)).isoformat(),
            "adults": 1,
        },
    )
    assert booked.status_code == 200, booked.text
    inn = await ac.post(f"/api/v1/hotel/reservations/{booked.json()['data']['id']}/check-in", headers=h, json={})
    bill = await ac.get(f"/api/v1/hotel/folios/{inn.json()['data']['folio_id']}", headers=h)
    assert any(c["description"] == "Room charge (1 night)" for c in bill.json()["data"]["charges"])


@pytest.mark.asyncio
async def test_rooms_with_guests_in_them_are_not_counted_as_waiting_for_housekeeping(client, seeded, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    h = await _admin(ac, seed)
    room = await _room(ac, h)
    guest = await _guest(ac, h)
    today = date.today()
    booked = await ac.post(
        "/api/v1/hotel/reservations",
        headers=h,
        json={
            "room_id": room["id"],
            "guest_id": guest["id"],
            "check_in_date": today.isoformat(),
            "check_out_date": (today + timedelta(days=1)).isoformat(),
            "adults": 1,
        },
    )
    assert booked.status_code == 200, booked.text
    inn = await ac.post(f"/api/v1/hotel/reservations/{booked.json()['data']['id']}/check-in", headers=h, json={})
    assert inn.status_code == 200, inn.text
    summary = await ac.get("/api/v1/hotel/summary", headers=h, params={"on_date": today.isoformat()})
    assert summary.json()["data"]["rooms_dirty"] == 0


@pytest.mark.asyncio
async def test_report_compares_periods_and_answers_who_owes(client, seeded, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    h = await _admin(ac, seed)
    room = await _room(ac, h, rate_amount=300, room_type="deluxe")
    guest = await _guest(ac, h)
    today = date.today()
    booked = await ac.post(
        "/api/v1/hotel/reservations",
        headers=h,
        json={
            "room_id": room["id"],
            "guest_id": guest["id"],
            "check_in_date": today.isoformat(),
            "check_out_date": (today + timedelta(days=2)).isoformat(),
            "adults": 1,
            "booking_source": "phone",
        },
    )
    assert booked.status_code == 200, booked.text
    inn = await ac.post(f"/api/v1/hotel/reservations/{booked.json()['data']['id']}/check-in", headers=h, json={})
    folio_id = inn.json()["data"]["folio_id"]
    paid = await ac.post(f"/api/v1/hotel/folios/{folio_id}/payments", headers=h, json={"method": "momo", "amount": 100})
    assert paid.status_code == 200, paid.text

    res = await ac.get(
        "/api/v1/hotel/reports",
        headers=h,
        params={"start_date": today.isoformat(), "end_date": (today + timedelta(days=6)).isoformat()},
    )
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert len(data["days"]) == 7
    assert [d["sold"] for d in data["days"]][:3] == [1, 1, 0]
    assert sum(d["room_revenue"] for d in data["days"]) == pytest.approx(data["room_revenue"]) == pytest.approx(600)
    assert data["previous"]["end_date"] == (today - timedelta(days=1)).isoformat()
    assert data["previous"]["start_date"] == (today - timedelta(days=7)).isoformat()
    assert data["previous"]["room_revenue"] == 0
    assert data["payments_by_method"] == {"momo": 100}
    assert data["source_detail"]["phone"] == {"stays": 1, "nights": 2, "revenue": 600}
    assert data["rooms"][0]["code"] == room["code"]
    assert data["rooms"][0]["nights"] == 2
    assert data["room_type_detail"]["deluxe"]["revenue"] == 600
    assert data["stays"] == 1 and data["average_stay_nights"] == 2
    assert data["on_the_books"]["next_7"]["occupied_nights"] == 2
    assert data["owing"][0]["guest_name"] == guest["full_name"]
    assert data["owing"][0]["balance"] == pytest.approx(500)


def test_room_care_staff_may_close_lost_items_but_rate_plans_stay_with_managers():
    url = f"/api/v1/hotel/lost-found/{uuid4()}/close"
    hotel_jobs.enforce("hotel_housekeeping", "POST", url)
    hotel_jobs.enforce("hotel_front_desk", "POST", url)
    with pytest.raises(HTTPException):
        hotel_jobs.enforce("hotel_cashier", "POST", url)
    with pytest.raises(HTTPException):
        hotel_jobs.enforce("hotel_front_desk", "PATCH", f"/api/v1/hotel/rate-plans/{uuid4()}")
