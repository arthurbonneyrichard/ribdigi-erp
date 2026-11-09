"""Bakery: buying stock, expenses, the full report, and drivers who deliver, sell and hand in cash."""

from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

import pytest

from app import models as m
from app.rbac import permissions_for_role
from app.security import hash_password
from tests.conftest import auth_headers, set_tenant_industry


async def _owner(ac, seed, db_session):
    await set_tenant_industry(db_session, seed["t1"], "bakery")
    return await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")


async def _driver(ac, seed, db_session, name="Kofi"):
    email = f"driver-{uuid4().hex[:6]}@alpha.example.com"
    user = m.User(
        tenant_id=seed["t1"].id, email=email, full_name=name, password_hash=hash_password("SecurePass123!"),
        role="bakery_driver", email_verified=True, permissions=permissions_for_role("bakery_driver"),
    )
    db_session.add(user)
    await db_session.commit()
    return user.id, await auth_headers(ac, email=email, tenant_slug="alpha")


async def _item(ac, h, *, price=10, stock=50, cost=4):
    r = await ac.post("/api/v1/bakery/stock", headers=h, json={"name": f"Loaf {uuid4().hex[:5]}", "kind": "item", "price": price})
    assert r.status_code == 200, r.text
    pid = r.json()["data"]["id"]
    if stock:
        r = await ac.post(
            "/api/v1/bakery/stock/receive", headers=h,
            json={"product_id": pid, "quantity": stock, "unit_cost": cost, "paid_with": "cash"},
        )
        assert r.status_code == 200, r.text
    return pid


async def _even(ac, h):
    tb = (await ac.get("/api/v1/accounting/trial-balance", headers=h)).json()["data"]
    assert round(tb["total_debit"], 2) == round(tb["total_credit"], 2)


@pytest.mark.asyncio
async def test_buying_stock_raises_it_and_averages_the_cost(client, seeded, db_session):
    ac, seed = client
    h = await _owner(ac, seed, db_session)
    pid = await _item(ac, h, stock=10, cost=4)
    r = await ac.post(
        "/api/v1/bakery/stock/receive", headers=h,
        json={"product_id": pid, "quantity": 10, "unit_cost": 6, "paid_with": "credit", "supplier": "Mill Ltd"},
    )
    assert r.status_code == 200, r.text
    rows = {x["id"]: x for x in (await ac.get("/api/v1/bakery/stock", headers=h)).json()["data"]["items"]}
    assert rows[pid]["stock_qty"] == 20 and rows[pid]["cost_price"] == 5 and rows[pid]["kind"] == "item"
    await _even(ac, h)


@pytest.mark.asyncio
async def test_an_ingredient_never_shows_at_the_counter(client, seeded, db_session):
    ac, seed = client
    h = await _owner(ac, seed, db_session)
    r = await ac.post("/api/v1/bakery/stock", headers=h, json={"name": "Flour kg", "kind": "ingredient", "price": 99})
    assert r.status_code == 200, r.text
    names = [i["name"] for i in (await ac.get("/api/v1/bakery/items", headers=h)).json()["data"]]
    assert "Flour kg" not in names
    dup = await ac.post("/api/v1/bakery/stock", headers=h, json={"name": "flour KG", "kind": "ingredient"})
    assert dup.status_code == 409


@pytest.mark.asyncio
async def test_expenses_from_the_till_reduce_the_drawer(client, seeded, db_session):
    ac, seed = client
    h = await _owner(ac, seed, db_session)
    await ac.post("/api/v1/bakery/till/shift/open", headers=h, json={"opening_cash": 100})
    body = {"category": "gas", "description": "Gas refill", "amount": 30, "paid_with": "cash", "spent_on": date.today().isoformat(), "from_till": True}
    r = await ac.post("/api/v1/bakery/expenses", headers=h, json=body)
    assert r.status_code == 200, r.text
    shift = (await ac.get("/api/v1/bakery/till/shift", headers=h)).json()["data"]
    assert shift["expected_cash"] == 70
    card = await ac.post("/api/v1/bakery/expenses", headers=h, json={**body, "paid_with": "card"})
    assert card.status_code == 422
    future = await ac.post("/api/v1/bakery/expenses", headers=h, json={**body, "from_till": False, "spent_on": (date.today() + timedelta(days=2)).isoformat()})
    assert future.status_code == 422
    await _even(ac, h)


