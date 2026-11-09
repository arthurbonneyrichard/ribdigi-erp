"""A bakery's day: recipes, baking, the counter, pre-orders and waste, with the books and drawer in step."""

from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from app import models as m
from tests.conftest import auth_headers, set_tenant_industry


async def _owner(ac, seed, db_session):
    # The company's own admin, not a platform login: platform roles skip the industry gates.
    await set_tenant_industry(db_session, seed["t1"], "bakery")
    return await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")


async def _product(db_session, seed, name, *, cost=0, price=0, stock=0):
    row = m.Product(
        tenant_id=seed["t1"].id, name=f"{name} {uuid4().hex[:4]}", sku=f"B{uuid4().hex[:7]}",
        cost_price=cost, selling_price=price, stock_qty=stock, is_active=True, tracks_batches=False,
    )
    db_session.add(row)
    await db_session.commit()
    return row


async def _bread(ac, h, db_session, seed, *, price=10, flour_stock=100):
    """Two kilos of flour at 5 a kilo makes ten loaves: 1 a loaf."""
    flour = await _product(db_session, seed, "Flour", cost=5, stock=flour_stock)
    loaf = await _product(db_session, seed, "Loaf", price=price)
    r = await ac.post(
        "/api/v1/bakery/recipes", headers=h,
        json={
            "product_id": loaf.id, "name": "Tea bread", "yield_qty": 10,
            "lines": [{"ingredient_id": flour.id, "quantity": 2}],
        },
    )
    assert r.status_code == 200, r.text
    return flour, loaf, r.json()["data"]


async def _bake(ac, h, recipe, batches=1):
    r = await ac.post("/api/v1/bakery/batches", headers=h, json={"recipe_id": recipe["id"], "batches": batches})
    assert r.status_code == 200, r.text
    return r.json()["data"]


async def _open_till(ac, h, cash=100):
    r = await ac.post("/api/v1/bakery/till/shift/open", headers=h, json={"opening_cash": cash})
    assert r.status_code == 200, r.text


async def _sell(ac, h, loaf, qty=1, method="cash"):
    r = await ac.post(
        "/api/v1/bakery/sales", headers=h,
        json={"payment_method": method, "lines": [{"product_id": loaf.id, "quantity": qty}]},
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]


async def _order(ac, h, loaf, *, qty=5, deposit=0, method="cash", days=2):
    r = await ac.post(
        "/api/v1/bakery/orders", headers=h,
        json={
            "customer_name": "Ama Boateng",
            "due_date": (date.today() + timedelta(days=days)).isoformat(),
            "lines": [{"product_id": loaf.id, "quantity": qty, "note": "Happy birthday Kofi"}],
            "deposit": deposit,
            "deposit_method": method if deposit else None,
        },
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]


async def _balances(ac, h) -> dict[str, float]:
    tb = (await ac.get("/api/v1/accounting/trial-balance", headers=h)).json()["data"]
    assert tb["total_debit"] == pytest.approx(tb["total_credit"])
    rows = tb.get("rows") or tb.get("accounts") or []
    return {r["code"]: round(float(r.get("debit") or 0) - float(r.get("credit") or 0), 2) for r in rows}


def _moved(before, after, code):
    return round(after.get(code, 0) - before.get(code, 0), 2)


async def _stock(db_session, product):
    await db_session.refresh(product)
    return float(product.stock_qty)


async def _shift(ac, h):
    return (await ac.get("/api/v1/bakery/till/shift", headers=h)).json()["data"]


# --- Recipes and baking --------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_recipe_shows_what_a_loaf_really_costs(client, seeded, db_session):
    ac, seed = client
    h = await _owner(ac, seed, db_session)
    _flour, _loaf, recipe = await _bread(ac, h, db_session, seed, price=4)
    assert recipe["batch_cost"] == 10
    assert recipe["unit_cost"] == 1
    assert recipe["margin_percent"] == 75


@pytest.mark.asyncio
async def test_baking_moves_flour_into_loaves(client, seeded, db_session):
    ac, seed = client
    h = await _owner(ac, seed, db_session)
    flour, loaf, recipe = await _bread(ac, h, db_session, seed)
    batch = await _bake(ac, h, recipe, batches=2)
    assert batch["made_qty"] == 20
    assert batch["unit_cost"] == 1
    assert await _stock(db_session, flour) == 96
    assert await _stock(db_session, loaf) == 20
    await db_session.refresh(loaf)
    assert float(loaf.cost_price) == 1


