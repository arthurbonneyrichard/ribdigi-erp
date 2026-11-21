"""Restaurant, 15 Nov 2026: a bill paid more than one way, a bill split by dish, happy hours,
the live board's change check, and Mobile Money prompts (test mode)."""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import select

from app import models as m
from app import restaurant as restaurant_svc
from tests.conftest import auth_headers, set_tenant_industry
from tests.test_restaurant_till_shift import _dish

R = "/api/v1/restaurant"


async def _setup(ac, seed, db_session):
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    assert (await ac.post(f"{R}/till/shift/open", headers=admin, json={"opening_cash": 0})).status_code == 200
    return admin


async def _order(ac, h, lines):
    res = await ac.post(f"{R}/orders", headers=h, json={"service_mode": "takeaway", "customer_name": "Ama", "lines": lines})
    assert res.status_code == 200, res.text
    return res.json()["data"]


async def _account(db_session, tenant_id, code) -> float:
    value = (
        await db_session.execute(select(m.Account.balance).where(m.Account.tenant_id == tenant_id, m.Account.code == code))
    ).scalar_one_or_none()
    return float(value or 0)


@pytest.mark.asyncio
async def test_one_bill_paid_with_cash_and_card(client, seeded, db_session):
    ac, seed = client
    h = await _setup(ac, seed, db_session)
    dish = await _dish(ac, h, "Banku", 60)
    order = await _order(ac, h, [{"product_id": dish["id"], "quantity": "1"}])
    total = order["total_amount"]
    cash_before = await _account(db_session, seed["t1"].id, "1000")
    bank_before = await _account(db_session, seed["t1"].id, "1010")

    short = await ac.post(
        f"{R}/orders/{order['id']}/complete", headers=h,
        json={"payments": [{"method": "cash", "amount": 10}, {"method": "card", "amount": 10}]},
    )
    assert short.status_code == 422  # the parts must add up to the bill

    done = await ac.post(
        f"{R}/orders/{order['id']}/complete", headers=h,
        json={"payments": [{"method": "cash", "amount": 20}, {"method": "card", "amount": total - 20}]},
    )
    assert done.status_code == 200, done.text
    assert done.json()["data"]["payment_method"] == "split"
    await db_session.commit()
    assert round(await _account(db_session, seed["t1"].id, "1000") - cash_before, 2) == 20
    assert round(await _account(db_session, seed["t1"].id, "1010") - bank_before, 2) == round(total - 20, 2)

    shift = (await ac.get(f"{R}/till/shift", headers=h)).json()["data"]
    assert shift["cash_sales"] == 20
    assert shift["card_sales"] == round(total - 20, 2)
    assert shift["expected_cash"] == 20  # only the cash part sits in the drawer

    again = await ac.post(
        f"{R}/orders/{order['id']}/complete", headers=h,
        json={"payments": [{"method": "cash", "amount": 20}, {"method": "card", "amount": total - 20}]},
    )
    assert again.status_code == 409  # already paid: new parts are refused, not ignored
    assert (await ac.post(f"{R}/orders/{order['id']}/complete", headers=h, json={})).status_code == 200  # a repeat tap is fine

    refund = await ac.post(f"{R}/orders/{order['id']}/refund", headers=h, json={})
    assert refund.status_code == 200, refund.text
    shift = (await ac.get(f"{R}/till/shift", headers=h)).json()["data"]
    assert shift["cash_refunds"] == 20  # only the cash part leaves the drawer


@pytest.mark.asyncio
async def test_bill_split_by_dish(client, seeded, db_session):
    ac, seed = client
    h = await _setup(ac, seed, db_session)
    rice = await _dish(ac, h, "Waakye", 30)
    soup = await _dish(ac, h, "Light soup", 45)
    order = await _order(ac, h, [{"product_id": rice["id"], "quantity": "1"}, {"product_id": soup["id"], "quantity": "1"}])
    lines = (
        await db_session.execute(select(m.RestaurantOrderLine).where(m.RestaurantOrderLine.order_id == order["id"]))
    ).scalars().all()
    soup_line = next(ln for ln in lines if ln.product_id == soup["id"])
    everything = await ac.post(f"{R}/orders/{order['id']}/split", headers=h, json={"line_ids": [ln.id for ln in lines]})
    assert everything.status_code == 422  # something must stay on the first bill
    res = await ac.post(f"{R}/orders/{order['id']}/split", headers=h, json={"line_ids": [soup_line.id]})
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["order"]["subtotal"] == 30
    assert data["new_order"]["subtotal"] == 45
    assert data["new_order"]["order_number"] != data["order"]["order_number"]
    for bill in (data["order"], data["new_order"]):
        paid = await ac.post(f"{R}/orders/{bill['id']}/complete", headers=h, json={})
        assert paid.status_code == 200, paid.text


def test_happy_hour_rules_and_midnight():
    tenant = m.Tenant(id="t", slug="t", company_name="T", timezone="Africa/Accra")
    tenant.document_numbering = {
        restaurant_svc.HAPPY_KEY: restaurant_svc.clean_happy_hours(
            [
                {"name": "After work", "percent": 20, "days": ["fri"], "start": "17:00", "end": "19:00", "product_ids": []},
                {"name": "Late", "percent": 50, "days": ["fri"], "start": "22:00", "end": "02:00", "product_ids": ["beer"]},
            ]
        )
    }
    friday_6pm = datetime(2026, 11, 13, 18, 0)  # a Friday
    assert restaurant_svc.happy_hour_for(tenant, "rice", friday_6pm)["percent"] == 20
    assert restaurant_svc.happy_hour_for(tenant, "rice", datetime(2026, 11, 13, 19, 0)) is None
    assert restaurant_svc.happy_hour_for(tenant, "beer", datetime(2026, 11, 14, 1, 30))["name"] == "Late"  # Saturday 01:30
    assert restaurant_svc.happy_hour_for(tenant, "rice", datetime(2026, 11, 14, 1, 30)) is None
    with pytest.raises(Exception):
        restaurant_svc.clean_happy_hours([{"name": "x", "percent": 95, "days": ["mon"], "start": "10:00", "end": "11:00"}])