@pytest.mark.asyncio
async def test_full_report_counts_profit_after_expenses(client, seeded, db_session):
    ac, seed = client
    h = await _owner(ac, seed, db_session)
    pid = await _item(ac, h, price=10, stock=20, cost=4)
    await ac.post("/api/v1/bakery/till/shift/open", headers=h, json={"opening_cash": 0})
    sale = await ac.post("/api/v1/bakery/sales", headers=h, json={"payment_method": "cash", "lines": [{"product_id": pid, "quantity": 5}]})
    assert sale.status_code == 200, sale.text
    await ac.post(
        "/api/v1/bakery/expenses", headers=h,
        json={"category": "rent", "description": "Shop rent", "amount": 7, "paid_with": "bank_transfer", "spent_on": date.today().isoformat()},
    )
    data = (await ac.get("/api/v1/bakery/reports/full", headers=h)).json()["data"]
    item = data["by_item"][0]
    assert item["quantity"] == 5 and item["cost"] == 20
    assert data["expenses"] == 7
    assert data["net_profit"] == round(data["gross_profit"] - 7, 2)
    assert data["previous"]["revenue"] == 0
    assert len(data["trend"]["points"]) == 7
    assert data["by_hour"] and data["shifts"] == []
    bad = await ac.get("/api/v1/bakery/reports/full?start_date=2026-05-01&end_date=2026-04-01", headers=h)
    assert bad.status_code == 422


@pytest.mark.asyncio
async def test_driver_picks_up_delivers_takes_money_and_hands_it_in(client, seeded, db_session):
    ac, seed = client
    h = await _owner(ac, seed, db_session)
    pid = await _item(ac, h, price=20, stock=10)
    driver_id, d = await _driver(ac, seed, db_session)
    no_address = await ac.post(
        "/api/v1/bakery/orders", headers=h,
        json={"customer_name": "Ama", "due_date": date.today().isoformat(), "lines": [{"product_id": pid, "quantity": 2}], "delivery": True},
    )
    assert no_address.status_code == 422
    order = (
        await ac.post(
            "/api/v1/bakery/orders", headers=h,
            json={
                "customer_name": "Ama", "due_date": date.today().isoformat(), "lines": [{"product_id": pid, "quantity": 2}],
                "delivery": True, "address": "12 Palm Street", "driver_id": driver_id,
            },
        )
    ).json()["data"]
    assert order["delivery_status"] == "waiting" and order["driver_name"] == "Kofi"
    mine = (await ac.get("/api/v1/bakery/deliveries", headers=d)).json()["data"]
    assert [o["id"] for o in mine] == [order["id"]]

    url = f"/api/v1/bakery/orders/{order['id']}"
    assert (await ac.post(f"{url}/pick-up", headers=d)).status_code == 409
    assert (await ac.post("/api/v1/bakery/driver/bag", headers=d, json={"opening_cash": 20})).status_code == 200
    early = await ac.post(f"{url}/collect", headers=d, json={"payment_method": "cash"})
    assert early.status_code == 409
    assert (await ac.post(f"{url}/pick-up", headers=d)).status_code == 200
    done = await ac.post(f"{url}/collect", headers=d, json={"payment_method": "cash"})
    assert done.status_code == 200, done.text
    assert done.json()["data"]["delivery_status"] == "delivered"

    till = (await ac.get("/api/v1/bakery/till/shift", headers=h)).json()["data"]
    assert till is None
    drivers = (await ac.get("/api/v1/bakery/drivers", headers=h)).json()["data"]
    bag = next(d for d in drivers if d["id"] == driver_id)["bag"]
    assert bag["expected_cash"] == round(20 + order["total"], 2)

    own = await ac.post(f"/api/v1/bakery/driver/bags/{bag['id']}/hand-in", headers=d, json={"counted_cash": 0})
    assert own.status_code == 403
    r = await ac.post(f"/api/v1/bakery/driver/bags/{bag['id']}/hand-in", headers=h, json={"counted_cash": bag["expected_cash"] - 5})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["over_short"] == -5
    await _even(ac, h)


