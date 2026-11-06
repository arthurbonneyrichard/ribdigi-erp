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


async def _deposit_stay(ac, h, *, amount=200, method="cash", days_ahead=3):
    room = await _room(ac, h)
    guest = await _guest(ac, h)
    start = date.today() + timedelta(days=days_ahead)
    booked = await ac.post(
        "/api/v1/hotel/reservations",
        headers=h,
        json={
            "room_id": room["id"],
            "guest_id": guest["id"],
            "check_in_date": start.isoformat(),
            "check_out_date": (start + timedelta(days=1)).isoformat(),
            "adults": 1,
            "deposit_amount": amount,
            "deposit_method": method,
        },
    )
    assert booked.status_code == 200, booked.text
    return booked.json()["data"]["id"]


async def _accounts(ac, h) -> dict[str, float]:
    tb = await ac.get("/api/v1/accounting/trial-balance", headers=h)
    data = tb.json()["data"]
    assert data["total_debit"] == pytest.approx(data["total_credit"])
    rows = data.get("rows") or data.get("accounts") or []
    return {r["code"]: round(float(r.get("debit") or 0) - float(r.get("credit") or 0), 2) for r in rows}


@pytest.mark.asyncio
async def test_deposit_reaches_the_books_when_taken_and_is_not_booked_twice_at_check_in(client, seeded, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    h = await _admin(ac, seed)
    before = await _accounts(ac, h)
    stay_id = await _deposit_stay(ac, h, amount=200, days_ahead=0)
    taken = await _accounts(ac, h)
    assert round(taken.get("1000", 0) - before.get("1000", 0), 2) == 200
    assert round(taken.get("1100", 0) - before.get("1100", 0), 2) == -200

    inn = await ac.post(f"/api/v1/hotel/reservations/{stay_id}/check-in", headers=h, json={})
    assert inn.status_code == 200, inn.text
    bill = await ac.get(f"/api/v1/hotel/folios/{inn.json()['data']['folio_id']}", headers=h)
    assert bill.json()["data"]["payments_total"] == 200
    after = await _accounts(ac, h)
    assert after.get("1000", 0) == taken.get("1000", 0)


@pytest.mark.asyncio
async def test_cancelled_deposit_waits_for_a_decision_then_refund_and_keep_reach_the_books(client, seeded, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    h = await _admin(ac, seed)
    stay_id = await _deposit_stay(ac, h, amount=200)
    early = await ac.post(f"/api/v1/hotel/reservations/{stay_id}/deposit", headers=h, json={"refund_amount": 50})
    assert early.status_code == 409

    assert (await ac.post(f"/api/v1/hotel/reservations/{stay_id}/cancel", headers=h, json={})).status_code == 200
    held = (await ac.get("/api/v1/hotel/deposits", headers=h)).json()["data"]
    assert [d["reservation_id"] for d in held] == [stay_id]
    assert held[0]["amount"] == 200

    too_much = await ac.post(f"/api/v1/hotel/reservations/{stay_id}/deposit", headers=h, json={"refund_amount": 201})
    assert too_much.status_code == 422

    before = await _accounts(ac, h)
    done = await ac.post(f"/api/v1/hotel/reservations/{stay_id}/deposit", headers=h, json={"refund_amount": 150})
    assert done.status_code == 200, done.text
    assert done.json()["data"]["kept"] == 50
    after = await _accounts(ac, h)
    assert round(after.get("1000", 0) - before.get("1000", 0), 2) == -150
    assert round(after.get("4000", 0) - before.get("4000", 0), 2) == -50  # income shows as a credit
    assert round(after.get("1100", 0) - before.get("1100", 0), 2) == 200

    assert (await ac.get("/api/v1/hotel/deposits", headers=h)).json()["data"] == []
    twice = await ac.post(f"/api/v1/hotel/reservations/{stay_id}/deposit", headers=h, json={"refund_amount": 0})
    assert twice.status_code == 409


@pytest.mark.asyncio
async def test_drawer_counts_deposits_when_taken_and_given_back_but_not_again_at_check_in(client, seeded, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    h = await _admin(ac, seed)
    opened = await ac.post("/api/v1/hotel/cashier/shift/open", headers=h, json={"opening_float": 100})
    assert opened.status_code == 200, opened.text

    async def expected():
        return (await ac.get("/api/v1/hotel/cashier/shift", headers=h)).json()["data"]["expected_cash"]

    today_stay = await _deposit_stay(ac, h, amount=200, days_ahead=0)
    assert await expected() == 300
    assert (await ac.post(f"/api/v1/hotel/reservations/{today_stay}/check-in", headers=h, json={})).status_code == 200
    assert await expected() == 300

    later = await _deposit_stay(ac, h, amount=50)
    assert await expected() == 350
    await ac.post(f"/api/v1/hotel/reservations/{later}/cancel", headers=h, json={})
    await ac.post(f"/api/v1/hotel/reservations/{later}/deposit", headers=h, json={"refund_amount": 50})
    assert await expected() == 300


@pytest.mark.asyncio
async def test_guest_documents_carry_the_hotel_name_and_email_needs_an_address(client, seeded, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    h = await _admin(ac, seed)
    await ac.patch("/api/v1/hotel/settings", headers=h, json={"property_name": "Palm Test Hotel"})
    stay_id = await _deposit_stay(ac, h, amount=100, days_ahead=0)
    inn = await ac.post(f"/api/v1/hotel/reservations/{stay_id}/check-in", headers=h, json={})
    folio_id = inn.json()["data"]["folio_id"]

    bill = await ac.get(f"/api/v1/hotel/folios/{folio_id}/print", headers=h)
    assert bill.status_code == 200, bill.text
    assert "Palm Test Hotel" in bill.json()["data"]["html"]
    assert "Guest bill" in bill.json()["data"]["html"]
    slip = await ac.get(f"/api/v1/hotel/reservations/{stay_id}/print", headers=h)
    assert "Palm Test Hotel" in slip.json()["data"]["html"]

    no_address = await ac.post(f"/api/v1/hotel/folios/{folio_id}/send", headers=h, json={})
    assert no_address.status_code == 400


@pytest.mark.asyncio
async def test_new_hotel_routes_stay_inside_the_company(client, seeded, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    await set_tenant_industry(db_session, seed["t2"], "hotel")
    h = await _admin(ac, seed)
    stay_id = await _deposit_stay(ac, h)
    room = await _room(ac, h)
    plan = await ac.post("/api/v1/hotel/rate-plans", headers=h, json={"code": f"X{uuid4().hex[:6]}", "name": "Own plan", "amount": 100})
    item = await ac.post("/api/v1/hotel/lost-found", headers=h, json={"description": "Own item", "kind": "found"})
    await ac.post(f"/api/v1/hotel/reservations/{stay_id}/cancel", headers=h, json={})

    plan_row = (await db_session.execute(select(m.HotelRatePlan).where(m.HotelRatePlan.id == plan.json()["data"]["id"]))).scalar_one()
    item_row = (await db_session.execute(select(m.HotelLostFound).where(m.HotelLostFound.id == item.json()["data"]["id"]))).scalar_one()
    room_row = (await db_session.execute(select(m.HotelRoom).where(m.HotelRoom.id == room["id"]))).scalar_one()
    stay_row = (await db_session.execute(select(m.HotelReservation).where(m.HotelReservation.id == stay_id))).scalar_one()
    for row in (plan_row, item_row, room_row, stay_row):
        row.tenant_id = seed["t2"].id
    await db_session.commit()

    day = (date.today() + timedelta(days=4)).isoformat()
    after = (date.today() + timedelta(days=5)).isoformat()
    assert (await ac.patch(f"/api/v1/hotel/rate-plans/{plan_row.id}", headers=h, json={"amount": 1})).status_code == 404
    assert (await ac.post(f"/api/v1/hotel/lost-found/{item_row.id}/close", headers=h, json={})).status_code == 404
    assert (await ac.get("/api/v1/hotel/quote", headers=h, params={"room_id": room_row.id, "check_in_date": day, "check_out_date": after})).status_code == 404
    assert (await ac.post(f"/api/v1/hotel/reservations/{stay_id}/deposit", headers=h, json={"refund_amount": 0})).status_code == 404
    assert (await ac.get(f"/api/v1/hotel/reservations/{stay_id}/print", headers=h)).status_code == 404
    assert (await ac.get("/api/v1/hotel/deposits", headers=h)).json()["data"] == []


@pytest.mark.asyncio
async def test_a_brand_new_hotel_opens_every_read_screen(client, seeded, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    h = await _admin(ac, seed)
    today = date.today().isoformat()
    for path in (
        f"summary?on_date={today}", "rooms", "guests", "reservations", "settings", "housekeeping", "maintenance",
        "services", "folios", "rate-plans", "guest-requests", "lost-found", "cashier/shift", "cashier/shifts",
        "night-audits", "events", "deposits", "reports", "booking-link",
    ):
        res = await ac.get(f"/api/v1/hotel/{path}", headers=h)
        assert res.status_code == 200, (path, res.text)


def test_only_cashiers_and_managers_settle_deposits():
    url = f"/api/v1/hotel/reservations/{uuid4()}/deposit"
    hotel_jobs.enforce("hotel_cashier", "POST", url)
    hotel_jobs.enforce("hotel_manager", "POST", url)
    for role in ("hotel_front_desk", "hotel_reservations", "hotel_housekeeping"):
        with pytest.raises(HTTPException):
            hotel_jobs.enforce(role, "POST", url)
    with pytest.raises(HTTPException):
        hotel_jobs.enforce("hotel_housekeeping", "GET", "/api/v1/hotel/deposits")


def test_room_care_staff_may_close_lost_items_but_rate_plans_stay_with_managers():
    url = f"/api/v1/hotel/lost-found/{uuid4()}/close"
    hotel_jobs.enforce("hotel_housekeeping", "POST", url)
    hotel_jobs.enforce("hotel_front_desk", "POST", url)
    with pytest.raises(HTTPException):
        hotel_jobs.enforce("hotel_cashier", "POST", url)
    with pytest.raises(HTTPException):
        hotel_jobs.enforce("hotel_front_desk", "PATCH", f"/api/v1/hotel/rate-plans/{uuid4()}")