@pytest.mark.asyncio
async def test_baking_without_enough_flour_names_what_is_short_and_changes_nothing(client, seeded, db_session):
    ac, seed = client
    h = await _owner(ac, seed, db_session)
    flour, loaf, recipe = await _bread(ac, h, db_session, seed, flour_stock=1)
    r = await ac.post("/api/v1/bakery/batches", headers=h, json={"recipe_id": recipe["id"]})
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["code"] == "INGREDIENT_SHORT"
    assert "Flour" in r.json()["detail"]["message"]
    assert await _stock(db_session, flour) == 1
    assert await _stock(db_session, loaf) == 0


@pytest.mark.asyncio
async def test_a_dearer_batch_averages_into_the_cost(client, seeded, db_session):
    ac, seed = client
    h = await _owner(ac, seed, db_session)
    flour, loaf, recipe = await _bread(ac, h, db_session, seed)
    await _bake(ac, h, recipe)
    flour.cost_price = 15  # flour tripled, so the next ten loaves cost 3 each
    await db_session.commit()
    await _bake(ac, h, recipe)
    await db_session.refresh(loaf)
    assert float(loaf.cost_price) == 2


@pytest.mark.asyncio
async def test_a_recipe_cannot_use_itself_or_repeat_an_ingredient(client, seeded, db_session):
    ac, seed = client
    h = await _owner(ac, seed, db_session)
    flour = await _product(db_session, seed, "Flour", cost=5, stock=10)
    loaf = await _product(db_session, seed, "Loaf", price=5)
    for lines in (
        [{"ingredient_id": loaf.id, "quantity": 1}],
        [{"ingredient_id": flour.id, "quantity": 1}, {"ingredient_id": flour.id, "quantity": 2}],
    ):
        r = await ac.post(
            "/api/v1/bakery/recipes", headers=h,
            json={"product_id": loaf.id, "name": "Bad", "yield_qty": 1, "lines": lines},
        )
        assert r.status_code == 422, r.text


# --- The counter ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_money_needs_an_open_till(client, seeded, db_session):
    ac, seed = client
    h = await _owner(ac, seed, db_session)
    _flour, loaf, recipe = await _bread(ac, h, db_session, seed)
    await _bake(ac, h, recipe)
    r = await ac.post(
        "/api/v1/bakery/sales", headers=h, json={"lines": [{"product_id": loaf.id, "quantity": 1}]}
    )
    assert r.status_code == 409, r.text


@pytest.mark.asyncio
async def test_a_sale_reaches_stock_the_books_and_the_drawer(client, seeded, db_session):
    ac, seed = client
    h = await _owner(ac, seed, db_session)
    _flour, loaf, recipe = await _bread(ac, h, db_session, seed, price=10)
    await _bake(ac, h, recipe)
    await _open_till(ac, h, cash=100)
    before = await _balances(ac, h)
    sale = await _sell(ac, h, loaf, qty=3)
    assert sale["total"] == 30
    assert await _stock(db_session, loaf) == 7
    after = await _balances(ac, h)
    assert _moved(before, after, "1000") == 30
    assert _moved(before, after, "4000") == -30
    assert _moved(before, after, "5000") == 3
    assert _moved(before, after, "1200") == -3
    shift = await _shift(ac, h)
    assert shift["cash_taken"] == 30
    assert shift["expected_cash"] == 130


@pytest.mark.asyncio
async def test_the_price_comes_from_the_catalogue_not_the_request(client, seeded, db_session):
    ac, seed = client
    h = await _owner(ac, seed, db_session)
    _flour, loaf, recipe = await _bread(ac, h, db_session, seed, price=10)
    await _bake(ac, h, recipe)
    await _open_till(ac, h)
    r = await ac.post(
        "/api/v1/bakery/sales", headers=h,
        json={"lines": [{"product_id": loaf.id, "quantity": 1, "unit_price": 0.01}]},
    )
    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_selling_more_than_is_baked_is_refused_with_nothing_half_done(client, seeded, db_session):
    ac, seed = client
    h = await _owner(ac, seed, db_session)
    _flour, loaf, recipe = await _bread(ac, h, db_session, seed)
    await _bake(ac, h, recipe)
    await _open_till(ac, h)
    r = await ac.post(
        "/api/v1/bakery/sales", headers=h, json={"lines": [{"product_id": loaf.id, "quantity": 11}]}
    )
    assert r.status_code == 409, r.text
    assert await _stock(db_session, loaf) == 10
    assert (await _shift(ac, h))["cash_taken"] == 0


