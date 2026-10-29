"""Hotel commercial stay fixture: 2 nights × 250 = 500.

Settings tax is stored and is not added to the room folio line.
Checkout writes a sales invoice from the folio. A retail tenant is refused.
"""

from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

import pyotp
import pytest

from tests.conftest import auth_headers, set_tenant_industry


async def _hotel_admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_hotel_commercial_stay_reconciles_folio_invoice_and_onboarding(client, seeded, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    admin = await _hotel_admin(ac, seed)
    suffix = uuid4().hex[:6]
    check_in = date.today() + timedelta(days=1)
    check_out = check_in + timedelta(days=2)
    last_night = check_out - timedelta(days=1)

    tax = await ac.patch(
        "/api/v1/hotel/settings",
        headers=admin,
        json={"tax_percent": 5, "early_checkin_fee": 40, "late_checkout_fee": 25},
    )
    assert tax.status_code == 200, tax.text
    assert tax.json()["data"]["tax_percent"] == 5

    before = await ac.get("/api/v1/onboarding/checklist", headers=admin)
    assert before.status_code == 200, before.text
    before_steps = {s["id"]: s for s in before.json()["data"]["steps"]}
    assert before_steps["add_products"]["title"] == "Add rooms"
    assert before_steps["first_sale"]["title"] == "Check in a guest"
    assert before_steps["first_sale"]["auto_completed"] is False

    room = await ac.post(
        "/api/v1/hotel/rooms",
        headers=admin,
        json={"code": f"C{suffix}", "name": "Commercial 101", "rate_amount": 250},
    )
    assert room.status_code == 200, room.text
    guest = await ac.post(
        "/api/v1/hotel/guests",
        headers=admin,
        json={"full_name": f"Stay Guest {suffix}"},
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
            "status": "booked",
        },
    )
    assert booked.status_code == 200, booked.text
    assert booked.json()["data"]["nights"] == 2
    assert booked.json()["data"]["estimated_total"] == 500
    res_id = booked.json()["data"]["id"]

    mid = await ac.get("/api/v1/onboarding/checklist", headers=admin)
    mid_steps = {s["id"]: s for s in mid.json()["data"]["steps"]}
    assert mid_steps["add_products"]["auto_completed"] is True
    assert mid_steps["create_supplier"]["auto_completed"] is True
    assert mid_steps["stock_ready"]["auto_completed"] is True
    assert mid_steps["first_sale"]["auto_completed"] is False

    checked_in = await ac.post(
        f"/api/v1/hotel/reservations/{res_id}/check-in",
        headers=admin,
        json={},
    )
    assert checked_in.status_code == 200, checked_in.text
    folio_id = checked_in.json()["data"]["folio_id"]
    folio = await ac.get(f"/api/v1/hotel/folios/{folio_id}", headers=admin)
    assert folio.status_code == 200, folio.text
    assert folio.json()["data"]["charges_total"] == 500
    assert folio.json()["data"]["balance"] == 500

    after_in = await ac.get("/api/v1/onboarding/checklist", headers=admin)
    after_steps = {s["id"]: s for s in after_in.json()["data"]["steps"]}
    assert after_steps["first_sale"]["auto_completed"] is True

    pay = await ac.post(
        f"/api/v1/hotel/folios/{folio_id}/payments",
        headers=admin,
        json={"method": "cash", "amount": 500, "reference": f"CASH-{suffix}"},
    )
    assert pay.status_code == 200, pay.text
    assert pay.json()["data"]["payments_total"] == 500
    assert pay.json()["data"]["balance"] == 0

    checked_out = await ac.post(
        f"/api/v1/hotel/reservations/{res_id}/check-out",
        headers=admin,
        json={},
    )
    assert checked_out.status_code == 200, checked_out.text
    assert checked_out.json()["data"]["status"] == "checked_out"
    closed = await ac.get(f"/api/v1/hotel/folios/{folio_id}", headers=admin)
    assert closed.json()["data"]["status"] == "closed"
    invoice_id = closed.json()["data"].get("sales_invoice_id")
    assert invoice_id
    invoice = await ac.get(f"/api/v1/sales/invoices/{invoice_id}", headers=admin)
    assert invoice.status_code == 200, invoice.text
    assert invoice.json()["data"]["total_amount"] == 500

    reports = await ac.get(
        f"/api/v1/hotel/reports?start_date={check_in.isoformat()}&end_date={last_night.isoformat()}",
        headers=admin,
    )
    assert reports.status_code == 200, reports.text
    assert reports.json()["data"]["occupied_nights"] == 2
    assert reports.json()["data"]["room_revenue"] == 500
    assert reports.json()["data"]["adr"] == 250

    retail = await auth_headers(ac, email="cashier@beta.example.com", tenant_slug="beta")
    denied = await ac.get("/api/v1/hotel/rooms", headers=retail)
    assert denied.status_code == 403, denied.text
