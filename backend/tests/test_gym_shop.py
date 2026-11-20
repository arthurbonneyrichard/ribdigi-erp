"""Gym shop: own stock, sold and restocked through the gym till, books balanced."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select

from app import models as m
from tests.conftest import auth_headers, set_tenant_industry
from tests.test_gym_desk import _admin, _even, _member, _open

S = "/api/v1/gym/shop"


async def _product(ac, h, name="Protein shake", price=15, reorder=2):
    r = await ac.post(f"{S}/products", headers=h, json={"name": name, "price": price, "reorder_level": reorder})
    assert r.status_code == 200, r.text
    return r.json()["data"]


@pytest.mark.asyncio
async def test_restock_averages_cost_pays_from_the_till_and_sale_books_revenue_and_cost(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    p = await _product(ac, h)
    assert (await ac.post(f"{S}/products/{p['id']}/restock", headers=h, json={"quantity": 10, "unit_cost": 6, "method": "cash"})).status_code == 409  # no till
    await _open(ac, h)
    assert (await ac.post(f"{S}/products", headers=h, json={"name": "protein SHAKE", "price": 1})).status_code == 409
    r1 = await ac.post(f"{S}/products/{p['id']}/restock", headers=h, json={"quantity": 10, "unit_cost": 6, "method": "cash"})
    assert r1.status_code == 200 and r1.json()["data"]["stock_qty"] == 10 and r1.json()["data"]["cost"] == 6.0
    r2 = (await ac.post(f"{S}/products/{p['id']}/restock", headers=h, json={"quantity": 10, "unit_cost": 8, "method": "cash"})).json()["data"]
    assert r2["stock_qty"] == 20 and r2["cost"] == 7.0  # average cost
    sold = await ac.post(f"{S}/sales", headers=h, json={"items": [{"product_id": p["id"], "quantity": 3}, {"product_id": p["id"], "quantity": 2}], "method": "mobile_money"})
    assert sold.status_code == 200, sold.text
    assert sold.json()["data"]["total"] >= 75 and len(sold.json()["data"]["lines"]) == 1  # same product merged
    items = (await ac.get(f"{S}/products", headers=h)).json()["data"]
    assert items[0]["stock_qty"] == 15
    kinds = sorted(x.kind for x in (await db_session.execute(select(m.GymPayment))).scalars().all())
    assert kinds.count("stock_purchase") == 2 and kinds.count("shop_sale") == 1
    await _even(ac, h)  # the trial balance still balances after sale, cost of sales and stock buys
    shift = (await ac.get("/api/v1/gym/till/shift", headers=h)).json()["data"]
    assert shift["expected_cash"] == 100 - 60 - 80  # float less two cash stock buys; the sale was by Mobile Money


@pytest.mark.asyncio
async def test_stock_never_goes_negative_and_inactive_products_are_refused(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    await _open(ac, h)
    p = await _product(ac, h)
    await ac.post(f"{S}/products/{p['id']}/restock", headers=h, json={"quantity": 2, "unit_cost": 5, "method": "cash"})
    over = await ac.post(f"{S}/sales", headers=h, json={"items": [{"product_id": p["id"], "quantity": 3}], "method": "cash"})
    assert over.status_code == 409 and "Only 2" in over.json()["detail"]
    assert (await ac.get(f"{S}/products", headers=h)).json()["data"][0]["stock_qty"] == 2
    assert (await ac.post(f"{S}/products/{p['id']}", headers=h, json={"is_active": False})).status_code == 200
    assert (await ac.post(f"{S}/sales", headers=h, json={"items": [{"product_id": p["id"], "quantity": 1}], "method": "cash"})).status_code == 409
    assert (await ac.post(f"{S}/sales", headers=h, json={"items": [], "method": "cash"})).status_code == 422
    assert (await ac.post(f"{S}/sales", headers=h, json={"items": [{"product_id": p["id"], "quantity": 1}], "method": "crypto"})).status_code == 422


@pytest.mark.asyncio
async def test_shop_is_tenant_scoped_and_gym_only(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    await _open(ac, h)
    theirs = m.GymProduct(tenant_id=seed["t2"].id, name="Theirs", price=5, stock_qty=9)
    other = m.GymMember(tenant_id=seed["t2"].id, member_number="GM-1", full_name="T", joined_on=date.today())
    db_session.add_all([theirs, other])
    await db_session.commit()
    mine = await _product(ac, h, "Mine")
    assert (await ac.post(f"{S}/sales", headers=h, json={"items": [{"product_id": theirs.id, "quantity": 1}], "method": "cash"})).status_code == 404
    assert (await ac.post(f"{S}/products/{theirs.id}/restock", headers=h, json={"quantity": 1, "unit_cost": 1, "method": "cash"})).status_code == 404
    member_id = other.id
    assert (await ac.post(f"{S}/sales", headers=h, json={"items": [{"product_id": mine["id"], "quantity": 1}], "method": "cash", "member_id": member_id})).status_code in (404, 409)
    assert [x["name"] for x in (await ac.get(f"{S}/products", headers=h)).json()["data"]] == ["Mine"]
    await set_tenant_industry(db_session, seed["t1"], "bakery")
    h = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    assert (await ac.get(f"{S}/products", headers=h)).status_code == 403


@pytest.mark.asyncio
async def test_refund_returns_stock_at_cost_reverses_revenue_and_is_capped(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    await _open(ac, h)
    p = await _product(ac, h)
    await ac.post(f"{S}/products/{p['id']}/restock", headers=h, json={"quantity": 10, "unit_cost": 6, "method": "cash"})
    sale = (await ac.post(f"{S}/sales", headers=h, json={"items": [{"product_id": p["id"], "quantity": 4}], "method": "cash"})).json()["data"]
    listed = (await ac.get(f"{S}/sales", headers=h)).json()["data"][0]
    assert listed["lines"][0]["refundable"] == 4
    part = await ac.post(f"{S}/sales/{sale['id']}/refund", headers=h, json={"items": [{"product_id": p["id"], "quantity": 1}], "method": "cash"})
    assert part.status_code == 200, part.text
    assert part.json()["data"]["refunded"] == round(sale["total"] / 4, 2)
    assert (await ac.get(f"{S}/products", headers=h)).json()["data"][0]["stock_qty"] == 7
    assert (await ac.post(f"{S}/sales/{sale['id']}/refund", headers=h, json={"items": [{"product_id": p["id"], "quantity": 4}], "method": "cash"})).status_code == 409
    assert (await ac.post(f"{S}/sales/{sale['id']}/refund", headers=h, json={"items": [{"product_id": p["id"], "quantity": 3}], "method": "cash"})).status_code == 200
    assert (await ac.get(f"{S}/sales", headers=h)).json()["data"][0]["lines"][0]["refundable"] == 0
    assert (await ac.post(f"{S}/sales/{sale['id']}/refund", headers=h, json={"items": [{"product_id": p["id"], "quantity": 1}], "method": "cash"})).status_code == 409
    await _even(ac, h)
    shift = (await ac.get("/api/v1/gym/till/shift", headers=h)).json()["data"]
    assert shift["expected_cash"] == round(100 - 60 + sale["total"] - sale["total"], 2)  # all four returned, so only the stock buy is out


@pytest.mark.asyncio
async def test_stock_on_credit_makes_a_bill_that_is_paid_from_the_till(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    p = await _product(ac, h)
    credit = {"quantity": 10, "unit_cost": 5, "method": "credit", "supplier_name": "Accra Wholesale"}
    r = await ac.post(f"{S}/products/{p['id']}/restock", headers=h, json=credit)  # no till needed: nothing is paid today
    assert r.status_code == 200, r.text
    assert r.json()["data"]["stock_qty"] == 10 and r.json()["data"]["bill_id"]
    assert (await ac.post(f"{S}/products/{p['id']}/restock", headers=h, json={"quantity": 1, "unit_cost": 5, "method": "credit"})).status_code in (400, 422)
    bills = (await ac.get(f"{S}/bills?status=open", headers=h)).json()["data"]
    assert len(bills) == 1 and bills[0]["amount"] == 50.0 and bills[0]["supplier"] == "Accra Wholesale"
    assert (await ac.post(f"{S}/bills/{bills[0]['id']}/pay", headers=h, json={"method": "cash"})).status_code == 409  # till is closed
    await _open(ac, h)
    paid = await ac.post(f"{S}/bills/{bills[0]['id']}/pay", headers=h, json={"method": "cash"})
    assert paid.status_code == 200 and paid.json()["data"]["status"] == "paid"
    assert (await ac.post(f"{S}/bills/{bills[0]['id']}/pay", headers=h, json={"method": "cash"})).status_code == 409
    await _even(ac, h)
    shift = (await ac.get("/api/v1/gym/till/shift", headers=h)).json()["data"]
    assert shift["expected_cash"] == 50.0  # 100 float less the 50 paid to the supplier