@pytest.mark.asyncio
async def test_a_card_sale_does_not_touch_the_drawer(client, seeded, db_session):
    ac, seed = client
    h = await _owner(ac, seed, db_session)
    _flour, loaf, recipe = await _bread(ac, h, db_session, seed)
    await _bake(ac, h, recipe)
    await _open_till(ac, h, cash=50)
    await _sell(ac, h, loaf, method="card")
    shift = await _shift(ac, h)
    assert shift["expected_cash"] == 50
    assert shift["by_method"]["card"] == 10


@pytest.mark.asyncio
async def test_closing_the_till_shows_over_or_short(client, seeded, db_session):
    ac, seed = client
    h = await _owner(ac, seed, db_session)
    _flour, loaf, recipe = await _bread(ac, h, db_session, seed)
    await _bake(ac, h, recipe)
    await _open_till(ac, h, cash=100)
    await _sell(ac, h, loaf, qty=2)
    r = await ac.post("/api/v1/bakery/till/shift/close", headers=h, json={"counted_cash": 115})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["expected_cash"] == 120
    assert r.json()["data"]["over_short"] == -5


@pytest.mark.asyncio
async def test_a_refund_on_a_later_shift_leaves_that_drawer(client, seeded, db_session):
    ac, seed = client
    h = await _owner(ac, seed, db_session)
    _flour, loaf, recipe = await _bread(ac, h, db_session, seed)
    await _bake(ac, h, recipe)
    await _open_till(ac, h, cash=0)
    sale = await _sell(ac, h, loaf, qty=2)
    await ac.post("/api/v1/bakery/till/shift/close", headers=h, json={"counted_cash": 20})
    await _open_till(ac, h, cash=200)
    before = await _balances(ac, h)
    r = await ac.post(f"/api/v1/bakery/sales/{sale['id']}/refund", headers=h, json={"reason": "Burnt underneath"})
    assert r.status_code == 200, r.text
    shift = await _shift(ac, h)
    assert shift["cash_taken"] == -20
    assert shift["expected_cash"] == 180
    after = await _balances(ac, h)
    assert _moved(before, after, "1000") == -20
    # Food that left the counter is not back on the shelf.
    assert await _stock(db_session, loaf) == 8
    again = await ac.post(f"/api/v1/bakery/sales/{sale['id']}/refund", headers=h, json={"reason": "Twice"})
    assert again.status_code == 409, again.text


# --- Pre-orders ----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_deposit_is_held_for_the_customer_until_collection(client, seeded, db_session):
    ac, seed = client
    h = await _owner(ac, seed, db_session)
    _flour, loaf, recipe = await _bread(ac, h, db_session, seed, price=10)
    await _bake(ac, h, recipe)
    await _open_till(ac, h, cash=0)
    before = await _balances(ac, h)
    order = await _order(ac, h, loaf, qty=5, deposit=20)
    assert order["balance"] == 30
    mid = await _balances(ac, h)
    assert _moved(before, mid, "1000") == 20
    assert _moved(before, mid, "1100") == -20
    assert _moved(before, mid, "4000") == 0  # not revenue yet
    assert await _stock(db_session, loaf) == 10  # not taken yet

    r = await ac.post(f"/api/v1/bakery/orders/{order['id']}/collect", headers=h, json={"payment_method": "cash"})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["status"] == "collected"
    after = await _balances(ac, h)
    assert _moved(before, after, "1000") == 50
    assert _moved(before, after, "1100") == 0
    assert _moved(before, after, "4000") == -50
    assert _moved(before, after, "5000") == 5
    assert await _stock(db_session, loaf) == 5
    assert (await _shift(ac, h))["cash_taken"] == 50

    twice = await ac.post(f"/api/v1/bakery/orders/{order['id']}/collect", headers=h, json={"payment_method": "cash"})
    assert twice.status_code == 409, twice.text