@pytest.mark.asyncio
async def test_happy_hour_price_goes_on_the_bill(client, seeded, db_session):
    ac, seed = client
    h = await _setup(ac, seed, db_session)
    dish = await _dish(ac, h, "Kelewele", 40)
    every_day = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    saved = await ac.put(
        f"{R}/happy-hours", headers=h,
        json={"rules": [{"name": "All day", "percent": 25, "days": every_day, "start": "00:00", "end": "23:59", "product_ids": [dish["id"]]}]},
    )
    assert saved.status_code == 200, saved.text
    order = await _order(ac, h, [{"product_id": dish["id"], "quantity": "1"}])
    assert order["subtotal"] == 30


@pytest.mark.asyncio
async def test_board_change_check_moves_when_an_order_changes(client, seeded, db_session):
    ac, seed = client
    h = await _setup(ac, seed, db_session)
    first = (await ac.get(f"{R}/orders/version", headers=h)).json()["data"]["version"]
    assert first == (await ac.get(f"{R}/orders/version", headers=h)).json()["data"]["version"]
    dish = await _dish(ac, h, "Red red", 35)
    await _order(ac, h, [{"product_id": dish["id"], "quantity": "1"}])
    assert (await ac.get(f"{R}/orders/version", headers=h)).json()["data"]["version"] != first


@pytest.mark.asyncio
async def test_mobile_money_prompt_pays_once(client, seeded, db_session):
    ac, seed = client
    h = await _setup(ac, seed, db_session)
    dish = await _dish(ac, h, "Fufu", 55)
    order = await _order(ac, h, [{"product_id": dish["id"], "quantity": "1"}])
    total = order["total_amount"]
    sent = await ac.post(f"{R}/till/momo", headers=h, json={"amount": total, "phone": "0241234567", "provider": "mtn"})
    assert sent.status_code == 200, sent.text
    ref = sent.json()["data"]["reference"]
    assert sent.json()["data"]["phone"] == "024****567"
    done = await ac.post(
        f"{R}/orders/{order['id']}/complete", headers=h,
        json={"payments": [{"method": "mobile_money", "amount": total, "reference": ref}]},
    )
    assert done.status_code == 200, done.text
    second = await _order(ac, h, [{"product_id": dish["id"], "quantity": "1"}])
    again = await ac.post(
        f"{R}/orders/{second['id']}/complete", headers=h,
        json={"payments": [{"method": "mobile_money", "amount": total, "reference": ref}]},
    )
    assert again.status_code == 409  # one prompt pays one bill


async def _table(ac, h, code, store_id=None):
    body = {"code": code, "name": f"Table {code}", "seats": 4}
    res = await ac.post(f"{R}/tables", headers=h, json=body)
    assert res.status_code == 200, res.text
    return res.json()["data"]


@pytest.mark.asyncio
async def test_move_bill_to_another_table_and_merge_bills(client, seeded, db_session):
    ac, seed = client
    h = await _setup(ac, seed, db_session)
    dish = await _dish(ac, h, "Jollof", 40)
    t1 = await _table(ac, h, "M1")
    t2 = await _table(ac, h, "M2")
    t3 = await _table(ac, h, "M3")

    def body(table):
        return {"service_mode": "dine_in", "table_id": table["id"], "lines": [{"product_id": dish["id"], "quantity": "1"}]}

    a = await ac.post(f"{R}/orders", headers=h, json=body(t1))
    assert a.status_code == 200, a.text
    a = a.json()["data"]

    moved = await ac.post(f"{R}/orders/{a['id']}/move-table", headers=h, json={"table_id": t2["id"]})
    assert moved.status_code == 200, moved.text
    tables = {t["code"]: t["status"] for t in (await ac.get(f"{R}/tables", headers=h)).json()["data"]}
    assert tables["M1"] == "available" and tables["M2"] == "occupied"
    assert (await ac.post(f"{R}/orders/{a['id']}/move-table", headers=h, json={"table_id": t2["id"]})).status_code == 409

    b = (await ac.post(f"{R}/orders", headers=h, json=body(t3))).json()["data"]
    busy = await ac.post(f"{R}/orders/{a['id']}/move-table", headers=h, json={"table_id": t3["id"]})
    assert busy.status_code == 409  # a table with guests: merge instead

    assert (await ac.post(f"{R}/orders/{a['id']}/merge", headers=h, json={"into_order_id": a["id"]})).status_code == 422
    merged = await ac.post(f"{R}/orders/{a['id']}/merge", headers=h, json={"into_order_id": b["id"]})
    assert merged.status_code == 200, merged.text
    assert merged.json()["data"]["subtotal"] == 80
    tables = {t["code"]: t["status"] for t in (await ac.get(f"{R}/tables", headers=h)).json()["data"]}
    assert tables["M2"] == "available" and tables["M3"] == "occupied"
    again = await ac.post(f"{R}/orders/{a['id']}/merge", headers=h, json={"into_order_id": b["id"]})
    assert again.status_code == 409  # the merged bill is closed
