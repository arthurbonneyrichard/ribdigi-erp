"""Restaurant, 21 Nov 2026: manager discounts and comps, the guest on a bill with loyalty points,
gift cards, delivery riders, and guest feedback."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app import models as m
from tests.conftest import auth_headers, set_tenant_industry
from tests.test_restaurant_site import _menu_item, _open_site
from tests.test_restaurant_split_happy_15nov import _account, _order, _setup
from tests.test_restaurant_till_shift import _dish

R = "/api/v1/restaurant"
SITE = "/api/v1/public/restaurant-site/alpha"


@pytest.mark.asyncio
async def test_manager_discount_and_comp(client, seeded, db_session):
    ac, seed = client
    h = await _setup(ac, seed, db_session)
    dish = await _dish(ac, h, "Fufu", 100)
    order = await _order(ac, h, [{"product_id": dish["id"], "quantity": "1"}])
    full = order["total_amount"]

    bad = await ac.post(f"{R}/orders/{order['id']}/discount", headers=h, json={"kind": "percent", "value": 10, "reason": "!!!"})
    assert bad.status_code in (400, 422)
    over = await ac.post(f"{R}/orders/{order['id']}/discount", headers=h, json={"kind": "percent", "value": 150, "reason": "Birthday"})
    assert over.status_code == 422

    res = await ac.post(f"{R}/orders/{order['id']}/discount", headers=h, json={"kind": "percent", "value": 10, "reason": "Regular guest"})
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["discount_amount"] == 10
    assert data["subtotal"] == 90
    assert data["total_amount"] < full

    cleared = await ac.post(f"{R}/orders/{order['id']}/discount", headers=h, json={"kind": "clear"})
    assert cleared.json()["data"]["total_amount"] == full

    await ac.post(f"{R}/orders/{order['id']}/discount", headers=h, json={"kind": "amount", "value": 25, "reason": "Slow service"})
    sales_before = await _account(db_session, seed["t1"].id, "4000")
    done = await ac.post(f"{R}/orders/{order['id']}/complete", headers=h, json={})
    assert done.status_code == 200, done.text
    await db_session.commit()
    paid = done.json()["data"]["total_amount"]
    assert paid < full
    assert await _account(db_session, seed["t1"].id, "4000") - sales_before > 0  # revenue is booked net of the discount

    comp_order = await _order(ac, h, [{"product_id": dish["id"], "quantity": "1"}])
    comp = await ac.post(f"{R}/orders/{comp_order['id']}/discount", headers=h, json={"kind": "comp", "reason": "Owner's guest"})
    assert comp.status_code == 200, comp.text
    assert comp.json()["data"]["total_amount"] == 0
    finished = await ac.post(f"{R}/orders/{comp_order['id']}/complete", headers=h, json={})
    assert finished.status_code == 200, finished.text
    assert finished.json()["data"]["status"] == "completed"

    # A paid bill cannot be discounted afterwards.
    late = await ac.post(f"{R}/orders/{order['id']}/discount", headers=h, json={"kind": "percent", "value": 5, "reason": "Too late"})
    assert late.status_code == 409


@pytest.mark.asyncio
async def test_guest_points_and_gift_card_spend_and_refund(client, seeded, db_session):
    ac, seed = client
    h = await _setup(ac, seed, db_session)
    dish = await _dish(ac, h, "Banku", 100)
    phone = "+233200000001"

    first = await _order(ac, h, [{"product_id": dish["id"], "quantity": "1"}])
    att = await ac.post(f"{R}/orders/{first['id']}/guest", headers=h, json={"phone": phone, "name": "Efua"})
    assert att.status_code == 200, att.text
    assert att.json()["data"]["name"] == "Efua"
    assert (await ac.post(f"{R}/orders/{first['id']}/complete", headers=h, json={})).status_code == 200
    guest = (await ac.get(f"{R}/orders/{first['id']}/guest", headers=h)).json()["data"]
    earned = guest["loyalty_points"]
    assert earned >= 1  # 1% of the bill

    # Sell a gift card for cash (counted in the open till).
    sold = await ac.post(f"{R}/gift-cards", headers=h, json={"amount": 50, "method": "cash", "buyer": "Kojo"})
    assert sold.status_code == 200, sold.text
    code = sold.json()["data"]["code"]
    assert (await ac.get(f"{R}/gift-cards/{code}", headers=h)).json()["data"]["balance"] == 50
    shift = (await ac.get(f"{R}/till/shift", headers=h)).json()["data"]
    assert shift["cash_in"] == 50

    second = await _order(ac, h, [{"product_id": dish["id"], "quantity": "1"}])
    total = second["total_amount"]
    await ac.post(f"{R}/orders/{second['id']}/guest", headers=h, json={"phone": phone})

    # Not enough on the card, and points need the guest on the bill.
    too_much = await ac.post(
        f"{R}/orders/{second['id']}/complete", headers=h,
        json={"payments": [{"method": "gift_card", "amount": 80, "reference": code}, {"method": "cash", "amount": total - 80}]},
    )
    assert too_much.status_code == 409, too_much.text
    wrong_sum = await ac.post(
        f"{R}/orders/{second['id']}/complete", headers=h,
        json={"payments": [{"method": "gift_card", "amount": 30, "reference": code}]},
    )
    assert wrong_sum.status_code == 422

    liability_before = await _account(db_session, seed["t1"].id, "2150")
    done = await ac.post(
        f"{R}/orders/{second['id']}/complete", headers=h,
        json={"payments": [
            {"method": "gift_card", "amount": 30, "reference": code},
            {"method": "loyalty", "amount": 1},
            {"method": "cash", "amount": round(total - 31, 2)},
        ]},
    )
    assert done.status_code == 200, done.text
    await db_session.commit()
    assert (await ac.get(f"{R}/gift-cards/{code}", headers=h)).json()["data"]["balance"] == 20
    assert await _account(db_session, seed["t1"].id, "2150") < liability_before  # the card liability was used up
    after = (await ac.get(f"{R}/orders/{second['id']}/guest", headers=h)).json()["data"]["loyalty_points"]
    assert after < earned + total * 0.01  # one point was spent

    refund = await ac.post(f"{R}/orders/{second['id']}/refund", headers=h, json={})
    assert refund.status_code == 200, refund.text
    assert (await ac.get(f"{R}/gift-cards/{code}", headers=h)).json()["data"]["balance"] == 50
    back = (await ac.get(f"{R}/orders/{second['id']}/guest", headers=h)).json()["data"]["loyalty_points"]
    assert back == earned  # spent point returned, earned points taken back

    no_guest = await _order(ac, h, [{"product_id": dish["id"], "quantity": "1"}])
    refused = await ac.post(
        f"{R}/orders/{no_guest['id']}/complete", headers=h,
        json={"payments": [{"method": "loyalty", "amount": no_guest["total_amount"]}]},
    )
    assert refused.status_code == 422


@pytest.mark.asyncio
async def test_rider_tracking_and_guest_feedback(client, seeded, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    jollof = await _menu_item(ac, admin, "Jollof", 40, category="Mains")
    await _open_site(ac, admin, booking=False)
    placed = await ac.post(
        f"{SITE}/order",
        json={"service": "delivery", "customer_name": "Esi", "phone": "+233201234567", "pay_with": "cash",
              "delivery_address": "12 Oxford St, Osu", "lines": [{"product_id": jollof["id"], "quantity": 1}]},
    )
    assert placed.status_code == 200, placed.text
    oid = placed.json()["data"]["id"]

    assert (await ac.post(f"{R}/orders/{oid}/dispatch", headers=admin)).status_code == 409  # no rider yet
    rider = await ac.post(f"{R}/orders/{oid}/rider", headers=admin, json={"name": "Yaw Boateng", "phone": "+233244000111"})
    assert rider.status_code == 200, rider.text
    assert rider.json()["data"]["delivery_status"] == "assigned"
    early = await ac.post(f"{R}/orders/{oid}/dispatch", headers=admin)
    assert early.status_code == 409  # not ready yet

    row = await db_session.get(m.RestaurantOrder, oid)
    row.status = "ready"
    await db_session.commit()
    assert (await ac.post(f"{R}/orders/{oid}/delivered", headers=admin)).status_code == 409  # has not left
    assert (await ac.post(f"{R}/orders/{oid}/dispatch", headers=admin)).status_code == 200
    tracked = (await ac.get(f"{SITE}/order/{oid}")).json()["data"]
    assert tracked["delivery_words"] == "On the way to you" and tracked["rider_name"] == "Yaw Boateng"
    assert tracked["can_rate"] is False

    assert (await ac.post(f"{R}/orders/{oid}/delivered", headers=admin)).status_code == 200
    assert (await ac.post(f"{SITE}/order/{oid}/feedback", json={"rating": 5})).status_code == 409  # not paid and done yet
    assert (await ac.post(f"{R}/orders/{oid}/complete", headers=admin, json={})).status_code == 200
    tracked = (await ac.get(f"{SITE}/order/{oid}")).json()["data"]
    assert tracked["can_rate"] is True and tracked["rider_name"] is None  # rider details leave once delivered

    assert (await ac.post(f"{SITE}/order/{oid}/feedback", json={"rating": 9})).status_code == 422
    rated = await ac.post(f"{SITE}/order/{oid}/feedback", json={"rating": 4, "comment": "Hot and on time"})
    assert rated.status_code == 200, rated.text
    assert rated.json()["data"]["can_rate"] is False
    assert (await ac.post(f"{SITE}/order/{oid}/feedback", json={"rating": 5})).status_code == 409

    staff = await ac.post(f"{R}/feedback", headers=admin, json={"rating": 2, "comment": "Cold chips", "guest_name": "Table 4"})
    assert staff.status_code == 200, staff.text
    board = (await ac.get(f"{R}/feedback", headers=admin)).json()["data"]
    assert board["count"] == 2 and board["average"] == 3 and board["by_rating"]["4"] == 1

    pickup = await _order_pickup(ac, admin, jollof["id"])
    assert (await ac.post(f"{R}/orders/{pickup}/rider", headers=admin, json={"name": "Yaw Boateng"})).status_code == 409


async def _order_pickup(ac, h, product_id):
    res = await ac.post(f"{R}/orders", headers=h, json={"service_mode": "takeaway", "customer_name": "Ama", "lines": [{"product_id": product_id, "quantity": "1"}]})
    assert res.status_code == 200, res.text
    return res.json()["data"]["id"]


@pytest.mark.asyncio
async def test_comp_still_books_what_the_food_cost(client, seeded, db_session):
    ac, seed = client
    h = await _setup(ac, seed, db_session)
    made = await ac.post(
        "/api/v1/products",
        json={"name": "Grilled tilapia", "selling_price": 100, "cost_price": 35, "stock_qty": 20, "prep_station": "kitchen"},
        headers=h,
    )
    assert made.status_code == 200, made.text
    order = await _order(ac, h, [{"product_id": made.json()["data"]["id"], "quantity": "1"}])
    await ac.post(f"{R}/orders/{order['id']}/discount", headers=h, json={"kind": "comp", "reason": "Chef's tasting"})
    cogs_before = await _account(db_session, seed["t1"].id, "5000")
    sales_before = await _account(db_session, seed["t1"].id, "4000")
    done = await ac.post(f"{R}/orders/{order['id']}/complete", headers=h, json={})
    assert done.status_code == 200, done.text
    await db_session.commit()
    assert round(await _account(db_session, seed["t1"].id, "5000") - cogs_before, 2) == 35  # the cost is still an expense
    assert await _account(db_session, seed["t1"].id, "4000") == sales_before  # and no sale was booked
    refund = await ac.post(f"{R}/orders/{order['id']}/refund", headers=h, json={})
    assert refund.status_code == 200, refund.text
    await db_session.commit()
    assert round(await _account(db_session, seed["t1"].id, "5000") - cogs_before, 2) == 0
