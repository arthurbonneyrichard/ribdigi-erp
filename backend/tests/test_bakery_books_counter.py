"""Bakery books and counter: input VAT, expense accounts, till over/short, discounts,
split payment, part refunds, refunding a collected order, and stock counts."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app import models as m
from app.security import hash_password, permissions_for_role
from tests.conftest import auth_headers
from tests.test_bakery_desk import (
    _balances,
    _bake,
    _bread,
    _moved,
    _open_till,
    _order,
    _owner,
    _product,
    _sell,
    _shift,
    _stock,
)


async def _vat(ac, h, rate=20):
    r = await ac.post(
        "/api/v1/tax/rates", headers=h,
        json={"name": "VAT", "rate": rate, "pricing_mode": "exclusive", "is_default": True},
    )
    assert r.status_code == 200, r.text


async def _cashier(ac, seed, db_session):
    email = f"cashier-{uuid4().hex[:6]}@alpha.example.com"
    db_session.add(
        m.User(
            tenant_id=seed["t1"].id, email=email, full_name="Esi", password_hash=hash_password("SecurePass123!"),
            role="bakery_cashier", email_verified=True, permissions=permissions_for_role("bakery_cashier"),
        )
    )
    await db_session.commit()
    return await auth_headers(ac, email=email, tenant_slug="alpha")


# --- Buying in and expenses ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_vat_on_flour_bought_is_claimable_and_not_stock_cost(client, seeded, db_session):
    ac, seed = client
    h = await _owner(ac, seed, db_session)
    flour = await _product(db_session, seed, "Flour")
    before = await _balances(ac, h)
    r = await ac.post(
        "/api/v1/bakery/stock/receive", headers=h,
        json={"product_id": flour.id, "quantity": 10, "unit_cost": 5, "tax": 7.5, "paid_with": "cash"},
    )
    assert r.status_code == 200, r.text
    after = await _balances(ac, h)
    assert _moved(before, after, "1200") == 50
    assert _moved(before, after, "1300") == 7.5
    assert _moved(before, after, "1000") == -57.5
    await db_session.refresh(flour)
    assert float(flour.cost_price) == 5
    report = (await ac.get("/api/v1/reports/tax", headers=h)).json()["data"]
    assert report["input_tax"] == pytest.approx(7.5)


@pytest.mark.asyncio
async def test_an_expense_goes_to_its_own_account_without_its_vat(client, seeded, db_session):
    ac, seed = client
    h = await _owner(ac, seed, db_session)
    before = await _balances(ac, h)
    r = await ac.post(
        "/api/v1/bakery/expenses", headers=h,
        json={
            "category": "repairs", "description": "Oven door fixed", "amount": 120, "tax": 20,
            "paid_with": "bank_transfer", "spent_on": "2026-11-01",
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["cost"] == 100
    after = await _balances(ac, h)
    assert _moved(before, after, "6060") == 100
    assert _moved(before, after, "6000") == 0
    assert _moved(before, after, "1300") == 20
    wages = await ac.post(
        "/api/v1/bakery/expenses", headers=h,
        json={"category": "wages", "description": "Weekend help", "amount": 50, "paid_with": "cash", "spent_on": "2026-11-01"},
    )
    assert wages.status_code == 200, wages.text
    assert _moved(after, await _balances(ac, h), "6200") == 50


# --- Till counts ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_short_till_is_booked_so_cash_matches_the_drawer(client, seeded, db_session):
    ac, seed = client
    h = await _owner(ac, seed, db_session)
    _flour, loaf, recipe = await _bread(ac, h, db_session, seed, price=10)
    await _bake(ac, h, recipe)
    await _open_till(ac, h, cash=0)
    await _sell(ac, h, loaf, qty=3)
    before = await _balances(ac, h)
    r = await ac.post("/api/v1/bakery/till/shift/close", headers=h, json={"counted_cash": 28})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["over_short"] == -2
    after = await _balances(ac, h)
    assert _moved(before, after, "1000") == -2
    assert _moved(before, after, "6900") == 2


@pytest.mark.asyncio
async def test_a_till_that_balances_books_nothing(client, seeded, db_session):
    ac, seed = client
    h = await _owner(ac, seed, db_session)
    await _open_till(ac, h, cash=50)
    before = await _balances(ac, h)
    r = await ac.post("/api/v1/bakery/till/shift/close", headers=h, json={"counted_cash": 50})
    assert r.status_code == 200, r.text
    assert await _balances(ac, h) == before


# --- Discounts and split payment -----------------------------------------------------------


@pytest.mark.asyncio
async def test_a_discount_comes_off_before_tax_and_needs_a_reason(client, seeded, db_session):
    ac, seed = client
    h = await _owner(ac, seed, db_session)
    await _vat(ac, h)
    _flour, loaf, recipe = await _bread(ac, h, db_session, seed, price=10)
    await _bake(ac, h, recipe)
    await _open_till(ac, h)
    line = {"product_id": loaf.id, "quantity": 2, "discount_percent": 50}
    no_reason = await ac.post("/api/v1/bakery/sales", headers=h, json={"lines": [line]})
    assert no_reason.status_code == 400, no_reason.text
    r = await ac.post("/api/v1/bakery/sales", headers=h, json={"lines": [line], "discount_reason": "Day-old bread"})
    assert r.status_code == 200, r.text
    sale = r.json()["data"]
    assert sale["total"] == 12  # 2 x 5 + 20% VAT
    assert sale["tax"] == 2
    assert sale["discount"] == 12
    assert sale["discount_reason"] == "Day-old bread"


@pytest.mark.asyncio
async def test_a_cashier_may_only_take_a_little_off(client, seeded, db_session):
    ac, seed = client
    h = await _owner(ac, seed, db_session)
    _flour, loaf, recipe = await _bread(ac, h, db_session, seed, price=10)
    await _bake(ac, h, recipe)
    await _open_till(ac, h)
    c = await _cashier(ac, seed, db_session)
    big = await ac.post(
        "/api/v1/bakery/sales", headers=c,
        json={"lines": [{"product_id": loaf.id, "quantity": 1, "discount_percent": 30}], "discount_reason": "Friend"},
    )
    assert big.status_code == 403, big.text
    assert big.json()["detail"]["code"] == "DISCOUNT_TOO_BIG"
    small = await ac.post(
        "/api/v1/bakery/sales", headers=c,
        json={"lines": [{"product_id": loaf.id, "quantity": 1, "discount_percent": 10}], "discount_reason": "Regular"},
    )
    assert small.status_code == 200, small.text
    assert small.json()["data"]["total"] == 9


@pytest.mark.asyncio
async def test_a_bill_paid_two_ways_reaches_both_accounts(client, seeded, db_session):
    ac, seed = client
    h = await _owner(ac, seed, db_session)
    _flour, loaf, recipe = await _bread(ac, h, db_session, seed, price=10)
    await _bake(ac, h, recipe)
    await _open_till(ac, h, cash=0)
    before = await _balances(ac, h)
    wrong = await ac.post(
        "/api/v1/bakery/sales", headers=h,
        json={
            "lines": [{"product_id": loaf.id, "quantity": 3}],
            "payments": [{"method": "cash", "amount": 10}, {"method": "mobile_money", "amount": 10}],
        },
    )
    assert wrong.status_code == 422, wrong.text
    assert wrong.json()["detail"]["code"] == "SPLIT_NOT_EQUAL"
    r = await ac.post(
        "/api/v1/bakery/sales", headers=h,
        json={
            "lines": [{"product_id": loaf.id, "quantity": 3}],
            "payments": [{"method": "cash", "amount": 10}, {"method": "mobile_money", "amount": 20}],
        },
    )
    assert r.status_code == 200, r.text
    sale = r.json()["data"]
    assert sale["payment_method"] == "split"
    assert {p["method"]: p["amount"] for p in sale["payments"]} == {"cash": 10, "mobile_money": 20}
    after = await _balances(ac, h)
    assert _moved(before, after, "1000") == 10
    assert _moved(before, after, "1010") == 20
    shift = await _shift(ac, h)
    assert shift["cash_taken"] == 10
    assert shift["by_method"]["mobile_money"] == 20
    rest = await ac.post(
        "/api/v1/bakery/sales", headers=h,
        json={
            "lines": [{"product_id": loaf.id, "quantity": 2}],
            "payments": [{"method": "cash", "amount": 5}, {"method": "card"}],
        },
    )
    assert rest.status_code == 200, rest.text
    assert {p["method"]: p["amount"] for p in rest.json()["data"]["payments"]} == {"cash": 5, "card": 15}
    # Giving money back on a split bill needs to say how.
    refund = await ac.post(f"/api/v1/bakery/sales/{sale['id']}/refund", headers=h, json={"reason": "Wrong order"})
    assert refund.status_code == 422, refund.text


# --- Refunds -------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_part_of_a_sale_can_be_refunded_and_counts_on_its_own_day(client, seeded, db_session):
    ac, seed = client
    h = await _owner(ac, seed, db_session)
    await _vat(ac, h)
    _flour, loaf, recipe = await _bread(ac, h, db_session, seed, price=10)
    await _bake(ac, h, recipe)
    await _open_till(ac, h, cash=100)
    sale = await _sell(ac, h, loaf, qty=4)
    assert sale["total"] == 48
    line_id = sale["items"][0]["id"]
    before = await _balances(ac, h)
    r = await ac.post(
        f"/api/v1/bakery/sales/{sale['id']}/refund", headers=h,
        json={"reason": "One was squashed", "lines": [{"sale_line_id": line_id, "quantity": 1}], "restock": False},
    )
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert body["status"] == "part_refunded"
    assert body["refunded_total"] == 12
    after = await _balances(ac, h)
    assert _moved(before, after, "1000") == -12
    assert _moved(before, after, "4000") == 10
    assert _moved(before, after, "2100") == 2
    too_many = await ac.post(
        f"/api/v1/bakery/sales/{sale['id']}/refund", headers=h,
        json={"reason": "More", "lines": [{"sale_line_id": line_id, "quantity": 4}]},
    )
    assert too_many.status_code == 409, too_many.text
    tax = (await ac.get("/api/v1/reports/tax", headers=h)).json()["data"]
    assert tax["output_tax"] == pytest.approx(8 - 2)
    numbers = (await ac.get("/api/v1/bakery/reports", headers=h)).json()["data"]
    assert numbers["revenue"] == 30
    assert numbers["refund_count"] == 1
    rest = await ac.post(f"/api/v1/bakery/sales/{sale['id']}/refund", headers=h, json={"reason": "Customer changed mind", "restock": True})
    assert rest.status_code == 200, rest.text
    assert rest.json()["data"]["status"] == "refunded"
    assert rest.json()["data"]["refunded_total"] == 48
    assert await _stock(db_session, loaf) == 6 + 3


@pytest.mark.asyncio
async def test_a_collected_order_can_be_refunded(client, seeded, db_session):
    ac, seed = client
    h = await _owner(ac, seed, db_session)
    _flour, loaf, recipe = await _bread(ac, h, db_session, seed, price=10)
    await _bake(ac, h, recipe)
    await _open_till(ac, h, cash=100)
    order = await _order(ac, h, loaf, qty=2, deposit=5)
    r = await ac.post(f"/api/v1/bakery/orders/{order['id']}/collect", headers=h, json={"payment_method": "cash"})
    assert r.status_code == 200, r.text
    sales = (await ac.get("/api/v1/bakery/sales", headers=h)).json()["data"]
    sale = next(s for s in sales if s["order_id"] == order["id"])
    before = await _balances(ac, h)
    refund = await ac.post(f"/api/v1/bakery/sales/{sale['id']}/refund", headers=h, json={"reason": "Cake was wrong"})
    assert refund.status_code == 200, refund.text
    assert refund.json()["data"]["status"] == "refunded"
    after = await _balances(ac, h)
    assert _moved(before, after, "1000") == -20
    assert _moved(before, after, "4000") == 20


@pytest.mark.asyncio
async def test_a_cash_refund_cannot_take_more_than_the_drawer_holds(client, seeded, db_session):
    ac, seed = client
    h = await _owner(ac, seed, db_session)
    _flour, loaf, recipe = await _bread(ac, h, db_session, seed, price=10)
    await _bake(ac, h, recipe)
    await _open_till(ac, h, cash=0)
    sale = await _sell(ac, h, loaf, qty=2, method="card")
    r = await ac.post(
        f"/api/v1/bakery/sales/{sale['id']}/refund", headers=h, json={"reason": "Card machine fault", "method": "cash"}
    )
    assert r.status_code == 409, r.text
    by_card = await ac.post(f"/api/v1/bakery/sales/{sale['id']}/refund", headers=h, json={"reason": "Card machine fault"})
    assert by_card.status_code == 200, by_card.text


# --- Stock counts --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_stock_count_sets_the_shelf_and_books_the_loss(client, seeded, db_session):
    ac, seed = client
    h = await _owner(ac, seed, db_session)
    flour = await _product(db_session, seed, "Flour", cost=5, stock=20)
    sugar = await _product(db_session, seed, "Sugar", cost=2, stock=10)
    before = await _balances(ac, h)
    r = await ac.post(
        "/api/v1/bakery/stock/count", headers=h,
        json={
            "lines": [{"product_id": flour.id, "counted_qty": 17}, {"product_id": sugar.id, "counted_qty": 11}],
            "notes": "Month end",
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["value_change"] == -13  # 3 x 5 lost, 1 x 2 found
    assert await _stock(db_session, flour) == 17
    assert await _stock(db_session, sugar) == 11
    after = await _balances(ac, h)
    assert _moved(before, after, "1200") == -13
    assert _moved(before, after, "5100") == 13
    counts = (await ac.get("/api/v1/bakery/stock/counts", headers=h)).json()["data"]
    assert counts[0]["notes"] == "Month end"
    assert {line["difference"] for line in counts[0]["lines"]} == {-3, 1}
    c = await _cashier(ac, seed, db_session)
    denied = await ac.post(
        "/api/v1/bakery/stock/count", headers=c, json={"lines": [{"product_id": flour.id, "counted_qty": 1}]}
    )
    assert denied.status_code == 403
