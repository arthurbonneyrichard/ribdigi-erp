"""Hotel work of 15 Nov 2026: nightly room revenue, VAT on discounts, clean-room check-in, booking-site
calendars (iCal), city ledger, online hold expiry, custom roles doing their hotel job, event deposits."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from app import hotel as hotel_svc
from app import hotel_channels
from app import hotel_jobs
from app import models as m
from tests.conftest import set_tenant_industry
from tests.test_hotel_folio_books import _admin, _balances, _moved, _pay, _stay


async def _hotel(ac, seed, db_session):
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    return await _admin(ac, seed)


async def _folio(db_session, folio_id: str) -> m.HotelFolio:
    return (await db_session.execute(select(m.HotelFolio).where(m.HotelFolio.id == folio_id))).scalar_one()


@pytest.mark.asyncio
async def test_room_revenue_is_earned_one_night_at_a_time(client, seeded, db_session):
    ac, seed = client
    h = await _hotel(ac, seed, db_session)
    before = await _balances(ac, h)
    res_id, folio_id = await _stay(ac, h, rate=300, nights=3)
    tenant_id = seed["t1"].id

    books = await _balances(ac, h)
    assert _moved(before, books, "2165") == -900  # sold, not yet earned
    assert _moved(before, books, "4000") == 0

    folio = await _folio(db_session, folio_id)
    today = date.today()
    await hotel_svc.recognise_open_stays(db_session, tenant_id=tenant_id, through=today)
    await db_session.commit()
    assert _moved(before, await _balances(ac, h), "4000") == -300  # first night
    # Running it again for the same night moves nothing.
    assert await hotel_svc.recognise_room_revenue(db_session, tenant_id=tenant_id, folio=folio, through=today) == 0
    await hotel_svc.recognise_open_stays(db_session, tenant_id=tenant_id, through=today + timedelta(days=1))
    await db_session.commit()
    assert _moved(before, await _balances(ac, h), "4000") == -600

    await _pay(ac, h, folio_id, 900)
    out = await ac.post(f"/api/v1/hotel/reservations/{res_id}/check-out", headers=h, json={})
    assert out.status_code == 200, out.text
    after = await _balances(ac, h)
    assert _moved(before, after, "4000") == -900  # the rest is earned at check-out
    assert _moved(before, after, "2165") == 0


@pytest.mark.asyncio
async def test_night_audit_earns_tonight(client, seeded, db_session):
    ac, seed = client
    h = await _hotel(ac, seed, db_session)
    before = await _balances(ac, h)
    await _stay(ac, h, rate=200, nights=2)
    audit = await ac.post("/api/v1/hotel/night-audits", headers=h, json={})
    assert audit.status_code == 200, audit.text
    assert audit.json()["data"]["snapshot"]["room_revenue_earned"]["amount"] >= 200
    assert _moved(before, await _balances(ac, h), "4000") == -200


@pytest.mark.asyncio
async def test_a_discount_takes_its_share_of_vat_off(client, seeded, db_session):
    ac, seed = client
    h = await _hotel(ac, seed, db_session)
    await ac.patch("/api/v1/hotel/settings", headers=h, json={"tax_percent": 25})
    _res_id, folio_id = await _stay(ac, h, rate=1000, nights=1)
    before = await _balances(ac, h)
    disc = await ac.post(
        f"/api/v1/hotel/folios/{folio_id}/charges",
        headers=h,
        json={"charge_type": "discount", "description": "Loyal guest", "unit_amount": 100},
    )
    assert disc.status_code == 200, disc.text
    books = await _balances(ac, h)
    assert _moved(before, books, "2100") == 20  # 20% of the bill is tax, so 20 of the 100
    assert _moved(before, books, "4000") == 80
    assert _moved(before, books, "1100") == -100


@pytest.mark.asyncio
async def test_check_in_needs_a_clean_room_unless_a_manager_says_so(client, seeded, db_session):
    ac, seed = client
    h = await _hotel(ac, seed, db_session)
    suffix = uuid4().hex[:6]
    room = (await ac.post("/api/v1/hotel/rooms", headers=h, json={"code": f"D{suffix}", "name": "Dirty", "rate_amount": 100})).json()["data"]
    guest = (await ac.post("/api/v1/hotel/guests", headers=h, json={"full_name": f"Clean Test {suffix}"})).json()["data"]
    start = date.today()
    booked = await ac.post(
        "/api/v1/hotel/reservations",
        headers=h,
        json={"room_id": room["id"], "guest_id": guest["id"], "check_in_date": start.isoformat(), "check_out_date": (start + timedelta(days=1)).isoformat()},
    )
    assert booked.status_code == 200, booked.text
    row = (await db_session.execute(select(m.HotelRoom).where(m.HotelRoom.id == room["id"]))).scalar_one()
    row.housekeeping_status = "dirty"
    await db_session.commit()
    stay_id = booked.json()["data"]["id"]
    refused = await ac.post(f"/api/v1/hotel/reservations/{stay_id}/check-in", headers=h, json={})
    assert refused.status_code == 409
    assert refused.json()["detail"]["code"] == "ROOM_NOT_CLEAN"
    ok = await ac.post(f"/api/v1/hotel/reservations/{stay_id}/check-in?allow_dirty=true", headers=h, json={})
    assert ok.status_code == 200, ok.text


def test_booking_site_calendar_is_read():
    text = (
        "BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\nUID:abc-1@booking.com\r\nDTSTART;VALUE=DATE:20270105\r\n"
        "DTEND;VALUE=DATE:20270108\r\nSUMMARY:CLOSED - Not\r\n available\r\nEND:VEVENT\r\n"
        "BEGIN:VEVENT\r\nUID:gone@x\r\nDTSTART:20270110\r\nDTEND:20270111\r\nSTATUS:CANCELLED\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"
    )
    events = hotel_channels.parse_calendar(text)
    assert events == [
        {"uid": "abc-1@booking.com", "start": date(2027, 1, 5), "end": date(2027, 1, 8), "summary": "CLOSED - Notavailable"}
    ]


@pytest.mark.asyncio
async def test_booking_site_bookings_close_the_room_and_ours_are_published(client, seeded, db_session):
    ac, seed = client
    h = await _hotel(ac, seed, db_session)
    suffix = uuid4().hex[:6]
    room = (await ac.post("/api/v1/hotel/rooms", headers=h, json={"code": f"C{suffix}", "name": "Channel", "rate_amount": 150})).json()["data"]
    feed = await ac.post("/api/v1/hotel/channels", headers=h, json={"room_id": room["id"], "channel": "booking_com"})
    assert feed.status_code == 200, feed.text
    feed = feed.json()["data"]

    start = date.today() + timedelta(days=10)
    end = start + timedelta(days=2)
    cal = (
        "BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\nUID:bk-777\r\n"
        f"DTSTART;VALUE=DATE:{start:%Y%m%d}\r\nDTEND;VALUE=DATE:{end:%Y%m%d}\r\nSUMMARY:Reserved\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"
    )
    row = (await db_session.execute(select(m.HotelChannelFeed).where(m.HotelChannelFeed.id == feed["id"]))).scalar_one()
    first = await hotel_channels.sync_feed(db_session, tenant_id=seed["t1"].id, feed=row, text=cal)
    await db_session.commit()
    assert first["added"] == 1 and not first["clashes"]
    again = await hotel_channels.sync_feed(db_session, tenant_id=seed["t1"].id, feed=row, text=cal)
    assert again["added"] == 0  # the same booking is not added twice
    stay = (
        await db_session.execute(select(m.HotelReservation).where(m.HotelReservation.channel_uid == "bk-777"))
    ).scalar_one()
    assert stay.booking_source == "ota" and stay.status == "booked"

    # Our own direct booking on the same room goes out on our calendar; the site's own does not come back.
    guest = (await ac.post("/api/v1/hotel/guests", headers=h, json={"full_name": f"Direct {suffix}"})).json()["data"]
    direct_in = start + timedelta(days=5)
    made = await ac.post(
        "/api/v1/hotel/reservations",
        headers=h,
        json={"room_id": room["id"], "guest_id": guest["id"], "check_in_date": direct_in.isoformat(), "check_out_date": (direct_in + timedelta(days=1)).isoformat()},
    )
    assert made.status_code == 200, made.text
    ics = await ac.get(feed["export_path"])
    assert ics.status_code == 200
    assert ics.headers["content-type"].startswith("text/calendar")
    assert f"DTSTART;VALUE=DATE:{direct_in:%Y%m%d}" in ics.text
    assert f"DTSTART;VALUE=DATE:{start:%Y%m%d}" not in ics.text
    assert guest["full_name"] not in ics.text  # dates only, no guest names

    # The site cancels: the booking disappears from its calendar, so the room frees up here.
    gone = await hotel_channels.sync_feed(
        db_session, tenant_id=seed["t1"].id, feed=row, text="BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n"
    )
    await db_session.commit()
    assert gone["cancelled"] == 1
    await db_session.refresh(stay)
    assert stay.status == "cancelled"


@pytest.mark.asyncio
async def test_city_ledger_stay_is_invoiced_to_the_company(client, seeded, db_session):
    ac, seed = client
    h = await _hotel(ac, seed, db_session)
    company = await ac.post("/api/v1/hotel/companies", headers=h, json={"name": f"Acme Mining {uuid4().hex[:4]}"})
    assert company.status_code == 200, company.text
    company = company.json()["data"]
    res_id, folio_id = await _stay(ac, h, rate=400, nights=1)
    billed = await ac.post(f"/api/v1/hotel/reservations/{res_id}/bill-to", headers=h, json={"party_id": company["id"]})
    assert billed.status_code == 200, billed.text
    assert billed.json()["data"]["bill_to_party_id"] == company["id"]
    out = await ac.post(f"/api/v1/hotel/reservations/{res_id}/check-out", headers=h, json={"allow_balance": True})
    assert out.status_code == 200, out.text
    folio = await _folio(db_session, folio_id)
    invoice = (await db_session.execute(select(m.SalesInvoice).where(m.SalesInvoice.id == folio.sales_invoice_id))).scalar_one()
    assert invoice.customer_id == company["id"]
    ledger = (await ac.get("/api/v1/hotel/city-ledger", headers=h)).json()["data"]
    assert any(a["party_id"] == company["id"] and a["owed"] == 400 for a in ledger)
    invoices = (await ac.get("/api/v1/hotel/invoices", headers=h)).json()["data"]["items"]
    assert any(i["company_name"] == company["name"] and i["billed_to_company"] for i in invoices)


@pytest.mark.asyncio
async def test_unconfirmed_online_requests_let_the_room_go(client, seeded, db_session):
    ac, seed = client
    h = await _hotel(ac, seed, db_session)
    suffix = uuid4().hex[:6]
    room = (await ac.post("/api/v1/hotel/rooms", headers=h, json={"code": f"O{suffix}", "name": "Online", "rate_amount": 90})).json()["data"]
    guest = (await ac.post("/api/v1/hotel/guests", headers=h, json={"full_name": f"Web {suffix}"})).json()["data"]
    start = date.today() + timedelta(days=3)
    made = await ac.post(
        "/api/v1/hotel/reservations",
        headers=h,
        json={"room_id": room["id"], "guest_id": guest["id"], "check_in_date": start.isoformat(), "check_out_date": (start + timedelta(days=1)).isoformat(), "status": "tentative", "booking_source": "online"},
    )
    assert made.status_code == 200, made.text
    tenant_id = seed["t1"].id
    assert await hotel_svc.expire_online_holds(db_session, tenant_id=tenant_id) == 0  # still fresh
    later = datetime.utcnow() + timedelta(hours=hotel_svc.ONLINE_HOLD_HOURS + 1)
    assert await hotel_svc.expire_online_holds(db_session, tenant_id=tenant_id, now=later) == 1
    stay = (await db_session.execute(select(m.HotelReservation).where(m.HotelReservation.id == made.json()["data"]["id"]))).scalar_one()
    assert stay.status == "cancelled"
    assert "expired" in (stay.notes or "")


@pytest.mark.asyncio
async def test_custom_role_copied_from_housekeeping_keeps_the_housekeeping_job(db_session, seeded):
    seed = seeded
    tenant_id = seed["t1"].id
    db_session.add(
        m.CustomRole(tenant_id=tenant_id, key="night_cleaner", label="Night cleaner", base_role="hotel_housekeeping", permissions={"hotel": ["read", "write"]})
    )
    await db_session.flush()
    job = await hotel_jobs.job_role(db_session, tenant_id, "night_cleaner")
    assert job == "hotel_housekeeping"
    from fastapi import HTTPException

    with pytest.raises(HTTPException):
        hotel_jobs.enforce(job, "POST", "/api/v1/hotel/folios/f1/payments")


@pytest.mark.asyncio
async def test_event_deposit_reaches_the_books_when_taken(client, seeded, db_session):
    ac, seed = client
    h = await _hotel(ac, seed, db_session)
    before = await _balances(ac, h)
    start = date.today() + timedelta(days=20)
    event = await ac.post(
        "/api/v1/hotel/events",
        headers=h,
        json={"title": "Wedding lunch", "space_name": "Garden", "starts_on": start.isoformat(), "ends_on": (start + timedelta(days=1)).isoformat(), "deposit_amount": 500},
    )
    assert event.status_code == 200, event.text
    books = await _balances(ac, h)
    assert _moved(before, books, "1000") == 500
    assert _moved(before, books, "1100") == -500