@pytest.mark.asyncio
async def test_a_fully_paid_order_collects_with_no_money_at_the_door(client, seeded, db_session):
    ac, seed = client
    h = await _owner(ac, seed, db_session)
    _flour, loaf, recipe = await _bread(ac, h, db_session, seed, price=10)
    await _bake(ac, h, recipe)
    await _open_till(ac, h, cash=0)
    order = await _order(ac, h, loaf, qty=2, deposit=20)
    await ac.post("/api/v1/bakery/till/shift/close", headers=h, json={"counted_cash": 20})
    r = await ac.post(f"/api/v1/bakery/orders/{order['id']}/collect", headers=h, json={})
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_a_deposit_cannot_be_more_than_the_order(client, seeded, db_session):
    ac, seed = client
    h = await _owner(ac, seed, db_session)
    _flour, loaf, recipe = await _bread(ac, h, db_session, seed, price=10)
    await _open_till(ac, h)
    r = await ac.post(
        "/api/v1/bakery/orders", headers=h,
        json={
            "customer_name": "Kofi", "due_date": date.today().isoformat(), "deposit": 500, "deposit_method": "cash",
            "lines": [{"product_id": loaf.id, "quantity": 1}],
        },
    )
    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_a_cancelled_order_refunds_or_keeps_the_deposit(client, seeded, db_session):
    ac, seed = client
    h = await _owner(ac, seed, db_session)
    _flour, loaf, recipe = await _bread(ac, h, db_session, seed, price=10)
    await _open_till(ac, h, cash=0)
    before = await _balances(ac, h)

    one = await _order(ac, h, loaf, deposit=20)
    undecided = await ac.post(f"/api/v1/bakery/orders/{one['id']}/cancel", headers=h, json={"reason": "Party moved"})
    assert undecided.status_code == 422, undecided.text
    r = await ac.post(
        f"/api/v1/bakery/orders/{one['id']}/cancel", headers=h,
        json={"reason": "Party moved", "deposit_action": "refund"},
    )
    assert r.status_code == 200, r.text
    mid = await _balances(ac, h)
    assert _moved(before, mid, "1000") == 0
    assert _moved(before, mid, "1100") == 0
    assert (await _shift(ac, h))["cash_taken"] == 0

    two = await _order(ac, h, loaf, deposit=30)
    r = await ac.post(
        f"/api/v1/bakery/orders/{two['id']}/cancel", headers=h,
        json={"reason": "Never came", "deposit_action": "keep"},
    )
    assert r.status_code == 200, r.text
    after = await _balances(ac, h)
    assert _moved(before, after, "1000") == 30
    assert _moved(before, after, "4000") == -30
    assert _moved(before, after, "1100") == 0


@pytest.mark.asyncio
async def test_the_bake_list_is_what_orders_need_less_what_is_on_the_shelf(client, seeded, db_session):
    ac, seed = client
    h = await _owner(ac, seed, db_session)
    _flour, loaf, recipe = await _bread(ac, h, db_session, seed, price=10)
    await _bake(ac, h, recipe)  # ten on the shelf
    await _order(ac, h, loaf, qty=14, days=1)
    summary = (await ac.get("/api/v1/bakery/summary", headers=h)).json()["data"]
    row = next(r for r in summary["to_bake"] if r["product_id"] == loaf.id)
    assert row["ordered"] == 14
    assert row["on_hand"] == 10
    assert row["to_bake"] == 4


