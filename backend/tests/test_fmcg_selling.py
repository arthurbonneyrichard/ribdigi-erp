"""FMCG selling desk: book, load, deliver, collect, return and settle, on its own tables."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select

from app import fmcg_orders
from app import models as m
from tests.conftest import auth_headers, set_tenant_industry

ORDERS = "/api/v1/fmcg/orders"


async def _admin(ac, seed, db_session):
    await set_tenant_industry(db_session, seed["t1"], "fmcg")
    return await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")


async def _product(db_session, seed, *, price=10, cost=6, stock=100):
    row = m.Product(
        tenant_id=seed["t1"].id, name=f"Soap {uuid4().hex[:5]}", sku=f"F{uuid4().hex[:7]}",
        cost_price=cost, selling_price=price, stock_qty=stock, is_active=True, tracks_batches=False,
    )
    db_session.add(row)
    await db_session.commit()
    return SimpleNamespace(id=row.id)


async def _outlet(ac, h, **extra):
    body = {"name": f"Kiosk {uuid4().hex[:5]}", **extra}
    r = await ac.post("/api/v1/fmcg/outlets", headers=h, json=body)
    assert r.status_code == 200, r.text
    return r.json()["data"]["id"]


async def _order(ac, h, outlet, product, qty=10, terms="credit", **extra):
    r = await ac.post(
        ORDERS, headers=h,
        json={"customer_id": outlet, "terms": terms, "lines": [{"product_id": product.id, "quantity": qty}], **extra},
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]


async def _balance(db_session, outlet):
    db_session.expire_all()
    return float((await db_session.get(m.Party, outlet)).balance or 0)


async def _trial_balance_is_even(ac, h):
    tb = (await ac.get("/api/v1/accounting/trial-balance", headers=h)).json()["data"]
    assert round(tb["total_debit"], 2) == round(tb["total_credit"], 2)


@pytest.mark.asyncio
async def test_booking_moves_nothing_and_delivery_books_the_sale(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    tenant_id = seed["t1"].id
    product = await _product(db_session, seed)
    outlet = await _outlet(ac, h)
    order = await _order(ac, h, outlet, product)
    assert order["status"] == "booked"
    db_session.expire_all()
    assert float((await db_session.get(m.Product, product.id)).stock_qty) == 100
    assert await _balance(db_session, outlet) == 0

    r = await ac.post(f"{ORDERS}/{order['id']}/deliver", headers=h, json={})
    assert r.status_code == 200, r.text
    done = r.json()["data"]
    assert done["status"] == "delivered" and done["balance_due"] == done["total"]
    db_session.expire_all()
    assert float((await db_session.get(m.Product, product.id)).stock_qty) == 90
    assert await _balance(db_session, outlet) == done["total"]
    await _trial_balance_is_even(ac, h)

    again = await ac.post(f"{ORDERS}/{order['id']}/deliver", headers=h, json={})
    assert again.status_code == 409
    assert (await db_session.execute(select(m.Transaction).where(m.Transaction.tenant_id == tenant_id))).first() is None


@pytest.mark.asyncio
async def test_price_comes_from_the_catalogue_and_schemes_come_off(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    product = await _product(db_session, seed, price=100)
    scheme = await ac.post(
        "/api/v1/fmcg/schemes", headers=h,
        json={"code": f"S{uuid4().hex[:5]}", "name": "Ten off", "scheme_type": "percent", "value": 10, "product_id": product.id},
    )
    assert scheme.status_code == 200, scheme.text
    outlet = await _outlet(ac, h)
    order = await _order(ac, h, outlet, product, qty=2)
    assert order["discount"] == 20
    assert order["lines"][0]["unit_price"] == 100
    forged = await ac.post(
        ORDERS, headers=h,
        json={"customer_id": outlet, "lines": [{"product_id": product.id, "quantity": 1, "unit_price": 1}]},
    )
    assert forged.status_code == 422


@pytest.mark.asyncio
async def test_cash_on_delivery_needs_a_method_and_settles_at_once(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    product = await _product(db_session, seed)
    outlet = await _outlet(ac, h)
    order = await _order(ac, h, outlet, product, terms="cash")
    assert (await ac.post(f"{ORDERS}/{order['id']}/deliver", headers=h, json={})).status_code == 422
    r = await ac.post(f"{ORDERS}/{order['id']}/deliver", headers=h, json={"payment_method": "cash"})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["balance_due"] == 0
    assert await _balance(db_session, outlet) == 0
    await _trial_balance_is_even(ac, h)


@pytest.mark.asyncio
async def test_credit_limit_counts_orders_already_booked(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    product = await _product(db_session, seed)
    outlet = await _outlet(ac, h, credit_limit=150)
    await _order(ac, h, outlet, product, qty=10)
    body = {"customer_id": outlet, "terms": "credit", "lines": [{"product_id": product.id, "quantity": 10}]}
    over = await ac.post(ORDERS, headers=h, json=body)
    assert over.status_code in (402, 403, 409), over.text
    assert "CREDIT_LIMIT" in over.text
    allowed = await ac.post(ORDERS, headers=h, json={**body, "override_reason": "Known outlet, paying Friday"})
    assert allowed.status_code == 200, allowed.text
    cash = await ac.post(ORDERS, headers=h, json={**body, "terms": "cash"})
    assert cash.status_code == 200, cash.text


@pytest.mark.asyncio
async def test_collection_pays_oldest_first_and_cannot_overpay(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    product = await _product(db_session, seed)
    outlet = await _outlet(ac, h)
    first = await _order(ac, h, outlet, product, qty=5)
    second = await _order(ac, h, outlet, product, qty=5)
    for order in (first, second):
        assert (await ac.post(f"{ORDERS}/{order['id']}/deliver", headers=h, json={})).status_code == 200
    owed = await _balance(db_session, outlet)
    too_much = await ac.post(
        "/api/v1/fmcg/collections", headers=h, json={"customer_id": outlet, "amount": owed + 1, "method": "cash"}
    )
    assert too_much.status_code == 409
    part = round(first["total"] + 1, 2)
    r = await ac.post("/api/v1/fmcg/collections", headers=h, json={"customer_id": outlet, "amount": part, "method": "mobile_money"})
    assert r.status_code == 200, r.text
    rows = {o["id"]: o for o in (await ac.get(f"{ORDERS}?show=delivered", headers=h)).json()["data"]}
    assert rows[first["id"]]["balance_due"] == 0
    assert rows[second["id"]]["balance_due"] == round(second["total"] - 1, 2)
    assert await _balance(db_session, outlet) == round(owed - part, 2)
    await _trial_balance_is_even(ac, h)


@pytest.mark.asyncio
async def test_return_credits_the_outlet_and_only_good_stock_comes_back(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    product = await _product(db_session, seed)
    outlet = await _outlet(ac, h)
    order = await _order(ac, h, outlet, product, qty=10)
    done = (await ac.post(f"{ORDERS}/{order['id']}/deliver", headers=h, json={})).json()["data"]
    line = done["lines"][0]
    url = f"{ORDERS}/{order['id']}/returns"
    good = await ac.post(url, headers=h, json={"lines": [{"line_id": line["id"], "quantity": 2}], "reason": "unsold", "resaleable": True})
    assert good.status_code == 200, good.text
    bad = await ac.post(url, headers=h, json={"lines": [{"line_id": line["id"], "quantity": 3}], "reason": "damaged"})
    assert bad.status_code == 200, bad.text
    db_session.expire_all()
    assert float((await db_session.get(m.Product, product.id)).stock_qty) == 92
    assert await _balance(db_session, outlet) == round(done["total"] / 2, 2)
    too_many = await ac.post(url, headers=h, json={"lines": [{"line_id": line["id"], "quantity": 6}], "reason": "other"})
    assert too_many.status_code == 409
    await _trial_balance_is_even(ac, h)


@pytest.mark.asyncio
async def test_loading_cannot_promise_the_same_stock_twice(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    product = await _product(db_session, seed, stock=10)
    outlet = await _outlet(ac, h)
    route = (await ac.post("/api/v1/fmcg/routes", headers=h, json={"code": f"R{uuid4().hex[:5]}", "name": "North"})).json()["data"]
    dispatch = (await ac.post("/api/v1/fmcg/dispatches", headers=h, json={"route_id": route["id"]})).json()["data"]
    a = await _order(ac, h, outlet, product, qty=8)
    b = await _order(ac, h, outlet, product, qty=8)
    body = {"dispatch_id": dispatch["id"]}
    assert (await ac.post(f"{ORDERS}/{a['id']}/load", headers=h, json=body)).status_code == 200
    assert (await ac.post(f"{ORDERS}/{b['id']}/load", headers=h, json=body)).status_code == 409


@pytest.mark.asyncio
async def test_failed_delivery_goes_back_and_moves_nothing(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    product = await _product(db_session, seed)
    outlet = await _outlet(ac, h)
    route = (await ac.post("/api/v1/fmcg/routes", headers=h, json={"code": f"R{uuid4().hex[:5]}", "name": "East"})).json()["data"]
    dispatch = (await ac.post("/api/v1/fmcg/dispatches", headers=h, json={"route_id": route["id"]})).json()["data"]
    order = await _order(ac, h, outlet, product)
    await ac.post(f"{ORDERS}/{order['id']}/load", headers=h, json={"dispatch_id": dispatch["id"]})
    r = await ac.post(f"{ORDERS}/{order['id']}/failed", headers=h, json={"reason": "Shop was shut"})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["status"] == "booked" and r.json()["data"]["dispatch_id"] is None
    db_session.expire_all()
    assert float((await db_session.get(m.Product, product.id)).stock_qty) == 100


@pytest.mark.asyncio
async def test_settling_a_dispatch_shows_the_cash_gap_and_unloads(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    product = await _product(db_session, seed)
    outlet = await _outlet(ac, h)
    route = (await ac.post("/api/v1/fmcg/routes", headers=h, json={"code": f"R{uuid4().hex[:5]}", "name": "West"})).json()["data"]
    dispatch = (await ac.post("/api/v1/fmcg/dispatches", headers=h, json={"route_id": route["id"]})).json()["data"]
    sold = await _order(ac, h, outlet, product, qty=5, terms="cash")
    left = await _order(ac, h, outlet, product, qty=5)
    body = {"dispatch_id": dispatch["id"]}
    await ac.post(f"{ORDERS}/{sold['id']}/load", headers=h, json=body)
    await ac.post(f"{ORDERS}/{left['id']}/load", headers=h, json=body)
    await ac.post(f"{ORDERS}/{sold['id']}/deliver", headers=h, json={"payment_method": "cash"})
    r = await ac.post(
        f"/api/v1/fmcg/dispatches/{dispatch['id']}/settle", headers=h, json={"counted_cash": sold["total"] - 5}
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["expected_cash"] == sold["total"] and data["over_short"] == -5 and data["orders_back"] == 1
    rows = {o["id"]: o for o in (await ac.get(ORDERS, headers=h)).json()["data"]}
    assert rows[left["id"]]["status"] == "booked"
    again = await ac.post(f"/api/v1/fmcg/dispatches/{dispatch['id']}/settle", headers=h, json={"counted_cash": 0})
    assert again.status_code == 409


@pytest.mark.asyncio
async def test_cancelling_a_delivered_order_is_refused(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    product = await _product(db_session, seed)
    outlet = await _outlet(ac, h)
    order = await _order(ac, h, outlet, product)
    await ac.post(f"{ORDERS}/{order['id']}/deliver", headers=h, json={})
    r = await ac.post(f"{ORDERS}/{order['id']}/cancel", headers=h, json={"reason": "Changed mind"})
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_reports_and_tax_read_delivered_sales(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    product = await _product(db_session, seed)
    outlet = await _outlet(ac, h)
    order = await _order(ac, h, outlet, product, qty=10)
    await ac.post(f"{ORDERS}/{order['id']}/deliver", headers=h, json={})
    data = (await ac.get("/api/v1/fmcg/reports", headers=h)).json()["data"]
    assert data["delivered_orders"] == 1
    assert data["revenue"] == round(order["total"] - order["tax"], 2)
    assert data["cost_of_sales"] == 60
    assert data["aging"]["total"] == order["total"]
    tax = (await ac.get("/api/v1/reports/tax", headers=h)).json()["data"]
    assert tax["output_tax"] == order["tax"]
    assert (await ac.get("/api/v1/fmcg/today", headers=h)).json()["data"]["delivered_today"] == 1


def test_each_role_has_its_own_job():
    from fastapi import HTTPException

    def can(role, area):
        try:
            fmcg_orders.job({"role": role}, area)
            return True
        except HTTPException:
            return False

    assert can("fmcg_rep", "orders") and can("fmcg_rep", "outlets") and can("fmcg_rep", "collect")
    assert not can("fmcg_rep", "deliver") and not can("fmcg_rep", "correct") and not can("fmcg_rep", "dispatch")
    assert can("fmcg_driver", "deliver") and can("fmcg_driver", "collect") and can("fmcg_driver", "returns")
    assert not can("fmcg_driver", "orders") and not can("fmcg_driver", "correct")
    for area in ("outlets", "orders", "deliver", "collect", "returns", "dispatch", "correct"):
        assert can("fmcg_manager", area)


@pytest.mark.asyncio
async def test_other_industries_cannot_sell_on_the_fmcg_desk(client, seeded, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "bakery")
    h = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    assert (await ac.get(ORDERS, headers=h)).status_code == 403


@pytest.mark.asyncio
async def test_an_fmcg_company_cannot_use_the_retail_till(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    assert (await ac.get("/api/v1/pos/sessions", headers=h)).status_code == 403


@pytest.mark.asyncio
async def test_one_distributor_cannot_touch_anothers_orders(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    theirs = m.Party(tenant_id=seed["t2"].id, kind="customer", name="Theirs", status="active")
    db_session.add(theirs)
    await db_session.commit()
    product = await _product(db_session, seed)
    r = await ac.post(ORDERS, headers=h, json={"customer_id": theirs.id, "lines": [{"product_id": product.id, "quantity": 1}]})
    assert r.status_code == 404
    other = m.FmcgOrder(tenant_id=seed["t2"].id, order_number="FO-X", customer_id=theirs.id, terms="credit", status="booked")
    db_session.add(other)
    await db_session.commit()
    assert (await ac.post(f"{ORDERS}/{other.id}/deliver", headers=h, json={})).status_code == 404
