"""Restaurant till shifts, cash and guests live on restaurant tables; the retail till refuses a restaurant."""

from __future__ import annotations

import pytest

from tests.conftest import auth_headers, set_tenant_industry

pytestmark = pytest.mark.asyncio


async def _dish(ac, headers, name: str, price: float):
    created = await ac.post(
        "/api/v1/products",
        json={"name": name, "selling_price": price, "stock_qty": 50, "prep_station": "kitchen"},
        headers=headers,
    )
    assert created.status_code == 200, created.text
    return created.json()["data"]


async def _paid_order(ac, headers, dish_id: str, method: str, *, name="Ama", phone=None):
    body = {
        "service_mode": "takeaway",
        "payment_method": method,
        "customer_name": name,
        "lines": [{"product_id": dish_id, "quantity": "2"}],
    }
    if phone:
        body["phone"] = phone
    order = await ac.post("/api/v1/restaurant/orders", json=body, headers=headers)
    assert order.status_code == 200, order.text
    done = await ac.post(f"/api/v1/restaurant/orders/{order.json()['data']['id']}/complete", headers=headers)
    assert done.status_code == 200, done.text
    return done.json()["data"]


async def test_restaurant_cannot_use_the_retail_till(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    opened = await ac.post("/api/v1/pos/sessions/open", headers=admin, json={"opening_cash": 0})
    assert opened.status_code == 403, opened.text
    current = await ac.get("/api/v1/pos/sessions/current", headers=admin)
    assert current.status_code == 403, current.text
    sale = await ac.post("/api/v1/pos/sales", headers=admin, json={"items": []})
    assert sale.status_code in {403, 422}, sale.text


async def test_restaurant_till_shift_counts_cash_and_closes(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    dish = await _dish(ac, admin, "Waakye", 25)

    none_yet = await ac.get("/api/v1/restaurant/till/shift", headers=admin)
    assert none_yet.status_code == 200, none_yet.text
    assert none_yet.json()["data"] is None

    opened = await ac.post("/api/v1/restaurant/till/shift/open", headers=admin, json={"opening_cash": 100})
    assert opened.status_code == 200, opened.text
    shift = opened.json()["data"]
    assert shift["status"] == "open" and shift["opening_cash"] == 100
    again = await ac.post("/api/v1/restaurant/till/shift/open", headers=admin, json={"opening_cash": 5})
    assert again.json()["data"]["id"] == shift["id"]

    cash_order = await _paid_order(ac, admin, dish["id"], "cash")
    assert cash_order["till_shift_id"] == shift["id"]
    await _paid_order(ac, admin, dish["id"], "card")

    sid = shift["id"]
    put_in = await ac.post(
        f"/api/v1/restaurant/till/shift/{sid}/cash", headers=admin,
        json={"movement_type": "cash_in", "amount": 20, "reason": "More change"},
    )
    assert put_in.status_code == 200, put_in.text
    too_much = await ac.post(
        f"/api/v1/restaurant/till/shift/{sid}/cash", headers=admin,
        json={"movement_type": "cash_out", "amount": 10000, "reason": "Bank run"},
    )
    assert too_much.status_code == 400, too_much.text
    blank = await ac.post(
        f"/api/v1/restaurant/till/shift/{sid}/cash", headers=admin,
        json={"movement_type": "cash_out", "amount": 5, "reason": "!!!"},
    )
    assert blank.status_code == 400, blank.text

    refunded = await ac.post(f"/api/v1/restaurant/orders/{cash_order['id']}/refund", headers=admin)
    assert refunded.status_code == 200, refunded.text

    live = (await ac.get("/api/v1/restaurant/till/shift", headers=admin)).json()["data"]
    assert live["cash_sales"] == cash_order["total_amount"]
    assert live["card_sales"] > 0
    assert live["sale_count"] == 2
    assert live["refunded_sales"] == cash_order["total_amount"]
    assert live["cash_in"] == 20
    assert live["cash_refunds"] == cash_order["total_amount"]
    # 100 float + cash sale + 20 in − cash refund.
    assert live["expected_cash"] == 120
    assert {row["movement_type"] for row in live["moves"]} == {"cash_in", "refund"}

    closed = await ac.post(
        f"/api/v1/restaurant/till/shift/{sid}/close", headers=admin, json={"counted_cash": 118, "notes": "Two short"},
    )
    assert closed.status_code == 200, closed.text
    body = closed.json()["data"]
    assert body["status"] == "closed"
    assert body["expected_cash"] == 120 and body["counted_cash"] == 118 and body["variance"] == -2
    twice = await ac.post(f"/api/v1/restaurant/till/shift/{sid}/close", headers=admin, json={"counted_cash": 1})
    assert twice.status_code == 409, twice.text
    assert (await ac.get("/api/v1/restaurant/till/shift", headers=admin)).json()["data"] is None
    listed = await ac.get("/api/v1/restaurant/till/shifts", headers=admin)
    assert listed.json()["data"][0]["id"] == sid

    # A sale with no open shift is still a sale; it simply has no drawer.
    later = await _paid_order(ac, admin, dish["id"], "cash")
    assert later["till_shift_id"] is None


async def test_restaurant_guests_come_from_orders_and_bookings(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    dish = await _dish(ac, admin, "Fufu", 30)
    await _paid_order(ac, admin, dish["id"], "cash", name="Kofi Mensah", phone="+233241234567")
    await _paid_order(ac, admin, dish["id"], "card", name="kofi mensah", phone="+233241234567")
    await _paid_order(ac, admin, dish["id"], "cash", name="Walk-in")
    guests = await ac.get("/api/v1/restaurant/guests", headers=admin)
    assert guests.status_code == 200, guests.text
    rows = guests.json()["data"]
    assert len(rows) == 1
    kofi = rows[0]
    assert kofi["name"].lower() == "kofi mensah"
    assert kofi["visits"] == 2
    assert kofi["favourite_dish"] == "Fufu"
    assert kofi["spent"] > 0


async def test_retail_cannot_use_the_restaurant_till_shift(client, db_session):
    ac, _seed = client
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    denied = await ac.post("/api/v1/restaurant/till/shift/open", headers=admin, json={"opening_cash": 0})
    assert denied.status_code == 403, denied.text
