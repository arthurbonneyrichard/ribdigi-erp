"""Stage 6 N2: tenant onboarding checklist API."""

from __future__ import annotations

import pyotp
import pytest

from tests.conftest import auth_headers, set_tenant_industry


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_onboarding_checklist_progress_skip_dismiss(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)

    res = await ac.get("/api/v1/onboarding/checklist", headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["total_count"] == 5
    assert data["visible"] is True
    assert data["dismissed"] is False
    assert data["progress_pct"] < 80
    assert data["dismissible"] is False

    by_id = {s["id"]: s for s in data["steps"]}
    # Seed has product + stock for alpha; company profile / supplier / sale still open.
    assert by_id["add_products"]["auto_completed"] is True
    assert by_id["stock_ready"]["auto_completed"] is True
    assert by_id["setup_company"]["auto_completed"] is False
    assert by_id["create_supplier"]["auto_completed"] is False
    assert by_id["first_sale"]["auto_completed"] is False

    early = await ac.post("/api/v1/onboarding/checklist/dismiss", headers=headers)
    assert early.status_code == 400

    skip1 = await ac.post(
        "/api/v1/onboarding/checklist/steps/setup_company/skip", headers=headers
    )
    assert skip1.status_code == 200, skip1.text
    skip2 = await ac.post(
        "/api/v1/onboarding/checklist/steps/create_supplier/skip", headers=headers
    )
    assert skip2.status_code == 200, skip2.text
    mid = skip2.json()["data"]
    assert mid["progress_pct"] >= 80
    assert mid["dismissible"] is True

    bad_step = await ac.post(
        "/api/v1/onboarding/checklist/steps/not_a_step/skip", headers=headers
    )
    assert bad_step.status_code == 422

    dismissed = await ac.post("/api/v1/onboarding/checklist/dismiss", headers=headers)
    assert dismissed.status_code == 200, dismissed.text
    ddata = dismissed.json()["data"]
    assert ddata["dismissed"] is True
    assert ddata["visible"] is False

    restored = await ac.post("/api/v1/onboarding/checklist/restore", headers=headers)
    assert restored.status_code == 200, restored.text
    rdata = restored.json()["data"]
    assert rdata["dismissed"] is False
    assert rdata["visible"] is True

    unskip = await ac.post(
        "/api/v1/onboarding/checklist/steps/setup_company/unskip", headers=headers
    )
    assert unskip.status_code == 200, unskip.text
    assert unskip.json()["data"]["progress_pct"] < 80


@pytest.mark.asyncio
async def test_onboarding_checklist_requires_auth(client):
    ac, _seed = client
    res = await ac.get("/api/v1/onboarding/checklist")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_hotel_onboarding_completes_check_in_without_pos_sale(client, seeded, db_session):
    from datetime import date, timedelta
    from uuid import uuid4

    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    headers = await _admin(ac, seed)
    suffix = uuid4().hex[:6]
    check_in = date.today() + timedelta(days=1)
    check_out = check_in + timedelta(days=1)

    start = await ac.get("/api/v1/onboarding/checklist", headers=headers)
    assert start.status_code == 200, start.text
    titles = [s["title"] for s in start.json()["data"]["steps"]]
    assert titles == [
        "Setup company profile",
        "Add rooms",
        "Add guests",
        "Create a reservation",
        "Check in a guest",
    ]
    assert start.json()["data"]["steps"][-1]["auto_completed"] is False

    room = await ac.post(
        "/api/v1/hotel/rooms",
        headers=headers,
        json={"code": f"O{suffix}", "name": "Onboard 101", "rate_amount": 250},
    )
    guest = await ac.post(
        "/api/v1/hotel/guests",
        headers=headers,
        json={"full_name": f"Onboard Guest {suffix}"},
    )
    booked = await ac.post(
        "/api/v1/hotel/reservations",
        headers=headers,
        json={
            "room_id": room.json()["data"]["id"],
            "guest_id": guest.json()["data"]["id"],
            "check_in_date": check_in.isoformat(),
            "check_out_date": check_out.isoformat(),
            "status": "booked",
        },
    )
    assert booked.status_code == 200, booked.text
    cin = await ac.post(
        f"/api/v1/hotel/reservations/{booked.json()['data']['id']}/check-in",
        headers=headers,
        json={},
    )
    assert cin.status_code == 200, cin.text
    done = await ac.get("/api/v1/onboarding/checklist", headers=headers)
    by_id = {s["id"]: s for s in done.json()["data"]["steps"]}
    assert by_id["add_products"]["auto_completed"] is True
    assert by_id["create_supplier"]["auto_completed"] is True
    assert by_id["stock_ready"]["auto_completed"] is True
    assert by_id["first_sale"]["auto_completed"] is True
    assert by_id["first_sale"]["href"] == "/hotel?tab=reservations"


@pytest.mark.asyncio
async def test_restaurant_onboarding_completes_a_bill_without_an_invoice(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    start = await ac.get("/api/v1/onboarding/checklist", headers=headers)
    assert start.status_code == 200, start.text
    titles = [step["title"] for step in start.json()["data"]["steps"]]
    assert titles == [
        "Setup company profile",
        "Add a menu item",
        "Create a supplier",
        "Stock an ingredient",
        "Complete a bill",
    ]
    assert start.json()["data"]["steps"][-1]["description"] == "Complete a table, takeaway, or delivery bill"
    assert start.json()["data"]["steps"][-1]["auto_completed"] is False

    dish = await ac.post(
        "/api/v1/products",
        headers=headers,
        json={"name": "Onboard plate", "selling_price": 20, "prep_station": "kitchen", "stock_qty": 5},
    )
    assert dish.status_code == 200, dish.text
    opened = await ac.post(
        "/api/v1/restaurant/orders",
        headers=headers,
        json={
            "service_mode": "dine_in",
            "payment_method": "cash",
            "lines": [{"product_id": dish.json()["data"]["id"], "quantity": 1}],
        },
    )
    assert opened.status_code == 200, opened.text
    done_order = await ac.post(
        f"/api/v1/restaurant/orders/{opened.json()['data']['id']}/complete",
        headers=headers,
    )
    assert done_order.status_code == 200, done_order.text

    done = await ac.get("/api/v1/onboarding/checklist", headers=headers)
    by_id = {step["id"]: step for step in done.json()["data"]["steps"]}
    assert by_id["add_products"]["auto_completed"] is True
    assert by_id["add_products"]["title"] == "Add a menu item"
    assert by_id["first_sale"]["auto_completed"] is True
    assert by_id["first_sale"]["title"] == "Complete a bill"
    assert by_id["first_sale"]["href"] == "/restaurant?tab=orders"

    await set_tenant_industry(db_session, seed["t1"], "retail")
    retail = await ac.get("/api/v1/onboarding/checklist", headers=headers)
    retail_titles = [step["title"] for step in retail.json()["data"]["steps"]]
    assert retail_titles[-1] == "Make first sale"
    assert retail.json()["data"]["steps"][-1]["description"] == "Post a sales invoice or complete a POS sale"
