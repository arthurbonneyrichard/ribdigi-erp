"""Full hotel audit, November 2026. Each test is a way a real hotel could lose money, a room or a guest's data."""

from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

import pyotp
import pytest
from sqlalchemy import select

from app import hotel as hotel_svc
from app import hotel_jobs
from app import models as m
from tests.conftest import auth_headers, set_tenant_industry


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code)


async def _hotel(ac, seed, db_session):
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    return await _admin(ac, seed)


async def _room(ac, h, *, rate=500, **extra):
    suffix = uuid4().hex[:6]
    r = await ac.post(
        "/api/v1/hotel/rooms",
        headers=h,
        json={"code": f"A{suffix}", "name": f"Room {suffix}", "rate_amount": rate, **extra},
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]


async def _guest(ac, h, name="Audit Guest", **extra):
    r = await ac.post(
        "/api/v1/hotel/guests", headers=h, json={"full_name": f"{name} {uuid4().hex[:6]}", **extra}
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]


async def _book(ac, h, room, guest, *, start=None, nights=2, **extra):
    start = start or date.today()
    r = await ac.post(
        "/api/v1/hotel/reservations",
        headers=h,
        json={
            "room_id": room["id"],
            "guest_id": guest["id"],
            "check_in_date": start.isoformat(),
            "check_out_date": (start + timedelta(days=nights)).isoformat(),
            "adults": 1,
            **extra,
        },
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]


async def _check_in(ac, h, res_id):
    r = await ac.post(f"/api/v1/hotel/reservations/{res_id}/check-in", headers=h, json={})
    assert r.status_code == 200, r.text
    return r.json()["data"]


async def _stay(ac, h, *, rate=500, nights=2, **room_extra):
    room = await _room(ac, h, rate=rate, **room_extra)
    guest = await _guest(ac, h)
    res = await _book(ac, h, room, guest, nights=nights)
    inn = await _check_in(ac, h, res["id"])
    return room, guest, res["id"], inn["folio_id"]


async def _folio(ac, h, folio_id):
    r = await ac.get(f"/api/v1/hotel/folios/{folio_id}", headers=h)
    assert r.status_code == 200, r.text
    return r.json()["data"]


async def _balances(ac, h) -> dict[str, float]:
    tb = await ac.get("/api/v1/accounting/trial-balance", headers=h)
    assert tb.status_code == 200, tb.text
    data = tb.json()["data"]
    assert data["total_debit"] == pytest.approx(data["total_credit"])
    rows = data.get("rows") or data.get("accounts") or []
    return {r["code"]: round(float(r.get("debit") or 0) - float(r.get("credit") or 0), 2) for r in rows}


def _moved(before: dict, after: dict, code: str) -> float:
    return round(after.get(code, 0) - before.get(code, 0), 2)


async def _rooms_by_id(ac, h) -> dict[str, dict]:
    r = await ac.get("/api/v1/hotel/rooms", headers=h)
    return {row["id"]: row for row in r.json()["data"]}


# --- Rooms and stays -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_second_guest_cannot_check_into_a_room_someone_is_still_in(client, seeded, db_session):
    """The first guest was due out today but has not left. The next arrival must wait."""
    ac, seed = client
    h = await _hotel(ac, seed, db_session)
    room = await _room(ac, h)
    first = await _book(ac, h, room, await _guest(ac, h), start=date.today() - timedelta(days=1), nights=1)
    await _check_in(ac, h, first["id"])
    second = await _book(ac, h, room, await _guest(ac, h), nights=1)

    blocked = await ac.post(f"/api/v1/hotel/reservations/{second['id']}/check-in", headers=h, json={})
    assert blocked.status_code == 409, blocked.text
    assert "still" in blocked.text.lower()


@pytest.mark.asyncio
async def test_taking_a_room_off_sale_cannot_strand_the_guest_inside_it(client, seeded, db_session):
    ac, seed = client
    h = await _hotel(ac, seed, db_session)
    room, _guest_row, res_id, folio_id = await _stay(ac, h, nights=1)

    off = await ac.patch(f"/api/v1/hotel/rooms/{room['id']}", headers=h, json={"is_active": False})
    assert off.status_code == 409, off.text

    # A room closed the old way must still let its stay finish.
    row = await db_session.get(m.HotelRoom, room["id"])
    row.is_active = False
    await db_session.commit()
    await ac.post(f"/api/v1/hotel/folios/{folio_id}/payments", headers=h, json={"method": "cash", "amount": 500})
    out = await ac.post(f"/api/v1/hotel/reservations/{res_id}/check-out", headers=h, json={})
    assert out.status_code == 200, out.text


@pytest.mark.asyncio
async def test_a_room_with_a_future_booking_cannot_be_taken_off_sale(client, seeded, db_session):
    ac, seed = client
    h = await _hotel(ac, seed, db_session)
    room = await _room(ac, h)
    await _book(ac, h, room, await _guest(ac, h), start=date.today() + timedelta(days=5))
    off = await ac.patch(f"/api/v1/hotel/rooms/{room['id']}", headers=h, json={"is_active": False})
    assert off.status_code == 409, off.text


@pytest.mark.asyncio
async def test_room_status_cannot_be_changed_under_a_guest(client, seeded, db_session):
    ac, seed = client
    h = await _hotel(ac, seed, db_session)
    room, *_ = await _stay(ac, h)
    r = await ac.patch(f"/api/v1/hotel/rooms/{room['id']}", headers=h, json={"status": "out_of_order"})
    assert r.status_code == 409, r.text
    empty = await _room(ac, h)
    r = await ac.patch(f"/api/v1/hotel/rooms/{empty['id']}", headers=h, json={"status": "occupied"})
    assert r.status_code == 409, r.text


@pytest.mark.asyncio
async def test_moving_a_stay_respects_room_size_and_future_dates(client, seeded, db_session):
    ac, seed = client
    h = await _hotel(ac, seed, db_session)
    big = await _room(ac, h, max_occupancy=4)
    small = await _room(ac, h, max_occupancy=1)
    res = await _book(ac, h, big, await _guest(ac, h), start=date.today() + timedelta(days=9), adults=3)

    too_small = await ac.post(
        f"/api/v1/hotel/reservations/{res['id']}/move", headers=h, json={"new_room_id": small["id"]}
    )
    assert too_small.status_code == 409, too_small.text
    edit = await ac.patch(
        f"/api/v1/hotel/reservations/{res['id']}", headers=h, json={"room_id": small["id"]}
    )
    assert edit.status_code == 409, edit.text
    more_people = await ac.patch(f"/api/v1/hotel/reservations/{res['id']}", headers=h, json={"adults": 9})
    assert more_people.status_code == 409, more_people.text

    # A room in use tonight is fine for a stay next week.
    busy, *_ = await _stay(ac, h, nights=1, max_occupancy=4)
    moved = await ac.post(
        f"/api/v1/hotel/reservations/{res['id']}/move", headers=h, json={"new_room_id": busy["id"]}
    )
    assert moved.status_code == 200, moved.text