@pytest.mark.asyncio
async def test_driver_sells_on_the_road_into_their_bag(client, seeded, db_session):
    ac, seed = client
    h = await _owner(ac, seed, db_session)
    pid = await _item(ac, h, price=15, stock=10)
    _, d = await _driver(ac, seed, db_session)
    body = {"payment_method": "mobile_money", "lines": [{"product_id": pid, "quantity": 2}]}
    assert (await ac.post("/api/v1/bakery/sales", headers=d, json=body)).status_code == 409
    await ac.post("/api/v1/bakery/driver/bag", headers=d, json={"opening_cash": 0})
    r = await ac.post("/api/v1/bakery/sales", headers=d, json=body)
    assert r.status_code == 200, r.text
    today = (await ac.get("/api/v1/bakery/driver/today", headers=d)).json()["data"]
    assert today["road_sales_today"] == 1 and today["bag"]["by_method"]["mobile_money"] == 30
    assert (await ac.get("/api/v1/bakery/till/shift", headers=d)).status_code == 403
    assert (await ac.get("/api/v1/bakery/reports/full", headers=d)).status_code == 403


@pytest.mark.asyncio
async def test_failed_delivery_comes_back_and_another_driver_cannot_take_it(client, seeded, db_session):
    ac, seed = client
    h = await _owner(ac, seed, db_session)
    pid = await _item(ac, h, price=20, stock=10)
    _, d1 = await _driver(ac, seed, db_session, "Kofi")
    _, d2 = await _driver(ac, seed, db_session, "Yaw")
    order = (
        await ac.post(
            "/api/v1/bakery/orders", headers=h,
            json={"customer_name": "Esi", "due_date": date.today().isoformat(), "lines": [{"product_id": pid, "quantity": 1}], "delivery": True, "address": "Madina"},
        )
    ).json()["data"]
    for hdr in (d1, d2):
        await ac.post("/api/v1/bakery/driver/bag", headers=hdr, json={"opening_cash": 0})
    url = f"/api/v1/bakery/orders/{order['id']}"
    assert (await ac.post(f"{url}/pick-up", headers=d1)).status_code == 200
    assert (await ac.post(f"{url}/pick-up", headers=d2)).status_code == 409
    failed = await ac.post(f"{url}/delivery-failed", headers=d1, json={"reason": "Nobody home"})
    assert failed.status_code == 200 and failed.json()["data"]["delivery_status"] == "failed"
    db_session.expire_all()
    assert float((await db_session.get(m.Product, pid)).stock_qty) == 10


@pytest.mark.asyncio
async def test_hand_in_waits_for_deliveries_still_on_the_road(client, seeded, db_session):
    ac, seed = client
    h = await _owner(ac, seed, db_session)
    pid = await _item(ac, h, price=20, stock=10)
    _, d = await _driver(ac, seed, db_session)
    bag = (await ac.post("/api/v1/bakery/driver/bag", headers=d, json={"opening_cash": 0})).json()["data"]
    order = (
        await ac.post(
            "/api/v1/bakery/orders", headers=h,
            json={"customer_name": "Esi", "due_date": date.today().isoformat(), "lines": [{"product_id": pid, "quantity": 1}], "delivery": True, "address": "Madina"},
        )
    ).json()["data"]
    await ac.post(f"/api/v1/bakery/orders/{order['id']}/pick-up", headers=d)
    r = await ac.post(f"/api/v1/bakery/driver/bags/{bag['id']}/hand-in", headers=h, json={"counted_cash": 0})
    assert r.status_code == 409 and "on the road" in r.text


@pytest.mark.asyncio
async def test_counter_price_matches_what_the_sale_charges(client, seeded, db_session):
    ac, seed = client
    h = await _owner(ac, seed, db_session)
    pid = await _item(ac, h, price=6, stock=20)
    shown = next(i for i in (await ac.get("/api/v1/bakery/items", headers=h)).json()["data"] if i["id"] == pid)
    await ac.post("/api/v1/bakery/till/shift/open", headers=h, json={"opening_cash": 0})
    sale = (await ac.post("/api/v1/bakery/sales", headers=h, json={"payment_method": "cash", "lines": [{"product_id": pid, "quantity": 3}]})).json()["data"]
    assert round(shown["price_to_pay"] * 3, 2) == sale["total"]
    assert shown["price_to_pay"] >= shown["price"]


