"""A hotel stay reaches the books: revenue, tax, cash and receivables stay in step with the folio."""

from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

import pyotp
import pytest
from fastapi import HTTPException

from app import hotel_jobs
from tests.conftest import auth_headers, set_tenant_industry


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code)


async def _stay(ac, h, *, rate=500, nights=2, guest="Books Guest"):
    suffix = uuid4().hex[:6]
    room = await ac.post(
        "/api/v1/hotel/rooms", headers=h, json={"code": f"B{suffix}", "name": f"Room {suffix}", "rate_amount": rate}
    )
    assert room.status_code == 200, room.text
    who = await ac.post("/api/v1/hotel/guests", headers=h, json={"full_name": f"{guest} {suffix}"})
    start = date.today()
    booked = await ac.post(
        "/api/v1/hotel/reservations",
        headers=h,
        json={
            "room_id": room.json()["data"]["id"],
            "guest_id": who.json()["data"]["id"],
            "check_in_date": start.isoformat(),
            "check_out_date": (start + timedelta(days=nights)).isoformat(),
            "adults": 1,
        },
    )
    assert booked.status_code == 200, booked.text
    res_id = booked.json()["data"]["id"]
    inn = await ac.post(f"/api/v1/hotel/reservations/{res_id}/check-in", headers=h, json={})
    assert inn.status_code == 200, inn.text
    return res_id, inn.json()["data"]["folio_id"]


async def _balances(ac, h) -> dict[str, float]:
    tb = await ac.get("/api/v1/accounting/trial-balance", headers=h)
    assert tb.status_code == 200, tb.text
    data = tb.json()["data"]
    assert data["total_debit"] == pytest.approx(data["total_credit"])
    rows = data.get("rows") or data.get("accounts") or []
    return {r["code"]: round(float(r.get("debit") or 0) - float(r.get("credit") or 0), 2) for r in rows}


def _moved(before: dict, after: dict, code: str) -> float:
    return round(after.get(code, 0) - before.get(code, 0), 2)


async def _pay(ac, h, folio_id, amount, method="cash"):
    r = await ac.post(
        f"/api/v1/hotel/folios/{folio_id}/payments", headers=h, json={"method": method, "amount": amount}
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]