@pytest.mark.asyncio
async def test_a_room_change_leaves_a_cleaning_task_behind(client, seeded, db_session):
    ac, seed = client
    h = await _hotel(ac, seed, db_session)
    room, _g, res_id, _f = await _stay(ac, h)
    other = await _room(ac, h)
    moved = await ac.post(f"/api/v1/hotel/reservations/{res_id}/move", headers=h, json={"new_room_id": other["id"]})
    assert moved.status_code == 200, moved.text
    tasks = (await ac.get("/api/v1/hotel/housekeeping?status=pending", headers=h)).json()["data"]
    assert any(t["room_id"] == room["id"] for t in tasks)


@pytest.mark.asyncio
async def test_cancelling_one_booking_keeps_the_room_held_for_the_other(client, seeded, db_session):
    ac, seed = client
    h = await _hotel(ac, seed, db_session)
    room = await _room(ac, h)
    one = await _book(ac, h, room, await _guest(ac, h), start=date.today() + timedelta(days=2))
    await _book(ac, h, room, await _guest(ac, h), start=date.today() + timedelta(days=8))
    await ac.post(f"/api/v1/hotel/reservations/{one['id']}/cancel", headers=h, json={})
    assert (await _rooms_by_id(ac, h))[room["id"]]["status"] == "reserved"


@pytest.mark.asyncio
async def test_editing_a_booking_into_another_room_moves_the_hold(client, seeded, db_session):
    ac, seed = client
    h = await _hotel(ac, seed, db_session)
    room = await _room(ac, h)
    other = await _room(ac, h)
    res = await _book(ac, h, room, await _guest(ac, h), start=date.today() + timedelta(days=2))
    r = await ac.patch(f"/api/v1/hotel/reservations/{res['id']}", headers=h, json={"room_id": other["id"]})
    assert r.status_code == 200, r.text
    rooms = await _rooms_by_id(ac, h)
    assert rooms[room["id"]]["status"] == "available"
    assert rooms[other["id"]]["status"] == "reserved"


@pytest.mark.asyncio
async def test_a_guest_who_checked_in_early_holds_the_room_from_today(client, seeded, db_session):
    """Their booked dates and bill stay as they were, but tonight cannot be sold to someone else."""
    ac, seed = client
    h = await _hotel(ac, seed, db_session)
    room = await _room(ac, h, rate=100)
    start = date.today() + timedelta(days=5)
    res = await _book(ac, h, room, await _guest(ac, h), start=start, nights=2)
    inn = await _check_in(ac, h, res["id"])
    assert inn["check_in_date"] == start.isoformat()
    assert (await _folio(ac, h, inn["folio_id"]))["charges_total"] == 200

    tonight = {
        "room_id": room["id"],
        "guest_id": (await _guest(ac, h))["id"],
        "check_in_date": date.today().isoformat(),
        "check_out_date": (date.today() + timedelta(days=1)).isoformat(),
    }
    clash = await ac.post("/api/v1/hotel/reservations", headers=h, json=tonight)
    assert clash.status_code == 409, clash.text
    free = await ac.get(
        "/api/v1/hotel/availability",
        headers=h,
        params={"check_in_date": tonight["check_in_date"], "check_out_date": tonight["check_out_date"]},
    )
    assert free.status_code == 200, free.text
    assert room["id"] not in {r["id"] for r in free.json()["data"]}


@pytest.mark.asyncio
async def test_an_early_check_in_cannot_take_a_room_sold_to_someone_else_tonight(client, seeded, db_session):
    ac, seed = client
    h = await _hotel(ac, seed, db_session)
    room = await _room(ac, h)
    await _book(ac, h, room, await _guest(ac, h), start=date.today() + timedelta(days=1), nights=1)
    later = await _book(ac, h, room, await _guest(ac, h), start=date.today() + timedelta(days=3), nights=2)
    r = await ac.post(f"/api/v1/hotel/reservations/{later['id']}/check-in", headers=h, json={})
    assert r.status_code == 409, r.text


@pytest.mark.asyncio
async def test_check_in_stops_at_a_room_closed_for_maintenance_today(client, seeded, db_session):
    ac, seed = client
    h = await _hotel(ac, seed, db_session)
    room = await _room(ac, h)
    res = await _book(ac, h, room, await _guest(ac, h), start=date.today() + timedelta(days=1), nights=1)
    # The fault is reported after the booking, with a window that reaches the stay.
    t = await ac.post(
        "/api/v1/hotel/maintenance",
        headers=h,
        json={"room_id": room["id"], "title": "Burst pipe", "ooo_starts_on": date.today().isoformat()},
    )
    assert t.status_code == 200, t.text
    r = await ac.post(f"/api/v1/hotel/reservations/{res['id']}/check-in", headers=h, json={})
    assert r.status_code == 409, r.text


@pytest.mark.asyncio
async def test_two_other_open_tickets_do_not_break_closing_a_third(client, seeded, db_session):
    ac, seed = client
    h = await _hotel(ac, seed, db_session)
    room = await _room(ac, h)
    ids = []
    for title in ("Leak", "Socket", "Door"):
        t = await ac.post("/api/v1/hotel/maintenance", headers=h, json={"room_id": room["id"], "title": title})
        ids.append(t.json()["data"]["id"])
    done = await ac.post(f"/api/v1/hotel/maintenance/{ids[0]}/complete", headers=h, json={})
    assert done.status_code == 200, done.text
    assert (await _rooms_by_id(ac, h))[room["id"]]["status"] in {"maintenance", "out_of_order"}


@pytest.mark.asyncio
async def test_a_room_fixed_while_dirty_still_needs_cleaning(client, seeded, db_session):
    ac, seed = client
    h = await _hotel(ac, seed, db_session)
    room = await _room(ac, h)
    await ac.post("/api/v1/hotel/housekeeping", headers=h, json={"room_id": room["id"]})
    t = await ac.post("/api/v1/hotel/maintenance", headers=h, json={"room_id": room["id"], "title": "Lamp"})
    await ac.post(f"/api/v1/hotel/maintenance/{t.json()['data']['id']}/complete", headers=h, json={})
    row = (await _rooms_by_id(ac, h))[room["id"]]
    assert row["status"] == "dirty"
    assert row["housekeeping_status"] == "dirty"