@pytest.mark.asyncio
async def test_a_manager_can_drive_deliver_and_sell_from_the_van(client, seeded, db_session):
    ac, seed = client
    h = await _owner(ac, seed, db_session)
    pid = await _item(ac, h, price=20, stock=10)
    order = (
        await ac.post(
            "/api/v1/bakery/orders", headers=h,
            json={"customer_name": "Esi", "due_date": date.today().isoformat(), "lines": [{"product_id": pid, "quantity": 1}], "delivery": True, "address": "Madina"},
        )
    ).json()["data"]
    url = f"/api/v1/bakery/orders/{order['id']}"
    assert (await ac.post(f"{url}/pick-up", headers=h)).status_code == 409
    bag = (await ac.post("/api/v1/bakery/driver/bag", headers=h, json={"opening_cash": 10})).json()["data"]
    assert (await ac.post(f"{url}/pick-up", headers=h)).status_code == 200
    done = await ac.post(f"{url}/collect", headers=h, json={"payment_method": "cash"})
    assert done.status_code == 200, done.text
    sold = await ac.post(
        "/api/v1/bakery/sales", headers=h,
        json={"payment_method": "cash", "lines": [{"product_id": pid, "quantity": 1}], "from_bag": True},
    )
    assert sold.status_code == 200, sold.text
    assert (await ac.get("/api/v1/bakery/till/shift", headers=h)).json()["data"] is None
    today = (await ac.get("/api/v1/bakery/driver/today", headers=h)).json()["data"]
    expected = round(10 + order["total"] + sold.json()["data"]["total"], 2)
    assert today["bag"]["expected_cash"] == expected
    assert any(d["full_name"] and not d["is_driver"] for d in (await ac.get("/api/v1/bakery/drivers", headers=h)).json()["data"])
    r = await ac.post(f"/api/v1/bakery/driver/bags/{bag['id']}/hand-in", headers=h, json={"counted_cash": expected})
    assert r.status_code == 200 and r.json()["data"]["over_short"] == 0


@pytest.mark.asyncio
async def test_a_cashier_cannot_sell_from_a_bag(client, seeded, db_session):
    ac, seed = client
    await _owner(ac, seed, db_session)
    email = f"cashier-{uuid4().hex[:6]}@alpha.example.com"
    db_session.add(
        m.User(
            tenant_id=seed["t1"].id, email=email, full_name="Ama", password_hash=hash_password("SecurePass123!"),
            role="bakery_cashier", email_verified=True, permissions=permissions_for_role("bakery_cashier"),
        )
    )
    await db_session.commit()
    c = await auth_headers(ac, email=email, tenant_slug="alpha")
    assert (await ac.post("/api/v1/bakery/driver/bag", headers=c, json={"opening_cash": 0})).status_code == 403
    r = await ac.post("/api/v1/bakery/sales", headers=c, json={"payment_method": "cash", "lines": [{"product_id": str(uuid4()), "quantity": 1}], "from_bag": True})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_a_manager_covering_can_take_over_a_waiting_delivery(client, seeded, db_session):
    ac, seed = client
    h = await _owner(ac, seed, db_session)
    pid = await _item(ac, h, price=20, stock=10)
    driver_id, _ = await _driver(ac, seed, db_session)
    order = (
        await ac.post(
            "/api/v1/bakery/orders", headers=h,
            json={"customer_name": "Esi", "due_date": date.today().isoformat(), "lines": [{"product_id": pid, "quantity": 1}],
                  "delivery": True, "address": "Madina", "driver_id": driver_id},
        )
    ).json()["data"]
    await ac.post("/api/v1/bakery/driver/bag", headers=h, json={"opening_cash": 0})
    r = await ac.post(f"/api/v1/bakery/orders/{order['id']}/pick-up", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["data"]["driver_name"] == "Alpha Admin"

