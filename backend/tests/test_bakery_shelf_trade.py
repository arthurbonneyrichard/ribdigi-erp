"""Bakery: shelf life and day-old prices, allergens and labels, recipe units, shelf levels,
trade customers, suppliers, and more than one till."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from app import models as m
from app.security import hash_password, permissions_for_role
from tests.conftest import auth_headers
from tests.test_bakery_desk import _balances, _bake, _bread, _moved, _open_till, _owner, _product, _stock


async def _details(ac, h, product, **body):
    r = await ac.put(f"/api/v1/bakery/items/{product.id}/details", headers=h, json=body)
    assert r.status_code == 200, r.text
    return r.json()["data"]


async def _staff(ac, seed, db_session, role):
    email = f"{role}-{uuid4().hex[:6]}@alpha.example.com"
    db_session.add(
        m.User(
            tenant_id=seed["t1"].id, email=email, full_name=role.title(), password_hash=hash_password("SecurePass123!"),
            role=role, email_verified=True, permissions=permissions_for_role(role),
        )
    )
    await db_session.commit()
    return await auth_headers(ac, email=email, tenant_slug="alpha")


# --- Shelf life and day-old ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_bake_gets_its_best_before_and_old_bread_sells_at_the_day_old_price(client, seeded, db_session):
    ac, seed = client
    h = await _owner(ac, seed, db_session)
    _flour, loaf, recipe = await _bread(ac, h, db_session, seed, price=10)
    await _details(ac, h, loaf, shelf_life_days=2, day_old_discount_pct=40)
    old = await _bake(ac, h, recipe)
    assert old["best_before"] == (date.today() + timedelta(days=2)).isoformat()
    # The first bake was yesterday's.
    batch = await db_session.get(m.BakeryBatch, old["id"])
    batch.created_at = datetime.utcnow() - timedelta(days=1)
    batch.best_before = date.today() + timedelta(days=1)
    await db_session.commit()
    await _bake(ac, h, recipe)  # ten fresh today
    shelf = (await ac.get("/api/v1/bakery/shelf", headers=h)).json()["data"]
    states = {s["state"]: s["quantity"] for s in shelf if s["product_id"] == loaf.id}
    assert states == {"fresh": 10, "day_old": 10}
    await _open_till(ac, h)
    cashier = await _staff(ac, seed, db_session, "bakery_cashier")
    r = await ac.post(
        "/api/v1/bakery/sales", headers=cashier,
        json={"lines": [{"product_id": loaf.id, "quantity": 4, "day_old": True}]},
    )
    assert r.status_code == 200, r.text
    sale = r.json()["data"]
    assert sale["total"] == 24  # 40% off, allowed for a cashier because a manager set it
    assert sale["discount_reason"] == "Day-old"
    too_many = await ac.post(
        "/api/v1/bakery/sales", headers=cashier,
        json={"lines": [{"product_id": loaf.id, "quantity": 7, "day_old": True}]},
    )
    assert too_many.status_code == 409, too_many.text


@pytest.mark.asyncio
async def test_bread_past_its_date_is_flagged_and_left_out_of_the_bake_list(client, seeded, db_session):
    ac, seed = client
    h = await _owner(ac, seed, db_session)
    _flour, loaf, recipe = await _bread(ac, h, db_session, seed, price=10)
    await _details(ac, h, loaf, shelf_life_days=1, par_level=10)
    made = await _bake(ac, h, recipe)
    batch = await db_session.get(m.BakeryBatch, made["id"])
    batch.created_at = datetime.utcnow() - timedelta(days=3)
    batch.best_before = date.today() - timedelta(days=2)
    await db_session.commit()
    summary = (await ac.get("/api/v1/bakery/summary", headers=h)).json()["data"]
    assert summary["shelf"]["expired"] == 10
    assert any("Past its date" in a["text"] for a in summary["attention"])
    row = next(r for r in summary["to_bake"] if r["product_id"] == loaf.id)
    assert row["on_hand"] == 0 and row["shelf_level"] == 10 and row["to_bake"] == 10


# --- Shelf level ------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_bake_list_tops_the_shelf_up_to_its_level(client, seeded, db_session):
    ac, seed = client
    h = await _owner(ac, seed, db_session)
    _flour, loaf, recipe = await _bread(ac, h, db_session, seed, price=10)
    await _details(ac, h, loaf, par_level=25)
    await _bake(ac, h, recipe)  # ten on the shelf
    summary = (await ac.get("/api/v1/bakery/summary", headers=h)).json()["data"]
    row = next(r for r in summary["to_bake"] if r["product_id"] == loaf.id)
    assert row["shelf_level"] == 25 and row["to_bake"] == 15


# --- Allergens and labels -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_label_lists_ingredients_by_weight_and_allergens_from_every_ingredient(client, seeded, db_session):
    ac, seed = client
    h = await _owner(ac, seed, db_session)
    flour = await _product(db_session, seed, "Wheat flour", cost=5, stock=100)
    butter = await _product(db_session, seed, "Butter", cost=30, stock=10)
    loaf = await _product(db_session, seed, "Butter bread", price=12)
    await _details(ac, h, flour, allergens=["gluten"], stock_unit="kg")
    await _details(ac, h, butter, allergens=["milk"], stock_unit="kg")
    await _details(ac, h, loaf, shelf_life_days=3, net_weight="400 g", allergens=["eggs"])
    r = await ac.post(
        "/api/v1/bakery/recipes", headers=h,
        json={
            "product_id": loaf.id, "name": "Butter bread", "yield_qty": 10,
            "lines": [
                {"ingredient_id": butter.id, "quantity": 300, "unit": "g"},
                {"ingredient_id": flour.id, "quantity": 2, "unit": "kg"},
            ],
        },
    )
    assert r.status_code == 200, r.text
    details = (await ac.get(f"/api/v1/bakery/items/{loaf.id}/details", headers=h)).json()["data"]
    assert details["label"]["ingredients"].startswith(flour.name)
    assert details["label"]["allergens"] == ["eggs", "gluten", "milk"]
    page = await ac.get(f"/api/v1/bakery/items/{loaf.id}/label?copies=2", headers=h)
    assert page.status_code == 200
    assert page.text.count('class="lbl"') == 2
    assert f"<b>{flour.name}</b>" in page.text and "Milk" in page.text and "400 g" in page.text
    bad = await ac.put(f"/api/v1/bakery/items/{loaf.id}/details", headers=h, json={"allergens": ["chocolate"]})
    assert bad.status_code == 422


# --- Units ------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_flour_bought_by_the_bag_and_used_by_the_gram(client, seeded, db_session):
    ac, seed = client
    h = await _owner(ac, seed, db_session)
    flour = await _product(db_session, seed, "Flour")
    loaf = await _product(db_session, seed, "Loaf", price=5)
    await _details(ac, h, flour, stock_unit="kg", purchase_unit="50 kg bag", units_per_purchase=50)
    r = await ac.post(
        "/api/v1/bakery/stock/receive", headers=h,
        json={"product_id": flour.id, "quantity": 2, "unit_cost": 600, "paid_with": "cash", "in_purchase_units": True},
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["total"] == 1200
    assert await _stock(db_session, flour) == 100
    await db_session.refresh(flour)
    assert float(flour.cost_price) == 12  # per kg
    recipe = await ac.post(
        "/api/v1/bakery/recipes", headers=h,
        json={"product_id": loaf.id, "name": "Rolls", "yield_qty": 10, "lines": [{"ingredient_id": flour.id, "quantity": 500, "unit": "g"}]},
    )
    assert recipe.status_code == 200, recipe.text
    assert recipe.json()["data"]["lines"][0]["quantity"] == 0.5
    assert recipe.json()["data"]["batch_cost"] == 6
    await _bake(ac, h, recipe.json()["data"])
    assert await _stock(db_session, flour) == 99.5
    wrong = await ac.post(
        "/api/v1/bakery/recipes", headers=h,
        json={"product_id": loaf.id, "name": "Rolls", "yield_qty": 10, "lines": [{"ingredient_id": flour.id, "quantity": 1, "unit": "ml"}]},
    )
    assert wrong.status_code == 422


# --- Trade customers --------------------------------------------------------------------------


async def _customer(ac, h, **body):
    r = await ac.post("/api/v1/bakery/trade/customers", headers=h, json={"name": f"Corner Shop {uuid4().hex[:4]}", **body})
    assert r.status_code == 200, r.text
    return r.json()["data"]


@pytest.mark.asyncio
async def test_standing_orders_make_one_invoice_a_day_on_credit(client, seeded, db_session):
    ac, seed = client
    h = await _owner(ac, seed, db_session)
    _flour, loaf, recipe = await _bread(ac, h, db_session, seed, price=10)
    await _bake(ac, h, recipe, batches=5)  # fifty
    shop = await _customer(ac, h, trade_discount_pct=20, terms_days=14)
    r = await ac.put(
        f"/api/v1/bakery/trade/customers/{shop['id']}/standing", headers=h,
        json={"product_id": loaf.id, "quantity": 20, "days": "1111111"},
    )
    assert r.status_code == 200, r.text
    summary = (await ac.get("/api/v1/bakery/summary", headers=h)).json()["data"]
    assert next(x for x in summary["to_bake"] if x["product_id"] == loaf.id)["trade"] == 20
    before = await _balances(ac, h)
    run = await ac.post("/api/v1/bakery/trade/run", headers=h)
    assert run.status_code == 200, run.text
    assert len(run.json()["data"]["made"]) == 1
    assert run.json()["data"]["made"][0]["total"] == 160  # 20 x 10 less 20%
    again = (await ac.post("/api/v1/bakery/trade/run", headers=h)).json()["data"]
    assert again["made"] == [] and again["skipped"][0]["reason"] == "Already made today"
    after = await _balances(ac, h)
    assert _moved(before, after, "1100") == 160
    assert _moved(before, after, "4000") == -160
    assert await _stock(db_session, loaf) == 30
    invoices = (await ac.get(f"/api/v1/bakery/trade/invoices?customer_id={shop['id']}", headers=h)).json()["data"]
    assert invoices[0]["due_date"] == (date.today() + timedelta(days=14)).isoformat()
    page = await ac.get(f"/api/v1/bakery/trade/invoices/{invoices[0]['id']}/print", headers=h)
    assert page.status_code == 200 and invoices[0]["invoice_number"] in page.text
    report = (await ac.get("/api/v1/bakery/reports", headers=h)).json()["data"]
    assert report["trade_revenue"] == 160


@pytest.mark.asyncio
async def test_a_trade_payment_clears_the_oldest_invoice_and_shows_on_the_statement(client, seeded, db_session):
    ac, seed = client
    h = await _owner(ac, seed, db_session)
    _flour, loaf, recipe = await _bread(ac, h, db_session, seed, price=10)
    await _bake(ac, h, recipe, batches=3)
    shop = await _customer(ac, h)
    for qty in (5, 3):
        r = await ac.post(
            "/api/v1/bakery/trade/invoices", headers=h,
            json={"customer_id": shop["id"], "lines": [{"product_id": loaf.id, "quantity": qty}]},
        )
        assert r.status_code == 200, r.text
    too_much = await ac.post(
        f"/api/v1/bakery/trade/customers/{shop['id']}/payments", headers=h, json={"amount": 100, "method": "bank_transfer"}
    )
    assert too_much.status_code == 422
    before = await _balances(ac, h)
    r = await ac.post(
        f"/api/v1/bakery/trade/customers/{shop['id']}/payments", headers=h,
        json={"amount": 60, "method": "mobile_money", "reference": "MoMo 1234"},
    )
    assert r.status_code == 200, r.text
    after = await _balances(ac, h)
    assert _moved(before, after, "1100") == -60
    assert _moved(before, after, "1010") == 60
    invoices = (await ac.get(f"/api/v1/bakery/trade/invoices?customer_id={shop['id']}", headers=h)).json()["data"]
    by_total = {i["total"]: i for i in invoices}
    assert by_total[50]["status"] == "paid"
    assert by_total[30]["status"] == "part_paid" and by_total[30]["balance"] == 20
    statement = (await ac.get(f"/api/v1/bakery/trade/customers/{shop['id']}/statement", headers=h)).json()["data"]
    assert statement["opening_balance"] == 0
    assert statement["closing_balance"] == 20
    assert len(statement["lines"]) == 3
    assert statement["owed_by_age"]["current"] == 20


@pytest.mark.asyncio
async def test_a_customer_over_their_limit_needs_a_manager(client, seeded, db_session):
    ac, seed = client
    h = await _owner(ac, seed, db_session)
    _flour, loaf, recipe = await _bread(ac, h, db_session, seed, price=10)
    await _bake(ac, h, recipe, batches=2)
    shop = await _customer(ac, h, credit_limit=50)
    cashier = await _staff(ac, seed, db_session, "bakery_cashier")
    body = {"customer_id": shop["id"], "lines": [{"product_id": loaf.id, "quantity": 6}], "override_limit": True}
    refused = await ac.post("/api/v1/bakery/trade/invoices", headers=cashier, json=body)
    assert refused.status_code == 409 and refused.json()["detail"]["code"] == "CREDIT_LIMIT"
    allowed = await ac.post("/api/v1/bakery/trade/invoices", headers=h, json=body)
    assert allowed.status_code == 200, allowed.text
    await ac.post(
        "/api/v1/tax/rates", headers=h, json={"name": "VAT", "rate": 20, "pricing_mode": "exclusive", "is_default": True}
    )
    taxed = await ac.post(
        "/api/v1/bakery/trade/invoices", headers=h,
        json={"customer_id": shop["id"], "lines": [{"product_id": loaf.id, "quantity": 1}], "override_limit": True},
    )
    assert taxed.status_code == 200 and taxed.json()["data"]["tax"] == 2
    assert (await ac.get("/api/v1/reports/tax", headers=h)).json()["data"]["output_tax"] == pytest.approx(2)
    void = await ac.post(
        f"/api/v1/bakery/trade/invoices/{allowed.json()['data']['id']}/void", headers=h,
        json={"reason": "Delivered to the wrong shop", "restock": True},
    )
    assert void.status_code == 200, void.text
    assert await _stock(db_session, loaf) == 19  # the six came back; one taxed loaf is still out


# --- Suppliers --------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_flour_bought_on_credit_is_owed_to_the_supplier_until_paid(client, seeded, db_session):
    ac, seed = client
    h = await _owner(ac, seed, db_session)
    flour = await _product(db_session, seed, "Flour")
    nobody = await ac.post(
        "/api/v1/bakery/stock/receive", headers=h,
        json={"product_id": flour.id, "quantity": 10, "unit_cost": 5, "paid_with": "credit"},
    )
    assert nobody.status_code == 422
    r = await ac.post(
        "/api/v1/bakery/stock/receive", headers=h,
        json={"product_id": flour.id, "quantity": 10, "unit_cost": 5, "tax": 5, "paid_with": "credit", "supplier": "Mill Co", "bill_number": "INV-77"},
    )
    assert r.status_code == 200, r.text
    suppliers = (await ac.get("/api/v1/bakery/suppliers", headers=h)).json()["data"]
    mill = next(s for s in suppliers if s["name"] == "Mill Co")
    assert mill["owed"] == 55
    await _open_till(ac, h, cash=20)
    short = await ac.post(
        f"/api/v1/bakery/suppliers/{mill['id']}/payments", headers=h, json={"amount": 30, "method": "cash", "from_till": True}
    )
    assert short.status_code == 409  # the drawer holds 20
    before = await _balances(ac, h)
    paid = await ac.post(f"/api/v1/bakery/suppliers/{mill['id']}/payments", headers=h, json={"amount": 55, "method": "bank_transfer"})
    assert paid.status_code == 200, paid.text
    after = await _balances(ac, h)
    assert _moved(before, after, "2000") == 55
    assert _moved(before, after, "1010") == -55
    assert next(s for s in (await ac.get("/api/v1/bakery/suppliers", headers=h)).json()["data"] if s["id"] == mill["id"])["owed"] == 0


# --- More than one till -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_two_tills_keep_their_own_drawers(client, seeded, db_session):
    ac, seed = client
    h = await _owner(ac, seed, db_session)
    _flour, loaf, recipe = await _bread(ac, h, db_session, seed, price=10)
    await _bake(ac, h, recipe)
    front = (await ac.post("/api/v1/bakery/till/shift/open", headers=h, json={"opening_cash": 50, "till_name": "Front"})).json()["data"]
    twice = await ac.post("/api/v1/bakery/till/shift/open", headers=h, json={"till_name": "Back"})
    assert twice.status_code == 409  # one person, one till
    cashier = await _staff(ac, seed, db_session, "bakery_cashier")
    same_name = await ac.post("/api/v1/bakery/till/shift/open", headers=cashier, json={"till_name": "front"})
    assert same_name.status_code == 409
    back = (await ac.post("/api/v1/bakery/till/shift/open", headers=cashier, json={"opening_cash": 10, "till_name": "Back"})).json()["data"]
    sale = {"lines": [{"product_id": loaf.id, "quantity": 2}]}
    assert (await ac.post("/api/v1/bakery/sales", headers=cashier, json=sale)).status_code == 200
    assert (await ac.post("/api/v1/bakery/sales", headers=h, json=sale)).status_code == 200
    assert (await ac.post("/api/v1/bakery/sales", headers={**h, "X-Bakery-Till": back["id"]}, json=sale)).status_code == 200
    tills = {t["till_name"]: t for t in (await ac.get("/api/v1/bakery/tills", headers=h)).json()["data"]}
    assert tills["Front"]["expected_cash"] == 70
    assert tills["Back"]["expected_cash"] == 50
    baker = await _staff(ac, seed, db_session, "bakery_manager")
    unsure = await ac.post("/api/v1/bakery/sales", headers=baker, json=sale)
    assert unsure.status_code == 409 and unsure.json()["detail"]["code"] == "TILL_CHOOSE"
    closed = await ac.post("/api/v1/bakery/till/shift/close", headers=cashier, json={"counted_cash": 50})
    assert closed.status_code == 200 and closed.json()["data"]["id"] == back["id"]
    assert (await ac.get("/api/v1/bakery/tills", headers=h)).json()["data"][0]["id"] == front["id"]
