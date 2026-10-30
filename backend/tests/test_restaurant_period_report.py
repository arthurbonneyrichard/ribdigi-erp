"""Restaurant period report: sales by day and hour, dishes with food cost, staff, payments, waste."""

from __future__ import annotations

import pytest

from tests.conftest import auth_headers, set_tenant_industry

pytestmark = pytest.mark.asyncio


async def _product(ac, headers, **body):
    created = await ac.post("/api/v1/products", json=body, headers=headers)
    assert created.status_code == 200, created.text
    return created.json()["data"]


async def _paid(ac, headers, dish_id: str, qty: str, method: str):
    order = await ac.post(
        "/api/v1/restaurant/orders",
        json={"service_mode": "takeaway", "payment_method": method, "customer_name": "Ama", "lines": [{"product_id": dish_id, "quantity": qty}]},
        headers=headers,
    )
    assert order.status_code == 200, order.text
    done = await ac.post(f"/api/v1/restaurant/orders/{order.json()['data']['id']}/complete", headers=headers)
    assert done.status_code == 200, done.text
    return done.json()["data"]


async def test_period_report_sales_food_cost_and_waste(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    await ac.post("/api/v1/restaurant/till/shift/open", headers=admin, json={"opening_cash": 0})

    rice = await _product(ac, admin, name="Report rice", cost_price=4, selling_price=0, stock_qty=100)
    dish = await _product(ac, admin, name="Report jollof", selling_price=30, stock_qty=0, prep_station="kitchen")
    recipe = await ac.post(
        "/api/v1/restaurant/recipes",
        headers=admin,
        json={"product_id": dish["id"], "name": "Report jollof", "lines": [{"ingredient_id": rice["id"], "quantity": "2"}]},
    )
    assert recipe.status_code == 200, recipe.text

    await _paid(ac, admin, dish["id"], "2", "cash")
    second = await _paid(ac, admin, dish["id"], "1", "card")
    refund = await ac.post(f"/api/v1/restaurant/orders/{second['id']}/refund", headers=admin)
    assert refund.status_code == 200, refund.text
    await _paid(ac, admin, dish["id"], "1", "card")
    waste = await ac.post(
        "/api/v1/restaurant/waste", headers=admin,
        json={"product_id": rice["id"], "quantity": 3, "reason": "spoilage"},
    )
    assert waste.status_code == 200, waste.text

    res = await ac.get("/api/v1/restaurant/reports/period", headers=admin)
    assert res.status_code == 200, res.text
    body = res.json()["data"]
    totals = body["totals"]
    assert body["days"] == 7 and len(body["by_day"]) == 7 and len(body["by_hour"]) == 24
    assert totals["orders"] == 2
    assert totals["refunded_orders"] == 1
    assert sum(d["orders"] for d in body["by_day"]) == 2
    jollof = next(d for d in body["dishes"] if d["product_id"] == dish["id"])
    assert jollof["quantity"] == 3
    # 3 plates × 2 rice × 4 = 24 food cost.
    assert jollof["cost"] == 24
    assert totals["food_cost"] == 24
    assert totals["food_cost_pct"] is not None
    assert totals["waste_cost"] == 12
    assert {r["payment_method"] for r in body["by_payment_method"]} == {"cash", "card"}
    assert body["by_staff"][0]["orders"] == 2

    bad = await ac.get("/api/v1/restaurant/reports/period?from_date=2026-02-10&to_date=2026-02-01", headers=admin)
    assert bad.status_code == 422, bad.text
    garbage = await ac.get("/api/v1/restaurant/reports/period?from_date=not-a-date", headers=admin)
    assert garbage.status_code == 422, garbage.text


async def test_period_report_is_restaurant_only(client, db_session):
    ac, _seed = client
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    res = await ac.get("/api/v1/restaurant/reports/period", headers=admin)
    assert res.status_code in {403, 404}, res.text