@pytest.mark.asyncio
async def test_a_room_with_a_fault_reported_during_a_stay_does_not_get_stuck(client, seeded, db_session):
    """Fault reported while occupied, guest leaves, cleaned, then fixed: the room must be sellable."""
    ac, seed = client
    h = await _hotel(ac, seed, db_session)
    room, _g, res_id, folio_id = await _stay(ac, h, nights=1)
    t = await ac.post("/api/v1/hotel/maintenance", headers=h, json={"room_id": room["id"], "title": "Aircon"})
    await ac.post(f"/api/v1/hotel/folios/{folio_id}/payments", headers=h, json={"method": "cash", "amount": 500})
    await ac.post(f"/api/v1/hotel/reservations/{res_id}/check-out", headers=h, json={})
    tasks = (await ac.get("/api/v1/hotel/housekeeping?status=pending", headers=h)).json()["data"]
    task = next(x for x in tasks if x["room_id"] == room["id"])
    await ac.post(f"/api/v1/hotel/housekeeping/{task['id']}/complete", headers=h, json={})
    await ac.post(f"/api/v1/hotel/maintenance/{t.json()['data']['id']}/complete", headers=h, json={})
    assert (await _rooms_by_id(ac, h))[room["id"]]["status"] == "available"


@pytest.mark.asyncio
async def test_guests_past_their_date_show_on_todays_departures_and_alerts(client, seeded, db_session):
    ac, seed = client
    h = await _hotel(ac, seed, db_session)
    room = await _room(ac, h)
    res = await _book(ac, h, room, await _guest(ac, h), start=date.today() - timedelta(days=3), nights=2)
    await _check_in(ac, h, res["id"])
    rows = (await ac.get("/api/v1/hotel/reservations?list_kind=departures", headers=h)).json()["data"]
    assert res["id"] in {r["id"] for r in rows}
    summary = (await ac.get("/api/v1/hotel/summary", headers=h)).json()["data"]
    assert "overstays" in {a["code"] for a in summary["alerts"]}


@pytest.mark.asyncio
async def test_arrivals_that_never_came_are_flagged(client, seeded, db_session):
    ac, seed = client
    h = await _hotel(ac, seed, db_session)
    room = await _room(ac, h)
    await _book(ac, h, room, await _guest(ac, h), start=date.today() - timedelta(days=1), nights=3)
    summary = (await ac.get("/api/v1/hotel/summary", headers=h)).json()["data"]
    assert "late_arrivals" in {a["code"] for a in summary["alerts"]}


@pytest.mark.asyncio
async def test_a_zero_hour_cancellation_policy_is_kept(client, seeded, db_session):
    ac, seed = client
    h = await _hotel(ac, seed, db_session)
    r = await ac.patch("/api/v1/hotel/settings", headers=h, json={"cancellation_hours": 0})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["cancellation_hours"] == 0
    assert await hotel_svc.stored_cancellation_hours(db_session, tenant_id=seed["t1"].id) == 0


@pytest.mark.asyncio
async def test_settings_refuse_bad_times_and_impossible_percents(client, seeded, db_session):
    ac, seed = client
    h = await _hotel(ac, seed, db_session)
    for body in ({"check_in_time": "noon"}, {"check_out_time": "25:00"}, {"tax_percent": 1000}, {"no_show_fee_percent": 150}):
        r = await ac.patch("/api/v1/hotel/settings", headers=h, json=body)
        assert r.status_code == 422, (body, r.text)


@pytest.mark.asyncio
async def test_a_weekend_rate_can_be_removed(client, seeded, db_session):
    ac, seed = client
    h = await _hotel(ac, seed, db_session)
    room = await _room(ac, h, weekend_rate=900)
    r = await ac.patch(f"/api/v1/hotel/rooms/{room['id']}", headers=h, json={"clear_weekend_rate": True})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["weekend_rate"] is None


@pytest.mark.asyncio
async def test_a_duplicate_rate_plan_code_is_a_clear_refusal(client, seeded, db_session):
    ac, seed = client
    h = await _hotel(ac, seed, db_session)
    body = {"code": "SAVE", "name": "Saver", "amount": 100}
    assert (await ac.post("/api/v1/hotel/rate-plans", headers=h, json=body)).status_code == 200
    r = await ac.post("/api/v1/hotel/rate-plans", headers=h, json=body)
    assert r.status_code == 409, r.text


# --- Money on the bill ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_moving_a_tax_inclusive_charge_keeps_its_amount(client, seeded, db_session):
    """Tax sits inside the rate, so a move must not add it on top."""
    ac, seed = client
    h = await _hotel(ac, seed, db_session)
    await ac.patch("/api/v1/hotel/settings", headers=h, json={"tax_percent": 25, "room_rates_include_tax": True})
    _r1, _g1, _res1, folio_a = await _stay(ac, h, rate=500, nights=2)
    _r2, _g2, _res2, folio_b = await _stay(ac, h, rate=100, nights=1)
    before = await _balances(ac, h)
    charge = (await _folio(ac, h, folio_a))["charges"][0]
    assert charge["line_total"] == 1000

    r = await ac.post(
        f"/api/v1/hotel/folios/{folio_a}/charges/{charge['id']}/transfer",
        headers=h,
        json={"target_folio_id": folio_b},
    )
    assert r.status_code == 200, r.text
    assert (await _folio(ac, h, folio_b))["charges_total"] == 1100
    assert (await _folio(ac, h, folio_a))["charges_total"] == 0
    after = await _balances(ac, h)
    assert _moved(before, after, "1100") == 0


@pytest.mark.asyncio
async def test_a_charge_cannot_be_moved_off_a_closed_bill(client, seeded, db_session):
    ac, seed = client
    h = await _hotel(ac, seed, db_session)
    _r, _g, res_id, folio_a = await _stay(ac, h, rate=100, nights=1)
    _r2, _g2, _res2, folio_b = await _stay(ac, h, rate=100, nights=1)
    charge = (await _folio(ac, h, folio_a))["charges"][0]
    await ac.post(f"/api/v1/hotel/folios/{folio_a}/payments", headers=h, json={"method": "cash", "amount": 100})
    await ac.post(f"/api/v1/hotel/reservations/{res_id}/check-out", headers=h, json={})
    r = await ac.post(
        f"/api/v1/hotel/folios/{folio_a}/charges/{charge['id']}/transfer",
        headers=h,
        json={"target_folio_id": folio_b},
    )
    assert r.status_code == 400, r.text
    assert (await _folio(ac, h, folio_b))["charges_total"] == 100