@pytest.mark.asyncio
async def test_paid_stay_lands_in_revenue_tax_and_cash(client, seeded, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    h = await _admin(ac, seed)
    await ac.patch("/api/v1/hotel/settings", headers=h, json={"tax_percent": 25})
    before = await _balances(ac, h)
    res_id, folio_id = await _stay(ac, h)

    folio = (await ac.get(f"/api/v1/hotel/folios/{folio_id}", headers=h)).json()["data"]
    assert folio["charges_total"] == 1000  # the quoted rate is what the guest pays
    assert folio["charges"][0]["tax_amount"] == 200  # tax sits inside it

    mid = await _balances(ac, h)
    assert _moved(before, mid, "1100") == 1000
    assert _moved(before, mid, "4000") == -800
    assert _moved(before, mid, "2100") == -200

    await _pay(ac, h, folio_id, 1000)
    out = await ac.post(f"/api/v1/hotel/reservations/{res_id}/check-out", headers=h, json={})
    assert out.status_code == 200, out.text
    after = await _balances(ac, h)
    assert _moved(before, after, "1100") == 0
    assert _moved(before, after, "1000") == 1000
    assert _moved(before, after, "4000") == -800

    closed = (await ac.get(f"/api/v1/hotel/folios/{folio_id}", headers=h)).json()["data"]
    invoice = (await ac.get(f"/api/v1/sales/invoices/{closed['sales_invoice_id']}", headers=h)).json()["data"]
    assert invoice["total_amount"] == 1000
    assert invoice["tax_amount"] == 200
    assert invoice["subtotal"] == 800


@pytest.mark.asyncio
async def test_tax_can_be_added_on_top_of_the_rate(client, seeded, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    h = await _admin(ac, seed)
    r = await ac.patch(
        "/api/v1/hotel/settings", headers=h, json={"tax_percent": 10, "room_rates_include_tax": False}
    )
    assert r.json()["data"]["room_rates_include_tax"] is False
    _res, folio_id = await _stay(ac, h)
    folio = (await ac.get(f"/api/v1/hotel/folios/{folio_id}", headers=h)).json()["data"]
    assert folio["charges_total"] == 1100
    assert folio["charges"][0]["tax_amount"] == 100


@pytest.mark.asyncio
async def test_void_reverses_and_transfer_leaves_the_books_alone(client, seeded, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    h = await _admin(ac, seed)
    _r1, folio_a = await _stay(ac, h)
    _r2, folio_b = await _stay(ac, h)
    before = await _balances(ac, h)
    charge = await ac.post(
        f"/api/v1/hotel/folios/{folio_a}/charges",
        headers=h,
        json={"charge_type": "extra", "description": "Minibar", "quantity": 1, "unit_amount": 80},
    )
    assert charge.status_code == 200, charge.text
    folio = (await ac.get(f"/api/v1/hotel/folios/{folio_a}", headers=h)).json()["data"]
    extra = [c for c in folio["charges"] if c["description"] == "Minibar"][0]
    assert _moved(before, await _balances(ac, h), "4000") == -80

    moved = await ac.post(
        f"/api/v1/hotel/folios/{folio_a}/charges/{extra['id']}/transfer",
        headers=h,
        json={"target_folio_id": folio_b},
    )
    assert moved.status_code == 200, moved.text
    assert _moved(before, await _balances(ac, h), "4000") == -80

    folio = (await ac.get(f"/api/v1/hotel/folios/{folio_b}", headers=h)).json()["data"]
    landed = [c for c in folio["charges"] if "Minibar" in c["description"] and not c["is_void"]][0]
    voided = await ac.post(
        f"/api/v1/hotel/folios/{folio_b}/charges/{landed['id']}/void",
        headers=h,
        json={"void_reason": "Guest did not use it"},
    )
    assert voided.status_code == 200, voided.text
    assert _moved(before, await _balances(ac, h), "4000") == 0


@pytest.mark.asyncio
async def test_refund_gives_money_back_once_and_credit_blocks_checkout(client, seeded, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    h = await _admin(ac, seed)
    res_id, folio_id = await _stay(ac, h)
    before = await _balances(ac, h)
    folio = await _pay(ac, h, folio_id, 1200)
    assert folio["balance"] == -200

    blocked = await ac.post(f"/api/v1/hotel/reservations/{res_id}/check-out", headers=h, json={})
    assert blocked.status_code == 400
    assert "credit" in blocked.json()["detail"]

    payment = folio["payments"][0]["id"]
    url = f"/api/v1/hotel/folios/{folio_id}/payments/{payment}/refund"
    too_much = await ac.post(url, headers=h, json={"amount": 1300, "reason": "Typed the wrong amount"})
    assert too_much.status_code == 422
    done = await ac.post(url, headers=h, json={"amount": 200, "reason": "Typed the wrong amount"})
    assert done.status_code == 200, done.text
    assert done.json()["data"]["balance"] == 0
    assert _moved(before, await _balances(ac, h), "1000") == 1000

    out = await ac.post(f"/api/v1/hotel/reservations/{res_id}/check-out", headers=h, json={})
    assert out.status_code == 200, out.text


@pytest.mark.asyncio
async def test_on_account_stays_owed_until_the_invoice_is_paid(client, seeded, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    h = await _admin(ac, seed)
    before = await _balances(ac, h)
    res_id, folio_id = await _stay(ac, h)
    await _pay(ac, h, folio_id, 1000, method="credit")
    out = await ac.post(f"/api/v1/hotel/reservations/{res_id}/check-out", headers=h, json={})
    assert out.status_code == 200, out.text
    assert _moved(before, await _balances(ac, h), "1100") == 1000

    closed = (await ac.get(f"/api/v1/hotel/folios/{folio_id}", headers=h)).json()["data"]
    invoice_id = closed["sales_invoice_id"]
    paid = await ac.post(
        f"/api/v1/hotel/invoices/{invoice_id}/payments", headers=h, json={"amount": 1000, "method": "cash"}
    )
    assert paid.status_code == 200, paid.text
    assert paid.json()["data"]["due"] == 0
    after = await _balances(ac, h)
    assert _moved(before, after, "1100") == 0
    assert _moved(before, after, "1000") == 1000


@pytest.mark.asyncio
async def test_each_night_is_charged_at_its_own_rate(client, seeded, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    h = await _admin(ac, seed)
    suffix = uuid4().hex[:6]
    room = await ac.post(
        "/api/v1/hotel/rooms",
        headers=h,
        json={"code": f"W{suffix}", "name": f"Room {suffix}", "rate_amount": 100, "weekend_rate": 200},
    )
    who = await ac.post("/api/v1/hotel/guests", headers=h, json={"full_name": f"Week Guest {suffix}"})
    today = date.today()
    monday = today + timedelta(days=(7 - today.weekday()) or 7)
    booked = await ac.post(
        "/api/v1/hotel/reservations",
        headers=h,
        json={
            "room_id": room.json()["data"]["id"],
            "guest_id": who.json()["data"]["id"],
            "check_in_date": monday.isoformat(),
            "check_out_date": (monday + timedelta(days=7)).isoformat(),
            "adults": 1,
        },
    )
    assert booked.status_code == 200, booked.text
    # Five weeknights at 100 and Saturday and Sunday at 200, not seven nights at 200.
    assert booked.json()["data"]["estimated_total"] == pytest.approx(900, abs=0.05)


@pytest.mark.asyncio
async def test_float_close_shows_what_the_drawer_should_hold(client, seeded, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    h = await _admin(ac, seed)
    _res, folio_id = await _stay(ac, h)
    opened = await ac.post("/api/v1/hotel/cashier/shift/open", headers=h, json={"opening_float": 100})
    assert opened.status_code == 200, opened.text
    await _pay(ac, h, folio_id, 300)
    await _pay(ac, h, folio_id, 200, method="card")  # a card payment never reaches the drawer
    live = (await ac.get("/api/v1/hotel/cashier/shift", headers=h)).json()["data"]
    assert live["cash_taken"] == 300
    assert live["expected_cash"] == 400
    closed = await ac.post("/api/v1/hotel/cashier/shift/close", headers=h, json={"closing_float": 390})
    assert closed.status_code == 200, closed.text
    assert closed.json()["data"]["expected_cash"] == 400
    assert closed.json()["data"]["over_short"] == -10


@pytest.mark.parametrize(
    "role, method, path, allowed",
    [
        ("hotel_housekeeping", "POST", "/hotel/housekeeping/t1/complete", True),
        ("hotel_housekeeping", "POST", "/hotel/folios/f1/payments", False),
        ("hotel_housekeeping", "POST", "/hotel/folios/f1/charges", False),
        ("hotel_housekeeping", "PATCH", "/hotel/settings", False),
        ("hotel_housekeeping", "GET", "/hotel/rooms", True),
        ("hotel_housekeeping", "GET", "/hotel/folios", False),
        ("hotel_housekeeping", "GET", "/hotel/reports", False),
        ("hotel_maintenance", "POST", "/hotel/maintenance/t1/complete", True),
        ("hotel_maintenance", "POST", "/hotel/reservations/r1/check-in", False),
        ("hotel_reservations", "POST", "/hotel/reservations", True),
        ("hotel_reservations", "POST", "/hotel/reservations/r1/check-in", False),
        ("hotel_reservations", "POST", "/hotel/folios/f1/payments", False),
        ("hotel_front_desk", "POST", "/hotel/reservations/r1/check-out", True),
        ("hotel_front_desk", "POST", "/hotel/folios/f1/payments", True),
        ("hotel_front_desk", "POST", "/hotel/folios/f1/payments/p1/refund", False),
        ("hotel_front_desk", "POST", "/hotel/folios/f1/charges/c1/void", False),
        ("hotel_front_desk", "PATCH", "/hotel/settings", False),
        ("hotel_front_desk", "POST", "/hotel/rooms", False),
        ("hotel_cashier", "POST", "/hotel/folios/f1/payments/p1/refund", True),
        ("hotel_cashier", "POST", "/hotel/night-audits", True),
        ("hotel_cashier", "POST", "/hotel/rooms", False),
        ("hotel_manager", "PATCH", "/hotel/settings", True),
        ("company_admin", "POST", "/hotel/folios/f1/payments/p1/refund", True),
    ],
)
def test_each_hotel_role_does_its_own_job(role, method, path, allowed):
    url = f"/api/v1{path}"
    if allowed:
        hotel_jobs.enforce(role, method, url)
        return
    with pytest.raises(HTTPException) as refused:
        hotel_jobs.enforce(role, method, url)
    assert refused.value.status_code == 403
    assert refused.value.detail["code"] == "HOTEL_ROLE_JOB"


@pytest.mark.asyncio
async def test_leaving_early_takes_unused_nights_off_the_bill_and_the_books(client, seeded, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    h = await _admin(ac, seed)
    before = await _balances(ac, h)
    res_id, folio_id = await _stay(ac, h, rate=100, nights=4)
    left = await ac.post(f"/api/v1/hotel/reservations/{res_id}/leave-early", headers=h, json={})
    assert left.status_code == 200, left.text
    assert left.json()["data"]["check_out_date"] == (date.today() + timedelta(days=1)).isoformat()

    folio = (await ac.get(f"/api/v1/hotel/folios/{folio_id}", headers=h)).json()["data"]
    assert folio["charges_total"] == 100  # one night stayed, three taken off
    assert _moved(before, await _balances(ac, h), "4000") == -100

    again = await ac.post(f"/api/v1/hotel/reservations/{res_id}/leave-early", headers=h, json={})
    assert again.status_code == 400