# --- Waste and reports ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_waste_leaves_stock_and_costs_money(client, seeded, db_session):
    ac, seed = client
    h = await _owner(ac, seed, db_session)
    _flour, loaf, recipe = await _bread(ac, h, db_session, seed)
    await _bake(ac, h, recipe)
    before = await _balances(ac, h)
    r = await ac.post(
        "/api/v1/bakery/waste", headers=h, json={"product_id": loaf.id, "quantity": 4, "reason": "unsold"}
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["total_cost"] == 4
    assert await _stock(db_session, loaf) == 6
    after = await _balances(ac, h)
    assert _moved(before, after, "5000") == 4
    assert _moved(before, after, "1200") == -4
    too_much = await ac.post(
        "/api/v1/bakery/waste", headers=h, json={"product_id": loaf.id, "quantity": 7, "reason": "burnt"}
    )
    assert too_much.status_code == 409, too_much.text


@pytest.mark.asyncio
async def test_the_day_adds_up_on_the_report(client, seeded, db_session):
    ac, seed = client
    h = await _owner(ac, seed, db_session)
    _flour, loaf, recipe = await _bread(ac, h, db_session, seed, price=10)
    await _bake(ac, h, recipe)
    await _open_till(ac, h)
    await _sell(ac, h, loaf, qty=5)
    await ac.post("/api/v1/bakery/waste", headers=h, json={"product_id": loaf.id, "quantity": 2, "reason": "unsold"})
    report = (await ac.get("/api/v1/bakery/reports", headers=h)).json()["data"]
    assert report["revenue"] == 50
    assert report["cost_of_sales"] == 5
    assert report["waste_cost"] == 2
    assert report["gross_profit"] == 43
    assert report["gross_margin_percent"] == 86
    assert report["waste_percent_of_baked"] == 20
    assert report["best_sellers"][0]["quantity"] == 5


@pytest.mark.asyncio
async def test_counter_vat_reaches_the_tax_filing(client, seeded, db_session):
    ac, seed = client
    h = await _owner(ac, seed, db_session)
    rate = await ac.post(
        "/api/v1/tax/rates", headers=h,
        json={"name": "VAT", "rate": 20, "pricing_mode": "exclusive", "is_default": True},
    )
    assert rate.status_code == 200, rate.text
    _flour, loaf, recipe = await _bread(ac, h, db_session, seed, price=10)
    await _bake(ac, h, recipe)
    await _open_till(ac, h)
    sale = await _sell(ac, h, loaf, qty=1)
    assert sale["tax"] == 2
    report = (await ac.get("/api/v1/reports/tax", headers=h)).json()["data"]
    assert report["output_tax"] == pytest.approx(2)


# --- Staff and isolation -------------------------------------------------------------------


def _as(role):
    from app.bakery_api import _job

    def allowed(area):
        try:
            _job({"role": role}, area)
        except Exception:
            return False
        return True

    return allowed


def test_each_role_does_its_own_job():
    baker, cashier, manager = _as("bakery_baker"), _as("bakery_cashier"), _as("bakery_manager")
    assert baker("bake") and baker("waste")
    assert not baker("till") and not baker("orders") and not baker("correct")
    assert cashier("till") and cashier("orders") and cashier("waste")
    assert not cashier("bake") and not cashier("correct")
    for area in ("bake", "waste", "till", "orders", "correct"):
        assert manager(area)


@pytest.mark.asyncio
async def test_other_industries_cannot_use_the_bakery(client, seeded, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    h = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    assert (await ac.get("/api/v1/bakery/summary", headers=h)).status_code == 403


@pytest.mark.asyncio
async def test_a_bakery_cannot_use_the_retail_till_or_hotel_desk(client, seeded, db_session):
    ac, seed = client
    h = await _owner(ac, seed, db_session)
    assert (await ac.get("/api/v1/pos/sessions", headers=h)).status_code == 403
    assert (await ac.get("/api/v1/hotel/summary", headers=h)).status_code == 403
    assert (await ac.get("/api/v1/restaurant/orders", headers=h)).status_code == 403


@pytest.mark.asyncio
async def test_one_bakery_cannot_touch_anothers_records(client, seeded, db_session):
    ac, seed = client
    h = await _owner(ac, seed, db_session)
    theirs = m.BakeryOrder(
        tenant_id=seed["t2"].id, order_number="BO-X", customer_name="Theirs", due_date=date.today(), status="booked",
        subtotal=1, tax=0, total=1, deposit=0,
    )
    db_session.add(theirs)
    await db_session.commit()
    r = await ac.post(f"/api/v1/bakery/orders/{theirs.id}/ready", headers=h, json={})
    assert r.status_code == 404, r.text
    rows = (await db_session.execute(select(m.BakeryOrder).where(m.BakeryOrder.id == theirs.id))).scalars().all()
    assert rows[0].status == "booked"


@pytest.mark.asyncio
async def test_a_bakery_comes_back_from_a_restore(client, seeded, db_session):
    import json

    from app import backup as backup_svc

    ac, seed = client
    h = await _owner(ac, seed, db_session)
    _flour, loaf, recipe = await _bread(ac, h, db_session, seed)
    await _bake(ac, h, recipe)
    await _open_till(ac, h)
    await _sell(ac, h, loaf)
    payload, counts = await backup_svc.collect_tenant_payload(db_session, seed["t1"].id)
    for name in ("bakery_recipes", "bakery_batches", "bakery_sales", "bakery_payments", "bakery_till_shifts"):
        assert counts[name] >= 1, name
    report = await backup_svc.apply_restore(db_session, seed["t1"].id, json.loads(json.dumps(payload, default=str)))
    assert report["proof"]["ok"] is True