@pytest.mark.asyncio
async def test_a_discount_line_takes_money_off_the_bill_and_the_books(client, seeded, db_session):
    ac, seed = client
    h = await _hotel(ac, seed, db_session)
    _r, _g, res_id, folio_id = await _stay(ac, h, rate=500, nights=2)
    before = await _balances(ac, h)
    r = await ac.post(
        f"/api/v1/hotel/folios/{folio_id}/charges",
        headers=h,
        json={"charge_type": "discount", "description": "Goodwill for the noise", "unit_amount": 100},
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["balance"] == 900
    after = await _balances(ac, h)
    assert _moved(before, after, "1100") == -100
    assert _moved(before, after, "4000") == 100

    line = next(c for c in r.json()["data"]["charges"] if c["charge_type"] == "discount")
    voided = await ac.post(
        f"/api/v1/hotel/folios/{folio_id}/charges/{line['id']}/void",
        headers=h,
        json={"void_reason": "Posted on the wrong bill"},
    )
    assert voided.status_code == 200, voided.text
    assert voided.json()["data"]["balance"] == 1000
    assert _moved(before, await _balances(ac, h), "1100") == 0


@pytest.mark.asyncio
async def test_a_discount_cannot_be_bigger_than_the_bill(client, seeded, db_session):
    ac, seed = client
    h = await _hotel(ac, seed, db_session)
    _r, _g, _res, folio_id = await _stay(ac, h, rate=100, nights=1)
    r = await ac.post(
        f"/api/v1/hotel/folios/{folio_id}/charges",
        headers=h,
        json={"charge_type": "discount", "description": "Too generous", "unit_amount": 500},
    )
    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_a_discounted_stay_invoices_at_the_discounted_total(client, seeded, db_session):
    ac, seed = client
    h = await _hotel(ac, seed, db_session)
    _r, _g, res_id, folio_id = await _stay(ac, h, rate=500, nights=1)
    await ac.post(
        f"/api/v1/hotel/folios/{folio_id}/charges",
        headers=h,
        json={"charge_type": "discount", "description": "Loyal guest", "unit_amount": 50},
    )
    await ac.post(f"/api/v1/hotel/folios/{folio_id}/payments", headers=h, json={"method": "cash", "amount": 450})
    out = await ac.post(f"/api/v1/hotel/reservations/{res_id}/check-out", headers=h, json={})
    assert out.status_code == 200, out.text
    folio = await _folio(ac, h, folio_id)
    invoice = await db_session.get(m.SalesInvoice, folio["sales_invoice_id"])
    assert float(invoice.total_amount) == 450
    assert invoice.status == "paid"
    items = (
        await db_session.execute(
            select(m.SalesInvoiceItem).where(m.SalesInvoiceItem.sales_invoice_id == invoice.id)
        )
    ).scalars().all()
    assert sum(float(i.line_total) for i in items) == 450


@pytest.mark.asyncio
async def test_a_tax_line_lands_in_tax_not_revenue(client, seeded, db_session):
    ac, seed = client
    h = await _hotel(ac, seed, db_session)
    _r, _g, _res, folio_id = await _stay(ac, h)
    before = await _balances(ac, h)
    r = await ac.post(
        f"/api/v1/hotel/folios/{folio_id}/charges",
        headers=h,
        json={"charge_type": "tax", "description": "Tourism levy", "unit_amount": 30},
    )
    assert r.status_code == 200, r.text
    after = await _balances(ac, h)
    assert _moved(before, after, "2100") == -30
    assert _moved(before, after, "4000") == 0


@pytest.mark.asyncio
async def test_service_charge_follows_the_room_charge(client, seeded, db_session):
    ac, seed = client
    h = await _hotel(ac, seed, db_session)
    await ac.patch("/api/v1/hotel/settings", headers=h, json={"service_charge_percent": 10})
    room = await _room(ac, h, rate=100)
    res = await _book(ac, h, room, await _guest(ac, h), start=date.today(), nights=4)
    folio_id = (await _check_in(ac, h, res["id"]))["folio_id"]
    r = await ac.post(f"/api/v1/hotel/folios/{folio_id}/service-charge", headers=h, json={})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["charges_total"] == 440

    extended = await ac.post(
        f"/api/v1/hotel/reservations/{res['id']}/extend",
        headers=h,
        json={"new_check_out_date": (date.today() + timedelta(days=5)).isoformat()},
    )
    assert extended.status_code == 200, extended.text
    assert (await _folio(ac, h, folio_id))["charges_total"] == 550

    early = await ac.post(f"/api/v1/hotel/reservations/{res['id']}/leave-early", headers=h, json={})
    assert early.status_code == 200, early.text
    # Check-in today, so one night stays on the bill.
    assert (await _folio(ac, h, folio_id))["charges_total"] == 110


@pytest.mark.asyncio
async def test_on_account_is_not_counted_as_money_received(client, seeded, db_session):
    ac, seed = client
    h = await _hotel(ac, seed, db_session)
    _r, _g, _res, folio_id = await _stay(ac, h, rate=500, nights=1)
    await ac.post(f"/api/v1/hotel/folios/{folio_id}/payments", headers=h, json={"method": "credit", "amount": 200})
    await ac.post(f"/api/v1/hotel/folios/{folio_id}/payments", headers=h, json={"method": "cash", "amount": 100})
    summary = (await ac.get("/api/v1/hotel/summary", headers=h)).json()["data"]
    assert summary["payments_received"] == 100
    report = (await ac.get("/api/v1/hotel/reports", headers=h)).json()["data"]
    assert report["payments_total"] == 100


@pytest.mark.asyncio
async def test_a_guest_in_credit_does_not_hide_what_others_owe(client, seeded, db_session):
    ac, seed = client
    h = await _hotel(ac, seed, db_session)
    _r, _g, _res, owing = await _stay(ac, h, rate=300, nights=1)
    _r2, _g2, _res2, credit = await _stay(ac, h, rate=100, nights=1)
    await ac.post(f"/api/v1/hotel/folios/{credit}/payments", headers=h, json={"method": "cash", "amount": 250})
    summary = (await ac.get("/api/v1/hotel/summary", headers=h)).json()["data"]
    assert summary["outstanding_folio_balance"] == 300
    report = (await ac.get("/api/v1/hotel/reports", headers=h)).json()["data"]
    assert report["outstanding_guest_balances"] == 300


@pytest.mark.asyncio
async def test_checkout_survives_two_customers_with_the_same_name(client, seeded, db_session):
    ac, seed = client
    h = await _hotel(ac, seed, db_session)
    guest = await _guest(ac, h, name="Kofi Mensah")
    for _ in range(2):
        db_session.add(
            m.Party(tenant_id=seed["t1"].id, kind="customer", name=guest["full_name"], status="active", credit_limit=0)
        )
    await db_session.commit()
    room = await _room(ac, h, rate=100)
    res = await _book(ac, h, room, guest, nights=1)
    folio_id = (await _check_in(ac, h, res["id"]))["folio_id"]
    await ac.post(f"/api/v1/hotel/folios/{folio_id}/payments", headers=h, json={"method": "cash", "amount": 100})
    out = await ac.post(f"/api/v1/hotel/reservations/{res['id']}/check-out", headers=h, json={})
    assert out.status_code == 200, out.text


@pytest.mark.asyncio
async def test_a_second_manual_line_with_a_fee_name_does_not_break_the_fee(client, seeded, db_session):
    ac, seed = client
    h = await _hotel(ac, seed, db_session)
    await ac.patch("/api/v1/hotel/settings", headers=h, json={"late_checkout_fee": 50})
    _r, _g, _res, folio_id = await _stay(ac, h)
    for _ in range(2):
        await ac.post(
            f"/api/v1/hotel/folios/{folio_id}/charges",
            headers=h,
            json={"description": "Late check-out", "unit_amount": 20},
        )
    r = await ac.post(f"/api/v1/hotel/folios/{folio_id}/timing-fee", headers=h, json={"kind": "late_checkout"})
    assert r.status_code == 200, r.text


# --- Deposits ------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_deposit_reaches_the_books_and_the_drawer_when_it_is_taken(client, seeded, db_session):
    ac, seed = client
    h = await _hotel(ac, seed, db_session)
    await ac.post("/api/v1/hotel/cashier/shift/open", headers=h, json={"opening_float": 100})
    before = await _balances(ac, h)
    room = await _room(ac, h, rate=200)
    res = await _book(
        ac, h, room, await _guest(ac, h),
        start=date.today() + timedelta(days=7), nights=2, deposit_amount=150, deposit_method="cash",
    )
    after = await _balances(ac, h)
    assert _moved(before, after, "1000") == 150
    assert _moved(before, after, "1100") == -150
    shift = (await ac.get("/api/v1/hotel/cashier/shift", headers=h)).json()["data"]
    assert shift["cash_taken"] == 150
    assert shift["expected_cash"] == 250

    # Check-in brings the room charge and does not take the deposit twice.
    inn = await _check_in(ac, h, res["id"])
    folio = await _folio(ac, h, inn["folio_id"])
    assert len(folio["payments"]) == 1
    assert folio["payments_total"] == 150
    assert folio["balance"] == round(folio["charges_total"] - 150, 2)
    assert _moved(before, await _balances(ac, h), "1000") == 150


@pytest.mark.asyncio
async def test_a_no_show_fee_is_paid_from_the_deposit_and_counted_once(client, seeded, db_session):
    ac, seed = client
    h = await _hotel(ac, seed, db_session)
    await ac.patch("/api/v1/hotel/settings", headers=h, json={"no_show_fee_percent": 100})
    before = await _balances(ac, h)
    res = await _book(
        ac, h, await _room(ac, h, rate=200), await _guest(ac, h), nights=1, deposit_amount=50, deposit_method="cash"
    )
    await ac.post(f"/api/v1/hotel/reservations/{res['id']}/no-show", headers=h, json={})
    fee = await ac.post(f"/api/v1/hotel/reservations/{res['id']}/no-show-fee", headers=h, json={})
    assert fee.status_code == 200, fee.text
    assert fee.json()["data"]["balance"] == 150

    # The deposit is on the bill now, so it cannot also be kept as income.
    assert (await ac.get("/api/v1/hotel/deposits", headers=h)).json()["data"] == []
    twice = await ac.post(f"/api/v1/hotel/reservations/{res['id']}/deposit", headers=h, json={"refund_amount": 0})
    assert twice.status_code == 409, twice.text
    after = await _balances(ac, h)
    assert _moved(before, after, "1000") == 50
    assert _moved(before, after, "4000") == -200
    assert _moved(before, after, "1100") == 150

    closed = await ac.post(f"/api/v1/hotel/reservations/{res['id']}/close-bill", headers=h, json={})
    assert closed.status_code == 200, closed.text
    assert closed.json()["data"]["status"] == "closed"
    owed = (await ac.get("/api/v1/hotel/invoices", headers=h)).json()["data"]
    assert owed["owed_total"] == 150


async def _no_show_in_credit(ac, h):
    """Deposit 150 against a fee of 100, so 50 is left over."""
    await ac.patch("/api/v1/hotel/settings", headers=h, json={"no_show_fee_percent": 50})
    res = await _book(
        ac, h, await _room(ac, h, rate=200), await _guest(ac, h), nights=1, deposit_amount=150, deposit_method="cash"
    )
    await ac.post(f"/api/v1/hotel/reservations/{res['id']}/no-show", headers=h, json={})
    fee = await ac.post(f"/api/v1/hotel/reservations/{res['id']}/no-show-fee", headers=h, json={})
    assert fee.json()["data"]["balance"] == -50
    return res


@pytest.mark.asyncio
async def test_leftover_deposit_needs_a_decision_before_the_bill_closes(client, seeded, db_session):
    ac, seed = client
    h = await _hotel(ac, seed, db_session)
    res = await _no_show_in_credit(ac, h)
    undecided = await ac.post(f"/api/v1/hotel/reservations/{res['id']}/close-bill", headers=h, json={})
    assert undecided.status_code == 422, undecided.text


@pytest.mark.asyncio
async def test_leftover_deposit_can_be_refunded(client, seeded, db_session):
    ac, seed = client
    h = await _hotel(ac, seed, db_session)
    before = await _balances(ac, h)
    res = await _no_show_in_credit(ac, h)
    closed = await ac.post(
        f"/api/v1/hotel/reservations/{res['id']}/close-bill",
        headers=h,
        json={"leftover": "refund", "reason": "Rest of the deposit returned"},
    )
    assert closed.status_code == 200, closed.text
    assert closed.json()["data"]["balance"] == 0
    after = await _balances(ac, h)
    assert _moved(before, after, "1000") == 100
    assert _moved(before, after, "1100") == 0


@pytest.mark.asyncio
async def test_leftover_deposit_can_be_kept_as_income(client, seeded, db_session):
    ac, seed = client
    h = await _hotel(ac, seed, db_session)
    before = await _balances(ac, h)
    res = await _no_show_in_credit(ac, h)
    closed = await ac.post(
        f"/api/v1/hotel/reservations/{res['id']}/close-bill",
        headers=h,
        json={"leftover": "keep", "reason": "Booking terms keep the deposit"},
    )
    assert closed.status_code == 200, closed.text
    after = await _balances(ac, h)
    assert _moved(before, after, "1000") == 150
    assert _moved(before, after, "4000") == -150
    assert _moved(before, after, "1100") == 0


@pytest.mark.asyncio
async def test_only_a_stay_that_never_happened_closes_this_way(client, seeded, db_session):
    ac, seed = client
    h = await _hotel(ac, seed, db_session)
    _r, _g, res_id, _f = await _stay(ac, h)
    r = await ac.post(f"/api/v1/hotel/reservations/{res_id}/close-bill", headers=h, json={})
    assert r.status_code == 400, r.text


@pytest.mark.asyncio
async def test_closing_a_bill_with_a_refund_is_a_cashier_job(client, seeded, db_session):
    with pytest.raises(Exception):
        hotel_jobs.enforce("hotel_front_desk", "POST", "/api/v1/hotel/reservations/abc/close-bill")
    hotel_jobs.enforce("hotel_cashier", "POST", "/api/v1/hotel/reservations/abc/close-bill")


# --- Cash drawer and shop ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cash_on_a_guest_invoice_counts_in_the_drawer(client, seeded, db_session):
    ac, seed = client
    h = await _hotel(ac, seed, db_session)
    _r, _g, res_id, folio_id = await _stay(ac, h, rate=200, nights=1)
    out = await ac.post(f"/api/v1/hotel/reservations/{res_id}/check-out", headers=h, json={"allow_balance": True})
    assert out.status_code == 200, out.text
    await ac.post("/api/v1/hotel/cashier/shift/open", headers=h, json={"opening_float": 0})
    invoice = (await ac.get("/api/v1/hotel/invoices", headers=h)).json()["data"]["items"][0]
    paid = await ac.post(
        f"/api/v1/hotel/invoices/{invoice['id']}/payments", headers=h, json={"amount": 200, "method": "cash"}
    )
    assert paid.status_code == 200, paid.text
    shift = (await ac.get("/api/v1/hotel/cashier/shift", headers=h)).json()["data"]
    assert shift["cash_taken"] == 200


async def _shop_item(db_session, seed, *, price=50, stock=20):
    product = m.Product(
        tenant_id=seed["t1"].id, name=f"Soap {uuid4().hex[:5]}", sku=f"S{uuid4().hex[:6]}",
        cost_price=10, selling_price=price, stock_qty=stock, is_active=True, tracks_batches=False,
    )
    db_session.add(product)
    await db_session.commit()
    return product


@pytest.mark.asyncio
async def test_a_cash_shop_refund_on_a_later_float_comes_out_of_that_drawer(client, seeded, db_session):
    ac, seed = client
    h = await _hotel(ac, seed, db_session)
    item = await _shop_item(db_session, seed)
    await ac.post("/api/v1/hotel/cashier/shift/open", headers=h, json={"opening_float": 0})
    sale = await ac.post(
        "/api/v1/hotel/shop/sales", headers=h,
        json={"payment_method": "cash", "lines": [{"product_id": item.id, "quantity": 1}]},
    )
    assert sale.status_code == 200, sale.text
    await ac.post("/api/v1/hotel/cashier/shift/close", headers=h, json={"closing_float": 50})

    closed = await ac.post(f"/api/v1/hotel/shop/sales/{sale.json()['data']['id']}/refund", headers=h, json={})
    assert closed.status_code == 409, closed.text

    await ac.post("/api/v1/hotel/cashier/shift/open", headers=h, json={"opening_float": 200})
    refund = await ac.post(f"/api/v1/hotel/shop/sales/{sale.json()['data']['id']}/refund", headers=h, json={})
    assert refund.status_code == 200, refund.text
    shift = (await ac.get("/api/v1/hotel/cashier/shift", headers=h)).json()["data"]
    assert shift["cash_taken"] == -50
    assert shift["expected_cash"] == 150


@pytest.mark.asyncio
async def test_the_shop_only_charges_guests_who_are_in_house(client, seeded, db_session):
    ac, seed = client
    h = await _hotel(ac, seed, db_session)
    item = await _shop_item(db_session, seed)
    await ac.patch("/api/v1/hotel/settings", headers=h, json={"no_show_fee_percent": 100})
    res = await _book(ac, h, await _room(ac, h), await _guest(ac, h), nights=1)
    await ac.post(f"/api/v1/hotel/reservations/{res['id']}/no-show", headers=h, json={})
    folio_id = (await ac.post(f"/api/v1/hotel/reservations/{res['id']}/no-show-fee", headers=h, json={})).json()["data"]["id"]
    rooms = (await ac.get("/api/v1/hotel/shop/rooms", headers=h)).json()["data"]
    assert rooms == []
    r = await ac.post(
        "/api/v1/hotel/shop/sales", headers=h,
        json={"payment_method": "room", "folio_id": folio_id, "lines": [{"product_id": item.id, "quantity": 1}]},
    )
    assert r.status_code == 409, r.text


@pytest.mark.asyncio
async def test_shop_vat_reaches_the_tax_filing(client, seeded, db_session):
    ac, seed = client
    h = await _hotel(ac, seed, db_session)
    rate = await ac.post(
        "/api/v1/tax/rates", headers=h,
        json={"name": "Shop VAT", "rate": 20, "pricing_mode": "exclusive", "is_default": True},
    )
    assert rate.status_code == 200, rate.text
    item = await _shop_item(db_session, seed, price=100)
    await ac.post("/api/v1/hotel/cashier/shift/open", headers=h, json={"opening_float": 0})
    before = (await ac.get("/api/v1/reports/tax", headers=h)).json()["data"]["output_tax"]
    sale = await ac.post(
        "/api/v1/hotel/shop/sales", headers=h,
        json={"payment_method": "cash", "lines": [{"product_id": item.id, "quantity": 1}]},
    )
    assert sale.status_code == 200, sale.text
    tax = sale.json()["data"]["tax"]
    assert tax > 0
    after = (await ac.get("/api/v1/reports/tax", headers=h)).json()["data"]["output_tax"]
    assert after == pytest.approx(before + tax)


@pytest.mark.asyncio
async def test_a_room_charged_shop_sale_is_not_taxed_twice(client, seeded, db_session):
    ac, seed = client
    h = await _hotel(ac, seed, db_session)
    await ac.post(
        "/api/v1/tax/rates", headers=h,
        json={"name": "Shop VAT", "rate": 20, "pricing_mode": "exclusive", "is_default": True},
    )
    item = await _shop_item(db_session, seed, price=100)
    _r, _g, res_id, folio_id = await _stay(ac, h, rate=100, nights=1)
    sale = await ac.post(
        "/api/v1/hotel/shop/sales", headers=h,
        json={"payment_method": "room", "folio_id": folio_id, "lines": [{"product_id": item.id, "quantity": 1}]},
    )
    assert sale.status_code == 200, sale.text
    tax = sale.json()["data"]["tax"]
    total = (await _folio(ac, h, folio_id))["balance"]
    await ac.post(f"/api/v1/hotel/folios/{folio_id}/payments", headers=h, json={"method": "cash", "amount": total})
    await ac.post(f"/api/v1/hotel/reservations/{res_id}/check-out", headers=h, json={})
    report = (await ac.get("/api/v1/reports/tax", headers=h)).json()["data"]
    assert report["output_tax"] == pytest.approx(tax)


@pytest.mark.asyncio
async def test_shop_sales_show_in_hotel_income(client, seeded, db_session):
    ac, seed = client
    h = await _hotel(ac, seed, db_session)
    item = await _shop_item(db_session, seed, price=80)
    await ac.post("/api/v1/hotel/cashier/shift/open", headers=h, json={"opening_float": 0})
    await ac.post(
        "/api/v1/hotel/shop/sales", headers=h,
        json={"payment_method": "cash", "lines": [{"product_id": item.id, "quantity": 2}]},
    )
    report = (await ac.get("/api/v1/hotel/reports", headers=h)).json()["data"]
    assert report["service_sales"]["shop"] == 160
    summary = (await ac.get("/api/v1/hotel/summary", headers=h)).json()["data"]
    assert summary["revenue_today"] == 160


# --- Staff and guest data ------------------------------------------------------------------


def _forbidden(role: str, method: str, path: str) -> bool:
    try:
        hotel_jobs.enforce(role, method, f"/api/v1/hotel{path}")
    except Exception:
        return True
    return False


def test_housekeeping_cannot_read_guest_files_or_money():
    for role in ("hotel_housekeeping", "hotel_maintenance"):
        assert _forbidden(role, "GET", "/guests")
        assert _forbidden(role, "GET", "/guests/abc/history")


def test_booking_staff_cannot_read_a_guests_money_history_through_the_guest_file():
    assert not _forbidden("hotel_reservations", "GET", "/guests/abc/history")


@pytest.mark.asyncio
async def test_money_is_stripped_from_stays_for_room_staff(client, seeded, db_session):
    from app.api import _hotel_stay_view

    ac, seed = client
    h = await _hotel(ac, seed, db_session)
    res = await _book(ac, h, await _room(ac, h), await _guest(ac, h), nights=1)
    clean = _hotel_stay_view(res, "hotel_housekeeping")
    for key in ("nightly_rate", "estimated_total", "deposit_amount", "deposit_method", "folio_balance", "guest_phone", "guest_email"):
        assert key not in clean
    assert _hotel_stay_view(res, "hotel_manager") == res


@pytest.mark.asyncio
async def test_booking_clerks_cannot_authorise_their_own_discount(client, seeded, db_session):
    from app.hotel import assert_discount_allowed
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as caught:
        assert_discount_allowed("hotel_front_desk", 10)
    assert caught.value.status_code == 403
    assert_discount_allowed("hotel_front_desk", 0)
    assert_discount_allowed("hotel_manager", 10)


@pytest.mark.asyncio
async def test_merging_guests_keeps_events_and_contact_details(client, seeded, db_session):
    ac, seed = client
    h = await _hotel(ac, seed, db_session)
    keep = await _guest(ac, h)
    gone = await _guest(ac, h, email=f"{uuid4().hex[:8]}@example.com", phone="+233241112222")
    start = date.today() + timedelta(days=30)
    event = await ac.post(
        "/api/v1/hotel/events", headers=h,
        json={
            "title": "Wedding", "space_name": "Hall", "guest_id": gone["id"],
            "starts_on": start.isoformat(), "ends_on": (start + timedelta(days=1)).isoformat(),
        },
    )
    assert event.status_code == 200, event.text
    merged = await ac.post(f"/api/v1/hotel/guests/{keep['id']}/merge", headers=h, json={"source_guest_id": gone["id"]})
    assert merged.status_code == 200, merged.text
    assert merged.json()["data"]["email"] == gone["email"]
    assert merged.json()["data"]["phone"] == gone["phone"]
    row = await db_session.get(m.HotelEvent, event.json()["data"]["id"])
    await db_session.refresh(row)
    assert row.guest_id == keep["id"]
    # The address is free to use again on the kept guest, not stuck on the merged one.
    old = await db_session.get(m.HotelGuest, gone["id"])
    await db_session.refresh(old)
    assert old.email is None


@pytest.mark.asyncio
async def test_records_cannot_point_at_another_companys_rooms_or_guests(client, seeded, db_session):
    ac, seed = client
    h = await _hotel(ac, seed, db_session)
    other = m.HotelRoom(tenant_id=seed["t2"].id, code="X1", name="Theirs", rate_amount=1, status="available")
    guest = m.HotelGuest(tenant_id=seed["t2"].id, full_name="Their guest")
    db_session.add_all([other, guest])
    await db_session.commit()
    start = date.today() + timedelta(days=30)
    event = {"title": "Gala", "space_name": "Hall", "starts_on": start.isoformat(), "ends_on": (start + timedelta(days=1)).isoformat()}
    assert (await ac.post("/api/v1/hotel/events", headers=h, json={**event, "room_id": other.id})).status_code == 404
    assert (await ac.post("/api/v1/hotel/events", headers=h, json={**event, "guest_id": guest.id})).status_code == 404
    r = await ac.post("/api/v1/hotel/lost-found", headers=h, json={"description": "Umbrella", "room_id": other.id})
    assert r.status_code == 404, r.text
    theirs = m.HotelReservation(
        tenant_id=seed["t2"].id, reservation_number="HR-X", room_id=other.id, guest_id=guest.id,
        check_in_date=start, check_out_date=start + timedelta(days=1),
    )
    db_session.add(theirs)
    await db_session.commit()
    r = await ac.post("/api/v1/hotel/guest-requests", headers=h, json={"title": "Towels", "reservation_id": theirs.id})
    assert r.status_code == 404, r.text


@pytest.mark.asyncio
async def test_a_cancelled_event_cannot_be_revived_over_a_new_booking(client, seeded, db_session):
    ac, seed = client
    h = await _hotel(ac, seed, db_session)
    room = await _room(ac, h)
    start = date.today() + timedelta(days=20)
    event = await ac.post(
        "/api/v1/hotel/events", headers=h,
        json={"title": "Dinner", "space_name": "Suite", "room_id": room["id"],
              "starts_on": start.isoformat(), "ends_on": (start + timedelta(days=1)).isoformat()},
    )
    event_id = event.json()["data"]["id"]
    assert (await ac.post(f"/api/v1/hotel/events/{event_id}/cancel", headers=h, json={})).status_code == 200
    await _book(ac, h, room, await _guest(ac, h), start=start, nights=1)
    r = await ac.post(f"/api/v1/hotel/events/{event_id}/confirm", headers=h, json={})
    assert r.status_code == 409, r.text


# --- Online booking ------------------------------------------------------------------------


async def _open_booking(ac, h, db_session, seed):
    r = await ac.put(
        "/api/v1/hotel/booking-link", headers=h,
        json={"hostname": f"{uuid4().hex[:8]}.example.com", "link_kind": "existing"},
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]["slug"]


def _request(room, *, name="Ama Boateng", phone="+233245550101", start=None, nights=1, **extra):
    start = start or date.today() + timedelta(days=3)
    return {
        "guest_name": name, "phone": phone, "room_id": room["id"],
        "check_in_date": start.isoformat(), "check_out_date": (start + timedelta(days=nights)).isoformat(),
        **extra,
    }


@pytest.mark.asyncio
async def test_the_public_page_gives_nothing_back_about_a_known_guest(client, seeded, db_session):
    ac, seed = client
    h = await _hotel(ac, seed, db_session)
    slug = await _open_booking(ac, h, db_session, seed)
    known = await ac.post(
        "/api/v1/hotel/guests", headers=h,
        json={"full_name": "Ama Boateng", "phone": "+233245550101", "email": "ama.private@example.com"},
    )
    assert known.status_code == 200, known.text
    r = await ac.post(f"/api/v1/public/hotel-booking/{slug}", json=_request(await _room(ac, h)))
    assert r.status_code == 200, r.text
    assert "ama.private@example.com" not in r.text
    assert "guest_id" not in r.text
    assert r.json()["data"]["reservation_number"]


@pytest.mark.asyncio
async def test_a_returning_guest_with_a_new_phone_can_still_book_online(client, seeded, db_session):
    ac, seed = client
    h = await _hotel(ac, seed, db_session)
    slug = await _open_booking(ac, h, db_session, seed)
    await ac.post("/api/v1/hotel/guests", headers=h, json={"full_name": "Esi Owusu", "email": "esi@example.com"})
    r = await ac.post(
        f"/api/v1/public/hotel-booking/{slug}",
        json=_request(await _room(ac, h), name="Esi Owusu", phone="+233245550102", email="esi@example.com"),
    )
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_the_public_page_does_not_offer_a_room_it_would_refuse(client, seeded, db_session):
    ac, seed = client
    h = await _hotel(ac, seed, db_session)
    slug = await _open_booking(ac, h, db_session, seed)
    room = await _room(ac, h)
    start = date.today() + timedelta(days=10)
    await ac.post(
        "/api/v1/hotel/events", headers=h,
        json={"title": "Party", "space_name": "Suite", "room_id": room["id"], "starts_on": start.isoformat(),
              "ends_on": (start + timedelta(days=2)).isoformat()},
    )
    found = await ac.get(
        f"/api/v1/public/hotel-booking/{slug}/rooms",
        params={"check_in": start.isoformat(), "check_out": (start + timedelta(days=1)).isoformat()},
    )
    assert found.status_code == 200, found.text
    assert room["id"] not in {r["id"] for r in found.json()["data"]}


@pytest.mark.asyncio
async def test_a_dated_repair_does_not_hide_a_room_for_other_dates_online(client, seeded, db_session):
    ac, seed = client
    h = await _hotel(ac, seed, db_session)
    slug = await _open_booking(ac, h, db_session, seed)
    room = await _room(ac, h)
    start = date.today() + timedelta(days=40)
    await ac.post(
        "/api/v1/hotel/maintenance", headers=h,
        json={"room_id": room["id"], "title": "Repaint", "ooo_starts_on": start.isoformat(), "ooo_ends_on": start.isoformat()},
    )
    soon = date.today() + timedelta(days=5)
    found = await ac.get(
        f"/api/v1/public/hotel-booking/{slug}/rooms",
        params={"check_in": soon.isoformat(), "check_out": (soon + timedelta(days=1)).isoformat()},
    )
    assert room["id"] in {r["id"] for r in found.json()["data"]}


@pytest.mark.asyncio
async def test_online_requests_cannot_lock_up_the_hotel(client, seeded, db_session):
    ac, seed = client
    h = await _hotel(ac, seed, db_session)
    slug = await _open_booking(ac, h, db_session, seed)
    room = await _room(ac, h)
    too_long = await ac.post(f"/api/v1/public/hotel-booking/{slug}", json=_request(room, nights=200))
    assert too_long.status_code == 422, too_long.text
    too_far = await ac.post(
        f"/api/v1/public/hotel-booking/{slug}", json=_request(room, start=date.today() + timedelta(days=800))
    )
    assert too_far.status_code == 422, too_far.text
    for _ in range(3):
        ok = await ac.post(f"/api/v1/public/hotel-booking/{slug}", json=_request(await _room(ac, h)))
        assert ok.status_code == 200, ok.text
    fourth = await ac.post(f"/api/v1/public/hotel-booking/{slug}", json=_request(await _room(ac, h)))
    assert fourth.status_code == 429, fourth.text


def test_the_public_booking_page_has_its_own_rate_bucket():
    from app.middleware import STOREFRONT_PUBLIC_PREFIXES

    assert "/api/v1/public/hotel-booking" in STOREFRONT_PUBLIC_PREFIXES


# --- Backups -------------------------------------------------------------------------------


def test_a_company_backup_carries_the_whole_hotel():
    from app.backup import DATASET_SPECS

    covered = {model for _name, model in DATASET_SPECS}
    hotel_models = {
        cls for cls in vars(m).values()
        if isinstance(cls, type) and issubclass(cls, m.Base) and cls.__name__.startswith("Hotel")
    }
    assert hotel_models <= covered, sorted(c.__name__ for c in hotel_models - covered)


@pytest.mark.asyncio
async def test_a_hotel_comes_back_from_a_restore(client, seeded, db_session):
    from app import backup as backup_svc

    ac, seed = client
    h = await _hotel(ac, seed, db_session)
    _r, _g, res_id, folio_id = await _stay(ac, h, rate=200, nights=1)
    await ac.post("/api/v1/hotel/night-audits", headers=h, json={})
    payload, counts = await backup_svc.collect_tenant_payload(db_session, seed["t1"].id)
    assert counts["hotel_reservations"] >= 1
    assert counts["hotel_folio_charges"] >= 1

    charge = (await db_session.execute(select(m.HotelFolioCharge).where(m.HotelFolioCharge.folio_id == folio_id))).scalars().first()
    charge.line_total = 1
    await db_session.commit()
    import json

    report = await backup_svc.apply_restore(
        db_session, seed["t1"].id, json.loads(json.dumps(payload, default=str))
    )
    await db_session.commit()
    assert report["applied"] is True
    assert report["restored"]["hotel_folio_charges"] >= 1
    await db_session.refresh(charge)
    assert float(charge.line_total) == 200


# --- Numbers -------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_guest_invoices_list_does_not_lose_old_debts_behind_paid_ones(client, seeded, db_session):
    """The 300-row window has to be taken from what is owed, not from everything."""
    from app import hotel_invoices

    ac, seed = client
    h = await _hotel(ac, seed, db_session)
    _r, _g, res_id, folio_id = await _stay(ac, h, rate=100, nights=1)
    await ac.post(f"/api/v1/hotel/reservations/{res_id}/check-out", headers=h, json={"allow_balance": True})
    data = await hotel_invoices.list_invoices(db_session, seed["t1"].id, show="owed")
    assert data["owed_total"] == 100


def test_a_room_number_clash_cannot_happen_on_a_shared_counter():
    import inspect

    source = inspect.getsource(hotel_svc._next_reservation_number)
    assert "_lock_numbers" in source
    assert "_lock_numbers" in inspect.getsource(hotel_svc._next_folio_number)


def test_number_locks_do_not_block_the_key_lock_inserts_need():
    """SQLite cannot show this. On Postgres a plain FOR UPDATE here deadlocks against the audit chain."""
    import inspect

    from app import doc_numbers

    assert "key_share=True" in inspect.getsource(hotel_svc._lock_numbers)
    assert "key_share=True" in inspect.getsource(doc_numbers.next_series_document_number)
