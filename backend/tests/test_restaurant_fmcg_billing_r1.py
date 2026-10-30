"""Restaurant floor, FMCG pack/expiry, and platform billing gateway setup."""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app import models as m
from app.billing_gateway import MockGateway
from app.config import settings
from app.jobs import job_process_subscription_renewals
from app.rbac import permissions_for_role
from app.security import hash_password
from tests.conftest import auth_headers, platform_owner_headers, set_tenant_industry

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _clear_mock_charges():
    MockGateway._charged.clear()
    yield
    MockGateway._charged.clear()


@pytest.fixture(autouse=True)
def _seed_legacy_restaurant_till_history(monkeypatch):
    """Restaurant and hotel till sales rung on /pos before the split are still in
    transactions / sales_returns, and reports keep reading them. These tests seed that
    history through /pos; the live API refuses a restaurant company there
    (tests/test_restaurant_till_shift.py)."""
    from app import industry_dashboard

    monkeypatch.setattr(
        industry_dashboard, "POS_INDUSTRIES", industry_dashboard.POS_INDUSTRIES | {"restaurant", "hotel"}
    )


def _sign(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


async def _product(ac, headers, **extra):
    body = {"name": extra.pop("name"), "selling_price": extra.pop("selling_price", 10), **extra}
    created = await ac.post("/api/v1/products", json=body, headers=headers)
    assert created.status_code == 200, created.text
    return created.json()["data"]


async def test_retail_and_hotel_cannot_use_restaurant_routes(client, db_session):
    ac, seed = client
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    denied = await ac.get("/api/v1/restaurant/summary", headers=admin)
    assert denied.status_code == 403, denied.text
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    still = await ac.get("/api/v1/restaurant/summary", headers=admin)
    assert still.status_code == 403, still.text
    ready = await ac.post(
        f"/api/v1/restaurant/kitchen/lines/{uuid.uuid4()}/ready",
        headers=admin,
        json={},
    )
    assert ready.status_code == 403, ready.text
    orders = await ac.get("/api/v1/restaurant/orders", headers=admin)
    assert orders.status_code == 403, orders.text
    modifiers = await ac.get("/api/v1/restaurant/modifiers", headers=admin)
    assert modifiers.status_code == 403, modifiers.text
    recipes = await ac.get("/api/v1/restaurant/recipes", headers=admin)
    assert recipes.status_code == 403, recipes.text
    hold = await ac.post(f"/api/v1/restaurant/tables/{uuid.uuid4()}/hold", headers=admin, json={})
    assert hold.status_code == 403, hold.text
    patch_table = await ac.patch(
        f"/api/v1/restaurant/tables/{uuid.uuid4()}",
        headers=admin,
        json={"name": "Patio"},
    )
    assert patch_table.status_code == 403, patch_table.text
    patch_code = await ac.patch(
        f"/api/v1/restaurant/tables/{uuid.uuid4()}",
        headers=admin,
        json={"code": "T9"},
    )
    assert patch_code.status_code == 403, patch_code.text
    patch_table_store = await ac.patch(
        f"/api/v1/restaurant/tables/{uuid.uuid4()}",
        headers=admin,
        json={"store_id": str(uuid.uuid4())},
    )
    assert patch_table_store.status_code == 403, patch_table_store.text
    retire = await ac.post(f"/api/v1/restaurant/tables/{uuid.uuid4()}/retire", headers=admin, json={})
    assert retire.status_code == 403, retire.text
    walk_in = await ac.post(
        "/api/v1/restaurant/bookings",
        headers=admin,
        json={
            "guest_name": "Ama Walkin",
            "phone": "+233241234567",
            "party_size": 2,
            "booked_for": (datetime.utcnow() + timedelta(hours=1)).replace(microsecond=0).isoformat(),
        },
    )
    assert walk_in.status_code == 403, walk_in.text
    patch_booking = await ac.patch(
        f"/api/v1/restaurant/bookings/{uuid.uuid4()}",
        headers=admin,
        json={"notes": "Window seat"},
    )
    assert patch_booking.status_code == 403, patch_booking.text
    waste = await ac.post(
        "/api/v1/restaurant/waste",
        headers=admin,
        json={"product_id": str(uuid.uuid4()), "quantity": "1", "reason": "spoilage"},
    )
    assert waste.status_code == 403, waste.text
    extra_retire = await ac.post(
        f"/api/v1/restaurant/modifiers/{uuid.uuid4()}/retire",
        headers=admin,
        json={},
    )
    assert extra_retire.status_code == 403, extra_retire.text
    extra_price = await ac.patch(
        f"/api/v1/restaurant/modifiers/{uuid.uuid4()}",
        headers=admin,
        json={"price": "12"},
    )
    assert extra_price.status_code == 403, extra_price.text
    extra_name = await ac.patch(
        f"/api/v1/restaurant/modifiers/{uuid.uuid4()}",
        headers=admin,
        json={"name": "Ripe plantain"},
    )
    assert extra_name.status_code == 403, extra_name.text
    leftover_recipe = await ac.patch(
        f"/api/v1/restaurant/recipes/{uuid.uuid4()}",
        headers=admin,
        json={"name": "House jollof"},
    )
    assert leftover_recipe.status_code == 403, leftover_recipe.text
    leftover_recipe_retire = await ac.post(
        f"/api/v1/restaurant/recipes/{uuid.uuid4()}/retire",
        headers=admin,
        json={},
    )
    assert leftover_recipe_retire.status_code == 403, leftover_recipe_retire.text
    leftover_group = await ac.patch(
        f"/api/v1/restaurant/modifier-groups/{uuid.uuid4()}",
        headers=admin,
        json={"name": "Add-ons"},
    )
    assert leftover_group.status_code == 403, leftover_group.text
    leftover_group_retire = await ac.post(
        f"/api/v1/restaurant/modifier-groups/{uuid.uuid4()}/retire",
        headers=admin,
        json={},
    )
    assert leftover_group_retire.status_code == 403, leftover_group_retire.text
    patch_order = await ac.patch(
        f"/api/v1/restaurant/orders/{uuid.uuid4()}",
        headers=admin,
        json={"notes": "No pepper"},
    )
    assert patch_order.status_code == 403, patch_order.text
    patch_customer = await ac.patch(
        f"/api/v1/restaurant/orders/{uuid.uuid4()}",
        headers=admin,
        json={"customer_name": "Ama Diner"},
    )
    assert patch_customer.status_code == 403, patch_customer.text
    patch_address = await ac.patch(
        f"/api/v1/restaurant/orders/{uuid.uuid4()}",
        headers=admin,
        json={"delivery_address": "14 Market Street"},
    )
    assert patch_address.status_code == 403, patch_address.text
    patch_payment = await ac.patch(
        f"/api/v1/restaurant/orders/{uuid.uuid4()}",
        headers=admin,
        json={"payment_method": "card"},
    )
    assert patch_payment.status_code == 403, patch_payment.text
    patch_service = await ac.patch(
        f"/api/v1/restaurant/orders/{uuid.uuid4()}",
        headers=admin,
        json={"service_mode": "takeaway"},
    )
    assert patch_service.status_code == 403, patch_service.text
    patch_qty = await ac.patch(
        f"/api/v1/restaurant/orders/{uuid.uuid4()}",
        headers=admin,
        json={"line_quantities": [{"line_id": str(uuid.uuid4()), "quantity": "2"}]},
    )
    assert patch_qty.status_code == 403, patch_qty.text
    patch_extra = await ac.patch(
        f"/api/v1/restaurant/orders/{uuid.uuid4()}",
        headers=admin,
        json={"line_modifiers": [{"line_id": str(uuid.uuid4()), "modifier_ids": []}]},
    )
    assert patch_extra.status_code == 403, patch_extra.text
    patch_store = await ac.patch(
        f"/api/v1/restaurant/orders/{uuid.uuid4()}",
        headers=admin,
        json={"store_id": str(uuid.uuid4())},
    )
    assert patch_store.status_code == 403, patch_store.text
    patch_price = await ac.patch(
        f"/api/v1/restaurant/orders/{uuid.uuid4()}",
        headers=admin,
        json={"line_prices": [{"line_id": str(uuid.uuid4()), "unit_price": "15"}]},
    )
    assert patch_price.status_code == 403, patch_price.text
    patch_station = await ac.patch(
        f"/api/v1/restaurant/orders/{uuid.uuid4()}",
        headers=admin,
        json={"line_stations": [{"line_id": str(uuid.uuid4()), "station": "bar"}]},
    )
    assert patch_station.status_code == 403, patch_station.text
    remove_line = await ac.patch(
        f"/api/v1/restaurant/orders/{uuid.uuid4()}",
        headers=admin,
        json={"remove_line_ids": [str(uuid.uuid4())]},
    )
    assert remove_line.status_code == 403, remove_line.text
    booking_link = await ac.put(
        "/api/v1/restaurant/booking-link",
        headers=admin,
        json={"hostname": "book.hotel.example", "link_kind": "new"},
    )
    assert booking_link.status_code == 403, booking_link.text
    rooms = await ac.get("/api/v1/hotel/rooms", headers=admin)
    assert rooms.status_code == 200, rooms.text


async def test_restaurant_lists_saved_extras(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    group = await ac.post("/api/v1/restaurant/modifier-groups", json={"name": "Extras"}, headers=admin)
    assert group.status_code == 200, group.text
    modifier = await ac.post(
        f"/api/v1/restaurant/modifier-groups/{group.json()['data']['id']}/modifiers",
        json={"name": "Cheese", "price": "2"},
        headers=admin,
    )
    assert modifier.status_code == 200, modifier.text
    listed = await ac.get("/api/v1/restaurant/modifiers", headers=admin)
    assert listed.status_code == 200, listed.text
    extras = listed.json()["data"]
    assert extras[0]["name"] == "Extras"
    assert extras[0]["modifiers"][0]["name"] == "Cheese"
    assert extras[0]["modifiers"][0]["price"] == 2


async def test_restaurant_recipe_saves_every_ingredient(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    dish = await _product(ac, admin, name="Jollof", selling_price=20)
    rice = await _product(ac, admin, name="Rice", selling_price=1)
    tomato = await _product(ac, admin, name="Tomato", selling_price=1)
    empty = await ac.post(
        "/api/v1/restaurant/recipes",
        json={"product_id": dish["id"], "name": "Jollof recipe", "lines": []},
        headers=admin,
    )
    assert empty.status_code == 422, empty.text
    saved = await ac.post(
        "/api/v1/restaurant/recipes",
        json={
            "product_id": dish["id"],
            "name": "Jollof recipe",
            "lines": [
                {"ingredient_id": rice["id"], "quantity": "2"},
                {"ingredient_id": tomato["id"], "quantity": "1"},
            ],
        },
        headers=admin,
    )
    assert saved.status_code == 200, saved.text
    lines = list(
        (
            await db_session.execute(
                select(m.RestaurantRecipeLine).where(
                    m.RestaurantRecipeLine.recipe_id == saved.json()["data"]["id"]
                )
            )
        ).scalars()
    )
    assert {row.ingredient_id for row in lines} == {rice["id"], tomato["id"]}
    assert float(next(row.quantity for row in lines if row.ingredient_id == rice["id"])) == 2
    listed = await ac.get("/api/v1/restaurant/recipes", headers=admin)
    assert listed.status_code == 200, listed.text
    recipe = next(row for row in listed.json()["data"] if row["id"] == saved.json()["data"]["id"])
    assert recipe["menu_item"] == "Jollof"
    assert recipe["station"] == "kitchen"
    assert {line["name"] for line in recipe["lines"]} == {"Rice", "Tomato"}
    blank = await ac.patch(f"/api/v1/restaurant/recipes/{recipe['id']}", headers=admin, json={})
    assert blank.status_code == 422, blank.text
    named = await ac.patch(
        f"/api/v1/restaurant/recipes/{recipe['id']}",
        headers=admin,
        json={"name": "House jollof"},
    )
    assert named.status_code == 200, named.text
    assert named.json()["data"]["name"] == "House jollof"
    leftover_lines = await ac.patch(
        f"/api/v1/restaurant/recipes/{recipe['id']}",
        headers=admin,
        json={
            "lines": [
                {"ingredient_id": rice["id"], "quantity": "3"},
                {"ingredient_id": tomato["id"], "quantity": "1"},
            ]
        },
    )
    assert leftover_lines.status_code == 200, leftover_lines.text
    menu_line = await ac.patch(
        f"/api/v1/restaurant/recipes/{recipe['id']}",
        headers=admin,
        json={"lines": [{"ingredient_id": dish["id"], "quantity": "1"}]},
    )
    assert menu_line.status_code == 422, menu_line.text
    assert menu_line.json()["detail"] == "Choose an ingredient."
    leftover = await ac.get("/api/v1/restaurant/recipes", headers=admin)
    assert leftover.status_code == 200, leftover.text
    leftover_recipe = next(row for row in leftover.json()["data"] if row["id"] == recipe["id"])
    assert leftover_recipe["name"] == "House jollof"
    assert leftover_recipe["menu_item"] == "Jollof"
    assert {line["name"]: line["quantity"] for line in leftover_recipe["lines"]} == {"Rice": 3, "Tomato": 1}
    dropped = await ac.patch(
        f"/api/v1/restaurant/recipes/{recipe['id']}",
        headers=admin,
        json={"lines": [{"ingredient_id": rice["id"], "quantity": "3"}]},
    )
    assert dropped.status_code == 200, dropped.text
    kept = await ac.get("/api/v1/restaurant/recipes", headers=admin)
    assert kept.status_code == 200, kept.text
    kept_recipe = next(row for row in kept.json()["data"] if row["id"] == recipe["id"])
    assert {line["name"]: line["quantity"] for line in kept_recipe["lines"]} == {"Rice": 3}
    empty_lines = await ac.patch(
        f"/api/v1/restaurant/recipes/{recipe['id']}",
        headers=admin,
        json={"lines": []},
    )
    assert empty_lines.status_code == 422, empty_lines.text
    assert empty_lines.json()["detail"] == "Recipe needs at least one ingredient"
    assert float(next(line["quantity"] for line in recipe["lines"] if line["name"] == "Rice")) == 2
    retired = await ac.post(
        f"/api/v1/restaurant/recipes/{recipe['id']}/retire",
        headers=admin,
        json={},
    )
    assert retired.status_code == 200, retired.text
    assert retired.json()["data"]["is_active"] is False
    again = await ac.post(
        f"/api/v1/restaurant/recipes/{recipe['id']}/retire",
        headers=admin,
        json={},
    )
    assert again.status_code == 409, again.text
    late = await ac.patch(
        f"/api/v1/restaurant/recipes/{recipe['id']}",
        headers=admin,
        json={"name": "Too late"},
    )
    assert late.status_code == 409, late.text
    hidden = await ac.get("/api/v1/restaurant/recipes", headers=admin)
    assert hidden.status_code == 200, hidden.text
    assert all(row["id"] != recipe["id"] for row in hidden.json()["data"])


async def test_restaurant_menu_item_station_goes_to_bar(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    drink = await _product(ac, admin, name="Sobolo", selling_price=5)
    patched = await ac.patch(
        f"/api/v1/products/{drink['id']}",
        json={"prep_station": "bar"},
        headers=admin,
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["data"]["prep_station"] == "bar"
    saved = await ac.post(
        "/api/v1/restaurant/orders",
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "lines": [{"product_id": drink["id"], "quantity": "1"}],
        },
        headers=admin,
    )
    assert saved.status_code == 200, saved.text
    sent = await ac.post(f"/api/v1/restaurant/orders/{saved.json()['data']['id']}/send", headers=admin)
    assert sent.status_code == 200, sent.text
    kitchen = await ac.get("/api/v1/restaurant/kitchen", headers=admin)
    tickets = [row for row in kitchen.json()["data"] if row["order_id"] == saved.json()["data"]["id"]]
    assert {row["station"] for row in tickets} == {"bar"}
    assert tickets[0]["items"][0]["name"] == "Sobolo"


async def test_restaurant_table_lists_seats(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    empty = await ac.get("/api/v1/restaurant/tables", headers=admin)
    assert empty.status_code == 200, empty.text
    assert empty.json()["data"] == []
    window = await ac.post(
        "/api/v1/restaurant/tables",
        json={"code": "T1", "name": "Window", "seats": 1},
        headers=admin,
    )
    assert window.status_code == 200, window.text
    booth = await ac.post(
        "/api/v1/restaurant/tables",
        json={"code": "T2", "name": "Booth", "seats": 4},
        headers=admin,
    )
    assert booth.status_code == 200, booth.text
    listed = await ac.get("/api/v1/restaurant/tables", headers=admin)
    by_code = {row["code"]: row for row in listed.json()["data"]}
    assert by_code["T1"]["seats"] == 1
    assert by_code["T1"]["status"] == "available"
    assert by_code["T2"]["seats"] == 4
    banku = await _product(ac, admin, name="Banku", selling_price=15)
    missing_table = await ac.post(
        "/api/v1/restaurant/orders",
        json={
            "service_mode": "dine_in",
            "payment_method": "cash",
            "lines": [{"product_id": banku["id"], "quantity": "1"}],
        },
        headers=admin,
    )
    assert missing_table.status_code == 422, missing_table.text
    assert "Dine in needs a table" in missing_table.text
    seated = await ac.post(
        "/api/v1/restaurant/orders",
        json={
            "service_mode": "dine_in",
            "payment_method": "cash",
            "table_id": window.json()["data"]["id"],
            "lines": [{"product_id": banku["id"], "quantity": "1"}],
        },
        headers=admin,
    )
    assert seated.status_code == 200, seated.text
    assert seated.json()["data"]["table_id"] == window.json()["data"]["id"]


async def test_restaurant_holds_and_releases_a_table(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    booth = await ac.post(
        "/api/v1/restaurant/tables",
        json={"code": "T3", "name": "Garden", "seats": 2},
        headers=admin,
    )
    assert booth.status_code == 200, booth.text
    table_id = booth.json()["data"]["id"]
    held = await ac.post(f"/api/v1/restaurant/tables/{table_id}/hold", headers=admin, json={})
    assert held.status_code == 200, held.text
    assert held.json()["data"]["status"] == "held"
    again = await ac.post(f"/api/v1/restaurant/tables/{table_id}/hold", headers=admin, json={})
    assert again.status_code == 409, again.text
    freed = await ac.post(f"/api/v1/restaurant/tables/{table_id}/release", headers=admin, json={})
    assert freed.status_code == 200, freed.text
    assert freed.json()["data"]["status"] == "available"
    idle = await ac.post(f"/api/v1/restaurant/tables/{table_id}/release", headers=admin, json={})
    assert idle.status_code == 409, idle.text
    dish = await _product(ac, admin, name="Waakye", selling_price=12)
    seated = await ac.post(
        "/api/v1/restaurant/orders",
        json={
            "service_mode": "dine_in",
            "payment_method": "cash",
            "table_id": table_id,
            "lines": [{"product_id": dish["id"], "quantity": "1"}],
        },
        headers=admin,
    )
    assert seated.status_code == 200, seated.text
    busy = await ac.post(f"/api/v1/restaurant/tables/{table_id}/hold", headers=admin, json={})
    assert busy.status_code == 409, busy.text
    stuck = await ac.post(f"/api/v1/restaurant/tables/{table_id}/release", headers=admin, json={})
    assert stuck.status_code == 409, stuck.text
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    hotel = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    denied = await ac.post(f"/api/v1/restaurant/tables/{table_id}/hold", headers=hotel, json={})
    assert denied.status_code == 403, denied.text


async def test_restaurant_records_waste_and_ready_without_prep_column(client, db_session, monkeypatch):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    rice = await _product(ac, admin, name="Rice", selling_price=1, stock_qty=10)
    dumped = await ac.post(
        "/api/v1/restaurant/waste",
        headers=admin,
        json={"product_id": rice["id"], "quantity": "3", "reason": "spoilage", "notes": "Burnt pot"},
    )
    assert dumped.status_code == 200, dumped.text
    assert dumped.json()["data"]["reason"] == "spoilage"
    assert dumped.json()["data"]["stock_qty"] == 7
    listed = await ac.get("/api/v1/restaurant/waste", headers=admin)
    assert listed.status_code == 200, listed.text
    assert listed.json()["data"][0]["reason"] == "spoilage"
    assert listed.json()["data"][0]["name"] == "Rice"
    assert listed.json()["data"][0]["quantity"] == 3
    assert listed.json()["data"][0]["notes"] == "Burnt pot"
    dry = await ac.post("/api/v1/warehouses", json={"name": "Dry store", "code": "DRY62"}, headers=admin)
    assert dry.status_code == 200, dry.text
    dry_id = dry.json()["data"]["id"]
    missing_warehouse = await ac.post(
        "/api/v1/restaurant/waste",
        headers=admin,
        json={"product_id": rice["id"], "quantity": "1", "reason": "waste", "warehouse_id": str(uuid.uuid4())},
    )
    assert missing_warehouse.status_code == 404, missing_warehouse.text
    empty_warehouse = await ac.post(
        "/api/v1/restaurant/waste",
        headers=admin,
        json={"product_id": rice["id"], "quantity": "1", "reason": "waste", "warehouse_id": dry_id},
    )
    assert empty_warehouse.status_code == 409, empty_warehouse.text
    received = await ac.post(
        "/api/v1/inventory/stock-in",
        headers=admin,
        json={"product_id": rice["id"], "quantity": "2", "warehouse_id": dry_id},
    )
    assert received.status_code == 200, received.text
    placed = await ac.post(
        "/api/v1/restaurant/waste",
        headers=admin,
        json={
            "product_id": rice["id"],
            "quantity": "1",
            "reason": "waste",
            "notes": "Shelf",
            "warehouse_id": dry_id,
        },
    )
    assert placed.status_code == 200, placed.text
    assert placed.json()["data"]["warehouse_id"] == dry_id
    assert placed.json()["data"]["stock_qty"] == 8
    placed_list = await ac.get("/api/v1/restaurant/waste", headers=admin)
    shelf = next(row for row in placed_list.json()["data"] if row["notes"] == "Shelf")
    assert shelf["warehouse_id"] == dry_id
    blank = await ac.post(
        "/api/v1/restaurant/waste",
        headers=admin,
        json={"product_id": rice["id"], "quantity": "1", "reason": "left-over"},
    )
    assert blank.status_code == 422, blank.text
    from app import schema_compat

    real = schema_compat.table_column_names

    async def hide_prep(db, table_name: str):
        names = await real(db, table_name)
        if table_name == "restaurant_order_lines":
            return set(names) - {"prep_status"}
        return names

    monkeypatch.setattr(schema_compat, "table_column_names", hide_prep)
    dish = await _product(ac, admin, name="Kenkey", selling_price=8)
    table = await ac.post(
        "/api/v1/restaurant/tables",
        json={"code": "TW", "name": "Waste window", "seats": 2},
        headers=admin,
    )
    assert table.status_code == 200, table.text
    opened = await ac.post(
        "/api/v1/restaurant/orders",
        json={
            "service_mode": "dine_in",
            "payment_method": "cash",
            "table_id": table.json()["data"]["id"],
            "lines": [{"product_id": dish["id"], "quantity": "1"}],
        },
        headers=admin,
    )
    assert opened.status_code == 200, opened.text
    sent = await ac.post(f"/api/v1/restaurant/orders/{opened.json()['data']['id']}/send", headers=admin)
    assert sent.status_code == 200, sent.text
    kitchen = await ac.get("/api/v1/restaurant/kitchen", headers=admin)
    ticket = next(row for row in kitchen.json()["data"] if row["order_id"] == opened.json()["data"]["id"])
    marked = await ac.post(
        f"/api/v1/restaurant/kitchen/lines/{ticket['items'][0]['id']}/ready",
        headers=admin,
        json={},
    )
    assert marked.status_code == 200, marked.text
    ready = next(row for row in marked.json()["data"] if row["order_id"] == opened.json()["data"]["id"])
    assert ready["status"] == "ready"
    assert ready["items"][0]["prep_status"] == "ready"
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    hotel = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    peek = await ac.get("/api/v1/restaurant/waste", headers=hotel)
    assert peek.status_code == 403, peek.text
    denied = await ac.post(
        "/api/v1/restaurant/waste",
        headers=hotel,
        json={"product_id": rice["id"], "quantity": "1", "reason": "waste", "warehouse_id": str(uuid.uuid4())},
    )
    assert denied.status_code == 403, denied.text


async def test_restaurant_void_and_refund_order(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    rice = await _product(ac, admin, name="Rice", selling_price=1, stock_qty=10)
    dish = await _product(ac, admin, name="Jollof", selling_price=20)
    recipe = await ac.post(
        "/api/v1/restaurant/recipes",
        json={
            "product_id": dish["id"],
            "name": "Jollof recipe",
            "lines": [{"ingredient_id": rice["id"], "quantity": "2"}],
        },
        headers=admin,
    )
    assert recipe.status_code == 200, recipe.text
    opened = await ac.post(
        "/api/v1/restaurant/orders",
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "lines": [{"product_id": dish["id"], "quantity": "1"}],
        },
        headers=admin,
    )
    assert opened.status_code == 200, opened.text
    early_refund = await ac.post(f"/api/v1/restaurant/orders/{opened.json()['data']['id']}/refund", headers=admin)
    assert early_refund.status_code == 409, early_refund.text
    voided = await ac.post(f"/api/v1/restaurant/orders/{opened.json()['data']['id']}/void", headers=admin)
    assert voided.status_code == 200, voided.text
    assert voided.json()["data"]["status"] == "voided"
    sold = await ac.post(
        "/api/v1/restaurant/orders",
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "lines": [{"product_id": dish["id"], "quantity": "1"}],
        },
        headers=admin,
    )
    assert sold.status_code == 200, sold.text
    done = await ac.post(f"/api/v1/restaurant/orders/{sold.json()['data']['id']}/complete", headers=admin)
    assert done.status_code == 200, done.text
    stock = await ac.get(f"/api/v1/products/{rice['id']}", headers=admin)
    assert float(stock.json()["data"]["stock_qty"]) == 8
    late_void = await ac.post(f"/api/v1/restaurant/orders/{sold.json()['data']['id']}/void", headers=admin)
    assert late_void.status_code == 409, late_void.text
    refunded = await ac.post(f"/api/v1/restaurant/orders/{sold.json()['data']['id']}/refund", headers=admin)
    assert refunded.status_code == 200, refunded.text
    assert refunded.json()["data"]["status"] == "refunded"
    restored = await ac.get(f"/api/v1/products/{rice['id']}", headers=admin)
    assert float(restored.json()["data"]["stock_qty"]) == 10


async def test_restaurant_order_saves_every_menu_item(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    banku = await _product(ac, admin, name="Banku", selling_price=15)
    soup = await _product(ac, admin, name="Light soup", selling_price=8)
    empty = await ac.post(
        "/api/v1/restaurant/orders",
        json={"service_mode": "dine_in", "payment_method": "cash", "lines": []},
        headers=admin,
    )
    assert empty.status_code == 422, empty.text
    saved = await ac.post(
        "/api/v1/restaurant/orders",
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "lines": [
                {"product_id": banku["id"], "quantity": "2"},
                {"product_id": soup["id"], "quantity": "1"},
            ],
        },
        headers=admin,
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["data"]["total_amount"] == 38
    listed = await ac.get("/api/v1/restaurant/orders", headers=admin)
    order = next(row for row in listed.json()["data"] if row["id"] == saved.json()["data"]["id"])
    names = {item["name"] for item in order["items"]}
    assert names == {"Banku", "Light soup"}
    assert float(next(item["quantity"] for item in order["items"] if item["name"] == "Banku")) == 2
    missing = await ac.post(
        "/api/v1/restaurant/orders",
        json={
            "service_mode": "delivery",
            "payment_method": "cash",
            "lines": [{"product_id": banku["id"], "quantity": "1"}],
        },
        headers=admin,
    )
    assert missing.status_code == 422, missing.text
    delivered = await ac.post(
        "/api/v1/restaurant/orders",
        json={
            "service_mode": "delivery",
            "payment_method": "cash",
            "delivery_address": "12 Market Street",
            "notes": "Leave at the gate",
            "lines": [{"product_id": soup["id"], "quantity": "1"}],
        },
        headers=admin,
    )
    assert delivered.status_code == 200, delivered.text
    assert delivered.json()["data"]["delivery_address"] == "12 Market Street"
    assert delivered.json()["data"]["notes"] == "Leave at the gate"
    listed_delivery = await ac.get("/api/v1/restaurant/orders", headers=admin)
    saved_delivery = next(
        row for row in listed_delivery.json()["data"] if row["id"] == delivered.json()["data"]["id"]
    )
    assert saved_delivery["delivery_address"] == "12 Market Street"
    assert saved_delivery["notes"] == "Leave at the gate"
    takeaway_address = await ac.patch(
        f"/api/v1/restaurant/orders/{saved.json()['data']['id']}",
        headers=admin,
        json={"delivery_address": "14 Market Street"},
    )
    assert takeaway_address.status_code == 422, takeaway_address.text
    assert takeaway_address.json()["detail"] == "This order is not a delivery."
    moved = await ac.patch(
        f"/api/v1/restaurant/orders/{delivered.json()['data']['id']}",
        headers=admin,
        json={"delivery_address": "14 Market Street"},
    )
    assert moved.status_code == 200, moved.text
    assert moved.json()["data"]["delivery_address"] == "14 Market Street"
    assert moved.json()["data"]["notes"] == "Leave at the gate"


async def test_restaurant_order_kitchen_and_ingredient_deduction(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    ingredient = await _product(ac, admin, name="Rice", selling_price=1, stock_qty=10)
    dish = await _product(ac, admin, name="Jollof", selling_price=20, prep_station="kitchen")
    group = await ac.post("/api/v1/restaurant/modifier-groups", json={"name": "Extras"}, headers=admin)
    assert group.status_code == 200, group.text
    modifier = await ac.post(
        f"/api/v1/restaurant/modifier-groups/{group.json()['data']['id']}/modifiers",
        json={"name": "Cheese", "price": "2"},
        headers=admin,
    )
    assert modifier.status_code == 200, modifier.text
    recipe = await ac.post(
        "/api/v1/restaurant/recipes",
        json={
            "product_id": dish["id"],
            "name": "Jollof recipe",
            "lines": [{"ingredient_id": ingredient["id"], "quantity": "2"}],
        },
        headers=admin,
    )
    assert recipe.status_code == 200, recipe.text
    table = await ac.post(
        "/api/v1/restaurant/tables",
        json={"code": "T1", "name": "Window"},
        headers=admin,
    )
    assert table.status_code == 200, table.text
    order = await ac.post(
        "/api/v1/restaurant/orders",
        json={
            "service_mode": "dine_in",
            "payment_method": "cash",
            "table_id": table.json()["data"]["id"],
            "customer_name": "Ama Mensah",
            "notes": "No pepper",
            "lines": [
                {
                    "product_id": dish["id"],
                    "quantity": "1",
                    "modifier_ids": [modifier.json()["data"]["id"]],
                }
            ],
        },
        headers=admin,
    )
    assert order.status_code == 200, order.text
    body = order.json()["data"]
    assert body["total_amount"] == 22
    order_id = body["id"]
    sent = await ac.post(f"/api/v1/restaurant/orders/{order_id}/send", headers=admin)
    assert sent.status_code == 200, sent.text
    kitchen = await ac.get("/api/v1/restaurant/kitchen", headers=admin)
    assert kitchen.status_code == 200, kitchen.text
    ticket = next(row for row in kitchen.json()["data"] if row["order_id"] == order_id and row["station"] == "kitchen")
    assert ticket["order_number"]
    assert ticket["service_mode"] == "dine_in"
    assert ticket["customer_name"] == "Ama Mensah"
    assert ticket["table_code"] == "T1"
    assert ticket["notes"] == "No pepper"
    assert ticket["items"][0]["name"] == "Jollof"
    assert ticket["items"][0]["modifiers"] == ["Cheese"]
    assert float(ticket["items"][0]["quantity"]) == 1
    assert ticket["items"][0]["prep_status"] == "queued"
    marked = await ac.post(
        f"/api/v1/restaurant/kitchen/lines/{ticket['items'][0]['id']}/ready",
        headers=admin,
        json={},
    )
    assert marked.status_code == 200, marked.text
    again = await ac.post(
        f"/api/v1/restaurant/kitchen/lines/{ticket['items'][0]['id']}/ready",
        headers=admin,
        json={},
    )
    assert again.status_code == 200, again.text
    charged = await ac.post(
        f"/api/v1/restaurant/kitchen/lines/{ticket['items'][0]['id']}/ready",
        headers=admin,
        json={"payment_method": "card"},
    )
    assert charged.status_code == 422, charged.text
    fresh = await ac.get("/api/v1/restaurant/kitchen", headers=admin)
    ready_ticket = next(row for row in fresh.json()["data"] if row["order_id"] == order_id and row["station"] == "kitchen")
    assert ready_ticket["status"] == "ready"
    assert ready_ticket["items"][0]["prep_status"] == "ready"
    desk = await ac.get("/api/v1/restaurant/orders", headers=admin)
    assert desk.status_code == 200, desk.text
    listed = next(row for row in desk.json()["data"] if row["id"] == order_id)
    assert listed["customer_name"] == "Ama Mensah"
    assert listed["payment_method"] == "cash"
    assert listed["items"][0]["name"] == "Jollof"
    assert listed["notes"] == "No pepper"
    assert listed["items"][0]["modifiers"] == ["Cheese"]
    assert listed["items"][0]["prep_status"] == "ready"
    drink = await _product(ac, admin, name="Sobolo", selling_price=5, prep_station="bar")
    bar_order = await ac.post(
        "/api/v1/restaurant/orders",
        json={
            "service_mode": "dine_in",
            "payment_method": "cash",
            "table_id": table.json()["data"]["id"],
            "lines": [{"product_id": drink["id"], "quantity": "1"}],
        },
        headers=admin,
    )
    assert bar_order.status_code == 200, bar_order.text
    pending = (
        await db_session.execute(
            select(m.RestaurantOrderLine).where(
                m.RestaurantOrderLine.order_id == bar_order.json()["data"]["id"]
            )
        )
    ).scalars().first()
    early = await ac.post(
        f"/api/v1/restaurant/kitchen/lines/{pending.id}/ready",
        headers=admin,
        json={},
    )
    assert early.status_code == 409, early.text
    bar_sent = await ac.post(
        f"/api/v1/restaurant/orders/{bar_order.json()['data']['id']}/send",
        headers=admin,
    )
    assert bar_sent.status_code == 200, bar_sent.text
    queue = await ac.get("/api/v1/restaurant/kitchen", headers=admin)
    bar_id = bar_order.json()["data"]["id"]
    bar_ticket = next(row for row in queue.json()["data"] if row["order_id"] == bar_id)
    assert bar_ticket["station"] == "bar"
    assert bar_ticket["items"][0]["name"] == "Sobolo"
    assert all(row["station"] != "kitchen" for row in queue.json()["data"] if row["order_id"] == bar_id)
    done = await ac.post(f"/api/v1/restaurant/orders/{order_id}/complete", headers=admin)
    assert done.status_code == 200, done.text
    assert done.json()["data"]["status"] == "completed"
    stock = await ac.get(f"/api/v1/products/{ingredient['id']}", headers=admin)
    assert stock.status_code == 200, stock.text
    assert float(stock.json()["data"]["stock_qty"]) == 8
    summary = await ac.get("/api/v1/restaurant/summary", headers=admin)
    assert summary.json()["data"]["sales_today"] == 22
    assert summary.json()["data"]["tables"].get("occupied") == 1
    assert summary.json()["data"]["kitchen_queue"] == 0
    assert summary.json()["data"]["bar_queue"] == 1
    assert summary.json()["data"]["booking_requests"] == 0
    reports = await ac.get("/api/v1/restaurant/reports", headers=admin)
    modes = {row["service_mode"] for row in reports.json()["data"]["by_service_mode"]}
    assert "dine_in" in modes
    tenders = {row["payment_method"] for row in reports.json()["data"]["by_payment_method"]}
    assert "cash" in tenders
    side = await _product(ac, admin, name="Kenkey", selling_price=8, prep_station="kitchen")
    pair = await ac.post(
        "/api/v1/restaurant/orders",
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "lines": [
                {"product_id": dish["id"], "quantity": "1"},
                {"product_id": side["id"], "quantity": "1"},
            ],
        },
        headers=admin,
    )
    assert pair.status_code == 200, pair.text
    pair_id = pair.json()["data"]["id"]
    pair_sent = await ac.post(f"/api/v1/restaurant/orders/{pair_id}/send", headers=admin)
    assert pair_sent.status_code == 200, pair_sent.text
    pair_queue = await ac.get("/api/v1/restaurant/kitchen", headers=admin)
    pair_ticket = next(row for row in pair_queue.json()["data"] if row["order_id"] == pair_id)
    kenkey = next(item for item in pair_ticket["items"] if item["name"] == "Kenkey")
    half = await ac.post(f"/api/v1/restaurant/kitchen/lines/{kenkey['id']}/ready", headers=admin, json={})
    assert half.status_code == 200, half.text
    half_ticket = next(row for row in half.json()["data"] if row["order_id"] == pair_id)
    assert half_ticket["status"] == "preparing"
    assert next(item["prep_status"] for item in half_ticket["items"] if item["name"] == "Jollof") == "queued"
    assert next(item["prep_status"] for item in half_ticket["items"] if item["name"] == "Kenkey") == "ready"
    pair_desk = await ac.get("/api/v1/restaurant/orders", headers=admin)
    pair_listed = next(row for row in pair_desk.json()["data"] if row["id"] == pair_id)
    assert next(item["prep_status"] for item in pair_listed["items"] if item["name"] == "Jollof") == "queued"
    assert next(item["prep_status"] for item in pair_listed["items"] if item["name"] == "Kenkey") == "ready"
    beta = m.User(
        tenant_id=seed["t2"].id,
        email="admin@beta.example.com",
        full_name="Beta Admin",
        password_hash=hash_password("SecurePass123!"),
        role="company_admin",
        email_verified=True,
        permissions=permissions_for_role("company_admin"),
    )
    db_session.add(beta)
    await db_session.commit()
    await set_tenant_industry(db_session, seed["t2"], "restaurant")
    other = await auth_headers(ac, email="admin@beta.example.com", tenant_slug="beta")
    leaked = await ac.post(f"/api/v1/restaurant/orders/{order_id}/refund", headers=other)
    assert leaked.status_code == 404, leaked.text


async def test_store_scoped_user_cannot_see_another_store_table(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    store_a = await ac.post("/api/v1/stores", json={"name": "Kitchen A", "code": "KA"}, headers=admin)
    store_b = await ac.post("/api/v1/stores", json={"name": "Kitchen B", "code": "KB"}, headers=admin)
    assert store_a.status_code == 200, store_a.text
    assert store_b.status_code == 200, store_b.text
    table = await ac.post(
        "/api/v1/restaurant/tables",
        json={"code": "A1", "name": "Store A", "store_id": store_a.json()["data"]["id"]},
        headers=admin,
    )
    assert table.status_code == 200, table.text
    cashier = (
        await db_session.execute(select(m.User).where(m.User.email == "cashier@alpha.example.com"))
    ).scalar_one()
    db_session.add(
        m.UserStoreMembership(
            tenant_id=seed["t1"].id,
            user_id=cashier.id,
            store_id=store_b.json()["data"]["id"],
            is_active=True,
        )
    )
    await db_session.commit()
    scoped = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    listed = await ac.get("/api/v1/restaurant/tables", headers=scoped)
    assert listed.status_code == 200, listed.text
    assert all(row["code"] != "A1" for row in listed.json()["data"])


async def test_fmcg_pack_conversion_and_expired_lot_block(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "fmcg")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    piece = await ac.post("/api/v1/catalog/units", json={"name": "Piece", "code": "PCXF"}, headers=admin)
    assert piece.status_code == 200, piece.text
    carton = await ac.post(
        "/api/v1/catalog/units",
        json={
            "name": "Carton",
            "code": "CTNF",
            "base_unit_id": piece.json()["data"]["id"],
            "conversion_ratio": 12,
        },
        headers=admin,
    )
    assert carton.status_code == 200, carton.text
    product = await _product(
        ac,
        admin,
        name="Soap",
        selling_price=5,
        stock_qty=0,
        tracks_batches=True,
        unit_id=piece.json()["data"]["id"],
    )
    converted = await ac.post(
        "/api/v1/fmcg/pack-convert",
        json={"product_id": product["id"], "from_unit_id": carton.json()["data"]["id"], "quantity": 2},
        headers=admin,
    )
    assert converted.status_code == 403, converted.text
    assert converted.json()["detail"]["code"] == "INDUSTRY_MODULE_DISABLED"
    db_session.add(
        m.ProductBatch(
            tenant_id=seed["t1"].id,
            product_id=product["id"],
            batch_number="OLD",
            expiry_date=datetime.utcnow() - timedelta(days=2),
            quantity=5,
        )
    )
    await db_session.commit()
    blocked = await ac.post(
        "/api/v1/inventory/stock-out",
        json={"product_id": product["id"], "quantity": 1, "reference_type": "sale"},
        headers=admin,
    )
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["detail"]["code"] == "NO_SALEABLE_BATCH"
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    hotel = await ac.post(
        "/api/v1/fmcg/pack-convert",
        json={"product_id": product["id"], "from_unit_id": carton.json()["data"]["id"], "quantity": 1},
        headers=admin,
    )
    assert hotel.status_code == 403, hotel.text
    assert hotel.json()["detail"]["code"] == "INDUSTRY_MODULE_DISABLED"


async def _save_mock(ac, owner):
    saved = await ac.put(
        "/api/v1/platform/billing/gateway",
        json={"provider": "mock", "mode": "sandbox", "secret": "mocksecret1", "webhook_secret": "webhooksec1"},
        headers=owner,
    )
    assert saved.status_code == 200, saved.text
    assert "mocksecret1" not in saved.text
    assert saved.json()["data"]["connected"] is False
    return saved.json()["data"]


async def test_gateway_rejects_invalid_credentials_and_ssrf(client, db_session):
    ac, seed = client
    owner = await platform_owner_headers(ac, seed)
    bad = await ac.put(
        "/api/v1/platform/billing/gateway",
        json={"provider": "mock", "mode": "sandbox", "secret": "!!!"},
        headers=owner,
    )
    assert bad.status_code == 422, bad.text
    paystack = await ac.put(
        "/api/v1/platform/billing/gateway",
        json={"provider": "paystack", "mode": "sandbox", "secret": "not_a_test_key"},
        headers=owner,
    )
    assert paystack.status_code == 422, paystack.text
    ssrf = await ac.put(
        "/api/v1/platform/billing/gateway",
        json={
            "provider": "paystack",
            "mode": "sandbox",
            "api_base_url": "http://127.0.0.1/charge",
            "secret": "sk_test_abcdefgh",
        },
        headers=owner,
    )
    assert ssrf.status_code == 422, ssrf.text
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    forbidden = await ac.put(
        "/api/v1/platform/billing/gateway",
        json={"provider": "mock", "mode": "sandbox", "secret": "mocksecret1"},
        headers=admin,
    )
    assert forbidden.status_code == 403, forbidden.text


async def test_connection_test_does_not_charge(client, db_session):
    ac, seed = client
    owner = await platform_owner_headers(ac, seed)
    await _save_mock(ac, owner)
    early = await ac.post("/api/v1/platform/billing/gateway/enable", headers=owner)
    assert early.status_code == 422, early.text
    tested = await ac.post("/api/v1/platform/billing/gateway/test", headers=owner)
    assert tested.status_code == 200, tested.text
    tested_body = tested.json()["data"]
    assert tested_body["last_test_ok"] is True
    assert tested_body["last_test_at"]
    assert tested_body["last_test_message"] == "sandbox_ready"
    assert tested_body["enabled"] is False
    assert tested_body["connected"] is False
    assert tested_body["secret_configured"] is True
    assert "mocksecret1" not in tested.text
    assert "secret" not in tested_body
    assert "webhook_secret" not in tested_body
    assert MockGateway._charged == set()
    enabled = await ac.post("/api/v1/platform/billing/gateway/enable", headers=owner)
    assert enabled.status_code == 200, enabled.text
    assert enabled.json()["data"]["connected"] is True
    rotated = await ac.post(
        "/api/v1/platform/billing/gateway/rotate",
        json={"secret": "mocksecret2"},
        headers=owner,
    )
    assert rotated.status_code == 200, rotated.text
    assert rotated.json()["data"]["enabled"] is False
    assert rotated.json()["data"]["connected"] is False
    assert "mocksecret2" not in rotated.text


async def test_failed_connection_keeps_saved_gateway(client, db_session, monkeypatch):
    ac, seed = client
    owner = await platform_owner_headers(ac, seed)
    await _save_mock(ac, owner)
    monkeypatch.setattr(MockGateway, "test_connection", lambda self: (False, "sandbox_refused"))
    tested = await ac.post("/api/v1/platform/billing/gateway/test", headers=owner)
    assert tested.status_code == 200, tested.text
    tested_body = tested.json()["data"]
    assert tested_body["last_test_ok"] is False
    assert tested_body["last_test_message"] == "sandbox_refused"
    assert tested_body["last_test_at"]
    assert tested_body["enabled"] is False
    assert tested_body["secret_configured"] is True
    assert "mocksecret1" not in tested.text
    assert "secret" not in tested_body
    assert MockGateway._charged == set()
    status = await ac.get("/api/v1/platform/billing/status", headers=owner)
    assert status.status_code == 200, status.text
    payload = status.json()["data"]
    assert payload["configured"] is True
    assert payload["live_charges"] is False
    assert payload["gateway"]["secret_configured"] is True
    assert payload["gateway"]["last_test_ok"] is False
    assert payload["gateway"]["enabled"] is False
    assert "mocksecret1" not in status.text


async def _enable_mock(ac, owner):
    await _save_mock(ac, owner)
    tested = await ac.post("/api/v1/platform/billing/gateway/test", headers=owner)
    assert tested.status_code == 200, tested.text
    enabled = await ac.post("/api/v1/platform/billing/gateway/enable", headers=owner)
    assert enabled.status_code == 200, enabled.text


async def test_failed_renewal_does_not_capture(client, db_session):
    ac, seed = client
    owner = await platform_owner_headers(ac, seed)
    await _enable_mock(ac, owner)
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    past = (datetime.utcnow() - timedelta(days=1)).isoformat()
    assigned = await ac.post(
        "/api/v1/platform/billing/tenants/alpha/assign",
        json={"plan_code": "professional-month", "next_renewal_at": past},
        headers=owner,
    )
    assert assigned.status_code == 200, assigned.text
    consent = await ac.post(
        "/api/v1/billing/consent",
        json={"plan_code": "professional-month", "accept": True},
        headers=admin,
    )
    assert consent.status_code == 200, consent.text
    saved = await ac.post(
        "/api/v1/billing/sandbox/authorize",
        json={"authorization_code": "mock_auth_fail_card"},
        headers=admin,
    )
    assert saved.status_code == 200, saved.text
    failed = await job_process_subscription_renewals()
    assert failed["failed"] == 1
    assert failed["charged"] == 0
    assert MockGateway._charged == set()


async def test_successful_renewal_webhook_and_currencies(client, db_session):
    ac, seed = client
    owner = await platform_owner_headers(ac, seed)
    await _enable_mock(ac, owner)
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    past = (datetime.utcnow() - timedelta(days=1)).isoformat()
    assigned = await ac.post(
        "/api/v1/platform/billing/tenants/alpha/assign",
        json={"plan_code": "professional-month", "next_renewal_at": past},
        headers=owner,
    )
    assert assigned.status_code == 200, assigned.text
    consent = await ac.post(
        "/api/v1/billing/consent",
        json={"plan_code": "professional-month", "accept": True},
        headers=admin,
    )
    assert consent.status_code == 200, consent.text
    saved_ok = await ac.post(
        "/api/v1/billing/sandbox/authorize",
        json={"authorization_code": "mock_auth_ok_safe1"},
        headers=admin,
    )
    assert saved_ok.status_code == 200, saved_ok.text
    charged = await job_process_subscription_renewals()
    assert charged["charged"] == 1
    invoices = (await ac.get("/api/v1/billing/invoices", headers=admin)).json()["data"]
    assert invoices
    event = {
        "id": "evt-gateway-1",
        "event": "charge.success",
        "data": {
            "reference": invoices[0]["idempotency_key"],
            "amount": 49900,
            "currency": "GHS",
            "tenant_id": seed["t1"].id,
            "gateway_reference": "mock_tx_gateway",
        },
    }
    raw = json.dumps(event, separators=(",", ":")).encode()
    bad_sig = await ac.post(
        "/api/v1/billing/webhooks/mock",
        content=raw,
        headers={"x-ribdigi-billing-signature": "deadbeef", "content-type": "application/json"},
    )
    assert bad_sig.status_code == 401, bad_sig.text
    signature = _sign(raw, "webhooksec1")
    first = await ac.post(
        "/api/v1/billing/webhooks/mock",
        content=raw,
        headers={"x-ribdigi-billing-signature": signature, "content-type": "application/json"},
    )
    second = await ac.post(
        "/api/v1/billing/webhooks/mock",
        content=raw,
        headers={"x-ribdigi-billing-signature": signature, "content-type": "application/json"},
    )
    assert first.status_code == 200, first.text
    assert first.json()["data"]["duplicate"] is False
    assert second.json()["data"]["duplicate"] is True
    ghs = await ac.post(
        "/api/v1/platform/billing/plans",
        json={
            "code": "ghs-month",
            "name": "GHS month",
            "package_code": "professional",
            "interval": "month",
            "amount": "499.00",
            "currency": "GHS",
            "trial_days": 14,
            "grace_days": 7,
        },
        headers=owner,
    )
    assert ghs.status_code == 200, ghs.text
    usd = await ac.post(
        "/api/v1/platform/billing/plans",
        json={
            "code": "usd-month",
            "name": "USD month",
            "package_code": "professional",
            "interval": "month",
            "amount": "49.00",
            "currency": "USD",
            "trial_days": 0,
            "grace_days": 7,
        },
        headers=owner,
    )
    assert usd.status_code == 200, usd.text
    euro = await ac.post(
        "/api/v1/platform/billing/plans",
        json={
            "code": "eur-month",
            "name": "EUR month",
            "package_code": "professional",
            "interval": "month",
            "amount": "49.00",
            "currency": "EUR",
            "trial_days": 0,
            "grace_days": 7,
        },
        headers=owner,
    )
    assert euro.status_code == 422, euro.text
    assert settings.BILLING_PROVIDER


async def test_migration_skips_tables_that_already_exist():
    import importlib.util
    from pathlib import Path

    from sqlalchemy import create_engine, inspect

    from alembic.operations import Operations
    from alembic.runtime.migration import MigrationContext

    engine = create_engine("sqlite://")
    m.Base.metadata.create_all(engine)
    path = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "20261008_0135_restaurant_and_billing_gateway.py"
    spec = importlib.util.spec_from_file_location("restaurant_billing_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.down_revision == "20261008_0117"
    with engine.begin() as conn:
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            module.upgrade()
            module.upgrade()
        names = set(inspect(conn).get_table_names())
    assert "platform_billing_gateways" in names
    assert "restaurant_orders" in names
    assert "restaurant_tables" in names


async def test_restaurant_online_booking_links_a_website_or_domain(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    closed = await ac.get("/api/v1/public/restaurant-booking/alpha")
    assert closed.status_code == 404, closed.text
    junk = await ac.put(
        "/api/v1/restaurant/booking-link",
        headers=admin,
        json={"hostname": "!!!", "link_kind": "existing"},
    )
    assert junk.status_code == 422, junk.text
    existing = await ac.put(
        "/api/v1/restaurant/booking-link",
        headers=admin,
        json={"hostname": "https://www.bistro.example/menu", "link_kind": "existing"},
    )
    assert existing.status_code == 200, existing.text
    assert existing.json()["data"]["hostname"] == "bistro.example"
    assert existing.json()["data"]["link_kind"] == "existing"
    assert existing.json()["data"]["path"] == "/book/alpha"
    newer = await ac.put(
        "/api/v1/restaurant/booking-link",
        headers=admin,
        json={"hostname": "tables.example", "link_kind": "new"},
    )
    assert newer.status_code == 200, newer.text
    assert newer.json()["data"]["hostname"] == "tables.example"
    assert newer.json()["data"]["link_kind"] == "new"
    page = await ac.get("/api/v1/public/restaurant-booking/alpha")
    assert page.status_code == 200, page.text
    assert page.json()["data"]["open"] is True
    by_host = await ac.get("/api/v1/public/restaurant-booking/by-host", params={"host": "www.tables.example"})
    assert by_host.status_code == 200, by_host.text
    assert by_host.json()["data"]["slug"] == "alpha"
    charged = await ac.post(
        "/api/v1/public/restaurant-booking/alpha",
        json={
            "guest_name": "Ama Boateng",
            "phone": "+233241234567",
            "party_size": 4,
            "booked_for": (datetime.utcnow() + timedelta(days=1)).replace(microsecond=0).isoformat(),
            "notes": "Window table",
            "payment_method": "card",
        },
    )
    assert charged.status_code == 422, charged.text
    past = await ac.post(
        "/api/v1/public/restaurant-booking/alpha",
        json={
            "guest_name": "Ama Boateng",
            "phone": "+233241234567",
            "party_size": 4,
            "booked_for": (datetime.utcnow() - timedelta(hours=2)).replace(microsecond=0).isoformat(),
            "notes": "Window table",
        },
    )
    assert past.status_code == 422, past.text
    booked = await ac.post(
        "/api/v1/public/restaurant-booking/alpha",
        json={
            "guest_name": "Ama Boateng",
            "phone": "+233241234567",
            "party_size": 4,
            "booked_for": (datetime.utcnow() + timedelta(days=1)).replace(microsecond=0).isoformat(),
            "notes": "Window table",
        },
    )
    assert booked.status_code == 200, booked.text
    body = booked.json()["data"]
    assert body["status"] == "requested"
    assert body["party_size"] == 4
    assert body["booking_number"] == "B-0001"
    listed = await ac.get("/api/v1/restaurant/bookings", headers=admin)
    assert listed.status_code == 200, listed.text
    assert listed.json()["data"][0]["guest_name"] == "Ama Boateng"
    orders_before = await ac.get("/api/v1/restaurant/orders", headers=admin)
    assert orders_before.status_code == 200, orders_before.text
    small = await ac.post(
        "/api/v1/restaurant/tables",
        headers=admin,
        json={"code": "T2", "name": "Two seats", "seats": 2},
    )
    assert small.status_code == 200, small.text
    large = await ac.post(
        "/api/v1/restaurant/tables",
        headers=admin,
        json={"code": "T4", "name": "Four seats", "seats": 4},
    )
    assert large.status_code == 200, large.text
    too_small = await ac.post(
        f"/api/v1/restaurant/bookings/{body['id']}/seat",
        headers=admin,
        json={"table_id": small.json()["data"]["id"]},
    )
    assert too_small.status_code == 422, too_small.text
    junk_table = await ac.post(
        f"/api/v1/restaurant/bookings/{body['id']}/seat",
        headers=admin,
        json={"table_id": "!!!"},
    )
    assert junk_table.status_code == 422, junk_table.text
    missing = await ac.post(
        f"/api/v1/restaurant/bookings/{body['id']}/seat",
        headers=admin,
        json={"table_id": str(uuid.uuid4())},
    )
    assert missing.status_code == 404, missing.text
    charged_seat = await ac.post(
        f"/api/v1/restaurant/bookings/{body['id']}/seat",
        headers=admin,
        json={"table_id": large.json()["data"]["id"], "payment_method": "card"},
    )
    assert charged_seat.status_code == 422, charged_seat.text
    seated = await ac.post(
        f"/api/v1/restaurant/bookings/{body['id']}/seat",
        headers=admin,
        json={"table_id": large.json()["data"]["id"]},
    )
    assert seated.status_code == 200, seated.text
    assert seated.json()["data"]["status"] == "seated"
    assert seated.json()["data"]["table_id"] == large.json()["data"]["id"]
    again = await ac.post(
        f"/api/v1/restaurant/bookings/{body['id']}/seat",
        headers=admin,
        json={"table_id": large.json()["data"]["id"]},
    )
    assert again.status_code == 409, again.text
    tables = await ac.get("/api/v1/restaurant/tables", headers=admin)
    assert tables.status_code == 200, tables.text
    occupied = next(row for row in tables.json()["data"] if row["code"] == "T4")
    assert occupied["status"] == "occupied"
    walk_in = await ac.post(
        "/api/v1/public/restaurant-booking/alpha",
        json={
            "guest_name": "Kofi Mensah",
            "phone": "+233201112233",
            "party_size": 2,
            "booked_for": (datetime.utcnow() + timedelta(days=2)).replace(microsecond=0).isoformat(),
        },
    )
    assert walk_in.status_code == 200, walk_in.text
    unassigned = await ac.post(
        f"/api/v1/restaurant/bookings/{walk_in.json()['data']['id']}/seat",
        headers=admin,
    )
    assert unassigned.status_code == 200, unassigned.text
    assert unassigned.json()["data"]["status"] == "seated"
    assert unassigned.json()["data"]["table_id"] is None
    taken = await ac.post(
        "/api/v1/public/restaurant-booking/alpha",
        json={
            "guest_name": "Abena Owusu",
            "phone": "+233244445555",
            "party_size": 2,
            "booked_for": (datetime.utcnow() + timedelta(days=2)).replace(microsecond=0).isoformat(),
        },
    )
    assert taken.status_code == 200, taken.text
    busy = await ac.post(
        f"/api/v1/restaurant/bookings/{taken.json()['data']['id']}/seat",
        headers=admin,
        json={"table_id": large.json()["data"]["id"]},
    )
    assert busy.status_code == 409, busy.text
    orders_after = await ac.get("/api/v1/restaurant/orders", headers=admin)
    assert orders_after.status_code == 200, orders_after.text
    assert len(orders_after.json()["data"]) == len(orders_before.json()["data"])
    early = await ac.post(
        f"/api/v1/restaurant/bookings/{taken.json()['data']['id']}/finish",
        headers=admin,
    )
    assert early.status_code == 409, early.text
    charged_finish = await ac.post(
        f"/api/v1/restaurant/bookings/{body['id']}/finish",
        headers=admin,
        json={"payment_method": "card"},
    )
    assert charged_finish.status_code == 422, charged_finish.text
    finished = await ac.post(f"/api/v1/restaurant/bookings/{body['id']}/finish", headers=admin)
    assert finished.status_code == 200, finished.text
    assert finished.json()["data"]["status"] == "finished"
    freed = await ac.get("/api/v1/restaurant/tables", headers=admin)
    assert next(row for row in freed.json()["data"] if row["code"] == "T4")["status"] == "available"
    twice = await ac.post(f"/api/v1/restaurant/bookings/{body['id']}/finish", headers=admin)
    assert twice.status_code == 409, twice.text
    walk_done = await ac.post(
        f"/api/v1/restaurant/bookings/{walk_in.json()['data']['id']}/finish",
        headers=admin,
    )
    assert walk_done.status_code == 200, walk_done.text
    reseat = await ac.post(
        f"/api/v1/restaurant/bookings/{taken.json()['data']['id']}/seat",
        headers=admin,
        json={"table_id": large.json()["data"]["id"]},
    )
    assert reseat.status_code == 200, reseat.text
    dish = await _product(ac, admin, name="Banku", selling_price=10, stock_qty=5)
    quick = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "dine_in",
            "payment_method": "cash",
            "table_id": large.json()["data"]["id"],
            "lines": [{"product_id": dish["id"], "quantity": "1"}],
        },
    )
    assert quick.status_code == 200, quick.text
    closed = await ac.post(
        f"/api/v1/restaurant/orders/{quick.json()['data']['id']}/complete",
        headers=admin,
    )
    assert closed.status_code == 200, closed.text
    kept = await ac.get("/api/v1/restaurant/tables", headers=admin)
    assert next(row for row in kept.json()["data"] if row["code"] == "T4")["status"] == "occupied"
    held = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "dine_in",
            "payment_method": "cash",
            "table_id": large.json()["data"]["id"],
            "lines": [{"product_id": dish["id"], "quantity": "1"}],
        },
    )
    assert held.status_code == 200, held.text
    released = await ac.post(
        f"/api/v1/restaurant/bookings/{taken.json()['data']['id']}/finish",
        headers=admin,
    )
    assert released.status_code == 200, released.text
    assert released.json()["data"]["status"] == "finished"
    still = await ac.get("/api/v1/restaurant/tables", headers=admin)
    assert next(row for row in still.json()["data"] if row["code"] == "T4")["status"] == "occupied"
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    hotel = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    denied = await ac.get("/api/v1/restaurant/booking-link", headers=hotel)
    assert denied.status_code == 403, denied.text
    denied_finish = await ac.post(f"/api/v1/restaurant/bookings/{body['id']}/finish", headers=hotel)
    assert denied_finish.status_code == 403, denied_finish.text
    gone = await ac.get("/api/v1/public/restaurant-booking/alpha")
    assert gone.status_code == 404, gone.text


async def test_restaurant_staff_records_walk_in_booking(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    junk = await ac.post(
        "/api/v1/restaurant/bookings",
        headers=admin,
        json={
            "guest_name": "Ama Walkin",
            "phone": "123",
            "party_size": 2,
            "booked_for": (datetime.utcnow() + timedelta(hours=1)).replace(microsecond=0).isoformat(),
        },
    )
    assert junk.status_code == 422, junk.text
    saved = await ac.post(
        "/api/v1/restaurant/bookings",
        headers=admin,
        json={
            "guest_name": "Ama Walkin",
            "phone": "+233241234567",
            "party_size": 3,
            "booked_for": (datetime.utcnow() + timedelta(hours=1)).replace(microsecond=0).isoformat(),
            "notes": "Window",
        },
    )
    assert saved.status_code == 200, saved.text
    body = saved.json()["data"]
    assert body["guest_name"] == "Ama Walkin"
    assert body["party_size"] == 3
    assert body["status"] == "requested"
    listed = await ac.get("/api/v1/restaurant/bookings", headers=admin)
    assert listed.status_code == 200, listed.text
    assert any(row["guest_name"] == "Ama Walkin" for row in listed.json()["data"])
    booking_id = body["id"]
    blank = await ac.patch(f"/api/v1/restaurant/bookings/{booking_id}", headers=admin, json={})
    assert blank.status_code == 422, blank.text
    patched = await ac.patch(
        f"/api/v1/restaurant/bookings/{booking_id}",
        headers=admin,
        json={"notes": "Window seat", "party_size": 2},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["data"]["notes"] == "Window seat"
    assert patched.json()["data"]["party_size"] == 2
    seated = await ac.post(
        f"/api/v1/restaurant/bookings/{booking_id}/seat",
        headers=admin,
        json={},
    )
    assert seated.status_code == 200, seated.text
    late = await ac.patch(
        f"/api/v1/restaurant/bookings/{booking_id}",
        headers=admin,
        json={"notes": "Too late"},
    )
    assert late.status_code == 409, late.text


async def test_restaurant_order_refuses_recipe_ingredient(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    rice = await _product(ac, admin, name="Rice", selling_price=1, stock_qty=8)
    dish = await _product(ac, admin, name="Jollof", selling_price=20, prep_station="kitchen")
    recipe = await ac.post(
        "/api/v1/restaurant/recipes",
        json={
            "product_id": dish["id"],
            "name": "Jollof recipe",
            "lines": [{"ingredient_id": rice["id"], "quantity": "2"}],
        },
        headers=admin,
    )
    assert recipe.status_code == 200, recipe.text
    sold_rice = await ac.post(
        "/api/v1/restaurant/orders",
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "lines": [{"product_id": rice["id"], "quantity": "1"}],
        },
        headers=admin,
    )
    assert sold_rice.status_code == 422, sold_rice.text
    assert sold_rice.json()["detail"] == "Choose a menu item."
    dumped_dish = await ac.post(
        "/api/v1/restaurant/waste",
        headers=admin,
        json={"product_id": dish["id"], "quantity": "1", "reason": "spoilage"},
    )
    assert dumped_dish.status_code == 422, dumped_dish.text
    assert dumped_dish.json()["detail"] == "Choose an ingredient."
    sold_dish = await ac.post(
        "/api/v1/restaurant/orders",
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "lines": [{"product_id": dish["id"], "quantity": "1"}],
        },
        headers=admin,
    )
    assert sold_dish.status_code == 200, sold_dish.text
    assert sold_dish.json()["data"]["total_amount"] == 20
    listed_orders = await ac.get("/api/v1/restaurant/orders", headers=admin)
    saved_order = next(
        row for row in listed_orders.json()["data"] if row["id"] == sold_dish.json()["data"]["id"]
    )
    assert saved_order["items"][0]["name"] == "Jollof"


async def test_restaurant_updates_and_retires_a_table(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    saved = await ac.post(
        "/api/v1/restaurant/tables",
        json={"code": "T4", "name": "Garden", "seats": 2},
        headers=admin,
    )
    assert saved.status_code == 200, saved.text
    table_id = saved.json()["data"]["id"]
    junk = await ac.patch(
        f"/api/v1/restaurant/tables/{table_id}",
        headers=admin,
        json={"name": "!!!"},
    )
    assert junk.status_code in {400, 422}, junk.text
    patched = await ac.patch(
        f"/api/v1/restaurant/tables/{table_id}",
        headers=admin,
        json={"name": "Patio", "seats": 6},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["data"]["name"] == "Patio"
    assert patched.json()["data"]["seats"] == 6
    recoded = await ac.patch(
        f"/api/v1/restaurant/tables/{table_id}",
        headers=admin,
        json={"code": "T9"},
    )
    assert recoded.status_code == 200, recoded.text
    assert recoded.json()["data"]["code"] == "T9"
    assert recoded.json()["data"]["name"] == "Patio"
    floor = await ac.post("/api/v1/stores", json={"name": "Main Floor", "code": "TF59"}, headers=admin)
    assert floor.status_code == 200, floor.text
    floor_id = floor.json()["data"]["id"]
    missing_store = await ac.patch(
        f"/api/v1/restaurant/tables/{table_id}",
        headers=admin,
        json={"store_id": str(uuid.uuid4())},
    )
    assert missing_store.status_code == 404, missing_store.text
    moved = await ac.patch(
        f"/api/v1/restaurant/tables/{table_id}",
        headers=admin,
        json={"store_id": floor_id},
    )
    assert moved.status_code == 200, moved.text
    assert moved.json()["data"]["store_id"] == floor_id
    cleared_store = await ac.patch(
        f"/api/v1/restaurant/tables/{table_id}",
        headers=admin,
        json={"store_id": None},
    )
    assert cleared_store.status_code == 200, cleared_store.text
    assert cleared_store.json()["data"]["store_id"] is None
    held = await ac.post(f"/api/v1/restaurant/tables/{table_id}/hold", headers=admin, json={})
    assert held.status_code == 200, held.text
    busy = await ac.post(f"/api/v1/restaurant/tables/{table_id}/retire", headers=admin, json={})
    assert busy.status_code == 409, busy.text
    freed = await ac.post(f"/api/v1/restaurant/tables/{table_id}/release", headers=admin, json={})
    assert freed.status_code == 200, freed.text
    retired = await ac.post(f"/api/v1/restaurant/tables/{table_id}/retire", headers=admin, json={})
    assert retired.status_code == 200, retired.text
    assert retired.json()["data"]["is_active"] is False
    listed = await ac.get("/api/v1/restaurant/tables", headers=admin)
    assert listed.status_code == 200, listed.text
    assert all(row["id"] != table_id for row in listed.json()["data"])


async def test_restaurant_retires_an_extra(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    group = await ac.post("/api/v1/restaurant/modifier-groups", json={"name": "Sides"}, headers=admin)
    assert group.status_code == 200, group.text
    extra = await ac.post(
        f"/api/v1/restaurant/modifier-groups/{group.json()['data']['id']}/modifiers",
        json={"name": "Plantain", "price": "3"},
        headers=admin,
    )
    assert extra.status_code == 200, extra.text
    extra_id = extra.json()["data"]["id"]
    blank = await ac.patch(f"/api/v1/restaurant/modifiers/{extra_id}", headers=admin, json={})
    assert blank.status_code == 422, blank.text
    priced = await ac.patch(
        f"/api/v1/restaurant/modifiers/{extra_id}",
        headers=admin,
        json={"price": "4.50"},
    )
    assert priced.status_code == 200, priced.text
    assert priced.json()["data"]["price"] == 4.5
    listed_priced = await ac.get("/api/v1/restaurant/modifiers", headers=admin)
    assert listed_priced.status_code == 200, listed_priced.text
    leftover_priced = listed_priced.json()["data"][0]["modifiers"]
    assert leftover_priced[0]["name"] == "Plantain"
    assert leftover_priced[0]["price"] == 4.5
    named = await ac.patch(
        f"/api/v1/restaurant/modifiers/{extra_id}",
        headers=admin,
        json={"name": "Ripe plantain"},
    )
    assert named.status_code == 200, named.text
    assert named.json()["data"]["name"] == "Ripe plantain"
    listed_named = await ac.get("/api/v1/restaurant/modifiers", headers=admin)
    assert listed_named.status_code == 200, listed_named.text
    leftover_named = listed_named.json()["data"][0]["modifiers"]
    assert leftover_named[0]["name"] == "Ripe plantain"
    assert leftover_named[0]["price"] == 4.5
    group_id = group.json()["data"]["id"]
    busy_group = await ac.post(
        f"/api/v1/restaurant/modifier-groups/{group_id}/retire",
        headers=admin,
        json={},
    )
    assert busy_group.status_code == 409, busy_group.text
    assert busy_group.json()["detail"] == "Retire leftover extras first."
    blank_group = await ac.patch(
        f"/api/v1/restaurant/modifier-groups/{group_id}",
        headers=admin,
        json={},
    )
    assert blank_group.status_code == 422, blank_group.text
    named_group = await ac.patch(
        f"/api/v1/restaurant/modifier-groups/{group_id}",
        headers=admin,
        json={"name": "Add-ons"},
    )
    assert named_group.status_code == 200, named_group.text
    assert named_group.json()["data"]["name"] == "Add-ons"
    retired = await ac.post(f"/api/v1/restaurant/modifiers/{extra_id}/retire", headers=admin, json={})
    assert retired.status_code == 200, retired.text
    assert retired.json()["data"]["is_active"] is False
    again = await ac.post(f"/api/v1/restaurant/modifiers/{extra_id}/retire", headers=admin, json={})
    assert again.status_code == 409, again.text
    late = await ac.patch(
        f"/api/v1/restaurant/modifiers/{extra_id}",
        headers=admin,
        json={"price": "6"},
    )
    assert late.status_code == 409, late.text
    listed = await ac.get("/api/v1/restaurant/modifiers", headers=admin)
    assert listed.status_code == 200, listed.text
    leftover = listed.json()["data"]
    assert leftover[0]["name"] == "Add-ons"
    assert leftover[0]["modifiers"] == []
    retired_group = await ac.post(
        f"/api/v1/restaurant/modifier-groups/{group_id}/retire",
        headers=admin,
        json={},
    )
    assert retired_group.status_code == 200, retired_group.text
    assert retired_group.json()["data"]["is_active"] is False
    again_group = await ac.post(
        f"/api/v1/restaurant/modifier-groups/{group_id}/retire",
        headers=admin,
        json={},
    )
    assert again_group.status_code == 409, again_group.text
    late_group = await ac.patch(
        f"/api/v1/restaurant/modifier-groups/{group_id}",
        headers=admin,
        json={"name": "Sides"},
    )
    assert late_group.status_code == 409, late_group.text
    hidden = await ac.get("/api/v1/restaurant/modifiers", headers=admin)
    assert hidden.status_code == 200, hidden.text
    assert hidden.json()["data"] == []


async def test_restaurant_adds_leftover_item_to_open_order(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    dish = await _product(ac, admin, name="Jollof", selling_price=20, prep_station="kitchen", stock_qty=5)
    drink = await _product(ac, admin, name="Sobolo", selling_price=5, prep_station="bar", stock_qty=5)
    opened = await ac.post(
        "/api/v1/restaurant/orders",
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "lines": [{"product_id": dish["id"], "quantity": "1"}],
        },
        headers=admin,
    )
    assert opened.status_code == 200, opened.text
    order_id = opened.json()["data"]["id"]
    blank = await ac.patch(f"/api/v1/restaurant/orders/{order_id}", headers=admin, json={})
    assert blank.status_code == 422, blank.text
    patched = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={
            "notes": "No pepper",
            "lines": [{"product_id": drink["id"], "quantity": "1"}],
        },
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["data"]["total_amount"] == 25
    assert patched.json()["data"]["notes"] == "No pepper"
    listed = await ac.get("/api/v1/restaurant/orders", headers=admin)
    saved = next(row for row in listed.json()["data"] if row["id"] == order_id)
    assert {item["name"] for item in saved["items"]} == {"Jollof", "Sobolo"}
    drink_line = next(item for item in saved["items"] if item["name"] == "Sobolo")
    missing = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"remove_line_ids": [str(uuid.uuid4())]},
    )
    assert missing.status_code == 404, missing.text
    removed = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"remove_line_ids": [drink_line["id"]]},
    )
    assert removed.status_code == 200, removed.text
    assert removed.json()["data"]["total_amount"] == 20
    leftover = await ac.get("/api/v1/restaurant/orders", headers=admin)
    leftover_row = next(row for row in leftover.json()["data"] if row["id"] == order_id)
    assert [item["name"] for item in leftover_row["items"]] == ["Jollof"]
    named = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"customer_name": "Ama Diner"},
    )
    assert named.status_code == 200, named.text
    assert named.json()["data"]["customer_name"] == "Ama Diner"
    paid = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"payment_method": "card"},
    )
    assert paid.status_code == 200, paid.text
    assert paid.json()["data"]["payment_method"] == "card"
    junk_pay = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"payment_method": "gift_card"},
    )
    assert junk_pay.status_code == 422, junk_pay.text
    floor = await ac.post(
        "/api/v1/restaurant/tables",
        json={"code": "T8", "name": "Patio", "seats": 4},
        headers=admin,
    )
    assert floor.status_code == 200, floor.text
    table_id = floor.json()["data"]["id"]
    needs_table = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"service_mode": "dine_in"},
    )
    assert needs_table.status_code == 422, needs_table.text
    assert needs_table.json()["detail"] == "Dine in needs a table."
    seated = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"service_mode": "dine_in", "table_id": table_id},
    )
    assert seated.status_code == 200, seated.text
    assert seated.json()["data"]["service_mode"] == "dine_in"
    assert seated.json()["data"]["table_id"] == table_id
    occupied = await ac.get("/api/v1/restaurant/tables", headers=admin)
    assert next(row for row in occupied.json()["data"] if row["id"] == table_id)["status"] == "occupied"
    needs_address = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"service_mode": "delivery"},
    )
    assert needs_address.status_code == 422, needs_address.text
    delivered = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"service_mode": "delivery", "delivery_address": "12 Market Street"},
    )
    assert delivered.status_code == 200, delivered.text
    assert delivered.json()["data"]["service_mode"] == "delivery"
    assert delivered.json()["data"]["delivery_address"] == "12 Market Street"
    assert delivered.json()["data"]["table_id"] is None
    back = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"service_mode": "takeaway"},
    )
    assert back.status_code == 200, back.text
    assert back.json()["data"]["service_mode"] == "takeaway"
    assert back.json()["data"]["delivery_address"] is None
    freed = await ac.get("/api/v1/restaurant/tables", headers=admin)
    assert next(row for row in freed.json()["data"] if row["id"] == table_id)["status"] == "available"
    line_id = leftover_row["items"][0]["id"]
    missing_qty = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"line_quantities": [{"line_id": str(uuid.uuid4()), "quantity": "2"}]},
    )
    assert missing_qty.status_code == 404, missing_qty.text
    doubled = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"line_quantities": [{"line_id": line_id, "quantity": "2"}]},
    )
    assert doubled.status_code == 200, doubled.text
    assert doubled.json()["data"]["total_amount"] == 40
    counted = await ac.get("/api/v1/restaurant/orders", headers=admin)
    counted_row = next(row for row in counted.json()["data"] if row["id"] == order_id)
    assert counted_row["items"][0]["quantity"] == 2
    restored = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"line_quantities": [{"line_id": line_id, "quantity": "1"}]},
    )
    assert restored.status_code == 200, restored.text
    assert restored.json()["data"]["total_amount"] == 20
    missing_price = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"line_prices": [{"line_id": str(uuid.uuid4()), "unit_price": "15"}]},
    )
    assert missing_price.status_code == 404, missing_price.text
    priced = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"line_prices": [{"line_id": line_id, "unit_price": "15"}]},
    )
    assert priced.status_code == 200, priced.text
    assert priced.json()["data"]["total_amount"] == 15
    priced_list = await ac.get("/api/v1/restaurant/orders", headers=admin)
    priced_row = next(row for row in priced_list.json()["data"] if row["id"] == order_id)
    assert priced_row["items"][0]["unit_price"] == 15
    restored_price = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"line_prices": [{"line_id": line_id, "unit_price": "20"}]},
    )
    assert restored_price.status_code == 200, restored_price.text
    assert restored_price.json()["data"]["total_amount"] == 20
    missing_station = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"line_stations": [{"line_id": str(uuid.uuid4()), "station": "bar"}]},
    )
    assert missing_station.status_code == 404, missing_station.text
    moved_station = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"line_stations": [{"line_id": line_id, "station": "bar"}]},
    )
    assert moved_station.status_code == 200, moved_station.text
    station_list = await ac.get("/api/v1/restaurant/orders", headers=admin)
    station_row = next(row for row in station_list.json()["data"] if row["id"] == order_id)
    assert station_row["items"][0]["station"] == "bar"
    restored_station = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"line_stations": [{"line_id": line_id, "station": "kitchen"}]},
    )
    assert restored_station.status_code == 200, restored_station.text
    kitchen_list = await ac.get("/api/v1/restaurant/orders", headers=admin)
    kitchen_row = next(row for row in kitchen_list.json()["data"] if row["id"] == order_id)
    assert kitchen_row["items"][0]["station"] == "kitchen"
    extra_group = await ac.post("/api/v1/restaurant/modifier-groups", json={"name": "Service"}, headers=admin)
    assert extra_group.status_code == 200, extra_group.text
    extra = await ac.post(
        f"/api/v1/restaurant/modifier-groups/{extra_group.json()['data']['id']}/modifiers",
        json={"name": "Table service", "price": "10"},
        headers=admin,
    )
    assert extra.status_code == 200, extra.text
    extra_id = extra.json()["data"]["id"]
    missing_extra = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"line_modifiers": [{"line_id": line_id, "modifier_ids": [str(uuid.uuid4())]}]},
    )
    assert missing_extra.status_code == 404, missing_extra.text
    with_extra = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"line_modifiers": [{"line_id": line_id, "modifier_ids": [extra_id]}]},
    )
    assert with_extra.status_code == 200, with_extra.text
    assert with_extra.json()["data"]["total_amount"] == 30
    extra_listed = await ac.get("/api/v1/restaurant/orders", headers=admin)
    extra_row = next(row for row in extra_listed.json()["data"] if row["id"] == order_id)
    assert extra_row["items"][0]["modifiers"] == ["Table service"]
    assert extra_id in extra_row["items"][0]["modifier_ids"]
    cleared_extra = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"line_modifiers": [{"line_id": line_id, "modifier_ids": []}]},
    )
    assert cleared_extra.status_code == 200, cleared_extra.text
    assert cleared_extra.json()["data"]["total_amount"] == 20
    await ac.post(f"/api/v1/restaurant/modifiers/{extra_id}/retire", headers=admin, json={})
    retired_extra = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"line_modifiers": [{"line_id": line_id, "modifier_ids": [extra_id]}]},
    )
    assert retired_extra.status_code == 409, retired_extra.text
    floor = await ac.post("/api/v1/stores", json={"name": "Main Floor", "code": "MF58"}, headers=admin)
    assert floor.status_code == 200, floor.text
    floor_id = floor.json()["data"]["id"]
    missing_store = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"store_id": str(uuid.uuid4())},
    )
    assert missing_store.status_code == 404, missing_store.text
    moved = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"store_id": floor_id},
    )
    assert moved.status_code == 200, moved.text
    assert moved.json()["data"]["store_id"] == floor_id
    cleared_store = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"store_id": None},
    )
    assert cleared_store.status_code == 200, cleared_store.text
    assert cleared_store.json()["data"]["store_id"] is None
    last = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"remove_line_ids": [leftover_row["items"][0]["id"]]},
    )
    assert last.status_code == 422, last.text
    done = await ac.post(f"/api/v1/restaurant/orders/{order_id}/complete", headers=admin)
    assert done.status_code == 200, done.text
    late = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"notes": "Too late"},
    )
    assert late.status_code == 409, late.text


async def test_restaurant_order_line_course(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    dish = await _product(ac, admin, name="Jollof", selling_price=20, prep_station="kitchen")
    opened = await ac.post(
        "/api/v1/restaurant/orders",
        json={
            "service_mode": "delivery",
            "payment_method": "cash",
            "delivery_address": "12 Market Street",
            "notes": "Gate",
            "lines": [{"product_id": dish["id"], "quantity": "1", "course": "starter"}],
        },
        headers=admin,
    )
    assert opened.status_code == 200, opened.text
    body = opened.json()["data"]
    order_id = body["id"]
    assert body["notes"] == "Gate"
    assert body["delivery_address"] == "12 Market Street"
    assert "[[course:" not in (body["notes"] or "")
    listed = await ac.get("/api/v1/restaurant/orders", headers=admin)
    saved = next(row for row in listed.json()["data"] if row["id"] == order_id)
    line = saved["items"][0]
    assert line["course"] == "starter"
    moved = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"delivery_address": "14 Market Street", "notes": "Side door"},
    )
    assert moved.status_code == 200, moved.text
    assert moved.json()["data"]["notes"] == "Side door"
    assert moved.json()["data"]["delivery_address"] == "14 Market Street"
    still = await ac.get("/api/v1/restaurant/orders", headers=admin)
    still_row = next(row for row in still.json()["data"] if row["id"] == order_id)
    assert still_row["items"][0]["course"] == "starter"
    changed = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"line_courses": [{"line_id": line["id"], "course": "dessert"}]},
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["data"]["notes"] == "Side door"
    after = await ac.get("/api/v1/restaurant/orders", headers=admin)
    after_row = next(row for row in after.json()["data"] if row["id"] == order_id)
    assert after_row["items"][0]["course"] == "dessert"
    main = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"line_courses": [{"line_id": line["id"], "course": "main"}]},
    )
    assert main.status_code == 200, main.text
    cleared = await ac.get("/api/v1/restaurant/orders", headers=admin)
    cleared_row = next(row for row in cleared.json()["data"] if row["id"] == order_id)
    assert cleared_row["items"][0]["course"] == "main"
    junk = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"line_courses": [{"line_id": line["id"], "course": "soup"}]},
    )
    assert junk.status_code == 422, junk.text
    missing = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"line_courses": [{"line_id": str(uuid.uuid4()), "course": "drink"}]},
    )
    assert missing.status_code == 404, missing.text
    sent = await ac.post(f"/api/v1/restaurant/orders/{order_id}/send", headers=admin)
    assert sent.status_code == 200, sent.text
    drink = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"line_courses": [{"line_id": line["id"], "course": "drink"}]},
    )
    assert drink.status_code == 200, drink.text
    kitchen = await ac.get("/api/v1/restaurant/kitchen", headers=admin)
    ticket = next(row for row in kitchen.json()["data"] if row["order_id"] == order_id)
    assert ticket["items"][0]["course"] == "drink"
    assert ticket["notes"] == "Side door"
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    denied = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"line_courses": [{"line_id": line["id"], "course": "starter"}]},
    )
    assert denied.status_code == 403, denied.text


async def test_restaurant_delivery_zones(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    tenant = seed["t1"]
    tenant.document_numbering = {"pos_sale": {"prefix": "POS", "next": 4, "year": 2026}}
    await db_session.commit()
    blank = await ac.put("/api/v1/restaurant/delivery-zones", headers=admin, json={"names": [" "]})
    assert blank.status_code == 422, blank.text
    junk = await ac.put(
        "/api/v1/restaurant/delivery-zones",
        headers=admin,
        json={"names": ["http://east.example"]},
    )
    assert junk.status_code == 422, junk.text
    saved = await ac.put(
        "/api/v1/restaurant/delivery-zones",
        headers=admin,
        json={"names": ["East Legon", "Airport"]},
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["data"] == ["East Legon", "Airport"]
    duplicate = await ac.put(
        "/api/v1/restaurant/delivery-zones",
        headers=admin,
        json={"names": ["East Legon", "east legon"]},
    )
    assert duplicate.status_code == 422, duplicate.text
    listed = await ac.get("/api/v1/restaurant/delivery-zones", headers=admin)
    assert listed.status_code == 200, listed.text
    assert listed.json()["data"] == ["East Legon", "Airport"]
    await db_session.refresh(tenant)
    assert tenant.document_numbering["pos_sale"]["prefix"] == "POS"
    assert tenant.document_numbering["restaurant_delivery_zones"] == ["East Legon", "Airport"]
    dish = await _product(ac, admin, name="Jollof", selling_price=20, prep_station="kitchen")
    missing = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "delivery",
            "payment_method": "cash",
            "delivery_address": "12 Market Street",
            "lines": [{"product_id": dish["id"], "quantity": "1", "course": "starter"}],
        },
    )
    assert missing.status_code == 422, missing.text
    unknown = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "delivery",
            "payment_method": "cash",
            "delivery_address": "12 Market Street",
            "delivery_zone": "Tema",
            "lines": [{"product_id": dish["id"], "quantity": "1"}],
        },
    )
    assert unknown.status_code == 422, unknown.text
    opened = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "delivery",
            "payment_method": "cash",
            "delivery_address": "12 Market Street",
            "delivery_zone": "east legon",
            "notes": "Gate",
            "lines": [{"product_id": dish["id"], "quantity": "1", "course": "starter"}],
        },
    )
    assert opened.status_code == 200, opened.text
    body = opened.json()["data"]
    assert body["delivery_zone"] == "East Legon"
    assert body["delivery_address"] == "12 Market Street"
    assert body["notes"] == "Gate"
    assert "[[zone:" not in (body["notes"] or "")
    order_id = body["id"]
    moved = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"delivery_address": "14 Market Street", "notes": "Side door"},
    )
    assert moved.status_code == 200, moved.text
    assert moved.json()["data"]["delivery_zone"] == "East Legon"
    assert moved.json()["data"]["notes"] == "Side door"
    rows = await ac.get("/api/v1/restaurant/orders", headers=admin)
    saved_order = next(row for row in rows.json()["data"] if row["id"] == order_id)
    assert saved_order["items"][0]["course"] == "starter"
    sent = await ac.post(f"/api/v1/restaurant/orders/{order_id}/send", headers=admin)
    assert sent.status_code == 200, sent.text
    kitchen = await ac.get("/api/v1/restaurant/kitchen", headers=admin)
    ticket = next(row for row in kitchen.json()["data"] if row["order_id"] == order_id)
    assert ticket["delivery_zone"] == "East Legon"
    assert ticket["notes"] == "Side door"
    cleared = await ac.put("/api/v1/restaurant/delivery-zones", headers=admin, json={"names": []})
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["data"] == []
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    denied = await ac.put(
        "/api/v1/restaurant/delivery-zones",
        headers=admin,
        json={"names": ["East Legon"]},
    )
    assert denied.status_code == 403, denied.text


async def test_restaurant_online_orders(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    tenant = seed["t1"]
    tenant.document_numbering = {"pos_sale": {"prefix": "POS", "next": 4, "year": 2026}}
    await db_session.commit()
    closed = await ac.get("/api/v1/public/restaurant-order/alpha")
    assert closed.status_code == 404, closed.text
    desk = await ac.get("/api/v1/restaurant/online-orders", headers=admin)
    assert desk.status_code == 200, desk.text
    assert desk.json()["data"]["open"] is False
    assert desk.json()["data"]["qr"] is None
    assert desk.json()["data"]["path"] == "/order/alpha"
    opened = await ac.put("/api/v1/restaurant/online-orders", headers=admin, json={"open": True})
    assert opened.status_code == 200, opened.text
    assert opened.json()["data"]["open"] is True
    assert str(opened.json()["data"]["qr"]).startswith("data:image/png;base64,")
    assert opened.json()["data"]["order_url"].endswith("/order/alpha")
    await db_session.refresh(tenant)
    assert tenant.document_numbering["pos_sale"]["prefix"] == "POS"
    assert tenant.document_numbering["restaurant_online_orders"] is True
    dish = await _product(ac, admin, name="Jollof", selling_price=20, prep_station="kitchen")
    rice = await _product(ac, admin, name="Rice", selling_price=4)
    page = await ac.get("/api/v1/public/restaurant-order/alpha")
    assert page.status_code == 200, page.text
    names = [row["name"] for row in page.json()["data"]["menu"]]
    assert "Jollof" in names
    assert "Rice" not in names
    blank = await ac.post(
        "/api/v1/public/restaurant-order/alpha",
        json={"customer_name": " ", "lines": [{"product_id": dish["id"], "quantity": 1}]},
    )
    assert blank.status_code == 422, blank.text
    junk = await ac.post(
        "/api/v1/public/restaurant-order/alpha",
        json={"customer_name": "http://guest.example", "lines": [{"product_id": dish["id"], "quantity": 1}]},
    )
    assert junk.status_code == 422, junk.text
    ingredient = await ac.post(
        "/api/v1/public/restaurant-order/alpha",
        json={"customer_name": "Ama", "lines": [{"product_id": rice["id"], "quantity": 1}]},
    )
    assert ingredient.status_code == 422, ingredient.text
    priced = await ac.post(
        "/api/v1/public/restaurant-order/alpha",
        json={
            "customer_name": "Ama",
            "lines": [{"product_id": dish["id"], "quantity": 1, "unit_price": 0}],
        },
    )
    assert priced.status_code == 422, priced.text
    placed = await ac.post(
        "/api/v1/public/restaurant-order/alpha",
        json={
            "customer_name": "Ama",
            "notes": "No pepper",
            "lines": [{"product_id": dish["id"], "quantity": 1}],
        },
    )
    assert placed.status_code == 200, placed.text
    body = placed.json()["data"]
    assert body["channel"] == "online"
    assert body["status"] == "open"
    assert body["service_mode"] == "takeaway"
    assert body["pay_at_counter"] is True
    assert body["customer_name"] == "Ama"
    assert body["notes"] == "No pepper"
    assert "[[channel:" not in (body["notes"] or "")
    order_id = body["id"]
    quiet = await ac.get("/api/v1/restaurant/kitchen", headers=admin)
    assert all(row["order_id"] != order_id for row in quiet.json()["data"])
    kept = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"notes": "Extra rice"},
    )
    assert kept.status_code == 200, kept.text
    assert kept.json()["data"]["channel"] == "online"
    assert kept.json()["data"]["notes"] == "Extra rice"
    sent = await ac.post(f"/api/v1/restaurant/orders/{order_id}/send", headers=admin)
    assert sent.status_code == 200, sent.text
    kitchen = await ac.get("/api/v1/restaurant/kitchen", headers=admin)
    ticket = next(row for row in kitchen.json()["data"] if row["order_id"] == order_id)
    assert ticket["channel"] == "online"
    assert ticket["notes"] == "Extra rice"
    assert "[[channel:" not in (ticket["notes"] or "")
    shut = await ac.put("/api/v1/restaurant/online-orders", headers=admin, json={"open": False})
    assert shut.status_code == 200, shut.text
    assert shut.json()["data"]["open"] is False
    assert shut.json()["data"]["qr"] is None
    again = await ac.get("/api/v1/public/restaurant-order/alpha")
    assert again.status_code == 404, again.text
    await db_session.refresh(tenant)
    assert "restaurant_online_orders" not in (tenant.document_numbering or {})
    assert tenant.document_numbering["pos_sale"]["prefix"] == "POS"
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    denied = await ac.put("/api/v1/restaurant/online-orders", headers=admin, json={"open": True})
    assert denied.status_code == 403, denied.text


async def test_restaurant_floor_places(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    tenant = seed["t1"]
    tenant.document_numbering = {"pos_sale": {"prefix": "POS", "next": 4, "year": 2026}}
    await db_session.commit()
    empty = await ac.get("/api/v1/restaurant/floor-places", headers=admin)
    assert empty.status_code == 200, empty.text
    assert empty.json()["data"] == []
    made = await ac.post(
        "/api/v1/restaurant/tables",
        headers=admin,
        json={"code": "W1", "name": "Window", "seats": 4},
    )
    assert made.status_code == 200, made.text
    table_id = made.json()["data"]["id"]
    assert made.json()["data"]["status"] == "available"
    off = await ac.put(
        "/api/v1/restaurant/floor-places",
        headers=admin,
        json={"places": [{"table_id": table_id, "x": 101, "y": 10}]},
    )
    assert off.status_code == 422, off.text
    missing = await ac.put(
        "/api/v1/restaurant/floor-places",
        headers=admin,
        json={"places": [{"table_id": str(uuid.uuid4()), "x": 10, "y": 10}]},
    )
    assert missing.status_code == 404, missing.text
    extra = await ac.put(
        "/api/v1/restaurant/floor-places",
        headers=admin,
        json={"places": [{"table_id": table_id, "x": 10, "y": 10, "note": "x"}]},
    )
    assert extra.status_code == 422, extra.text
    saved = await ac.put(
        "/api/v1/restaurant/floor-places",
        headers=admin,
        json={"places": [{"table_id": table_id, "x": 20, "y": 30}]},
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["data"] == [{"table_id": table_id, "x": 20, "y": 30}]
    duplicate = await ac.put(
        "/api/v1/restaurant/floor-places",
        headers=admin,
        json={
            "places": [
                {"table_id": table_id, "x": 20, "y": 30},
                {"table_id": table_id, "x": 40, "y": 40},
            ]
        },
    )
    assert duplicate.status_code == 422, duplicate.text
    listed = await ac.get("/api/v1/restaurant/floor-places", headers=admin)
    assert listed.json()["data"] == [{"table_id": table_id, "x": 20, "y": 30}]
    tables = await ac.get("/api/v1/restaurant/tables", headers=admin)
    window = next(row for row in tables.json()["data"] if row["id"] == table_id)
    assert window["status"] == "available"
    assert window["seats"] == 4
    assert window["name"] == "Window"
    await db_session.refresh(tenant)
    assert tenant.document_numbering["pos_sale"]["prefix"] == "POS"
    assert tenant.document_numbering["restaurant_floor_places"][0]["x"] == 20
    cleared = await ac.put("/api/v1/restaurant/floor-places", headers=admin, json={"places": []})
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["data"] == []
    await db_session.refresh(tenant)
    assert "restaurant_floor_places" not in (tenant.document_numbering or {})
    assert tenant.document_numbering["pos_sale"]["prefix"] == "POS"
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    denied = await ac.put(
        "/api/v1/restaurant/floor-places",
        headers=admin,
        json={"places": [{"table_id": table_id, "x": 20, "y": 30}]},
    )
    assert denied.status_code == 403, denied.text


async def test_restaurant_kitchen_sound(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    tenant = seed["t1"]
    tenant.document_numbering = {"pos_sale": {"prefix": "POS", "next": 4, "year": 2026}}
    await db_session.commit()
    quiet = await ac.get("/api/v1/restaurant/kitchen-sound", headers=admin)
    assert quiet.status_code == 200, quiet.text
    assert quiet.json()["data"]["on"] is False
    extra = await ac.put("/api/v1/restaurant/kitchen-sound", headers=admin, json={"on": True, "volume": 9})
    assert extra.status_code == 422, extra.text
    opened = await ac.put("/api/v1/restaurant/kitchen-sound", headers=admin, json={"on": True})
    assert opened.status_code == 200, opened.text
    assert opened.json()["data"]["on"] is True
    await db_session.refresh(tenant)
    assert tenant.document_numbering["pos_sale"]["prefix"] == "POS"
    assert tenant.document_numbering["restaurant_kitchen_sound"] is True
    shut = await ac.put("/api/v1/restaurant/kitchen-sound", headers=admin, json={"on": False})
    assert shut.status_code == 200, shut.text
    assert shut.json()["data"]["on"] is False
    await db_session.refresh(tenant)
    assert "restaurant_kitchen_sound" not in (tenant.document_numbering or {})
    assert tenant.document_numbering["pos_sale"]["prefix"] == "POS"
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    denied = await ac.put("/api/v1/restaurant/kitchen-sound", headers=admin, json={"on": True})
    assert denied.status_code == 403, denied.text


async def test_restaurant_clock(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    tenant = seed["t1"]
    tenant.document_numbering = {"pos_sale": {"prefix": "POS", "next": 4, "year": 2026}}
    await db_session.commit()
    user = (
        await db_session.execute(select(m.User).where(m.User.email == "admin@alpha.example.com"))
    ).scalar_one()
    empty = await ac.get("/api/v1/restaurant/clock", headers=admin)
    assert empty.status_code == 200, empty.text
    assert empty.json()["data"]["open"] == []
    assert empty.json()["data"]["mine_open"] is False
    extra = await ac.post("/api/v1/restaurant/clock/in", headers=admin, json={"name": "http://staff.example"})
    assert extra.status_code == 422, extra.text
    started = await ac.post("/api/v1/restaurant/clock/in", headers=admin, json={})
    assert started.status_code == 200, started.text
    body = started.json()["data"]
    assert body["mine_open"] is True
    assert body["open"][0]["user_id"] == user.id
    assert body["open"][0]["name"] == user.full_name
    assert body["open"][0]["out_at"] is None
    again = await ac.post("/api/v1/restaurant/clock/in", headers=admin, json={})
    assert again.status_code == 409, again.text
    await db_session.refresh(tenant)
    assert tenant.document_numbering["pos_sale"]["prefix"] == "POS"
    finished = await ac.post("/api/v1/restaurant/clock/out", headers=admin, json={})
    assert finished.status_code == 200, finished.text
    assert finished.json()["data"]["open"] == []
    assert finished.json()["data"]["mine_open"] is False
    late = await ac.post("/api/v1/restaurant/clock/out", headers=admin, json={})
    assert late.status_code == 409, late.text
    await db_session.refresh(tenant)
    assert tenant.document_numbering["pos_sale"]["prefix"] == "POS"
    assert tenant.document_numbering["restaurant_clock"][0]["out_at"]
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    denied = await ac.post("/api/v1/restaurant/clock/in", headers=admin, json={})
    assert denied.status_code == 403, denied.text


async def test_restaurant_sold_out(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    tenant = seed["t1"]
    tenant.document_numbering = {"pos_sale": {"prefix": "POS", "next": 4, "year": 2026}}
    await db_session.commit()
    empty = await ac.get("/api/v1/restaurant/sold-out", headers=admin)
    assert empty.status_code == 200, empty.text
    assert empty.json()["data"]["items"] == []
    dish = await _product(ac, admin, name="Jollof", selling_price=20, prep_station="kitchen")
    rice = await _product(ac, admin, name="Rice", selling_price=4)
    ingredient = await ac.put(
        "/api/v1/restaurant/sold-out",
        headers=admin,
        json={"product_ids": [rice["id"]]},
    )
    assert ingredient.status_code == 422, ingredient.text
    extra = await ac.put(
        "/api/v1/restaurant/sold-out",
        headers=admin,
        json={"product_ids": [dish["id"]], "stock": 0},
    )
    assert extra.status_code == 422, extra.text
    marked = await ac.put(
        "/api/v1/restaurant/sold-out",
        headers=admin,
        json={"product_ids": [dish["id"]]},
    )
    assert marked.status_code == 200, marked.text
    assert marked.json()["data"]["items"] == [{"id": dish["id"], "name": "Jollof"}]
    again = await ac.put(
        "/api/v1/restaurant/sold-out",
        headers=admin,
        json={"product_ids": [dish["id"], dish["id"]]},
    )
    assert again.status_code == 422, again.text
    await db_session.refresh(tenant)
    assert tenant.document_numbering["pos_sale"]["prefix"] == "POS"
    opened = await ac.put("/api/v1/restaurant/online-orders", headers=admin, json={"open": True})
    assert opened.status_code == 200, opened.text
    page = await ac.get("/api/v1/public/restaurant-order/alpha")
    assert page.status_code == 200, page.text
    assert all(row["id"] != dish["id"] for row in page.json()["data"]["menu"])
    guest = await ac.post(
        "/api/v1/public/restaurant-order/alpha",
        json={"customer_name": "Ama", "lines": [{"product_id": dish["id"], "quantity": 1}]},
    )
    assert guest.status_code == 422, guest.text
    staff = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "lines": [{"product_id": dish["id"], "quantity": 1}],
        },
    )
    assert staff.status_code == 422, staff.text
    cleared = await ac.put("/api/v1/restaurant/sold-out", headers=admin, json={"product_ids": []})
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["data"]["items"] == []
    page = await ac.get("/api/v1/public/restaurant-order/alpha")
    assert any(row["id"] == dish["id"] for row in page.json()["data"]["menu"])
    await db_session.refresh(tenant)
    assert "restaurant_sold_out" not in (tenant.document_numbering or {})
    assert tenant.document_numbering["pos_sale"]["prefix"] == "POS"
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    hotel = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    denied = await ac.put("/api/v1/restaurant/sold-out", headers=hotel, json={"product_ids": [dish["id"]]})
    assert denied.status_code == 403, denied.text


async def test_restaurant_order_covers(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    tenant = seed["t1"]
    tenant.document_numbering = {"pos_sale": {"prefix": "POS", "next": 4, "year": 2026}}
    await db_session.commit()
    dish = await _product(ac, admin, name="Jollof", selling_price=20, prep_station="kitchen")
    blank = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "covers": 0,
            "lines": [{"product_id": dish["id"], "quantity": 1}],
        },
    )
    assert blank.status_code == 422, blank.text
    wide = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "covers": 41,
            "lines": [{"product_id": dish["id"], "quantity": 1}],
        },
    )
    assert wide.status_code == 422, wide.text
    junk = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "covers": "http://covers.example",
            "lines": [{"product_id": dish["id"], "quantity": 1}],
        },
    )
    assert junk.status_code == 422, junk.text
    opened = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "notes": "Gate",
            "covers": 2,
            "lines": [{"product_id": dish["id"], "quantity": 1, "course": "main"}],
        },
    )
    assert opened.status_code == 200, opened.text
    body = opened.json()["data"]
    order_id = body["id"]
    assert body["covers"] == 2
    assert body["notes"] == "Gate"
    assert body["total_amount"] == 20
    assert "[[covers:" not in (body["notes"] or "")
    kept = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"notes": "Side door"},
    )
    assert kept.status_code == 200, kept.text
    assert kept.json()["data"]["notes"] == "Side door"
    assert kept.json()["data"]["covers"] == 2
    assert kept.json()["data"]["total_amount"] == 20
    changed = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"covers": 4},
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["data"]["covers"] == 4
    assert changed.json()["data"]["notes"] == "Side door"
    sent = await ac.post(f"/api/v1/restaurant/orders/{order_id}/send", headers=admin)
    assert sent.status_code == 200, sent.text
    kitchen = await ac.get("/api/v1/restaurant/kitchen", headers=admin)
    ticket = next(row for row in kitchen.json()["data"] if row["order_id"] == order_id)
    assert ticket["covers"] == 4
    assert ticket["notes"] == "Side door"
    assert "[[covers:" not in (ticket["notes"] or "")
    cleared = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"covers": None},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["data"]["covers"] is None
    assert cleared.json()["data"]["notes"] == "Side door"
    await db_session.refresh(tenant)
    assert tenant.document_numbering["pos_sale"]["prefix"] == "POS"
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    denied = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"covers": 2},
    )
    assert denied.status_code == 403, denied.text


async def test_restaurant_order_allergy(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    tenant = seed["t1"]
    tenant.document_numbering = {"pos_sale": {"prefix": "POS", "next": 4, "year": 2026}}
    await db_session.commit()
    dish = await _product(ac, admin, name="Jollof", selling_price=20, prep_station="kitchen")
    blank = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "allergy": " ",
            "lines": [{"product_id": dish["id"], "quantity": 1}],
        },
    )
    assert blank.status_code == 422, blank.text
    junk = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "allergy": "http://nuts.example",
            "lines": [{"product_id": dish["id"], "quantity": 1}],
        },
    )
    assert junk.status_code == 422, junk.text
    marks = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "allergy": "!!!",
            "lines": [{"product_id": dish["id"], "quantity": 1}],
        },
    )
    assert marks.status_code == 422, marks.text
    opened = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "notes": "Gate",
            "covers": 2,
            "allergy": "No nuts",
            "lines": [{"product_id": dish["id"], "quantity": 1, "course": "main"}],
        },
    )
    assert opened.status_code == 200, opened.text
    body = opened.json()["data"]
    order_id = body["id"]
    assert body["allergy"] == "No nuts"
    assert body["covers"] == 2
    assert body["notes"] == "Gate"
    assert body["total_amount"] == 20
    assert "[[allergy:" not in (body["notes"] or "")
    kept = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"notes": "Side door"},
    )
    assert kept.status_code == 200, kept.text
    assert kept.json()["data"]["notes"] == "Side door"
    assert kept.json()["data"]["allergy"] == "No nuts"
    assert kept.json()["data"]["covers"] == 2
    assert kept.json()["data"]["total_amount"] == 20
    changed = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"allergy": "Sesame"},
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["data"]["allergy"] == "Sesame"
    assert changed.json()["data"]["notes"] == "Side door"
    sent = await ac.post(f"/api/v1/restaurant/orders/{order_id}/send", headers=admin)
    assert sent.status_code == 200, sent.text
    kitchen = await ac.get("/api/v1/restaurant/kitchen", headers=admin)
    ticket = next(row for row in kitchen.json()["data"] if row["order_id"] == order_id)
    assert ticket["allergy"] == "Sesame"
    assert ticket["covers"] == 2
    assert ticket["notes"] == "Side door"
    assert "[[allergy:" not in (ticket["notes"] or "")
    cleared = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"allergy": None},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["data"]["allergy"] is None
    assert cleared.json()["data"]["notes"] == "Side door"
    assert cleared.json()["data"]["covers"] == 2
    await db_session.refresh(tenant)
    assert tenant.document_numbering["pos_sale"]["prefix"] == "POS"
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    denied = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"allergy": "No nuts"},
    )
    assert denied.status_code == 403, denied.text


async def test_restaurant_order_ready_by(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    tenant = seed["t1"]
    tenant.document_numbering = {"pos_sale": {"prefix": "POS", "next": 4, "year": 2026}}
    await db_session.commit()
    dish = await _product(ac, admin, name="Jollof", selling_price=20, prep_station="kitchen")
    blank = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "ready_by": " ",
            "lines": [{"product_id": dish["id"], "quantity": 1}],
        },
    )
    assert blank.status_code == 422, blank.text
    late = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "ready_by": "25:00",
            "lines": [{"product_id": dish["id"], "quantity": 1}],
        },
    )
    assert late.status_code == 422, late.text
    junk = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "ready_by": "http://time.example",
            "lines": [{"product_id": dish["id"], "quantity": 1}],
        },
    )
    assert junk.status_code == 422, junk.text
    opened = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "notes": "Gate",
            "covers": 2,
            "allergy": "No nuts",
            "ready_by": "19:00",
            "lines": [{"product_id": dish["id"], "quantity": 1, "course": "main"}],
        },
    )
    assert opened.status_code == 200, opened.text
    body = opened.json()["data"]
    order_id = body["id"]
    assert body["ready_by"] == "19:00"
    assert body["allergy"] == "No nuts"
    assert body["covers"] == 2
    assert body["notes"] == "Gate"
    assert body["total_amount"] == 20
    assert body["status"] == "open"
    assert "[[ready:" not in (body["notes"] or "")
    kept = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"notes": "Side door"},
    )
    assert kept.status_code == 200, kept.text
    assert kept.json()["data"]["notes"] == "Side door"
    assert kept.json()["data"]["ready_by"] == "19:00"
    assert kept.json()["data"]["allergy"] == "No nuts"
    assert kept.json()["data"]["total_amount"] == 20
    changed = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"ready_by": "19:30"},
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["data"]["ready_by"] == "19:30"
    assert changed.json()["data"]["notes"] == "Side door"
    assert changed.json()["data"]["status"] == "open"
    sent = await ac.post(f"/api/v1/restaurant/orders/{order_id}/send", headers=admin)
    assert sent.status_code == 200, sent.text
    kitchen = await ac.get("/api/v1/restaurant/kitchen", headers=admin)
    ticket = next(row for row in kitchen.json()["data"] if row["order_id"] == order_id)
    assert ticket["ready_by"] == "19:30"
    assert ticket["notes"] == "Side door"
    assert "[[ready:" not in (ticket["notes"] or "")
    cleared = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"ready_by": None},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["data"]["ready_by"] is None
    assert cleared.json()["data"]["notes"] == "Side door"
    assert cleared.json()["data"]["allergy"] == "No nuts"
    await db_session.refresh(tenant)
    assert tenant.document_numbering["pos_sale"]["prefix"] == "POS"
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    denied = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"ready_by": "19:00"},
    )
    assert denied.status_code == 403, denied.text


async def test_restaurant_order_rush(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    tenant = seed["t1"]
    tenant.document_numbering = {"pos_sale": {"prefix": "POS", "next": 4, "year": 2026}}
    await db_session.commit()
    dish = await _product(ac, admin, name="Jollof", selling_price=20, prep_station="kitchen")
    junk = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "rush": "http://rush.example",
            "lines": [{"product_id": dish["id"], "quantity": 1}],
        },
    )
    assert junk.status_code == 422, junk.text
    opened = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "notes": "Gate",
            "ready_by": "19:00",
            "allergy": "No nuts",
            "rush": True,
            "lines": [{"product_id": dish["id"], "quantity": 1, "course": "main"}],
        },
    )
    assert opened.status_code == 200, opened.text
    body = opened.json()["data"]
    order_id = body["id"]
    assert body["rush"] is True
    assert body["ready_by"] == "19:00"
    assert body["allergy"] == "No nuts"
    assert body["notes"] == "Gate"
    assert body["total_amount"] == 20
    assert body["status"] == "open"
    assert "[[rush]]" not in (body["notes"] or "")
    kept = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"notes": "Side door"},
    )
    assert kept.status_code == 200, kept.text
    assert kept.json()["data"]["notes"] == "Side door"
    assert kept.json()["data"]["rush"] is True
    assert kept.json()["data"]["ready_by"] == "19:00"
    assert kept.json()["data"]["total_amount"] == 20
    sent = await ac.post(f"/api/v1/restaurant/orders/{order_id}/send", headers=admin)
    assert sent.status_code == 200, sent.text
    kitchen = await ac.get("/api/v1/restaurant/kitchen", headers=admin)
    ticket = next(row for row in kitchen.json()["data"] if row["order_id"] == order_id)
    assert ticket["rush"] is True
    assert ticket["ready_by"] == "19:00"
    assert ticket["notes"] == "Side door"
    assert "[[rush]]" not in (ticket["notes"] or "")
    cleared = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"rush": False},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["data"]["rush"] is False
    assert cleared.json()["data"]["notes"] == "Side door"
    assert cleared.json()["data"]["ready_by"] == "19:00"
    assert cleared.json()["data"]["status"] == "sent"
    await db_session.refresh(tenant)
    assert tenant.document_numbering["pos_sale"]["prefix"] == "POS"
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    denied = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"rush": True},
    )
    assert denied.status_code == 403, denied.text


async def test_restaurant_order_server(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    tenant = seed["t1"]
    tenant.document_numbering = {"pos_sale": {"prefix": "POS", "next": 4, "year": 2026}}
    await db_session.commit()
    dish = await _product(ac, admin, name="Jollof", selling_price=20, prep_station="kitchen")
    opened = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "notes": "Gate",
            "lines": [{"product_id": dish["id"], "quantity": 1, "course": "main"}],
        },
    )
    assert opened.status_code == 200, opened.text
    order_id = opened.json()["data"]["id"]
    assert opened.json()["data"]["total_amount"] == 20
    assert opened.json()["data"]["status"] == "open"
    listed = await ac.get("/api/v1/restaurant/orders", headers=admin)
    assert listed.status_code == 200, listed.text
    row = next(item for item in listed.json()["data"] if item["id"] == order_id)
    assert row["server"] == "Alpha Admin"
    assert row["notes"] == "Gate"
    assert row["total_amount"] == 20
    kept = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"notes": "Side door"},
    )
    assert kept.status_code == 200, kept.text
    listed = await ac.get("/api/v1/restaurant/orders", headers=admin)
    row = next(item for item in listed.json()["data"] if item["id"] == order_id)
    assert row["server"] == "Alpha Admin"
    assert row["notes"] == "Side door"
    assert row["total_amount"] == 20
    assert row["status"] == "open"
    sent = await ac.post(f"/api/v1/restaurant/orders/{order_id}/send", headers=admin)
    assert sent.status_code == 200, sent.text
    kitchen = await ac.get("/api/v1/restaurant/kitchen", headers=admin)
    ticket = next(item for item in kitchen.json()["data"] if item["order_id"] == order_id)
    assert ticket["server"] == "Alpha Admin"
    assert ticket["notes"] == "Side door"
    await db_session.refresh(tenant)
    assert tenant.document_numbering["pos_sale"]["prefix"] == "POS"
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    denied = await ac.get("/api/v1/restaurant/orders", headers=admin)
    assert denied.status_code == 403, denied.text


async def test_restaurant_order_opened(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    tenant = seed["t1"]
    tenant.document_numbering = {"pos_sale": {"prefix": "POS", "next": 4, "year": 2026}}
    await db_session.commit()
    dish = await _product(ac, admin, name="Jollof", selling_price=20, prep_station="kitchen")
    opened = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "notes": "Gate",
            "lines": [{"product_id": dish["id"], "quantity": 1, "course": "main"}],
        },
    )
    assert opened.status_code == 200, opened.text
    order_id = opened.json()["data"]["id"]
    opened_at = opened.json()["data"]["opened_at"]
    assert isinstance(opened_at, str) and "T" in opened_at
    assert opened.json()["data"]["total_amount"] == 20
    assert opened.json()["data"]["status"] == "open"
    listed = await ac.get("/api/v1/restaurant/orders", headers=admin)
    row = next(item for item in listed.json()["data"] if item["id"] == order_id)
    assert row["opened_at"] == opened_at
    assert row["notes"] == "Gate"
    assert row["total_amount"] == 20
    kept = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"notes": "Side door"},
    )
    assert kept.status_code == 200, kept.text
    assert kept.json()["data"]["opened_at"] == opened_at
    assert kept.json()["data"]["notes"] == "Side door"
    assert kept.json()["data"]["total_amount"] == 20
    sent = await ac.post(f"/api/v1/restaurant/orders/{order_id}/send", headers=admin)
    assert sent.status_code == 200, sent.text
    kitchen = await ac.get("/api/v1/restaurant/kitchen", headers=admin)
    ticket = next(item for item in kitchen.json()["data"] if item["order_id"] == order_id)
    assert ticket["opened_at"] == opened_at
    assert ticket["notes"] == "Side door"
    await db_session.refresh(tenant)
    assert tenant.document_numbering["pos_sale"]["prefix"] == "POS"
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    denied = await ac.get("/api/v1/restaurant/kitchen", headers=admin)
    assert denied.status_code == 403, denied.text


async def test_restaurant_order_phone(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    tenant = seed["t1"]
    tenant.document_numbering = {"pos_sale": {"prefix": "POS", "next": 4, "year": 2026}}
    await db_session.commit()
    dish = await _product(ac, admin, name="Jollof", selling_price=20, prep_station="kitchen")
    junk = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "phone": "http://phone.example",
            "lines": [{"product_id": dish["id"], "quantity": 1}],
        },
    )
    assert junk.status_code == 422, junk.text
    short = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "phone": "123",
            "lines": [{"product_id": dish["id"], "quantity": 1}],
        },
    )
    assert short.status_code == 422, short.text
    opened = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "notes": "Gate",
            "allergy": "No nuts",
            "phone": "+233 24 123 4567",
            "lines": [{"product_id": dish["id"], "quantity": 1, "course": "main"}],
        },
    )
    assert opened.status_code == 200, opened.text
    body = opened.json()["data"]
    order_id = body["id"]
    assert body["phone"] == "+233241234567"
    assert body["allergy"] == "No nuts"
    assert body["notes"] == "Gate"
    assert "[[phone:" not in (body["notes"] or "")
    assert body["total_amount"] == 20
    assert body["status"] == "open"
    kept = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"notes": "Side door"},
    )
    assert kept.status_code == 200, kept.text
    assert kept.json()["data"]["phone"] == "+233241234567"
    assert kept.json()["data"]["allergy"] == "No nuts"
    assert kept.json()["data"]["notes"] == "Side door"
    assert kept.json()["data"]["total_amount"] == 20
    sent = await ac.post(f"/api/v1/restaurant/orders/{order_id}/send", headers=admin)
    assert sent.status_code == 200, sent.text
    kitchen = await ac.get("/api/v1/restaurant/kitchen", headers=admin)
    ticket = next(row for row in kitchen.json()["data"] if row["order_id"] == order_id)
    assert ticket["phone"] == "+233241234567"
    assert ticket["notes"] == "Side door"
    assert "[[phone:" not in (ticket["notes"] or "")
    cleared = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"phone": None},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["data"]["phone"] is None
    assert cleared.json()["data"]["notes"] == "Side door"
    assert cleared.json()["data"]["allergy"] == "No nuts"
    assert cleared.json()["data"]["status"] == "sent"
    await db_session.refresh(tenant)
    assert tenant.document_numbering["pos_sale"]["prefix"] == "POS"
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    denied = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"phone": "+233241234567"},
    )
    assert denied.status_code == 403, denied.text


async def test_restaurant_order_item_note(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    tenant = seed["t1"]
    tenant.document_numbering = {"pos_sale": {"prefix": "POS", "next": 4, "year": 2026}}
    await db_session.commit()
    dish = await _product(ac, admin, name="Jollof", selling_price=20, prep_station="kitchen")
    junk = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "lines": [{"product_id": dish["id"], "quantity": 1, "note": "http://item.example"}],
        },
    )
    assert junk.status_code == 422, junk.text
    opened = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "notes": "Gate",
            "phone": "+233241234567",
            "lines": [{"product_id": dish["id"], "quantity": 1, "course": "main", "note": "Less salt"}],
        },
    )
    assert opened.status_code == 200, opened.text
    body = opened.json()["data"]
    order_id = body["id"]
    assert body["notes"] == "Gate"
    assert body["phone"] == "+233241234567"
    assert "[[item:" not in (body["notes"] or "")
    assert body["total_amount"] == 20
    assert body["status"] == "open"
    listed = await ac.get("/api/v1/restaurant/orders", headers=admin)
    row = next(item for item in listed.json()["data"] if item["id"] == order_id)
    line_id = row["items"][0]["id"]
    assert row["items"][0]["note"] == "Less salt"
    assert row["items"][0]["course"] == "main"
    assert row["total_amount"] == 20
    kept = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"notes": "Side door"},
    )
    assert kept.status_code == 200, kept.text
    listed = await ac.get("/api/v1/restaurant/orders", headers=admin)
    row = next(item for item in listed.json()["data"] if item["id"] == order_id)
    assert row["notes"] == "Side door"
    assert row["phone"] == "+233241234567"
    assert row["items"][0]["note"] == "Less salt"
    assert row["total_amount"] == 20
    sent = await ac.post(f"/api/v1/restaurant/orders/{order_id}/send", headers=admin)
    assert sent.status_code == 200, sent.text
    kitchen = await ac.get("/api/v1/restaurant/kitchen", headers=admin)
    ticket = next(item for item in kitchen.json()["data"] if item["order_id"] == order_id)
    assert ticket["items"][0]["note"] == "Less salt"
    assert ticket["notes"] == "Side door"
    assert "[[item:" not in (ticket["notes"] or "")
    cleared = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"line_notes": [{"line_id": line_id, "note": None}]},
    )
    assert cleared.status_code == 200, cleared.text
    listed = await ac.get("/api/v1/restaurant/orders", headers=admin)
    row = next(item for item in listed.json()["data"] if item["id"] == order_id)
    assert row["items"][0]["note"] is None
    assert row["notes"] == "Side door"
    assert row["phone"] == "+233241234567"
    assert row["status"] == "sent"
    assert row["total_amount"] == 20
    await db_session.refresh(tenant)
    assert tenant.document_numbering["pos_sale"]["prefix"] == "POS"
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    denied = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"line_notes": [{"line_id": line_id, "note": "Less salt"}]},
    )
    assert denied.status_code == 403, denied.text


async def test_restaurant_order_item_hold(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    tenant = seed["t1"]
    tenant.document_numbering = {"pos_sale": {"prefix": "POS", "next": 4, "year": 2026}}
    await db_session.commit()
    dish = await _product(ac, admin, name="Jollof", selling_price=20, prep_station="kitchen")
    junk = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "lines": [{"product_id": dish["id"], "quantity": 1, "hold": "http://hold.example"}],
        },
    )
    assert junk.status_code == 422, junk.text
    opened = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "notes": "Gate",
            "lines": [{"product_id": dish["id"], "quantity": 1, "course": "main", "note": "Less salt", "hold": True}],
        },
    )
    assert opened.status_code == 200, opened.text
    body = opened.json()["data"]
    order_id = body["id"]
    assert body["notes"] == "Gate"
    assert "[[hold:" not in (body["notes"] or "")
    assert body["total_amount"] == 20
    assert body["status"] == "open"
    listed = await ac.get("/api/v1/restaurant/orders", headers=admin)
    row = next(item for item in listed.json()["data"] if item["id"] == order_id)
    line_id = row["items"][0]["id"]
    assert row["items"][0]["hold"] is True
    assert row["items"][0]["note"] == "Less salt"
    assert row["total_amount"] == 20
    kept = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"notes": "Side door"},
    )
    assert kept.status_code == 200, kept.text
    listed = await ac.get("/api/v1/restaurant/orders", headers=admin)
    row = next(item for item in listed.json()["data"] if item["id"] == order_id)
    assert row["notes"] == "Side door"
    assert row["items"][0]["hold"] is True
    assert row["items"][0]["note"] == "Less salt"
    sent = await ac.post(f"/api/v1/restaurant/orders/{order_id}/send", headers=admin)
    assert sent.status_code == 200, sent.text
    blocked = await ac.post(f"/api/v1/restaurant/kitchen/lines/{line_id}/ready", headers=admin, json={})
    assert blocked.status_code == 409, blocked.text
    kitchen = await ac.get("/api/v1/restaurant/kitchen", headers=admin)
    ticket = next(item for item in kitchen.json()["data"] if item["order_id"] == order_id)
    assert ticket["items"][0]["hold"] is True
    assert ticket["items"][0]["note"] == "Less salt"
    assert ticket["notes"] == "Side door"
    cleared = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"line_holds": [{"line_id": line_id, "hold": False}]},
    )
    assert cleared.status_code == 200, cleared.text
    listed = await ac.get("/api/v1/restaurant/orders", headers=admin)
    row = next(item for item in listed.json()["data"] if item["id"] == order_id)
    assert row["items"][0]["hold"] is False
    assert row["items"][0]["note"] == "Less salt"
    assert row["notes"] == "Side door"
    assert row["status"] == "sent"
    assert row["total_amount"] == 20
    await db_session.refresh(tenant)
    assert tenant.document_numbering["pos_sale"]["prefix"] == "POS"
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    denied = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"line_holds": [{"line_id": line_id, "hold": True}]},
    )
    assert denied.status_code == 403, denied.text


async def test_restaurant_order_item_seat(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    tenant = seed["t1"]
    tenant.document_numbering = {"pos_sale": {"prefix": "POS", "next": 4, "year": 2026}}
    await db_session.commit()
    dish = await _product(ac, admin, name="Jollof", selling_price=20, prep_station="kitchen")
    junk = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "lines": [{"product_id": dish["id"], "quantity": 1, "seat": "http://seat.example"}],
        },
    )
    assert junk.status_code == 422, junk.text
    opened = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "notes": "Gate",
            "lines": [{"product_id": dish["id"], "quantity": 1, "course": "main", "note": "Less salt", "seat": 2}],
        },
    )
    assert opened.status_code == 200, opened.text
    body = opened.json()["data"]
    order_id = body["id"]
    assert body["notes"] == "Gate"
    assert "[[seat:" not in (body["notes"] or "")
    assert body["total_amount"] == 20
    assert body["status"] == "open"
    listed = await ac.get("/api/v1/restaurant/orders", headers=admin)
    row = next(item for item in listed.json()["data"] if item["id"] == order_id)
    line_id = row["items"][0]["id"]
    assert row["items"][0]["seat"] == 2
    assert row["items"][0]["note"] == "Less salt"
    assert row["total_amount"] == 20
    kept = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"notes": "Side door"},
    )
    assert kept.status_code == 200, kept.text
    listed = await ac.get("/api/v1/restaurant/orders", headers=admin)
    row = next(item for item in listed.json()["data"] if item["id"] == order_id)
    assert row["notes"] == "Side door"
    assert row["items"][0]["seat"] == 2
    assert row["items"][0]["note"] == "Less salt"
    sent = await ac.post(f"/api/v1/restaurant/orders/{order_id}/send", headers=admin)
    assert sent.status_code == 200, sent.text
    kitchen = await ac.get("/api/v1/restaurant/kitchen", headers=admin)
    ticket = next(item for item in kitchen.json()["data"] if item["order_id"] == order_id)
    assert ticket["items"][0]["seat"] == 2
    assert ticket["items"][0]["note"] == "Less salt"
    assert ticket["notes"] == "Side door"
    cleared = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"line_seats": [{"line_id": line_id, "seat": None}]},
    )
    assert cleared.status_code == 200, cleared.text
    listed = await ac.get("/api/v1/restaurant/orders", headers=admin)
    row = next(item for item in listed.json()["data"] if item["id"] == order_id)
    assert row["items"][0]["seat"] is None
    assert row["items"][0]["note"] == "Less salt"
    assert row["notes"] == "Side door"
    assert row["status"] == "sent"
    assert row["total_amount"] == 20
    await db_session.refresh(tenant)
    assert tenant.document_numbering["pos_sale"]["prefix"] == "POS"
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    denied = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"line_seats": [{"line_id": line_id, "seat": 3}]},
    )
    assert denied.status_code == 403, denied.text


async def test_restaurant_order_pager(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    tenant = seed["t1"]
    tenant.document_numbering = {"pos_sale": {"prefix": "POS", "next": 4, "year": 2026}}
    await db_session.commit()
    dish = await _product(ac, admin, name="Jollof", selling_price=20, prep_station="kitchen")
    junk = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "pager": "http://pager.example",
            "lines": [{"product_id": dish["id"], "quantity": 1}],
        },
    )
    assert junk.status_code == 422, junk.text
    high = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "pager": 1000,
            "lines": [{"product_id": dish["id"], "quantity": 1}],
        },
    )
    assert high.status_code == 422, high.text
    opened = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "notes": "Gate",
            "phone": "+233241234567",
            "pager": 12,
            "lines": [{"product_id": dish["id"], "quantity": 1}],
        },
    )
    assert opened.status_code == 200, opened.text
    body = opened.json()["data"]
    order_id = body["id"]
    assert body["notes"] == "Gate"
    assert body["phone"] == "+233241234567"
    assert body["pager"] == 12
    assert "[[pager:" not in (body["notes"] or "")
    assert body["total_amount"] == 20
    assert body["status"] == "open"
    kept = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"notes": "Side door"},
    )
    assert kept.status_code == 200, kept.text
    assert kept.json()["data"]["notes"] == "Side door"
    assert kept.json()["data"]["pager"] == 12
    assert kept.json()["data"]["phone"] == "+233241234567"
    assert kept.json()["data"]["total_amount"] == 20
    sent = await ac.post(f"/api/v1/restaurant/orders/{order_id}/send", headers=admin)
    assert sent.status_code == 200, sent.text
    kitchen = await ac.get("/api/v1/restaurant/kitchen", headers=admin)
    ticket = next(item for item in kitchen.json()["data"] if item["order_id"] == order_id)
    assert ticket["pager"] == 12
    assert ticket["phone"] == "+233241234567"
    assert ticket["notes"] == "Side door"
    assert "[[pager:" not in (ticket["notes"] or "")
    cleared = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"pager": None},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["data"]["pager"] is None
    assert cleared.json()["data"]["phone"] == "+233241234567"
    assert cleared.json()["data"]["notes"] == "Side door"
    assert cleared.json()["data"]["status"] == "sent"
    assert cleared.json()["data"]["total_amount"] == 20
    await db_session.refresh(tenant)
    assert tenant.document_numbering["pos_sale"]["prefix"] == "POS"
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    denied = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"pager": 12},
    )
    assert denied.status_code == 403, denied.text


async def test_restaurant_order_cutlery(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    tenant = seed["t1"]
    tenant.document_numbering = {"pos_sale": {"prefix": "POS", "next": 4, "year": 2026}}
    await db_session.commit()
    dish = await _product(ac, admin, name="Jollof", selling_price=20, prep_station="kitchen")
    junk = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "cutlery": "http://cutlery.example",
            "lines": [{"product_id": dish["id"], "quantity": 1}],
        },
    )
    assert junk.status_code == 422, junk.text
    opened = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "notes": "Gate",
            "pager": 12,
            "cutlery": True,
            "lines": [{"product_id": dish["id"], "quantity": 1}],
        },
    )
    assert opened.status_code == 200, opened.text
    body = opened.json()["data"]
    order_id = body["id"]
    assert body["cutlery"] is True
    assert body["pager"] == 12
    assert body["notes"] == "Gate"
    assert "[[cutlery]]" not in (body["notes"] or "")
    assert body["total_amount"] == 20
    assert body["status"] == "open"
    kept = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"notes": "Side door"},
    )
    assert kept.status_code == 200, kept.text
    assert kept.json()["data"]["notes"] == "Side door"
    assert kept.json()["data"]["cutlery"] is True
    assert kept.json()["data"]["pager"] == 12
    assert kept.json()["data"]["total_amount"] == 20
    sent = await ac.post(f"/api/v1/restaurant/orders/{order_id}/send", headers=admin)
    assert sent.status_code == 200, sent.text
    kitchen = await ac.get("/api/v1/restaurant/kitchen", headers=admin)
    ticket = next(item for item in kitchen.json()["data"] if item["order_id"] == order_id)
    assert ticket["cutlery"] is True
    assert ticket["pager"] == 12
    assert ticket["notes"] == "Side door"
    assert "[[cutlery]]" not in (ticket["notes"] or "")
    cleared = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"cutlery": False},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["data"]["cutlery"] is False
    assert cleared.json()["data"]["pager"] == 12
    assert cleared.json()["data"]["notes"] == "Side door"
    assert cleared.json()["data"]["status"] == "sent"
    assert cleared.json()["data"]["total_amount"] == 20
    await db_session.refresh(tenant)
    assert tenant.document_numbering["pos_sale"]["prefix"] == "POS"
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    denied = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"cutlery": True},
    )
    assert denied.status_code == 403, denied.text


async def test_restaurant_order_guest_email(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    tenant = seed["t1"]
    tenant.document_numbering = {"pos_sale": {"prefix": "POS", "next": 4, "year": 2026}}
    await db_session.commit()
    dish = await _product(ac, admin, name="Jollof", selling_price=20, prep_station="kitchen")
    junk = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "guest_email": "http://guest.example",
            "lines": [{"product_id": dish["id"], "quantity": 1}],
        },
    )
    assert junk.status_code == 422, junk.text
    opened = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "notes": "Gate",
            "cutlery": True,
            "guest_email": "guest@example.com",
            "lines": [{"product_id": dish["id"], "quantity": 1}],
        },
    )
    assert opened.status_code == 200, opened.text
    body = opened.json()["data"]
    order_id = body["id"]
    assert body["guest_email"] == "guest@example.com"
    assert body["cutlery"] is True
    assert body["notes"] == "Gate"
    assert "[[email:" not in (body["notes"] or "")
    assert body["total_amount"] == 20
    assert body["status"] == "open"
    kept = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"notes": "Side door"},
    )
    assert kept.status_code == 200, kept.text
    assert kept.json()["data"]["notes"] == "Side door"
    assert kept.json()["data"]["guest_email"] == "guest@example.com"
    assert kept.json()["data"]["cutlery"] is True
    assert kept.json()["data"]["total_amount"] == 20
    sent = await ac.post(f"/api/v1/restaurant/orders/{order_id}/send", headers=admin)
    assert sent.status_code == 200, sent.text
    kitchen = await ac.get("/api/v1/restaurant/kitchen", headers=admin)
    ticket = next(item for item in kitchen.json()["data"] if item["order_id"] == order_id)
    assert ticket["guest_email"] == "guest@example.com"
    assert ticket["cutlery"] is True
    assert ticket["notes"] == "Side door"
    assert "[[email:" not in (ticket["notes"] or "")
    cleared = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"guest_email": None},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["data"]["guest_email"] is None
    assert cleared.json()["data"]["cutlery"] is True
    assert cleared.json()["data"]["notes"] == "Side door"
    assert cleared.json()["data"]["status"] == "sent"
    assert cleared.json()["data"]["total_amount"] == 20
    await db_session.refresh(tenant)
    assert tenant.document_numbering["pos_sale"]["prefix"] == "POS"
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    denied = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"guest_email": "guest@example.com"},
    )
    assert denied.status_code == 403, denied.text


async def test_restaurant_order_occasion(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    tenant = seed["t1"]
    tenant.document_numbering = {"pos_sale": {"prefix": "POS", "next": 4, "year": 2026}}
    await db_session.commit()
    dish = await _product(ac, admin, name="Jollof", selling_price=20, prep_station="kitchen")
    junk = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "occasion": "http://party.example",
            "lines": [{"product_id": dish["id"], "quantity": 1}],
        },
    )
    assert junk.status_code == 422, junk.text
    opened = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "notes": "Gate",
            "allergy": "No nuts",
            "occasion": "Birthday",
            "lines": [{"product_id": dish["id"], "quantity": 1}],
        },
    )
    assert opened.status_code == 200, opened.text
    body = opened.json()["data"]
    order_id = body["id"]
    assert body["occasion"] == "Birthday"
    assert body["allergy"] == "No nuts"
    assert body["notes"] == "Gate"
    assert "[[occasion:" not in (body["notes"] or "")
    assert body["total_amount"] == 20
    assert body["status"] == "open"
    kept = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"notes": "Side door"},
    )
    assert kept.status_code == 200, kept.text
    assert kept.json()["data"]["notes"] == "Side door"
    assert kept.json()["data"]["occasion"] == "Birthday"
    assert kept.json()["data"]["allergy"] == "No nuts"
    assert kept.json()["data"]["total_amount"] == 20
    sent = await ac.post(f"/api/v1/restaurant/orders/{order_id}/send", headers=admin)
    assert sent.status_code == 200, sent.text
    kitchen = await ac.get("/api/v1/restaurant/kitchen", headers=admin)
    ticket = next(item for item in kitchen.json()["data"] if item["order_id"] == order_id)
    assert ticket["occasion"] == "Birthday"
    assert ticket["allergy"] == "No nuts"
    assert ticket["notes"] == "Side door"
    assert "[[occasion:" not in (ticket["notes"] or "")
    cleared = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"occasion": None},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["data"]["occasion"] is None
    assert cleared.json()["data"]["allergy"] == "No nuts"
    assert cleared.json()["data"]["notes"] == "Side door"
    assert cleared.json()["data"]["status"] == "sent"
    assert cleared.json()["data"]["total_amount"] == 20
    await db_session.refresh(tenant)
    assert tenant.document_numbering["pos_sale"]["prefix"] == "POS"
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    denied = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"occasion": "Birthday"},
    )
    assert denied.status_code == 403, denied.text


async def test_restaurant_order_item_spice(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    tenant = seed["t1"]
    tenant.document_numbering = {"pos_sale": {"prefix": "POS", "next": 4, "year": 2026}}
    await db_session.commit()
    dish = await _product(ac, admin, name="Jollof", selling_price=20, prep_station="kitchen")
    junk = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "lines": [{"product_id": dish["id"], "quantity": 1, "spice": "http://spice.example"}],
        },
    )
    assert junk.status_code == 422, junk.text
    opened = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "notes": "Gate",
            "occasion": "Birthday",
            "lines": [{"product_id": dish["id"], "quantity": 1, "spice": "hot", "seat": 2}],
        },
    )
    assert opened.status_code == 200, opened.text
    body = opened.json()["data"]
    order_id = body["id"]
    assert body["occasion"] == "Birthday"
    assert body["notes"] == "Gate"
    assert "[[spice:" not in (body["notes"] or "")
    assert body["total_amount"] == 20
    assert body["status"] == "open"
    listed = await ac.get("/api/v1/restaurant/orders", headers=admin)
    row = next(item for item in listed.json()["data"] if item["id"] == order_id)
    line_id = row["items"][0]["id"]
    assert row["items"][0]["spice"] == "hot"
    assert row["items"][0]["seat"] == 2
    assert row["occasion"] == "Birthday"
    kept = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"notes": "Side door"},
    )
    assert kept.status_code == 200, kept.text
    listed = await ac.get("/api/v1/restaurant/orders", headers=admin)
    row = next(item for item in listed.json()["data"] if item["id"] == order_id)
    assert row["notes"] == "Side door"
    assert row["items"][0]["spice"] == "hot"
    assert row["items"][0]["seat"] == 2
    assert row["occasion"] == "Birthday"
    assert row["total_amount"] == 20
    sent = await ac.post(f"/api/v1/restaurant/orders/{order_id}/send", headers=admin)
    assert sent.status_code == 200, sent.text
    kitchen = await ac.get("/api/v1/restaurant/kitchen", headers=admin)
    ticket = next(item for item in kitchen.json()["data"] if item["order_id"] == order_id)
    dish_line = next(item for item in ticket["items"] if item["id"] == line_id)
    assert dish_line["spice"] == "hot"
    assert dish_line["seat"] == 2
    assert ticket["occasion"] == "Birthday"
    assert ticket["notes"] == "Side door"
    assert "[[spice:" not in (ticket["notes"] or "")
    cleared = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"line_spices": [{"line_id": line_id, "spice": None}]},
    )
    assert cleared.status_code == 200, cleared.text
    listed = await ac.get("/api/v1/restaurant/orders", headers=admin)
    row = next(item for item in listed.json()["data"] if item["id"] == order_id)
    assert row["items"][0]["spice"] is None
    assert row["items"][0]["seat"] == 2
    assert row["occasion"] == "Birthday"
    assert row["notes"] == "Side door"
    assert row["status"] == "sent"
    assert row["total_amount"] == 20
    await db_session.refresh(tenant)
    assert tenant.document_numbering["pos_sale"]["prefix"] == "POS"
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    denied = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"line_spices": [{"line_id": line_id, "spice": "mild"}]},
    )
    assert denied.status_code == 403, denied.text


async def test_restaurant_order_fire_at(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    tenant = seed["t1"]
    tenant.document_numbering = {"pos_sale": {"prefix": "POS", "next": 4, "year": 2026}}
    await db_session.commit()
    dish = await _product(ac, admin, name="Jollof", selling_price=20, prep_station="kitchen")
    junk = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "fire_at": "http://fire.example",
            "lines": [{"product_id": dish["id"], "quantity": 1}],
        },
    )
    assert junk.status_code == 422, junk.text
    opened = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "notes": "Gate",
            "ready_by": "19:00",
            "fire_at": "18:30",
            "lines": [{"product_id": dish["id"], "quantity": 1}],
        },
    )
    assert opened.status_code == 200, opened.text
    body = opened.json()["data"]
    order_id = body["id"]
    assert body["fire_at"] == "18:30"
    assert body["ready_by"] == "19:00"
    assert body["notes"] == "Gate"
    assert "[[fire:" not in (body["notes"] or "")
    assert body["total_amount"] == 20
    assert body["status"] == "open"
    kept = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"notes": "Side door"},
    )
    assert kept.status_code == 200, kept.text
    assert kept.json()["data"]["notes"] == "Side door"
    assert kept.json()["data"]["fire_at"] == "18:30"
    assert kept.json()["data"]["ready_by"] == "19:00"
    assert kept.json()["data"]["total_amount"] == 20
    sent = await ac.post(f"/api/v1/restaurant/orders/{order_id}/send", headers=admin)
    assert sent.status_code == 200, sent.text
    kitchen = await ac.get("/api/v1/restaurant/kitchen", headers=admin)
    ticket = next(item for item in kitchen.json()["data"] if item["order_id"] == order_id)
    assert ticket["fire_at"] == "18:30"
    assert ticket["ready_by"] == "19:00"
    assert ticket["notes"] == "Side door"
    assert "[[fire:" not in (ticket["notes"] or "")
    cleared = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"fire_at": None},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["data"]["fire_at"] is None
    assert cleared.json()["data"]["ready_by"] == "19:00"
    assert cleared.json()["data"]["notes"] == "Side door"
    assert cleared.json()["data"]["status"] == "sent"
    assert cleared.json()["data"]["total_amount"] == 20
    await db_session.refresh(tenant)
    assert tenant.document_numbering["pos_sale"]["prefix"] == "POS"
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    denied = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"fire_at": "18:30"},
    )
    assert denied.status_code == 403, denied.text


async def test_restaurant_order_packaging(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    tenant = seed["t1"]
    tenant.document_numbering = {"pos_sale": {"prefix": "POS", "next": 4, "year": 2026}}
    await db_session.commit()
    dish = await _product(ac, admin, name="Jollof", selling_price=20, prep_station="kitchen")
    junk = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "packaging": "http://pack.example",
            "lines": [{"product_id": dish["id"], "quantity": 1}],
        },
    )
    assert junk.status_code == 422, junk.text
    opened = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "notes": "Gate",
            "fire_at": "18:30",
            "packaging": "bag",
            "lines": [{"product_id": dish["id"], "quantity": 1}],
        },
    )
    assert opened.status_code == 200, opened.text
    body = opened.json()["data"]
    order_id = body["id"]
    assert body["packaging"] == "bag"
    assert body["fire_at"] == "18:30"
    assert body["notes"] == "Gate"
    assert "[[pack:" not in (body["notes"] or "")
    assert body["total_amount"] == 20
    assert body["status"] == "open"
    kept = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"notes": "Side door"},
    )
    assert kept.status_code == 200, kept.text
    assert kept.json()["data"]["notes"] == "Side door"
    assert kept.json()["data"]["packaging"] == "bag"
    assert kept.json()["data"]["fire_at"] == "18:30"
    assert kept.json()["data"]["total_amount"] == 20
    sent = await ac.post(f"/api/v1/restaurant/orders/{order_id}/send", headers=admin)
    assert sent.status_code == 200, sent.text
    kitchen = await ac.get("/api/v1/restaurant/kitchen", headers=admin)
    ticket = next(item for item in kitchen.json()["data"] if item["order_id"] == order_id)
    assert ticket["packaging"] == "bag"
    assert ticket["fire_at"] == "18:30"
    assert ticket["notes"] == "Side door"
    assert "[[pack:" not in (ticket["notes"] or "")
    cleared = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"packaging": None},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["data"]["packaging"] is None
    assert cleared.json()["data"]["fire_at"] == "18:30"
    assert cleared.json()["data"]["notes"] == "Side door"
    assert cleared.json()["data"]["status"] == "sent"
    assert cleared.json()["data"]["total_amount"] == 20
    await db_session.refresh(tenant)
    assert tenant.document_numbering["pos_sale"]["prefix"] == "POS"
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    denied = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"packaging": "box"},
    )
    assert denied.status_code == 403, denied.text


async def test_restaurant_order_high_chair(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    tenant = seed["t1"]
    tenant.document_numbering = {"pos_sale": {"prefix": "POS", "next": 4, "year": 2026}}
    await db_session.commit()
    dish = await _product(ac, admin, name="Jollof", selling_price=20, prep_station="kitchen")
    junk = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "high_chair": "http://highchair.example",
            "lines": [{"product_id": dish["id"], "quantity": 1}],
        },
    )
    assert junk.status_code == 422, junk.text
    opened = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "notes": "Gate",
            "packaging": "bag",
            "high_chair": True,
            "lines": [{"product_id": dish["id"], "quantity": 1}],
        },
    )
    assert opened.status_code == 200, opened.text
    body = opened.json()["data"]
    order_id = body["id"]
    assert body["high_chair"] is True
    assert body["packaging"] == "bag"
    assert body["notes"] == "Gate"
    assert "[[highchair]]" not in (body["notes"] or "")
    assert body["total_amount"] == 20
    assert body["status"] == "open"
    kept = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"notes": "Side door"},
    )
    assert kept.status_code == 200, kept.text
    assert kept.json()["data"]["notes"] == "Side door"
    assert kept.json()["data"]["high_chair"] is True
    assert kept.json()["data"]["packaging"] == "bag"
    assert kept.json()["data"]["total_amount"] == 20
    sent = await ac.post(f"/api/v1/restaurant/orders/{order_id}/send", headers=admin)
    assert sent.status_code == 200, sent.text
    kitchen = await ac.get("/api/v1/restaurant/kitchen", headers=admin)
    ticket = next(item for item in kitchen.json()["data"] if item["order_id"] == order_id)
    assert ticket["high_chair"] is True
    assert ticket["packaging"] == "bag"
    assert ticket["notes"] == "Side door"
    assert "[[highchair]]" not in (ticket["notes"] or "")
    cleared = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"high_chair": False},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["data"]["high_chair"] is False
    assert cleared.json()["data"]["packaging"] == "bag"
    assert cleared.json()["data"]["notes"] == "Side door"
    assert cleared.json()["data"]["status"] == "sent"
    assert cleared.json()["data"]["total_amount"] == 20
    await db_session.refresh(tenant)
    assert tenant.document_numbering["pos_sale"]["prefix"] == "POS"
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    denied = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"high_chair": True},
    )
    assert denied.status_code == 403, denied.text


async def test_restaurant_order_diet(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    tenant = seed["t1"]
    tenant.document_numbering = {"pos_sale": {"prefix": "POS", "next": 4, "year": 2026}}
    await db_session.commit()
    dish = await _product(ac, admin, name="Jollof", selling_price=20, prep_station="kitchen")
    junk = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "diet": "http://diet.example",
            "lines": [{"product_id": dish["id"], "quantity": 1}],
        },
    )
    assert junk.status_code == 422, junk.text
    opened = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "notes": "Gate",
            "high_chair": True,
            "diet": "vegetarian",
            "lines": [{"product_id": dish["id"], "quantity": 1}],
        },
    )
    assert opened.status_code == 200, opened.text
    body = opened.json()["data"]
    order_id = body["id"]
    assert body["diet"] == "vegetarian"
    assert body["high_chair"] is True
    assert body["notes"] == "Gate"
    assert "[[diet:" not in (body["notes"] or "")
    assert body["total_amount"] == 20
    assert body["status"] == "open"
    kept = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"notes": "Side door"},
    )
    assert kept.status_code == 200, kept.text
    assert kept.json()["data"]["notes"] == "Side door"
    assert kept.json()["data"]["diet"] == "vegetarian"
    assert kept.json()["data"]["high_chair"] is True
    assert kept.json()["data"]["total_amount"] == 20
    sent = await ac.post(f"/api/v1/restaurant/orders/{order_id}/send", headers=admin)
    assert sent.status_code == 200, sent.text
    kitchen = await ac.get("/api/v1/restaurant/kitchen", headers=admin)
    ticket = next(item for item in kitchen.json()["data"] if item["order_id"] == order_id)
    assert ticket["diet"] == "vegetarian"
    assert ticket["high_chair"] is True
    assert ticket["notes"] == "Side door"
    assert "[[diet:" not in (ticket["notes"] or "")
    cleared = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"diet": None},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["data"]["diet"] is None
    assert cleared.json()["data"]["high_chair"] is True
    assert cleared.json()["data"]["notes"] == "Side door"
    assert cleared.json()["data"]["status"] == "sent"
    assert cleared.json()["data"]["total_amount"] == 20
    await db_session.refresh(tenant)
    assert tenant.document_numbering["pos_sale"]["prefix"] == "POS"
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    denied = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"diet": "vegan"},
    )
    assert denied.status_code == 403, denied.text


async def test_restaurant_order_guest_source(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    tenant = seed["t1"]
    tenant.document_numbering = {"pos_sale": {"prefix": "POS", "next": 4, "year": 2026}}
    await db_session.commit()
    dish = await _product(ac, admin, name="Jollof", selling_price=20, prep_station="kitchen")
    junk = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "guest_source": "http://source.example",
            "lines": [{"product_id": dish["id"], "quantity": 1}],
        },
    )
    assert junk.status_code == 422, junk.text
    opened = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "notes": "Gate",
            "diet": "vegetarian",
            "guest_source": "walk_in",
            "lines": [{"product_id": dish["id"], "quantity": 1}],
        },
    )
    assert opened.status_code == 200, opened.text
    body = opened.json()["data"]
    order_id = body["id"]
    assert body["guest_source"] == "walk_in"
    assert body["diet"] == "vegetarian"
    assert body["notes"] == "Gate"
    assert "[[source:" not in (body["notes"] or "")
    assert body["total_amount"] == 20
    assert body["status"] == "open"
    kept = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"notes": "Side door"},
    )
    assert kept.status_code == 200, kept.text
    assert kept.json()["data"]["notes"] == "Side door"
    assert kept.json()["data"]["guest_source"] == "walk_in"
    assert kept.json()["data"]["diet"] == "vegetarian"
    assert kept.json()["data"]["total_amount"] == 20
    sent = await ac.post(f"/api/v1/restaurant/orders/{order_id}/send", headers=admin)
    assert sent.status_code == 200, sent.text
    kitchen = await ac.get("/api/v1/restaurant/kitchen", headers=admin)
    ticket = next(item for item in kitchen.json()["data"] if item["order_id"] == order_id)
    assert ticket["guest_source"] == "walk_in"
    assert ticket["diet"] == "vegetarian"
    assert ticket["notes"] == "Side door"
    assert "[[source:" not in (ticket["notes"] or "")
    cleared = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"guest_source": None},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["data"]["guest_source"] is None
    assert cleared.json()["data"]["diet"] == "vegetarian"
    assert cleared.json()["data"]["notes"] == "Side door"
    assert cleared.json()["data"]["status"] == "sent"
    assert cleared.json()["data"]["total_amount"] == 20
    await db_session.refresh(tenant)
    assert tenant.document_numbering["pos_sale"]["prefix"] == "POS"
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    denied = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"guest_source": "phone"},
    )
    assert denied.status_code == 403, denied.text


async def test_restaurant_order_vehicle(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    tenant = seed["t1"]
    tenant.document_numbering = {"pos_sale": {"prefix": "POS", "next": 4, "year": 2026}}
    await db_session.commit()
    dish = await _product(ac, admin, name="Jollof", selling_price=20, prep_station="kitchen")
    junk = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "vehicle": "http://car.example",
            "lines": [{"product_id": dish["id"], "quantity": 1}],
        },
    )
    assert junk.status_code == 422, junk.text
    opened = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "notes": "Gate",
            "guest_source": "walk_in",
            "vehicle": "Blue Corolla",
            "lines": [{"product_id": dish["id"], "quantity": 1}],
        },
    )
    assert opened.status_code == 200, opened.text
    body = opened.json()["data"]
    order_id = body["id"]
    assert body["vehicle"] == "Blue Corolla"
    assert body["guest_source"] == "walk_in"
    assert body["notes"] == "Gate"
    assert "[[vehicle:" not in (body["notes"] or "")
    assert body["total_amount"] == 20
    assert body["status"] == "open"
    kept = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"notes": "Side door"},
    )
    assert kept.status_code == 200, kept.text
    assert kept.json()["data"]["notes"] == "Side door"
    assert kept.json()["data"]["vehicle"] == "Blue Corolla"
    assert kept.json()["data"]["guest_source"] == "walk_in"
    assert kept.json()["data"]["total_amount"] == 20
    sent = await ac.post(f"/api/v1/restaurant/orders/{order_id}/send", headers=admin)
    assert sent.status_code == 200, sent.text
    kitchen = await ac.get("/api/v1/restaurant/kitchen", headers=admin)
    ticket = next(item for item in kitchen.json()["data"] if item["order_id"] == order_id)
    assert ticket["vehicle"] == "Blue Corolla"
    assert ticket["guest_source"] == "walk_in"
    assert ticket["notes"] == "Side door"
    assert "[[vehicle:" not in (ticket["notes"] or "")
    cleared = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"vehicle": None},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["data"]["vehicle"] is None
    assert cleared.json()["data"]["guest_source"] == "walk_in"
    assert cleared.json()["data"]["notes"] == "Side door"
    assert cleared.json()["data"]["status"] == "sent"
    assert cleared.json()["data"]["total_amount"] == 20
    await db_session.refresh(tenant)
    assert tenant.document_numbering["pos_sale"]["prefix"] == "POS"
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    denied = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"vehicle": "Red taxi"},
    )
    assert denied.status_code == 403, denied.text


async def test_restaurant_order_bay(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    tenant = seed["t1"]
    tenant.document_numbering = {"pos_sale": {"prefix": "POS", "next": 4, "year": 2026}}
    await db_session.commit()
    dish = await _product(ac, admin, name="Jollof", selling_price=20, prep_station="kitchen")
    junk = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "bay": "http://bay.example",
            "lines": [{"product_id": dish["id"], "quantity": 1}],
        },
    )
    assert junk.status_code == 422, junk.text
    high = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "bay": 41,
            "lines": [{"product_id": dish["id"], "quantity": 1}],
        },
    )
    assert high.status_code == 422, high.text
    opened = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "notes": "Gate",
            "vehicle": "Blue Corolla",
            "bay": 4,
            "lines": [{"product_id": dish["id"], "quantity": 1}],
        },
    )
    assert opened.status_code == 200, opened.text
    body = opened.json()["data"]
    order_id = body["id"]
    assert body["bay"] == 4
    assert body["vehicle"] == "Blue Corolla"
    assert body["notes"] == "Gate"
    assert "[[bay:" not in (body["notes"] or "")
    assert body["total_amount"] == 20
    assert body["status"] == "open"
    kept = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"notes": "Side door"},
    )
    assert kept.status_code == 200, kept.text
    assert kept.json()["data"]["notes"] == "Side door"
    assert kept.json()["data"]["bay"] == 4
    assert kept.json()["data"]["vehicle"] == "Blue Corolla"
    assert kept.json()["data"]["total_amount"] == 20
    sent = await ac.post(f"/api/v1/restaurant/orders/{order_id}/send", headers=admin)
    assert sent.status_code == 200, sent.text
    kitchen = await ac.get("/api/v1/restaurant/kitchen", headers=admin)
    ticket = next(item for item in kitchen.json()["data"] if item["order_id"] == order_id)
    assert ticket["bay"] == 4
    assert ticket["vehicle"] == "Blue Corolla"
    assert ticket["notes"] == "Side door"
    assert "[[bay:" not in (ticket["notes"] or "")
    cleared = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"bay": None},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["data"]["bay"] is None
    assert cleared.json()["data"]["vehicle"] == "Blue Corolla"
    assert cleared.json()["data"]["notes"] == "Side door"
    assert cleared.json()["data"]["status"] == "sent"
    assert cleared.json()["data"]["total_amount"] == 20
    await db_session.refresh(tenant)
    assert tenant.document_numbering["pos_sale"]["prefix"] == "POS"
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    denied = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"bay": 2},
    )
    assert denied.status_code == 403, denied.text


async def test_restaurant_order_item_doneness(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    tenant = seed["t1"]
    tenant.document_numbering = {"pos_sale": {"prefix": "POS", "next": 4, "year": 2026}}
    await db_session.commit()
    dish = await _product(ac, admin, name="Jollof", selling_price=20, prep_station="kitchen")
    junk = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "lines": [{"product_id": dish["id"], "quantity": 1, "doneness": "http://doneness.example"}],
        },
    )
    assert junk.status_code == 422, junk.text
    opened = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "notes": "Gate",
            "lines": [{"product_id": dish["id"], "quantity": 1, "doneness": "rare", "spice": "mild"}],
        },
    )
    assert opened.status_code == 200, opened.text
    body = opened.json()["data"]
    order_id = body["id"]
    assert body["notes"] == "Gate"
    assert "[[doneness:" not in (body["notes"] or "")
    assert body["total_amount"] == 20
    assert body["status"] == "open"
    listed = await ac.get("/api/v1/restaurant/orders", headers=admin)
    row = next(item for item in listed.json()["data"] if item["id"] == order_id)
    line_id = row["items"][0]["id"]
    assert row["items"][0]["doneness"] == "rare"
    assert row["items"][0]["spice"] == "mild"
    kept = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"notes": "Side door"},
    )
    assert kept.status_code == 200, kept.text
    listed = await ac.get("/api/v1/restaurant/orders", headers=admin)
    row = next(item for item in listed.json()["data"] if item["id"] == order_id)
    assert row["notes"] == "Side door"
    assert row["items"][0]["doneness"] == "rare"
    assert row["items"][0]["spice"] == "mild"
    assert row["total_amount"] == 20
    sent = await ac.post(f"/api/v1/restaurant/orders/{order_id}/send", headers=admin)
    assert sent.status_code == 200, sent.text
    kitchen = await ac.get("/api/v1/restaurant/kitchen", headers=admin)
    ticket = next(item for item in kitchen.json()["data"] if item["order_id"] == order_id)
    dish_line = next(item for item in ticket["items"] if item["id"] == line_id)
    assert dish_line["doneness"] == "rare"
    assert dish_line["spice"] == "mild"
    assert ticket["notes"] == "Side door"
    assert "[[doneness:" not in (ticket["notes"] or "")
    cleared = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"line_doneness": [{"line_id": line_id, "doneness": None}]},
    )
    assert cleared.status_code == 200, cleared.text
    listed = await ac.get("/api/v1/restaurant/orders", headers=admin)
    row = next(item for item in listed.json()["data"] if item["id"] == order_id)
    assert row["items"][0]["doneness"] is None
    assert row["items"][0]["spice"] == "mild"
    assert row["notes"] == "Side door"
    assert row["status"] == "sent"
    assert row["total_amount"] == 20
    await db_session.refresh(tenant)
    assert tenant.document_numbering["pos_sale"]["prefix"] == "POS"
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    denied = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"line_doneness": [{"line_id": line_id, "doneness": "well"}]},
    )
    assert denied.status_code == 403, denied.text


async def test_restaurant_order_allergen(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    tenant = seed["t1"]
    tenant.document_numbering = {"pos_sale": {"prefix": "POS", "next": 4, "year": 2026}}
    await db_session.commit()
    dish = await _product(ac, admin, name="Jollof", selling_price=20, prep_station="kitchen")
    junk = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "allergen": "http://allergen.example",
            "lines": [{"product_id": dish["id"], "quantity": 1}],
        },
    )
    assert junk.status_code == 422, junk.text
    opened = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "notes": "Gate",
            "allergy": "No peanuts in the sauce",
            "diet": "vegetarian",
            "allergen": "nuts",
            "lines": [{"product_id": dish["id"], "quantity": 1}],
        },
    )
    assert opened.status_code == 200, opened.text
    body = opened.json()["data"]
    order_id = body["id"]
    assert body["allergen"] == "nuts"
    assert body["allergy"] == "No peanuts in the sauce"
    assert body["diet"] == "vegetarian"
    assert body["notes"] == "Gate"
    assert "[[allergen:" not in (body["notes"] or "")
    assert body["total_amount"] == 20
    assert body["status"] == "open"
    kept = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"notes": "Side door"},
    )
    assert kept.status_code == 200, kept.text
    assert kept.json()["data"]["notes"] == "Side door"
    assert kept.json()["data"]["allergen"] == "nuts"
    assert kept.json()["data"]["allergy"] == "No peanuts in the sauce"
    assert kept.json()["data"]["diet"] == "vegetarian"
    assert kept.json()["data"]["total_amount"] == 20
    sent = await ac.post(f"/api/v1/restaurant/orders/{order_id}/send", headers=admin)
    assert sent.status_code == 200, sent.text
    kitchen = await ac.get("/api/v1/restaurant/kitchen", headers=admin)
    ticket = next(item for item in kitchen.json()["data"] if item["order_id"] == order_id)
    assert ticket["allergen"] == "nuts"
    assert ticket["allergy"] == "No peanuts in the sauce"
    assert ticket["diet"] == "vegetarian"
    assert ticket["notes"] == "Side door"
    assert "[[allergen:" not in (ticket["notes"] or "")
    cleared = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"allergen": None},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["data"]["allergen"] is None
    assert cleared.json()["data"]["allergy"] == "No peanuts in the sauce"
    assert cleared.json()["data"]["diet"] == "vegetarian"
    assert cleared.json()["data"]["notes"] == "Side door"
    assert cleared.json()["data"]["status"] == "sent"
    assert cleared.json()["data"]["total_amount"] == 20
    await db_session.refresh(tenant)
    assert tenant.document_numbering["pos_sale"]["prefix"] == "POS"
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    denied = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"allergen": "gluten"},
    )
    assert denied.status_code == 403, denied.text


async def test_restaurant_order_handoff(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    tenant = seed["t1"]
    tenant.document_numbering = {"pos_sale": {"prefix": "POS", "next": 4, "year": 2026}}
    await db_session.commit()
    dish = await _product(ac, admin, name="Jollof", selling_price=20, prep_station="kitchen")
    junk = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "handoff": "http://handoff.example",
            "lines": [{"product_id": dish["id"], "quantity": 1}],
        },
    )
    assert junk.status_code == 422, junk.text
    opened = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "notes": "Gate",
            "vehicle": "Silver taxi",
            "handoff": "door",
            "lines": [{"product_id": dish["id"], "quantity": 1}],
        },
    )
    assert opened.status_code == 200, opened.text
    body = opened.json()["data"]
    order_id = body["id"]
    assert body["handoff"] == "door"
    assert body["vehicle"] == "Silver taxi"
    assert body["delivery_address"] is None
    assert body["notes"] == "Gate"
    assert "[[handoff:" not in (body["notes"] or "")
    assert body["total_amount"] == 20
    assert body["status"] == "open"
    kept = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"notes": "Side door"},
    )
    assert kept.status_code == 200, kept.text
    assert kept.json()["data"]["notes"] == "Side door"
    assert kept.json()["data"]["handoff"] == "door"
    assert kept.json()["data"]["vehicle"] == "Silver taxi"
    assert kept.json()["data"]["delivery_address"] is None
    assert kept.json()["data"]["total_amount"] == 20
    sent = await ac.post(f"/api/v1/restaurant/orders/{order_id}/send", headers=admin)
    assert sent.status_code == 200, sent.text
    kitchen = await ac.get("/api/v1/restaurant/kitchen", headers=admin)
    ticket = next(item for item in kitchen.json()["data"] if item["order_id"] == order_id)
    assert ticket["handoff"] == "door"
    assert ticket["vehicle"] == "Silver taxi"
    assert ticket["delivery_address"] is None
    assert ticket["notes"] == "Side door"
    assert "[[handoff:" not in (ticket["notes"] or "")
    cleared = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"handoff": None},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["data"]["handoff"] is None
    assert cleared.json()["data"]["vehicle"] == "Silver taxi"
    assert cleared.json()["data"]["notes"] == "Side door"
    assert cleared.json()["data"]["status"] == "sent"
    assert cleared.json()["data"]["total_amount"] == 20
    await db_session.refresh(tenant)
    assert tenant.document_numbering["pos_sale"]["prefix"] == "POS"
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    denied = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"handoff": "hand"},
    )
    assert denied.status_code == 403, denied.text


async def test_restaurant_order_bill_asked(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    tenant = seed["t1"]
    tenant.document_numbering = {"pos_sale": {"prefix": "POS", "next": 4, "year": 2026}}
    await db_session.commit()
    dish = await _product(ac, admin, name="Jollof", selling_price=20, prep_station="kitchen")
    junk = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "bill_asked": "http://bill.example",
            "lines": [{"product_id": dish["id"], "quantity": 1}],
        },
    )
    assert junk.status_code == 422, junk.text
    opened = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "notes": "Gate",
            "rush": True,
            "bill_asked": True,
            "lines": [{"product_id": dish["id"], "quantity": 1}],
        },
    )
    assert opened.status_code == 200, opened.text
    body = opened.json()["data"]
    order_id = body["id"]
    assert body["bill_asked"] is True
    assert body["rush"] is True
    assert body["payment_method"] == "cash"
    assert body["notes"] == "Gate"
    assert "[[bill]]" not in (body["notes"] or "")
    assert body["total_amount"] == 20
    assert body["status"] == "open"
    kept = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"notes": "Side door"},
    )
    assert kept.status_code == 200, kept.text
    assert kept.json()["data"]["notes"] == "Side door"
    assert kept.json()["data"]["bill_asked"] is True
    assert kept.json()["data"]["rush"] is True
    assert kept.json()["data"]["payment_method"] == "cash"
    assert kept.json()["data"]["total_amount"] == 20
    sent = await ac.post(f"/api/v1/restaurant/orders/{order_id}/send", headers=admin)
    assert sent.status_code == 200, sent.text
    kitchen = await ac.get("/api/v1/restaurant/kitchen", headers=admin)
    ticket = next(item for item in kitchen.json()["data"] if item["order_id"] == order_id)
    assert ticket["bill_asked"] is True
    assert ticket["rush"] is True
    assert ticket["notes"] == "Side door"
    assert "[[bill]]" not in (ticket["notes"] or "")
    cleared = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"bill_asked": False},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["data"]["bill_asked"] is False
    assert cleared.json()["data"]["rush"] is True
    assert cleared.json()["data"]["payment_method"] == "cash"
    assert cleared.json()["data"]["notes"] == "Side door"
    assert cleared.json()["data"]["status"] == "sent"
    assert cleared.json()["data"]["total_amount"] == 20
    await db_session.refresh(tenant)
    assert tenant.document_numbering["pos_sale"]["prefix"] == "POS"
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    denied = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"bill_asked": True},
    )
    assert denied.status_code == 403, denied.text


async def test_restaurant_order_receipt(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    tenant = seed["t1"]
    tenant.document_numbering = {"pos_sale": {"prefix": "POS", "next": 4, "year": 2026}}
    await db_session.commit()
    dish = await _product(ac, admin, name="Jollof", selling_price=20, prep_station="kitchen")
    junk = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "receipt": "http://receipt.example",
            "lines": [{"product_id": dish["id"], "quantity": 1}],
        },
    )
    assert junk.status_code == 422, junk.text
    opened = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "notes": "Gate",
            "guest_email": "guest@example.com",
            "receipt": "email",
            "lines": [{"product_id": dish["id"], "quantity": 1}],
        },
    )
    assert opened.status_code == 200, opened.text
    body = opened.json()["data"]
    order_id = body["id"]
    assert body["receipt"] == "email"
    assert body["guest_email"] == "guest@example.com"
    assert body["notes"] == "Gate"
    assert "[[receipt:" not in (body["notes"] or "")
    assert body["total_amount"] == 20
    assert body["status"] == "open"
    kept = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"notes": "Side door"},
    )
    assert kept.status_code == 200, kept.text
    assert kept.json()["data"]["notes"] == "Side door"
    assert kept.json()["data"]["receipt"] == "email"
    assert kept.json()["data"]["guest_email"] == "guest@example.com"
    assert kept.json()["data"]["total_amount"] == 20
    sent = await ac.post(f"/api/v1/restaurant/orders/{order_id}/send", headers=admin)
    assert sent.status_code == 200, sent.text
    kitchen = await ac.get("/api/v1/restaurant/kitchen", headers=admin)
    ticket = next(item for item in kitchen.json()["data"] if item["order_id"] == order_id)
    assert ticket["receipt"] == "email"
    assert ticket["guest_email"] == "guest@example.com"
    assert ticket["notes"] == "Side door"
    assert "[[receipt:" not in (ticket["notes"] or "")
    cleared = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"receipt": None},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["data"]["receipt"] is None
    assert cleared.json()["data"]["guest_email"] == "guest@example.com"
    assert cleared.json()["data"]["notes"] == "Side door"
    assert cleared.json()["data"]["status"] == "sent"
    assert cleared.json()["data"]["total_amount"] == 20
    await db_session.refresh(tenant)
    assert tenant.document_numbering["pos_sale"]["prefix"] == "POS"
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    denied = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"receipt": "print"},
    )
    assert denied.status_code == 403, denied.text


async def test_restaurant_order_quoted_wait(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    tenant = seed["t1"]
    tenant.document_numbering = {"pos_sale": {"prefix": "POS", "next": 4, "year": 2026}}
    await db_session.commit()
    dish = await _product(ac, admin, name="Jollof", selling_price=20, prep_station="kitchen")
    junk = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "quoted_wait": "http://wait.example",
            "lines": [{"product_id": dish["id"], "quantity": 1}],
        },
    )
    assert junk.status_code == 422, junk.text
    short = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "quoted_wait": 4,
            "lines": [{"product_id": dish["id"], "quantity": 1}],
        },
    )
    assert short.status_code == 422, short.text
    opened = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "notes": "Gate",
            "ready_by": "19:30",
            "quoted_wait": 25,
            "lines": [{"product_id": dish["id"], "quantity": 1}],
        },
    )
    assert opened.status_code == 200, opened.text
    body = opened.json()["data"]
    order_id = body["id"]
    assert body["quoted_wait"] == 25
    assert body["ready_by"] == "19:30"
    assert body["notes"] == "Gate"
    assert "[[wait:" not in (body["notes"] or "")
    assert body["total_amount"] == 20
    assert body["status"] == "open"
    kept = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"notes": "Side door"},
    )
    assert kept.status_code == 200, kept.text
    assert kept.json()["data"]["notes"] == "Side door"
    assert kept.json()["data"]["quoted_wait"] == 25
    assert kept.json()["data"]["ready_by"] == "19:30"
    assert kept.json()["data"]["total_amount"] == 20
    sent = await ac.post(f"/api/v1/restaurant/orders/{order_id}/send", headers=admin)
    assert sent.status_code == 200, sent.text
    kitchen = await ac.get("/api/v1/restaurant/kitchen", headers=admin)
    ticket = next(item for item in kitchen.json()["data"] if item["order_id"] == order_id)
    assert ticket["quoted_wait"] == 25
    assert ticket["ready_by"] == "19:30"
    assert ticket["notes"] == "Side door"
    assert "[[wait:" not in (ticket["notes"] or "")
    assert ticket["status"] != "preparing"
    cleared = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"quoted_wait": None},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["data"]["quoted_wait"] is None
    assert cleared.json()["data"]["ready_by"] == "19:30"
    assert cleared.json()["data"]["notes"] == "Side door"
    assert cleared.json()["data"]["status"] == "sent"
    assert cleared.json()["data"]["total_amount"] == 20
    await db_session.refresh(tenant)
    assert tenant.document_numbering["pos_sale"]["prefix"] == "POS"
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    denied = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"quoted_wait": 30},
    )
    assert denied.status_code == 403, denied.text


async def test_restaurant_booking_turn(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    when = (datetime.utcnow() + timedelta(hours=3)).replace(microsecond=0).isoformat()
    junk = await ac.post(
        "/api/v1/restaurant/bookings",
        headers=admin,
        json={
            "guest_name": "Ama Walkin",
            "phone": "+233241234567",
            "party_size": 2,
            "booked_for": when,
            "turn": "http://turn.example",
        },
    )
    assert junk.status_code == 422, junk.text
    short = await ac.post(
        "/api/v1/restaurant/bookings",
        headers=admin,
        json={
            "guest_name": "Ama Walkin",
            "phone": "+233241234567",
            "party_size": 2,
            "booked_for": when,
            "turn": 45,
        },
    )
    assert short.status_code == 422, short.text
    opened = await ac.post(
        "/api/v1/restaurant/bookings",
        headers=admin,
        json={
            "guest_name": "Ama Walkin",
            "phone": "+233241234567",
            "party_size": 2,
            "booked_for": when,
            "notes": "Window seat",
            "turn": 90,
        },
    )
    assert opened.status_code == 200, opened.text
    body = opened.json()["data"]
    booking_id = body["id"]
    assert body["turn"] == 90
    assert body["notes"] == "Window seat"
    assert "[[turn:" not in (body["notes"] or "")
    assert body["status"] == "requested"
    assert body["table_id"] is None
    kept = await ac.patch(
        f"/api/v1/restaurant/bookings/{booking_id}",
        headers=admin,
        json={"notes": "Side door"},
    )
    assert kept.status_code == 200, kept.text
    assert kept.json()["data"]["notes"] == "Side door"
    assert kept.json()["data"]["turn"] == 90
    assert kept.json()["data"]["status"] == "requested"
    assert kept.json()["data"]["table_id"] is None
    cleared = await ac.patch(
        f"/api/v1/restaurant/bookings/{booking_id}",
        headers=admin,
        json={"turn": None},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["data"]["turn"] is None
    assert cleared.json()["data"]["notes"] == "Side door"
    assert cleared.json()["data"]["status"] == "requested"
    assert cleared.json()["data"]["table_id"] is None
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    denied = await ac.patch(
        f"/api/v1/restaurant/bookings/{booking_id}",
        headers=admin,
        json={"turn": 60},
    )
    assert denied.status_code == 403, denied.text


async def test_restaurant_order_guest_arrived(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    tenant = seed["t1"]
    tenant.document_numbering = {"pos_sale": {"prefix": "POS", "next": 4, "year": 2026}}
    await db_session.commit()
    dish = await _product(ac, admin, name="Jollof", selling_price=20, prep_station="kitchen")
    junk = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "guest_arrived": "http://arrived.example",
            "lines": [{"product_id": dish["id"], "quantity": 1}],
        },
    )
    assert junk.status_code == 422, junk.text
    opened = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "notes": "Gate",
            "bill_asked": True,
            "guest_arrived": True,
            "lines": [{"product_id": dish["id"], "quantity": 1}],
        },
    )
    assert opened.status_code == 200, opened.text
    body = opened.json()["data"]
    order_id = body["id"]
    assert body["guest_arrived"] is True
    assert body["bill_asked"] is True
    assert body["payment_method"] == "cash"
    assert body["notes"] == "Gate"
    assert "[[arrived]]" not in (body["notes"] or "")
    assert body["total_amount"] == 20
    assert body["status"] == "open"
    kept = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"notes": "Side door"},
    )
    assert kept.status_code == 200, kept.text
    assert kept.json()["data"]["notes"] == "Side door"
    assert kept.json()["data"]["guest_arrived"] is True
    assert kept.json()["data"]["bill_asked"] is True
    assert kept.json()["data"]["payment_method"] == "cash"
    assert kept.json()["data"]["status"] == "open"
    sent = await ac.post(f"/api/v1/restaurant/orders/{order_id}/send", headers=admin)
    assert sent.status_code == 200, sent.text
    kitchen = await ac.get("/api/v1/restaurant/kitchen", headers=admin)
    ticket = next(item for item in kitchen.json()["data"] if item["order_id"] == order_id)
    assert ticket["guest_arrived"] is True
    assert ticket["bill_asked"] is True
    assert ticket["notes"] == "Side door"
    assert "[[arrived]]" not in (ticket["notes"] or "")
    cleared = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"guest_arrived": False},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["data"]["guest_arrived"] is False
    assert cleared.json()["data"]["bill_asked"] is True
    assert cleared.json()["data"]["payment_method"] == "cash"
    assert cleared.json()["data"]["status"] == "sent"
    assert cleared.json()["data"]["total_amount"] == 20
    await db_session.refresh(tenant)
    assert tenant.document_numbering["pos_sale"]["prefix"] == "POS"
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    denied = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"guest_arrived": True},
    )
    assert denied.status_code == 403, denied.text


async def test_restaurant_table_room(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    tenant = seed["t1"]
    tenant.document_numbering = {"pos_sale": {"prefix": "POS", "next": 4, "year": 2026}}
    await db_session.commit()
    junk = await ac.post(
        "/api/v1/restaurant/tables",
        headers=admin,
        json={"code": "W1", "name": "Window", "seats": 4, "room": "http://room.example"},
    )
    assert junk.status_code == 422, junk.text
    made = await ac.post(
        "/api/v1/restaurant/tables",
        headers=admin,
        json={"code": "W1", "name": "Window", "seats": 4, "room": "patio"},
    )
    assert made.status_code == 200, made.text
    table = made.json()["data"]
    table_id = table["id"]
    assert table["room"] == "patio"
    assert table["name"] == "Window"
    assert table["seats"] == 4
    assert table["status"] == "available"
    placed = await ac.put(
        "/api/v1/restaurant/floor-places",
        headers=admin,
        json={"places": [{"table_id": table_id, "x": 20, "y": 30}]},
    )
    assert placed.status_code == 200, placed.text
    renamed = await ac.patch(
        f"/api/v1/restaurant/tables/{table_id}",
        headers=admin,
        json={"name": "Bay window"},
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["data"]["name"] == "Bay window"
    assert renamed.json()["data"]["room"] == "patio"
    assert renamed.json()["data"]["status"] == "available"
    await db_session.refresh(tenant)
    assert tenant.document_numbering["pos_sale"]["prefix"] == "POS"
    assert tenant.document_numbering["restaurant_floor_places"][0]["x"] == 20
    assert tenant.document_numbering["restaurant_table_rooms"][table_id] == "patio"
    moved = await ac.patch(
        f"/api/v1/restaurant/tables/{table_id}",
        headers=admin,
        json={"room": "private"},
    )
    assert moved.status_code == 200, moved.text
    assert moved.json()["data"]["room"] == "private"
    assert moved.json()["data"]["name"] == "Bay window"
    listed = await ac.get("/api/v1/restaurant/floor-places", headers=admin)
    assert listed.json()["data"] == [{"table_id": table_id, "x": 20, "y": 30}]
    cleared = await ac.patch(
        f"/api/v1/restaurant/tables/{table_id}",
        headers=admin,
        json={"room": None},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["data"]["room"] is None
    assert cleared.json()["data"]["name"] == "Bay window"
    assert cleared.json()["data"]["status"] == "available"
    await db_session.refresh(tenant)
    assert "restaurant_table_rooms" not in (tenant.document_numbering or {})
    assert tenant.document_numbering["restaurant_floor_places"][0]["x"] == 20
    assert tenant.document_numbering["pos_sale"]["prefix"] == "POS"
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    denied = await ac.patch(
        f"/api/v1/restaurant/tables/{table_id}",
        headers=admin,
        json={"room": "dining"},
    )
    assert denied.status_code == 403, denied.text


async def test_restaurant_recipe_cook_time(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    tenant = seed["t1"]
    tenant.document_numbering = {"pos_sale": {"prefix": "POS", "next": 4, "year": 2026}}
    await db_session.commit()
    dish = await _product(ac, admin, name="Jollof", selling_price=20, prep_station="kitchen")
    rice = await _product(ac, admin, name="Rice", selling_price=1)
    junk = await ac.post(
        "/api/v1/restaurant/recipes",
        headers=admin,
        json={
            "product_id": dish["id"],
            "name": "Jollof recipe",
            "cook_time": "http://cook.example",
            "lines": [{"ingredient_id": rice["id"], "quantity": 1}],
        },
    )
    assert junk.status_code == 422, junk.text
    short = await ac.post(
        "/api/v1/restaurant/recipes",
        headers=admin,
        json={
            "product_id": dish["id"],
            "name": "Jollof recipe",
            "cook_time": 0,
            "lines": [{"ingredient_id": rice["id"], "quantity": 1}],
        },
    )
    assert short.status_code == 422, short.text
    saved = await ac.post(
        "/api/v1/restaurant/recipes",
        headers=admin,
        json={
            "product_id": dish["id"],
            "name": "Jollof recipe",
            "cook_time": 25,
            "lines": [{"ingredient_id": rice["id"], "quantity": 1}],
        },
    )
    assert saved.status_code == 200, saved.text
    recipe_id = saved.json()["data"]["id"]
    assert saved.json()["data"]["cook_time"] == 25
    assert saved.json()["data"]["name"] == "Jollof recipe"
    renamed = await ac.patch(
        f"/api/v1/restaurant/recipes/{recipe_id}",
        headers=admin,
        json={"name": "House jollof"},
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["data"]["name"] == "House jollof"
    assert renamed.json()["data"]["cook_time"] == 25
    listed = await ac.get("/api/v1/restaurant/recipes", headers=admin)
    recipe = next(row for row in listed.json()["data"] if row["id"] == recipe_id)
    assert recipe["cook_time"] == 25
    assert recipe["lines"] == [{"ingredient_id": rice["id"], "name": "Rice", "quantity": 1}]
    assert recipe["station"] == "kitchen"
    await db_session.refresh(tenant)
    assert tenant.document_numbering["pos_sale"]["prefix"] == "POS"
    assert tenant.document_numbering["restaurant_cook_times"][recipe_id] == 25
    cleared = await ac.patch(
        f"/api/v1/restaurant/recipes/{recipe_id}",
        headers=admin,
        json={"cook_time": None},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["data"]["cook_time"] is None
    assert cleared.json()["data"]["name"] == "House jollof"
    kept = await ac.get("/api/v1/restaurant/recipes", headers=admin)
    kept_recipe = next(row for row in kept.json()["data"] if row["id"] == recipe_id)
    assert kept_recipe["lines"][0]["quantity"] == 1
    await db_session.refresh(tenant)
    assert "restaurant_cook_times" not in (tenant.document_numbering or {})
    assert tenant.document_numbering["pos_sale"]["prefix"] == "POS"
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    denied = await ac.patch(
        f"/api/v1/restaurant/recipes/{recipe_id}",
        headers=admin,
        json={"cook_time": 30},
    )
    assert denied.status_code == 403, denied.text


async def test_restaurant_recipe_servings(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    tenant = seed["t1"]
    tenant.document_numbering = {"pos_sale": {"prefix": "POS", "next": 4, "year": 2026}}
    await db_session.commit()
    dish = await _product(ac, admin, name="Jollof", selling_price=20, prep_station="kitchen")
    rice = await _product(ac, admin, name="Rice", selling_price=1)
    junk = await ac.post(
        "/api/v1/restaurant/recipes",
        headers=admin,
        json={
            "product_id": dish["id"],
            "name": "Jollof recipe",
            "servings": "http://servings.example",
            "lines": [{"ingredient_id": rice["id"], "quantity": 1}],
        },
    )
    assert junk.status_code == 422, junk.text
    zero = await ac.post(
        "/api/v1/restaurant/recipes",
        headers=admin,
        json={
            "product_id": dish["id"],
            "name": "Jollof recipe",
            "servings": 0,
            "lines": [{"ingredient_id": rice["id"], "quantity": 1}],
        },
    )
    assert zero.status_code == 422, zero.text
    saved = await ac.post(
        "/api/v1/restaurant/recipes",
        headers=admin,
        json={
            "product_id": dish["id"],
            "name": "Jollof recipe",
            "cook_time": 25,
            "servings": 4,
            "lines": [{"ingredient_id": rice["id"], "quantity": 1}],
        },
    )
    assert saved.status_code == 200, saved.text
    recipe_id = saved.json()["data"]["id"]
    assert saved.json()["data"]["servings"] == 4
    assert saved.json()["data"]["cook_time"] == 25
    renamed = await ac.patch(
        f"/api/v1/restaurant/recipes/{recipe_id}",
        headers=admin,
        json={"name": "House jollof"},
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["data"]["name"] == "House jollof"
    assert renamed.json()["data"]["servings"] == 4
    assert renamed.json()["data"]["cook_time"] == 25
    listed = await ac.get("/api/v1/restaurant/recipes", headers=admin)
    recipe = next(row for row in listed.json()["data"] if row["id"] == recipe_id)
    assert recipe["lines"][0]["quantity"] == 1
    assert recipe["station"] == "kitchen"
    await db_session.refresh(tenant)
    assert tenant.document_numbering["pos_sale"]["prefix"] == "POS"
    assert tenant.document_numbering["restaurant_cook_times"][recipe_id] == 25
    assert tenant.document_numbering["restaurant_recipe_servings"][recipe_id] == 4
    cleared = await ac.patch(
        f"/api/v1/restaurant/recipes/{recipe_id}",
        headers=admin,
        json={"servings": None},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["data"]["servings"] is None
    assert cleared.json()["data"]["cook_time"] == 25
    assert cleared.json()["data"]["name"] == "House jollof"
    kept = await ac.get("/api/v1/restaurant/recipes", headers=admin)
    kept_recipe = next(row for row in kept.json()["data"] if row["id"] == recipe_id)
    assert kept_recipe["lines"][0]["quantity"] == 1
    await db_session.refresh(tenant)
    assert "restaurant_recipe_servings" not in (tenant.document_numbering or {})
    assert tenant.document_numbering["restaurant_cook_times"][recipe_id] == 25
    assert tenant.document_numbering["pos_sale"]["prefix"] == "POS"
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    denied = await ac.patch(
        f"/api/v1/restaurant/recipes/{recipe_id}",
        headers=admin,
        json={"servings": 2},
    )
    assert denied.status_code == 403, denied.text


async def test_restaurant_bill_tax_journal_and_report(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    tenant = seed["t1"]
    too_high = await ac.put("/api/v1/restaurant/service-charge", headers=admin, json={"percent": 31})
    assert too_high.status_code == 422, too_high.text
    web = await ac.put(
        "/api/v1/restaurant/service-charge",
        headers=admin,
        json={"percent": "http://example.com"},
    )
    assert web.status_code == 422, web.text
    saved = await ac.put("/api/v1/restaurant/service-charge", headers=admin, json={"percent": 10})
    assert saved.status_code == 200, saved.text
    assert saved.json()["data"]["percent"] == 10
    db_session.add(
        m.TaxRate(
            tenant_id=tenant.id,
            name="VAT",
            rate=10,
            tax_type="vat",
            pricing_mode="exclusive",
            is_default=True,
            is_active=True,
        )
    )
    await db_session.commit()
    rice = await _product(ac, admin, name="Rice", selling_price=1, stock_qty=5)
    dish = await _product(ac, admin, name="House plate", selling_price=100, prep_station="kitchen")
    recipe = await ac.post(
        "/api/v1/restaurant/recipes",
        headers=admin,
        json={
            "product_id": dish["id"],
            "name": "House plate",
            "lines": [{"ingredient_id": rice["id"], "quantity": 1}],
        },
    )
    assert recipe.status_code == 200, recipe.text
    opened = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "dine_in",
            "payment_method": "cash",
            "lines": [{"product_id": dish["id"], "quantity": 1}],
        },
    )
    assert opened.status_code == 200, opened.text
    order_id = opened.json()["data"]["id"]
    listed = await ac.get("/api/v1/restaurant/orders", headers=admin)
    bill = next(row for row in listed.json()["data"] if row["id"] == order_id)
    assert bill["subtotal"] == 100
    assert bill["service_amount"] == 10
    assert bill["tax_amount"] == 11
    assert bill["total_amount"] == 121
    done = await ac.post(f"/api/v1/restaurant/orders/{order_id}/complete", headers=admin)
    assert done.status_code == 200, done.text
    stock = await ac.get(f"/api/v1/products/{rice['id']}", headers=admin)
    assert stock.status_code == 200, stock.text
    assert stock.json()["data"]["stock_qty"] == 4
    db_session.expire_all()
    stored = (
        await db_session.execute(select(m.RestaurantOrder).where(m.RestaurantOrder.id == order_id))
    ).scalar_one()
    journal = (
        await db_session.execute(
            select(m.Account.code, m.JournalEntryLine.debit, m.JournalEntryLine.credit)
            .join(m.Account, m.Account.id == m.JournalEntryLine.account_id)
            .where(m.JournalEntryLine.journal_entry_id == stored.journal_entry_id)
        )
    ).all()
    debits = round(sum(float(row.debit or 0) for row in journal), 2)
    credits = round(sum(float(row.credit or 0) for row in journal), 2)
    assert debits == credits == 121
    by_code = {row.code: row for row in journal}
    assert float(by_code["1000"].debit) == 121
    assert float(by_code["4000"].credit) == 110
    assert float(by_code["2100"].credit) == 11
    summary = await ac.get("/api/v1/restaurant/summary", headers=admin)
    assert summary.status_code == 200, summary.text
    assert summary.json()["data"]["sales_today"] == 121
    transactions = await ac.get("/api/v1/reports/sales/transactions", headers=admin)
    assert transactions.status_code == 200, transactions.text
    table_bill = next(row for row in transactions.json()["data"]["rows"] if row["number"] == stored.order_number)
    assert table_bill["source"] == "table_bill"
    assert table_bill["total"] == 121
    products = await ac.get("/api/v1/reports/sales/products", headers=admin)
    assert products.status_code == 200, products.text
    menu = next(row for row in products.json()["data"]["products"] if row["name"] == "House plate")
    assert menu["revenue"] == 100
    assert menu["quantity"] == 1
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    hotel_sales = await ac.get("/api/v1/reports/sales/transactions", headers=admin)
    assert hotel_sales.status_code == 200, hotel_sales.text
    assert all(row["number"] != stored.order_number for row in hotel_sales.json()["data"]["rows"])
    hotel_products = await ac.get("/api/v1/reports/sales/products", headers=admin)
    assert all(row["name"] != "House plate" or row["revenue"] == 0 for row in hotel_products.json()["data"]["products"])
    hotel_charge = await ac.put("/api/v1/restaurant/service-charge", headers=admin, json={"percent": 10})
    assert hotel_charge.status_code == 403, hotel_charge.text
    await set_tenant_industry(db_session, seed["t1"], "retail")
    retail_sales = await ac.get("/api/v1/reports/sales/transactions", headers=admin)
    assert retail_sales.status_code == 200, retail_sales.text
    assert all(row["number"] != stored.order_number for row in retail_sales.json()["data"]["rows"])


async def test_restaurant_home_includes_till_receipts(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    tenant_id = seed["t1"].id
    yesterday = datetime.utcnow() - timedelta(days=2)
    db_session.add_all(
        [
            m.Transaction(
                tenant_id=tenant_id,
                tx_type="pos_sale",
                reference="TILL-TODAY",
                subtotal=30,
                tax=0,
                total=30,
                status="completed",
                payload={"payment_method": "cash"},
            ),
            m.Transaction(
                tenant_id=tenant_id,
                tx_type="pos_sale",
                reference="TILL-DRAFT",
                subtotal=99,
                tax=0,
                total=99,
                status="draft",
                payload={"payment_method": "cash"},
            ),
            m.Transaction(
                tenant_id=tenant_id,
                tx_type="pos_sale",
                reference="TILL-VOID",
                subtotal=40,
                tax=0,
                total=40,
                status="void",
                payload={"payment_method": "card"},
            ),
            m.Transaction(
                tenant_id=tenant_id,
                tx_type="pos_sale",
                reference="TILL-OLD",
                subtotal=15,
                tax=0,
                total=15,
                status="completed",
                created_at=yesterday,
                payload={"payment_method": "cash"},
            ),
        ]
    )
    await db_session.commit()
    summary = await ac.get("/api/v1/restaurant/summary", headers=admin)
    assert summary.status_code == 200, summary.text
    body = summary.json()["data"]
    assert body["table_sales_today"] == 0
    assert body["till_sales_today"] == 30
    assert body["till_receipts"] == 1
    assert body["sales_today"] == 30
    reports = await ac.get("/api/v1/restaurant/reports", headers=admin)
    assert reports.status_code == 200, reports.text
    modes = {row["service_mode"]: row for row in reports.json()["data"]["by_service_mode"]}
    assert modes["restaurant_till"]["sales"] == 30
    assert modes["restaurant_till"]["orders"] == 1
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    hotel = await ac.get("/api/v1/restaurant/summary", headers=admin)
    assert hotel.status_code == 403, hotel.text
    await set_tenant_industry(db_session, seed["t1"], "retail")
    retail = await ac.get("/api/v1/restaurant/summary", headers=admin)
    assert retail.status_code == 403, retail.text


async def test_restaurant_till_uses_recipe_ingredients(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    rice = await _product(ac, admin, name="Till rice", selling_price=1, stock_qty=5)
    dish = await _product(ac, admin, name="Till plate", selling_price=20, stock_qty=3, prep_station="kitchen")
    bottle = await _product(ac, admin, name="Till bottle", selling_price=4, stock_qty=2)
    recipe = await ac.post(
        "/api/v1/restaurant/recipes",
        headers=admin,
        json={
            "product_id": dish["id"],
            "name": "Till plate",
            "lines": [{"ingredient_id": rice["id"], "quantity": 1}],
        },
    )
    assert recipe.status_code == 200, recipe.text
    opened = await ac.post("/api/v1/pos/sessions/open", headers=admin, json={"opening_cash": 0})
    assert opened.status_code == 200, opened.text
    session_id = opened.json()["data"].get("session_id") or opened.json()["data"]["id"]
    sale = await ac.post(
        "/api/v1/pos/sales",
        headers=admin,
        json={
            "session_id": session_id,
            "payment_method": "cash",
            "items": [{"product_id": dish["id"], "quantity": 1}],
        },
    )
    assert sale.status_code == 200, sale.text
    sale_id = sale.json()["data"]["id"]
    rice_after = await ac.get(f"/api/v1/products/{rice['id']}", headers=admin)
    dish_after = await ac.get(f"/api/v1/products/{dish['id']}", headers=admin)
    assert rice_after.json()["data"]["stock_qty"] == 4
    assert dish_after.json()["data"]["stock_qty"] == 3
    plain = await ac.post(
        "/api/v1/pos/sales",
        headers=admin,
        json={
            "session_id": session_id,
            "payment_method": "cash",
            "items": [{"product_id": bottle["id"], "quantity": 1}],
        },
    )
    assert plain.status_code == 200, plain.text
    bottle_after = await ac.get(f"/api/v1/products/{bottle['id']}", headers=admin)
    assert bottle_after.json()["data"]["stock_qty"] == 1
    restored = await ac.post(
        f"/api/v1/pos/sales/{sale_id}/returns",
        headers=admin,
        json={"items": [{"product_id": dish["id"], "quantity": 1}], "reason": "other"},
    )
    assert restored.status_code == 200, restored.text
    rice_back = await ac.get(f"/api/v1/products/{rice['id']}", headers=admin)
    dish_back = await ac.get(f"/api/v1/products/{dish['id']}", headers=admin)
    assert rice_back.json()["data"]["stock_qty"] == 5
    assert dish_back.json()["data"]["stock_qty"] == 3
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    hotel_sale = await ac.post(
        "/api/v1/pos/sales",
        headers=admin,
        json={
            "session_id": session_id,
            "payment_method": "cash",
            "items": [{"product_id": dish["id"], "quantity": 1}],
        },
    )
    assert hotel_sale.status_code == 200, hotel_sale.text
    hotel_dish = await ac.get(f"/api/v1/products/{dish['id']}", headers=admin)
    hotel_rice = await ac.get(f"/api/v1/products/{rice['id']}", headers=admin)
    assert hotel_dish.json()["data"]["stock_qty"] == 2
    assert hotel_rice.json()["data"]["stock_qty"] == 5


async def test_restaurant_kitchen_can_start_a_line(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    dish = await _product(ac, admin, name="Start plate", selling_price=10, prep_station="kitchen")
    opened = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "lines": [{"product_id": dish["id"], "quantity": 1}],
        },
    )
    assert opened.status_code == 200, opened.text
    order_id = opened.json()["data"]["id"]
    listed = await ac.get("/api/v1/restaurant/orders", headers=admin)
    line_id = next(row for row in listed.json()["data"] if row["id"] == order_id)["items"][0]["id"]
    early = await ac.post(f"/api/v1/restaurant/kitchen/lines/{line_id}/start", headers=admin, json={})
    assert early.status_code == 409, early.text
    sent = await ac.post(f"/api/v1/restaurant/orders/{order_id}/send", headers=admin)
    assert sent.status_code == 200, sent.text
    started = await ac.post(f"/api/v1/restaurant/kitchen/lines/{line_id}/start", headers=admin, json={})
    assert started.status_code == 200, started.text
    ticket = next(row for row in started.json()["data"] if row["order_id"] == order_id)
    assert ticket["items"][0]["prep_status"] == "preparing"
    assert ticket["status"] == "preparing"
    orders = await ac.get("/api/v1/restaurant/orders", headers=admin)
    order = next(row for row in orders.json()["data"] if row["id"] == order_id)
    assert order["status"] == "preparing"
    assert order["items"][0]["prep_status"] == "preparing"
    again = await ac.post(f"/api/v1/restaurant/kitchen/lines/{line_id}/start", headers=admin, json={})
    assert again.status_code == 200, again.text
    assert next(row for row in again.json()["data"] if row["order_id"] == order_id)["items"][0]["prep_status"] == "preparing"
    ready = await ac.post(f"/api/v1/restaurant/kitchen/lines/{line_id}/ready", headers=admin, json={})
    assert ready.status_code == 200, ready.text
    assert next(row for row in ready.json()["data"] if row["order_id"] == order_id)["items"][0]["prep_status"] == "ready"
    after = await ac.post(f"/api/v1/restaurant/kitchen/lines/{line_id}/start", headers=admin, json={})
    assert after.status_code == 409, after.text
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    hotel = await ac.post(f"/api/v1/restaurant/kitchen/lines/{line_id}/start", headers=admin, json={})
    assert hotel.status_code == 403, hotel.text


async def test_restaurant_dashboard_includes_table_bills(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    dish = await _product(ac, admin, name="Dash plate", selling_price=18, prep_station="kitchen", stock_qty=5)
    opened = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "customer_name": "Ama Dash",
            "lines": [{"product_id": dish["id"], "quantity": 1}],
        },
    )
    assert opened.status_code == 200, opened.text
    order_id = opened.json()["data"]["id"]
    done = await ac.post(f"/api/v1/restaurant/orders/{order_id}/complete", headers=admin)
    assert done.status_code == 200, done.text
    total = done.json()["data"]["total_amount"]
    number = done.json()["data"]["order_number"]
    dash = await ac.get("/api/v1/dashboard", headers=admin)
    assert dash.status_code == 200, dash.text
    body = dash.json()["data"]
    assert body["comparisons"]["sales_today"] >= total
    recent = next(row for row in body["recent_sales"] if row["reference"] == number)
    assert recent["type"] == "table_bill"
    assert recent["total"] == total
    assert recent["customer"] == "Ama Dash"
    today = datetime.utcnow().date().isoformat()
    day = next(row for row in body["daily_sales"] if row["date"] == today)
    assert day["sales"] >= total
    month = next(row for row in body["monthly_sales"] if row["year"] == datetime.utcnow().year and row["month"] == datetime.utcnow().month)
    assert month["total"] >= total
    ranked = next(row for row in body["top_products_by_revenue"] if row["name"] == "Dash plate")
    assert ranked["revenue"] == 18
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    hotel = await ac.get("/api/v1/dashboard", headers=admin)
    assert hotel.status_code == 200, hotel.text
    hotel_body = hotel.json()["data"]
    assert hotel_body["comparisons"]["sales_today"] == body["comparisons"]["sales_today"] - total
    assert all(row["reference"] != number for row in hotel_body["recent_sales"])
    await set_tenant_industry(db_session, seed["t1"], "retail")
    retail = await ac.get("/api/v1/dashboard", headers=admin)
    assert retail.status_code == 200, retail.text
    assert retail.json()["data"]["comparisons"]["sales_today"] == hotel_body["comparisons"]["sales_today"]


async def test_restaurant_waste_posts_inventory_journal(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    lime = await _product(ac, admin, name="Lime peel", selling_price=2, cost_price=4, stock_qty=5)
    dumped = await ac.post(
        "/api/v1/restaurant/waste",
        headers=admin,
        json={"product_id": lime["id"], "quantity": 2, "reason": "spoilage", "notes": "Soft fruit"},
    )
    assert dumped.status_code == 200, dumped.text
    body = dumped.json()["data"]
    assert body["stock_qty"] == 3
    assert body["cost_amount"] == 8
    assert body["journal_entry_id"]
    journal = (
        await db_session.execute(
            select(m.Account.code, m.JournalEntryLine.debit, m.JournalEntryLine.credit)
            .join(m.Account, m.Account.id == m.JournalEntryLine.account_id)
            .where(m.JournalEntryLine.journal_entry_id == body["journal_entry_id"])
        )
    ).all()
    debits = round(sum(float(row.debit or 0) for row in journal), 2)
    credits = round(sum(float(row.credit or 0) for row in journal), 2)
    assert debits == credits == 8
    by_code = {row.code: row for row in journal}
    assert float(by_code["6000"].debit) == 8
    assert float(by_code["1200"].credit) == 8
    listed = await ac.get("/api/v1/restaurant/waste", headers=admin)
    assert listed.status_code == 200, listed.text
    row = next(item for item in listed.json()["data"] if item["notes"] == "Soft fruit")
    assert row["journal_entry_id"] == body["journal_entry_id"]
    free = await _product(ac, admin, name="Ice water", selling_price=1, cost_price=0, stock_qty=4)
    plain = await ac.post(
        "/api/v1/restaurant/waste",
        headers=admin,
        json={"product_id": free["id"], "quantity": 1, "reason": "waste"},
    )
    assert plain.status_code == 200, plain.text
    assert plain.json()["data"]["stock_qty"] == 3
    assert plain.json()["data"]["cost_amount"] == 0
    assert plain.json()["data"]["journal_entry_id"] is None
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    hotel = await ac.post(
        "/api/v1/restaurant/waste",
        headers=admin,
        json={"product_id": lime["id"], "quantity": 1, "reason": "spoilage"},
    )
    assert hotel.status_code == 403, hotel.text
    await set_tenant_industry(db_session, seed["t1"], "retail")
    retail = await ac.post(
        "/api/v1/restaurant/waste",
        headers=admin,
        json={"product_id": lime["id"], "quantity": 1, "reason": "spoilage"},
    )
    assert retail.status_code == 403, retail.text
    stock = await ac.get(f"/api/v1/products/{lime['id']}", headers=admin)
    assert stock.status_code == 200, stock.text
    assert stock.json()["data"]["stock_qty"] == 3


async def _journal_codes(db, entry_id: str) -> dict:
    rows = (
        await db.execute(
            select(m.Account.code, m.JournalEntryLine.debit, m.JournalEntryLine.credit)
            .join(m.Account, m.Account.id == m.JournalEntryLine.account_id)
            .where(m.JournalEntryLine.journal_entry_id == entry_id)
        )
    ).all()
    return {row.code: row for row in rows}


async def test_restaurant_bill_posts_ingredient_cost(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    rice = await _product(ac, admin, name="Cost rice", selling_price=1, cost_price=2, stock_qty=5)
    plate = await _product(
        ac, admin, name="Cost plate", selling_price=20, cost_price=9, stock_qty=3, prep_station="kitchen"
    )
    bottle = await _product(ac, admin, name="Cost bottle", selling_price=4, cost_price=6, stock_qty=2)
    recipe = await ac.post(
        "/api/v1/restaurant/recipes",
        headers=admin,
        json={"product_id": plate["id"], "name": "Cost plate", "lines": [{"ingredient_id": rice["id"], "quantity": 1}]},
    )
    assert recipe.status_code == 200, recipe.text
    opened = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={"service_mode": "takeaway", "payment_method": "cash", "lines": [{"product_id": plate["id"], "quantity": 1}]},
    )
    assert opened.status_code == 200, opened.text
    order_id = opened.json()["data"]["id"]
    done = await ac.post(f"/api/v1/restaurant/orders/{order_id}/complete", headers=admin)
    assert done.status_code == 200, done.text
    rice_after = await ac.get(f"/api/v1/products/{rice['id']}", headers=admin)
    assert rice_after.json()["data"]["stock_qty"] == 4
    sale_entry = (
        await db_session.execute(
            select(m.JournalEntry).where(
                m.JournalEntry.source_id == order_id,
                m.JournalEntry.source_type == "restaurant_order",
                m.JournalEntry.description.startswith("Restaurant sale"),
            )
        )
    ).scalar_one()
    sale_codes = await _journal_codes(db_session, sale_entry.id)
    assert float(sale_codes["1000"].debit) == 20
    assert float(sale_codes["4000"].credit) == 20
    assert float(sale_codes["5000"].debit) == 2
    assert float(sale_codes["1200"].credit) == 2
    refunded = await ac.post(f"/api/v1/restaurant/orders/{order_id}/refund", headers=admin)
    assert refunded.status_code == 200, refunded.text
    rice_back = await ac.get(f"/api/v1/products/{rice['id']}", headers=admin)
    assert rice_back.json()["data"]["stock_qty"] == 5
    refund_entry = (
        await db_session.execute(
            select(m.JournalEntry).where(
                m.JournalEntry.source_id == order_id,
                m.JournalEntry.description.startswith("Restaurant refund"),
            )
        )
    ).scalar_one()
    refund_codes = await _journal_codes(db_session, refund_entry.id)
    assert float(refund_codes["1200"].debit) == 2
    assert float(refund_codes["5000"].credit) == 2
    plain = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={"service_mode": "takeaway", "payment_method": "cash", "lines": [{"product_id": bottle["id"], "quantity": 1}]},
    )
    assert plain.status_code == 200, plain.text
    plain_id = plain.json()["data"]["id"]
    plain_done = await ac.post(f"/api/v1/restaurant/orders/{plain_id}/complete", headers=admin)
    assert plain_done.status_code == 200, plain_done.text
    bottle_after = await ac.get(f"/api/v1/products/{bottle['id']}", headers=admin)
    assert bottle_after.json()["data"]["stock_qty"] == 1
    plain_entry = (
        await db_session.execute(
            select(m.JournalEntry).where(
                m.JournalEntry.source_id == plain_id,
                m.JournalEntry.description.startswith("Restaurant sale"),
            )
        )
    ).scalar_one()
    plain_codes = await _journal_codes(db_session, plain_entry.id)
    assert float(plain_codes["5000"].debit) == 6
    assert float(plain_codes["1200"].credit) == 6
    bottle_back = await ac.post(f"/api/v1/restaurant/orders/{plain_id}/refund", headers=admin)
    assert bottle_back.status_code == 200, bottle_back.text
    bottle_restored = await ac.get(f"/api/v1/products/{bottle['id']}", headers=admin)
    assert bottle_restored.json()["data"]["stock_qty"] == 2
    bottle_refund = (
        await db_session.execute(
            select(m.JournalEntry).where(
                m.JournalEntry.source_id == plain_id,
                m.JournalEntry.description.startswith("Restaurant refund"),
            )
        )
    ).scalar_one()
    bottle_refund_codes = await _journal_codes(db_session, bottle_refund.id)
    assert float(bottle_refund_codes["1200"].debit) == 6
    assert float(bottle_refund_codes["5000"].credit) == 6
    shift = await ac.post("/api/v1/pos/sessions/open", headers=admin, json={"opening_cash": 0})
    assert shift.status_code == 200, shift.text
    session_id = shift.json()["data"].get("session_id") or shift.json()["data"]["id"]
    sale = await ac.post(
        "/api/v1/pos/sales",
        headers=admin,
        json={"session_id": session_id, "payment_method": "cash", "items": [{"product_id": plate["id"], "quantity": 1}]},
    )
    assert sale.status_code == 200, sale.text
    sale_id = sale.json()["data"]["id"]
    till_rice = await ac.get(f"/api/v1/products/{rice['id']}", headers=admin)
    till_plate = await ac.get(f"/api/v1/products/{plate['id']}", headers=admin)
    assert till_rice.json()["data"]["stock_qty"] == 4
    assert till_plate.json()["data"]["stock_qty"] == 3
    till_entry = (
        await db_session.execute(
            select(m.JournalEntry).where(
                m.JournalEntry.source_id == sale_id,
                m.JournalEntry.source_type == "pos_sale",
            )
        )
    ).scalar_one()
    till_codes = await _journal_codes(db_session, till_entry.id)
    assert float(till_codes["5000"].debit) == 2
    assert float(till_codes["1200"].credit) == 2
    restored = await ac.post(
        f"/api/v1/pos/sales/{sale_id}/returns",
        headers=admin,
        json={"items": [{"product_id": plate["id"], "quantity": 1}], "reason": "other"},
    )
    assert restored.status_code == 200, restored.text
    rice_restored = await ac.get(f"/api/v1/products/{rice['id']}", headers=admin)
    assert rice_restored.json()["data"]["stock_qty"] == 5
    return_entry = (
        await db_session.execute(
            select(m.JournalEntry).where(
                m.JournalEntry.source_id == restored.json()["data"]["id"],
                m.JournalEntry.source_type == "sales_return",
            )
        )
    ).scalar_one()
    return_codes = await _journal_codes(db_session, return_entry.id)
    assert float(return_codes["1200"].debit) == 2
    assert float(return_codes["5000"].credit) == 2
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    hotel_sale = await ac.post(
        "/api/v1/pos/sales",
        headers=admin,
        json={"session_id": session_id, "payment_method": "cash", "items": [{"product_id": plate["id"], "quantity": 1}]},
    )
    assert hotel_sale.status_code == 200, hotel_sale.text
    hotel_plate = await ac.get(f"/api/v1/products/{plate['id']}", headers=admin)
    hotel_rice = await ac.get(f"/api/v1/products/{rice['id']}", headers=admin)
    assert hotel_plate.json()["data"]["stock_qty"] == 2
    assert hotel_rice.json()["data"]["stock_qty"] == 5
    hotel_entry = (
        await db_session.execute(
            select(m.JournalEntry).where(
                m.JournalEntry.source_id == hotel_sale.json()["data"]["id"],
                m.JournalEntry.source_type == "pos_sale",
            )
        )
    ).scalar_one()
    hotel_codes = await _journal_codes(db_session, hotel_entry.id)
    assert float(hotel_codes["5000"].debit) == 9
    assert float(hotel_codes["1200"].credit) == 9


async def test_restaurant_bill_refuses_credit(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    plate = await _product(ac, admin, name="Credit plate", selling_price=12, stock_qty=4)
    refused = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "credit",
            "lines": [{"product_id": plate["id"], "quantity": 1}],
        },
    )
    assert refused.status_code == 422, refused.text
    assert "cannot be put on credit" in refused.text
    opened = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "lines": [{"product_id": plate["id"], "quantity": 1}],
        },
    )
    assert opened.status_code == 200, opened.text
    order_id = opened.json()["data"]["id"]
    patched = await ac.patch(
        f"/api/v1/restaurant/orders/{order_id}",
        headers=admin,
        json={"payment_method": "credit"},
    )
    assert patched.status_code == 422, patched.text
    stored = (
        await db_session.execute(select(m.RestaurantOrder).where(m.RestaurantOrder.id == order_id))
    ).scalar_one()
    stored.payment_method = "credit"
    await db_session.commit()
    done = await ac.post(f"/api/v1/restaurant/orders/{order_id}/complete", headers=admin)
    assert done.status_code == 409, done.text
    assert "cannot be put on credit" in done.text
    stock = await ac.get(f"/api/v1/products/{plate['id']}", headers=admin)
    assert stock.json()["data"]["stock_qty"] == 4
    journals = (
        await db_session.execute(
            select(m.JournalEntry).where(m.JournalEntry.source_id == order_id)
        )
    ).scalars().all()
    assert journals == []


def _today_profit(body: dict) -> float:
    today = datetime.utcnow().date().isoformat()
    day = next(row for row in body["daily_sales"] if row["date"] == today)
    return float(day["profit"])


async def test_restaurant_dashboard_profit_uses_ingredient_cost(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    rice = await _product(ac, admin, name="Margin rice", selling_price=1, cost_price=2, stock_qty=5)
    plate = await _product(
        ac, admin, name="Margin plate", selling_price=20, cost_price=9, stock_qty=3, prep_station="kitchen"
    )
    bottle = await _product(ac, admin, name="Margin bottle", selling_price=4, cost_price=6, stock_qty=2)
    recipe = await ac.post(
        "/api/v1/restaurant/recipes",
        headers=admin,
        json={"product_id": plate["id"], "name": "Margin plate", "lines": [{"ingredient_id": rice["id"], "quantity": 1}]},
    )
    assert recipe.status_code == 200, recipe.text
    before = await ac.get("/api/v1/dashboard", headers=admin)
    assert before.status_code == 200, before.text
    start = _today_profit(before.json()["data"])
    opened = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={"service_mode": "takeaway", "payment_method": "cash", "lines": [{"product_id": plate["id"], "quantity": 1}]},
    )
    assert opened.status_code == 200, opened.text
    done = await ac.post(f"/api/v1/restaurant/orders/{opened.json()['data']['id']}/complete", headers=admin)
    assert done.status_code == 200, done.text
    after_plate = await ac.get("/api/v1/dashboard", headers=admin)
    assert _today_profit(after_plate.json()["data"]) == pytest.approx(start + 18)
    ranked = next(row for row in after_plate.json()["data"]["top_products_by_revenue"] if row["name"] == "Margin plate")
    assert ranked["revenue"] == 20
    plain = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={"service_mode": "takeaway", "payment_method": "cash", "lines": [{"product_id": bottle["id"], "quantity": 1}]},
    )
    assert plain.status_code == 200, plain.text
    plain_done = await ac.post(f"/api/v1/restaurant/orders/{plain.json()['data']['id']}/complete", headers=admin)
    assert plain_done.status_code == 200, plain_done.text
    after_bottle = await ac.get("/api/v1/dashboard", headers=admin)
    assert _today_profit(after_bottle.json()["data"]) == pytest.approx(start + 16)
    shift = await ac.post("/api/v1/pos/sessions/open", headers=admin, json={"opening_cash": 0})
    assert shift.status_code == 200, shift.text
    session_id = shift.json()["data"].get("session_id") or shift.json()["data"]["id"]
    sale = await ac.post(
        "/api/v1/pos/sales",
        headers=admin,
        json={"session_id": session_id, "payment_method": "cash", "items": [{"product_id": plate["id"], "quantity": 1}]},
    )
    assert sale.status_code == 200, sale.text
    after_till = await ac.get("/api/v1/dashboard", headers=admin)
    assert _today_profit(after_till.json()["data"]) == pytest.approx(start + 34)
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    hotel_before = await ac.get("/api/v1/dashboard", headers=admin)
    hotel_start = _today_profit(hotel_before.json()["data"])
    hotel_sale = await ac.post(
        "/api/v1/pos/sales",
        headers=admin,
        json={"session_id": session_id, "payment_method": "cash", "items": [{"product_id": plate["id"], "quantity": 1}]},
    )
    assert hotel_sale.status_code == 200, hotel_sale.text
    hotel_after = await ac.get("/api/v1/dashboard", headers=admin)
    assert _today_profit(hotel_after.json()["data"]) == pytest.approx(hotel_start + 11)


def _named_product(body: dict, name: str) -> dict:
    return next(row for row in body["products"] if row["name"] == name)


async def test_restaurant_sales_report_uses_ingredient_cost(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    rice = await _product(ac, admin, name="Report rice", selling_price=1, cost_price=2, stock_qty=5)
    plate = await _product(
        ac, admin, name="Report plate", selling_price=20, cost_price=9, stock_qty=3, prep_station="kitchen"
    )
    bottle = await _product(ac, admin, name="Report bottle", selling_price=4, cost_price=6, stock_qty=2)
    held = await _product(
        ac, admin, name="Report hotel plate", selling_price=20, cost_price=9, stock_qty=2, prep_station="kitchen"
    )
    recipe = await ac.post(
        "/api/v1/restaurant/recipes",
        headers=admin,
        json={
            "product_id": plate["id"],
            "name": "Report plate",
            "lines": [{"ingredient_id": rice["id"], "quantity": 1}],
        },
    )
    assert recipe.status_code == 200, recipe.text
    held_recipe = await ac.post(
        "/api/v1/restaurant/recipes",
        headers=admin,
        json={
            "product_id": held["id"],
            "name": "Report hotel plate",
            "lines": [{"ingredient_id": rice["id"], "quantity": 1}],
        },
    )
    assert held_recipe.status_code == 200, held_recipe.text
    opened = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={"service_mode": "takeaway", "payment_method": "cash", "lines": [{"product_id": plate["id"], "quantity": 1}]},
    )
    assert opened.status_code == 200, opened.text
    done = await ac.post(f"/api/v1/restaurant/orders/{opened.json()['data']['id']}/complete", headers=admin)
    assert done.status_code == 200, done.text
    products = await ac.get("/api/v1/reports/sales/products", headers=admin)
    assert products.status_code == 200, products.text
    menu = _named_product(products.json()["data"], "Report plate")
    assert menu["revenue"] == 20
    assert menu["cost"] == 2
    assert menu["profit"] == 18
    plain = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={"service_mode": "takeaway", "payment_method": "cash", "lines": [{"product_id": bottle["id"], "quantity": 1}]},
    )
    assert plain.status_code == 200, plain.text
    plain_done = await ac.post(f"/api/v1/restaurant/orders/{plain.json()['data']['id']}/complete", headers=admin)
    assert plain_done.status_code == 200, plain_done.text
    lines = await ac.get("/api/v1/reports/sales/lines", headers=admin)
    assert lines.status_code == 200, lines.text
    body = lines.json()["data"]
    plate_line = next(row for row in body["lines"] if row["product"] == "Report plate")
    bottle_line = next(row for row in body["lines"] if row["product"] == "Report bottle")
    assert plate_line["cost"] == 2
    assert plate_line["profit"] == 18
    assert bottle_line["cost"] == 6
    assert bottle_line["profit"] == -2
    shift = await ac.post("/api/v1/pos/sessions/open", headers=admin, json={"opening_cash": 0})
    assert shift.status_code == 200, shift.text
    session_id = shift.json()["data"].get("session_id") or shift.json()["data"]["id"]
    sale = await ac.post(
        "/api/v1/pos/sales",
        headers=admin,
        json={"session_id": session_id, "payment_method": "cash", "items": [{"product_id": plate["id"], "quantity": 1}]},
    )
    assert sale.status_code == 200, sale.text
    after_till = await ac.get("/api/v1/reports/sales/products", headers=admin)
    till_menu = _named_product(after_till.json()["data"], "Report plate")
    assert till_menu["revenue"] == 40
    assert till_menu["cost"] == 4
    assert till_menu["profit"] == 36
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    hotel_sale = await ac.post(
        "/api/v1/pos/sales",
        headers=admin,
        json={"session_id": session_id, "payment_method": "cash", "items": [{"product_id": held["id"], "quantity": 1}]},
    )
    assert hotel_sale.status_code == 200, hotel_sale.text
    hotel_products = await ac.get("/api/v1/reports/sales/products", headers=admin)
    hotel_plate = _named_product(hotel_products.json()["data"], "Report hotel plate")
    assert hotel_plate["revenue"] == 20
    assert hotel_plate["cost"] == 9
    assert hotel_plate["profit"] == 11


async def test_restaurant_bill_refund_is_listed_on_returns(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    plate = await _product(ac, admin, name="Refund plate", selling_price=20, stock_qty=2)
    opened = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "customer_name": "Ama Refund",
            "lines": [{"product_id": plate["id"], "quantity": 1}],
        },
    )
    assert opened.status_code == 200, opened.text
    order_id = opened.json()["data"]["id"]
    done = await ac.post(f"/api/v1/restaurant/orders/{order_id}/complete", headers=admin)
    assert done.status_code == 200, done.text
    number = done.json()["data"]["order_number"]
    refunded = await ac.post(f"/api/v1/restaurant/orders/{order_id}/refund", headers=admin)
    assert refunded.status_code == 200, refunded.text
    listed = await ac.get("/api/v1/reports/sales/returns", headers=admin)
    assert listed.status_code == 200, listed.text
    body = listed.json()["data"]
    row = next(item for item in body["returns"] if item["return_number"] == number)
    assert row["status"] == "refunded"
    assert row["reason"] == "table_bill"
    assert row["customer_name"] == "Ama Refund"
    assert row["total_amount"] == 20
    assert row["quantity"] == 1
    assert body["posted_amount"] >= 20
    sales = await ac.get("/api/v1/reports/sales/transactions", headers=admin)
    assert all(item["number"] != number for item in sales.json()["data"]["rows"])
    products = await ac.get("/api/v1/reports/sales/products", headers=admin)
    assert all(item["name"] != "Refund plate" or item["revenue"] == 0 for item in products.json()["data"]["products"])
    hidden = await ac.get("/api/v1/reports/sales/returns?status=draft", headers=admin)
    assert hidden.status_code == 200, hidden.text
    assert all(item["return_number"] != number for item in hidden.json()["data"]["returns"])
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    hotel = await ac.get("/api/v1/reports/sales/returns", headers=admin)
    assert all(item["return_number"] != number for item in hotel.json()["data"]["returns"])


def _today_sales(body: dict) -> float:
    today = datetime.utcnow().date().isoformat()
    day = next(row for row in body["daily_sales"] if row["date"] == today)
    return float(day["sales"])


async def test_restaurant_till_return_comes_off_sales_today(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    rice = await _product(ac, admin, name="Return till rice", selling_price=1, cost_price=2, stock_qty=5)
    plate = await _product(
        ac, admin, name="Return till plate", selling_price=20, cost_price=9, stock_qty=3, prep_station="kitchen"
    )
    recipe = await ac.post(
        "/api/v1/restaurant/recipes",
        headers=admin,
        json={
            "product_id": plate["id"],
            "name": "Return till plate",
            "lines": [{"ingredient_id": rice["id"], "quantity": 1}],
        },
    )
    assert recipe.status_code == 200, recipe.text
    before_home = await ac.get("/api/v1/restaurant/summary", headers=admin)
    assert before_home.status_code == 200, before_home.text
    home_start = before_home.json()["data"]["sales_today"]
    before = await ac.get("/api/v1/dashboard", headers=admin)
    assert before.status_code == 200, before.text
    sales_start = float(before.json()["data"]["comparisons"]["sales_today"])
    profit_start = _today_profit(before.json()["data"])
    day_start = _today_sales(before.json()["data"])
    shift = await ac.post("/api/v1/pos/sessions/open", headers=admin, json={"opening_cash": 0})
    assert shift.status_code == 200, shift.text
    session_id = shift.json()["data"].get("session_id") or shift.json()["data"]["id"]
    sale = await ac.post(
        "/api/v1/pos/sales",
        headers=admin,
        json={"session_id": session_id, "payment_method": "cash", "items": [{"product_id": plate["id"], "quantity": 1}]},
    )
    assert sale.status_code == 200, sale.text
    sold = await ac.get("/api/v1/restaurant/summary", headers=admin)
    assert sold.json()["data"]["sales_today"] == pytest.approx(home_start + 20)
    assert sold.json()["data"]["till_sales_today"] == pytest.approx(20)
    assert sold.json()["data"]["till_receipts"] == 1
    sold_dash = await ac.get("/api/v1/dashboard", headers=admin)
    assert float(sold_dash.json()["data"]["comparisons"]["sales_today"]) == pytest.approx(sales_start + 20)
    assert _today_profit(sold_dash.json()["data"]) == pytest.approx(profit_start + 18)
    assert _today_sales(sold_dash.json()["data"]) == pytest.approx(day_start + 20)
    restored = await ac.post(
        f"/api/v1/pos/sales/{sale.json()['data']['id']}/returns",
        headers=admin,
        json={"items": [{"product_id": plate["id"], "quantity": 1}], "reason": "other"},
    )
    assert restored.status_code == 200, restored.text
    home = await ac.get("/api/v1/restaurant/summary", headers=admin)
    assert home.json()["data"]["sales_today"] == pytest.approx(home_start)
    assert home.json()["data"]["till_sales_today"] == pytest.approx(0)
    assert home.json()["data"]["till_receipts"] == 1
    modes = {row["service_mode"]: row for row in (await ac.get("/api/v1/restaurant/reports", headers=admin)).json()["data"]["by_service_mode"]}
    assert modes["restaurant_till"]["orders"] == 1
    assert modes["restaurant_till"]["sales"] == pytest.approx(0)
    after = await ac.get("/api/v1/dashboard", headers=admin)
    assert float(after.json()["data"]["comparisons"]["sales_today"]) == pytest.approx(sales_start)
    assert _today_profit(after.json()["data"]) == pytest.approx(profit_start)
    assert _today_sales(after.json()["data"]) == pytest.approx(day_start)
    ranked = [row for row in after.json()["data"]["top_products_by_revenue"] if row["name"] == "Return till plate"]
    assert not ranked or ranked[0]["revenue"] == 0
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    hotel_home = await ac.get("/api/v1/restaurant/summary", headers=admin)
    assert hotel_home.status_code == 403, hotel_home.text
    hotel = await ac.get("/api/v1/dashboard", headers=admin)
    assert float(hotel.json()["data"]["comparisons"]["sales_today"]) == pytest.approx(sales_start + 20)
    assert _today_profit(hotel.json()["data"]) == pytest.approx(profit_start + 11)


async def test_restaurant_till_return_comes_off_menu_items_sold(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    rice = await _product(ac, admin, name="Sold return rice", selling_price=1, cost_price=2, stock_qty=5)
    plate = await _product(
        ac, admin, name="Sold return plate", selling_price=20, cost_price=9, stock_qty=3, prep_station="kitchen"
    )
    bottle = await _product(ac, admin, name="Sold return bottle", selling_price=4, cost_price=6, stock_qty=2)
    recipe = await ac.post(
        "/api/v1/restaurant/recipes",
        headers=admin,
        json={
            "product_id": plate["id"],
            "name": "Sold return plate",
            "lines": [{"ingredient_id": rice["id"], "quantity": 1}],
        },
    )
    assert recipe.status_code == 200, recipe.text
    shift = await ac.post("/api/v1/pos/sessions/open", headers=admin, json={"opening_cash": 0})
    assert shift.status_code == 200, shift.text
    session_id = shift.json()["data"].get("session_id") or shift.json()["data"]["id"]
    sale = await ac.post(
        "/api/v1/pos/sales",
        headers=admin,
        json={
            "session_id": session_id,
            "payment_method": "cash",
            "items": [
                {"product_id": plate["id"], "quantity": 1},
                {"product_id": bottle["id"], "quantity": 1},
            ],
        },
    )
    assert sale.status_code == 200, sale.text
    sold = await ac.get("/api/v1/reports/sales/products", headers=admin)
    assert sold.status_code == 200, sold.text
    menu = _named_product(sold.json()["data"], "Sold return plate")
    assert menu["revenue"] == 20
    assert menu["cost"] == 2
    assert menu["profit"] == 18
    restored = await ac.post(
        f"/api/v1/pos/sales/{sale.json()['data']['id']}/returns",
        headers=admin,
        json={"items": [{"product_id": plate["id"], "quantity": 1}], "reason": "other"},
    )
    assert restored.status_code == 200, restored.text
    products = await ac.get("/api/v1/reports/sales/products", headers=admin)
    assert all(row["name"] != "Sold return plate" for row in products.json()["data"]["products"])
    kept = _named_product(products.json()["data"], "Sold return bottle")
    assert kept["revenue"] == 4
    assert kept["cost"] == 6
    assert kept["profit"] == -2
    lines = await ac.get("/api/v1/reports/sales/lines", headers=admin)
    assert lines.status_code == 200, lines.text
    assert all(row["product"] != "Sold return plate" for row in lines.json()["data"]["lines"])
    bottle_line = next(row for row in lines.json()["data"]["lines"] if row["product"] == "Sold return bottle")
    assert bottle_line["sales_total"] == 4
    assert bottle_line["cost"] == 6
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    hotel = await ac.get("/api/v1/reports/sales/products", headers=admin)
    hotel_plate = _named_product(hotel.json()["data"], "Sold return plate")
    assert hotel_plate["revenue"] == 20
    assert hotel_plate["cost"] == 9
    assert hotel_plate["profit"] == 11


async def test_restaurant_till_return_comes_off_today_sales(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    rice = await _product(ac, admin, name="Day return rice", selling_price=1, cost_price=2, stock_qty=5)
    plate = await _product(
        ac, admin, name="Day return plate", selling_price=20, cost_price=9, stock_qty=3, prep_station="kitchen"
    )
    bottle = await _product(ac, admin, name="Day return bottle", selling_price=4, cost_price=6, stock_qty=2)
    recipe = await ac.post(
        "/api/v1/restaurant/recipes",
        headers=admin,
        json={
            "product_id": plate["id"],
            "name": "Day return plate",
            "lines": [{"ingredient_id": rice["id"], "quantity": 1}],
        },
    )
    assert recipe.status_code == 200, recipe.text
    shift = await ac.post("/api/v1/pos/sessions/open", headers=admin, json={"opening_cash": 0})
    assert shift.status_code == 200, shift.text
    session_id = shift.json()["data"].get("session_id") or shift.json()["data"]["id"]
    sale = await ac.post(
        "/api/v1/pos/sales",
        headers=admin,
        json={
            "session_id": session_id,
            "payment_method": "cash",
            "items": [
                {"product_id": plate["id"], "quantity": 1},
                {"product_id": bottle["id"], "quantity": 1},
            ],
        },
    )
    assert sale.status_code == 200, sale.text
    sold = await ac.get("/api/v1/reports/sales/daily", headers=admin)
    assert sold.status_code == 200, sold.text
    assert sold.json()["data"]["total_revenue"] == 24
    assert sold.json()["data"]["pos_revenue"] == 24
    assert sold.json()["data"]["pos_count"] == 1
    restored = await ac.post(
        f"/api/v1/pos/sales/{sale.json()['data']['id']}/returns",
        headers=admin,
        json={"items": [{"product_id": plate["id"], "quantity": 1}], "reason": "other"},
    )
    assert restored.status_code == 200, restored.text
    daily = await ac.get("/api/v1/reports/sales/daily", headers=admin)
    body = daily.json()["data"]
    assert body["total_revenue"] == 4
    assert body["pos_revenue"] == 4
    assert body["net_sales"] == 4
    assert body["pos_count"] == 1
    assert "comes off this total" in body["returns_note"]
    monthly = await ac.get("/api/v1/reports/sales/monthly", headers=admin)
    assert monthly.status_code == 200, monthly.text
    assert monthly.json()["data"]["total_revenue"] == 4
    today = datetime.utcnow().date().isoformat()
    day = next(row for row in monthly.json()["data"]["daily"] if row["date"] == today)
    assert day["revenue"] == 4
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    hotel = await ac.get("/api/v1/reports/sales/daily", headers=admin)
    assert hotel.json()["data"]["total_revenue"] == 24
    assert hotel.json()["data"]["pos_revenue"] == 24
    assert "Sales returns" in hotel.json()["data"]["returns_note"]


async def test_restaurant_till_return_comes_off_detailed_sales(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    rice = await _product(ac, admin, name="Detail return rice", selling_price=1, cost_price=2, stock_qty=5)
    plate = await _product(
        ac, admin, name="Detail return plate", selling_price=20, cost_price=9, stock_qty=3, prep_station="kitchen"
    )
    bottle = await _product(ac, admin, name="Detail return bottle", selling_price=4, cost_price=6, stock_qty=2)
    recipe = await ac.post(
        "/api/v1/restaurant/recipes",
        headers=admin,
        json={
            "product_id": plate["id"],
            "name": "Detail return plate",
            "lines": [{"ingredient_id": rice["id"], "quantity": 1}],
        },
    )
    assert recipe.status_code == 200, recipe.text
    shift = await ac.post("/api/v1/pos/sessions/open", headers=admin, json={"opening_cash": 0})
    assert shift.status_code == 200, shift.text
    session_id = shift.json()["data"].get("session_id") or shift.json()["data"]["id"]
    sale = await ac.post(
        "/api/v1/pos/sales",
        headers=admin,
        json={
            "session_id": session_id,
            "payment_method": "cash",
            "items": [
                {"product_id": plate["id"], "quantity": 1},
                {"product_id": bottle["id"], "quantity": 1},
            ],
        },
    )
    assert sale.status_code == 200, sale.text
    number = sale.json()["data"]["reference"]
    sold = await ac.get("/api/v1/reports/sales/transactions", headers=admin)
    assert sold.status_code == 200, sold.text
    sold_row = next(row for row in sold.json()["data"]["rows"] if row["number"] == number)
    assert sold_row["total"] == 24
    assert sold.json()["data"]["total"] == 24
    restored = await ac.post(
        f"/api/v1/pos/sales/{sale.json()['data']['id']}/returns",
        headers=admin,
        json={"items": [{"product_id": plate["id"], "quantity": 1}], "reason": "other"},
    )
    assert restored.status_code == 200, restored.text
    listed = await ac.get("/api/v1/reports/sales/transactions", headers=admin)
    body = listed.json()["data"]
    row = next(item for item in body["rows"] if item["number"] == number)
    assert row["total"] == 4
    assert body["total"] == 4
    assert "comes off this list" in body["returns_note"]
    till = await ac.get("/api/v1/reports/sales/pos", headers=admin)
    assert till.status_code == 200, till.text
    receipt = next(item for item in till.json()["data"]["rows"] if item["number"] == number)
    assert receipt["total"] == 24
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    hotel = await ac.get("/api/v1/reports/sales/transactions", headers=admin)
    hotel_row = next(item for item in hotel.json()["data"]["rows"] if item["number"] == number)
    assert hotel_row["total"] == 24
    assert "Sales returns" in hotel.json()["data"]["returns_note"]


async def test_restaurant_till_return_comes_off_payment_methods(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    rice = await _product(ac, admin, name="Tender return rice", selling_price=1, cost_price=2, stock_qty=5)
    plate = await _product(
        ac, admin, name="Tender return plate", selling_price=20, cost_price=9, stock_qty=3, prep_station="kitchen"
    )
    bottle = await _product(ac, admin, name="Tender return bottle", selling_price=4, cost_price=6, stock_qty=2)
    recipe = await ac.post(
        "/api/v1/restaurant/recipes",
        headers=admin,
        json={
            "product_id": plate["id"],
            "name": "Tender return plate",
            "lines": [{"ingredient_id": rice["id"], "quantity": 1}],
        },
    )
    assert recipe.status_code == 200, recipe.text
    shift = await ac.post("/api/v1/pos/sessions/open", headers=admin, json={"opening_cash": 0})
    assert shift.status_code == 200, shift.text
    session_id = shift.json()["data"].get("session_id") or shift.json()["data"]["id"]
    sale = await ac.post(
        "/api/v1/pos/sales",
        headers=admin,
        json={
            "session_id": session_id,
            "payment_method": "cash",
            "items": [
                {"product_id": plate["id"], "quantity": 1},
                {"product_id": bottle["id"], "quantity": 1},
            ],
        },
    )
    assert sale.status_code == 200, sale.text
    number = sale.json()["data"]["reference"]
    sold = await ac.get("/api/v1/reports/sales/payments", headers=admin)
    assert sold.status_code == 200, sold.text
    cash = next(row for row in sold.json()["data"]["rows"] if row["payment_method"] == "cash")
    assert cash["amount"] == 24
    assert cash["count"] == 1
    assert sold.json()["data"]["total"] == 24
    restored = await ac.post(
        f"/api/v1/pos/sales/{sale.json()['data']['id']}/returns",
        headers=admin,
        json={"items": [{"product_id": plate["id"], "quantity": 1}], "reason": "other"},
    )
    assert restored.status_code == 200, restored.text
    paid = await ac.get("/api/v1/reports/sales/payments", headers=admin)
    body = paid.json()["data"]
    cash = next(row for row in body["rows"] if row["payment_method"] == "cash")
    assert cash["amount"] == 4
    assert cash["count"] == 1
    assert body["total"] == 4
    assert "comes off this tender" in body["returns_note"]
    till = await ac.get("/api/v1/reports/sales/pos", headers=admin)
    receipt = next(item for item in till.json()["data"]["rows"] if item["number"] == number)
    assert receipt["total"] == 24
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    hotel = await ac.get("/api/v1/reports/sales/payments", headers=admin)
    hotel_cash = next(row for row in hotel.json()["data"]["rows"] if row["payment_method"] == "cash")
    assert hotel_cash["amount"] == 24
    assert "Sales returns" in hotel.json()["data"]["returns_note"]


async def test_restaurant_till_return_comes_off_sales_by_customer(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    rice = await _product(ac, admin, name="Customer return rice", selling_price=1, cost_price=2, stock_qty=5)
    plate = await _product(
        ac, admin, name="Customer return plate", selling_price=20, cost_price=9, stock_qty=3, prep_station="kitchen"
    )
    bottle = await _product(ac, admin, name="Customer return bottle", selling_price=4, cost_price=6, stock_qty=2)
    recipe = await ac.post(
        "/api/v1/restaurant/recipes",
        headers=admin,
        json={
            "product_id": plate["id"],
            "name": "Customer return plate",
            "lines": [{"ingredient_id": rice["id"], "quantity": 1}],
        },
    )
    assert recipe.status_code == 200, recipe.text
    shift = await ac.post("/api/v1/pos/sessions/open", headers=admin, json={"opening_cash": 0})
    assert shift.status_code == 200, shift.text
    session_id = shift.json()["data"].get("session_id") or shift.json()["data"]["id"]
    sale = await ac.post(
        "/api/v1/pos/sales",
        headers=admin,
        json={
            "session_id": session_id,
            "payment_method": "cash",
            "items": [
                {"product_id": plate["id"], "quantity": 1},
                {"product_id": bottle["id"], "quantity": 1},
            ],
        },
    )
    assert sale.status_code == 200, sale.text
    number = sale.json()["data"]["reference"]
    sold = await ac.get("/api/v1/reports/sales/customers", headers=admin)
    assert sold.status_code == 200, sold.text
    walk = next(row for row in sold.json()["data"]["customers"] if row["name"] == "Walk-in")
    assert walk["revenue"] == 24
    assert walk["pos_revenue"] == 24
    assert walk["pos_count"] == 1
    assert walk["sale_count"] == 1
    restored = await ac.post(
        f"/api/v1/pos/sales/{sale.json()['data']['id']}/returns",
        headers=admin,
        json={"items": [{"product_id": plate["id"], "quantity": 1}], "reason": "other"},
    )
    assert restored.status_code == 200, restored.text
    paid = await ac.get("/api/v1/reports/sales/customers", headers=admin)
    body = paid.json()["data"]
    walk = next(row for row in body["customers"] if row["name"] == "Walk-in")
    assert walk["revenue"] == 4
    assert walk["pos_revenue"] == 4
    assert walk["pos_count"] == 1
    assert walk["sale_count"] == 1
    assert body["total_revenue"] == 4
    assert body["total_sales"] == 1
    assert "comes off this customer" in body["returns_note"]
    till = await ac.get("/api/v1/reports/sales/pos", headers=admin)
    receipt = next(item for item in till.json()["data"]["rows"] if item["number"] == number)
    assert receipt["total"] == 24
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    hotel = await ac.get("/api/v1/reports/sales/customers", headers=admin)
    hotel_walk = next(row for row in hotel.json()["data"]["customers"] if row["name"] == "Walk-in")
    assert hotel_walk["revenue"] == 24
    assert "Sales returns" in hotel.json()["data"]["returns_note"]


async def test_restaurant_till_return_comes_off_sales_by_staff(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    rice = await _product(ac, admin, name="Staff return rice", selling_price=1, cost_price=2, stock_qty=5)
    plate = await _product(
        ac, admin, name="Staff return plate", selling_price=20, cost_price=9, stock_qty=3, prep_station="kitchen"
    )
    bottle = await _product(ac, admin, name="Staff return bottle", selling_price=4, cost_price=6, stock_qty=2)
    recipe = await ac.post(
        "/api/v1/restaurant/recipes",
        headers=admin,
        json={
            "product_id": plate["id"],
            "name": "Staff return plate",
            "lines": [{"ingredient_id": rice["id"], "quantity": 1}],
        },
    )
    assert recipe.status_code == 200, recipe.text
    shift = await ac.post("/api/v1/pos/sessions/open", headers=admin, json={"opening_cash": 0})
    assert shift.status_code == 200, shift.text
    session_id = shift.json()["data"].get("session_id") or shift.json()["data"]["id"]
    sale = await ac.post(
        "/api/v1/pos/sales",
        headers=admin,
        json={
            "session_id": session_id,
            "payment_method": "cash",
            "items": [
                {"product_id": plate["id"], "quantity": 1},
                {"product_id": bottle["id"], "quantity": 1},
            ],
        },
    )
    assert sale.status_code == 200, sale.text
    number = sale.json()["data"]["reference"]
    sold = await ac.get("/api/v1/reports/sales/salesperson", headers=admin)
    assert sold.status_code == 200, sold.text
    staff = sold.json()["data"]["salespeople"]
    assert len(staff) == 1
    assert staff[0]["revenue"] == 24
    assert staff[0]["pos_revenue"] == 24
    assert staff[0]["pos_count"] == 1
    assert staff[0]["sale_count"] == 1
    restored = await ac.post(
        f"/api/v1/pos/sales/{sale.json()['data']['id']}/returns",
        headers=admin,
        json={"items": [{"product_id": plate["id"], "quantity": 1}], "reason": "other"},
    )
    assert restored.status_code == 200, restored.text
    paid = await ac.get("/api/v1/reports/sales/salesperson", headers=admin)
    body = paid.json()["data"]
    staff = body["salespeople"]
    assert len(staff) == 1
    assert staff[0]["revenue"] == 4
    assert staff[0]["pos_revenue"] == 4
    assert staff[0]["pos_count"] == 1
    assert staff[0]["sale_count"] == 1
    assert body["total_revenue"] == 4
    assert body["total_sales"] == 1
    assert "comes off this staff member" in body["returns_note"]
    till = await ac.get("/api/v1/reports/sales/pos", headers=admin)
    receipt = next(item for item in till.json()["data"]["rows"] if item["number"] == number)
    assert receipt["total"] == 24
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    hotel = await ac.get("/api/v1/reports/sales/salesperson", headers=admin)
    hotel_staff = hotel.json()["data"]["salespeople"]
    assert len(hotel_staff) == 1
    assert hotel_staff[0]["revenue"] == 24
    assert "Sales returns" in hotel.json()["data"]["returns_note"]


async def test_restaurant_till_return_comes_off_sales_by_department(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    rice = await _product(ac, admin, name="Department return rice", selling_price=1, cost_price=2, stock_qty=5)
    plate = await _product(
        ac, admin, name="Department return plate", selling_price=20, cost_price=9, stock_qty=3, prep_station="kitchen"
    )
    bottle = await _product(ac, admin, name="Department return bottle", selling_price=4, cost_price=6, stock_qty=2)
    recipe = await ac.post(
        "/api/v1/restaurant/recipes",
        headers=admin,
        json={
            "product_id": plate["id"],
            "name": "Department return plate",
            "lines": [{"ingredient_id": rice["id"], "quantity": 1}],
        },
    )
    assert recipe.status_code == 200, recipe.text
    shift = await ac.post("/api/v1/pos/sessions/open", headers=admin, json={"opening_cash": 0})
    assert shift.status_code == 200, shift.text
    session_id = shift.json()["data"].get("session_id") or shift.json()["data"]["id"]
    sale = await ac.post(
        "/api/v1/pos/sales",
        headers=admin,
        json={
            "session_id": session_id,
            "payment_method": "cash",
            "items": [
                {"product_id": plate["id"], "quantity": 1},
                {"product_id": bottle["id"], "quantity": 1},
            ],
        },
    )
    assert sale.status_code == 200, sale.text
    number = sale.json()["data"]["reference"]
    sold = await ac.get("/api/v1/reports/sales/by-department", headers=admin)
    assert sold.status_code == 200, sold.text

    def till_row(body):
        rows = [row for row in body["departments"] if row["pos_count"]]
        assert len(rows) == 1
        return rows[0]

    dept = till_row(sold.json()["data"])
    assert dept["revenue"] == 24
    assert dept["pos_revenue"] == 24
    assert dept["pos_count"] == 1
    assert dept["sale_count"] == 1
    assert sold.json()["data"]["total_revenue"] == 24
    restored = await ac.post(
        f"/api/v1/pos/sales/{sale.json()['data']['id']}/returns",
        headers=admin,
        json={"items": [{"product_id": plate["id"], "quantity": 1}], "reason": "other"},
    )
    assert restored.status_code == 200, restored.text
    paid = await ac.get("/api/v1/reports/sales/by-department", headers=admin)
    body = paid.json()["data"]
    dept = till_row(body)
    assert dept["revenue"] == 4
    assert dept["pos_revenue"] == 4
    assert dept["pos_count"] == 1
    assert dept["sale_count"] == 1
    assert body["total_revenue"] == 4
    assert "comes off this department" in body["returns_note"]
    till = await ac.get("/api/v1/reports/sales/pos", headers=admin)
    receipt = next(item for item in till.json()["data"]["rows"] if item["number"] == number)
    assert receipt["total"] == 24
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    hotel = await ac.get("/api/v1/reports/sales/by-department", headers=admin)
    hotel_body = hotel.json()["data"]
    hotel_dept = till_row(hotel_body)
    assert hotel_dept["revenue"] == 24
    assert hotel_body["total_revenue"] == 24
    assert "Sales returns" in hotel_body["returns_note"]


async def test_restaurant_till_return_comes_off_sales_by_store(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    rice = await _product(ac, admin, name="Store return rice", selling_price=1, cost_price=2, stock_qty=5)
    plate = await _product(
        ac, admin, name="Store return plate", selling_price=20, cost_price=9, stock_qty=3, prep_station="kitchen"
    )
    bottle = await _product(ac, admin, name="Store return bottle", selling_price=4, cost_price=6, stock_qty=2)
    recipe = await ac.post(
        "/api/v1/restaurant/recipes",
        headers=admin,
        json={
            "product_id": plate["id"],
            "name": "Store return plate",
            "lines": [{"ingredient_id": rice["id"], "quantity": 1}],
        },
    )
    assert recipe.status_code == 200, recipe.text
    shift = await ac.post("/api/v1/pos/sessions/open", headers=admin, json={"opening_cash": 0})
    assert shift.status_code == 200, shift.text
    session_id = shift.json()["data"].get("session_id") or shift.json()["data"]["id"]
    sale = await ac.post(
        "/api/v1/pos/sales",
        headers=admin,
        json={
            "session_id": session_id,
            "payment_method": "cash",
            "items": [
                {"product_id": plate["id"], "quantity": 1},
                {"product_id": bottle["id"], "quantity": 1},
            ],
        },
    )
    assert sale.status_code == 200, sale.text
    number = sale.json()["data"]["reference"]
    sold = await ac.get("/api/v1/reports/sales/by-store", headers=admin)
    assert sold.status_code == 200, sold.text

    def till_row(body):
        rows = [row for row in body["stores"] if row["pos_count"]]
        assert len(rows) == 1
        return rows[0]

    store = till_row(sold.json()["data"])
    assert store["revenue"] == 24
    assert store["pos_revenue"] == 24
    assert store["pos_count"] == 1
    assert store["sale_count"] == 1
    assert sold.json()["data"]["total_revenue"] == 24
    restored = await ac.post(
        f"/api/v1/pos/sales/{sale.json()['data']['id']}/returns",
        headers=admin,
        json={"items": [{"product_id": plate["id"], "quantity": 1}], "reason": "other"},
    )
    assert restored.status_code == 200, restored.text
    paid = await ac.get("/api/v1/reports/sales/by-store", headers=admin)
    body = paid.json()["data"]
    store = till_row(body)
    assert store["revenue"] == 4
    assert store["pos_revenue"] == 4
    assert store["pos_count"] == 1
    assert store["sale_count"] == 1
    assert body["total_revenue"] == 4
    assert "comes off this store" in body["returns_note"]
    till = await ac.get("/api/v1/reports/sales/pos", headers=admin)
    receipt = next(item for item in till.json()["data"]["rows"] if item["number"] == number)
    assert receipt["total"] == 24
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    hotel = await ac.get("/api/v1/reports/sales/by-store", headers=admin)
    hotel_body = hotel.json()["data"]
    hotel_store = till_row(hotel_body)
    assert hotel_store["revenue"] == 24
    assert hotel_body["total_revenue"] == 24
    assert "Sales returns" in hotel_body["returns_note"]


async def test_restaurant_till_return_comes_off_till_tax(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    tenant = seed["t1"]
    db_session.add(
        m.TaxRate(
            tenant_id=tenant.id,
            name="VAT",
            rate=10,
            tax_type="vat",
            pricing_mode="exclusive",
            is_default=True,
            is_active=True,
        )
    )
    await db_session.commit()
    rice = await _product(ac, admin, name="Tax return rice", selling_price=1, cost_price=2, stock_qty=5)
    plate = await _product(
        ac, admin, name="Tax return plate", selling_price=20, cost_price=9, stock_qty=3, prep_station="kitchen"
    )
    bottle = await _product(ac, admin, name="Tax return bottle", selling_price=4, cost_price=6, stock_qty=2)
    recipe = await ac.post(
        "/api/v1/restaurant/recipes",
        headers=admin,
        json={
            "product_id": plate["id"],
            "name": "Tax return plate",
            "lines": [{"ingredient_id": rice["id"], "quantity": 1}],
        },
    )
    assert recipe.status_code == 200, recipe.text
    shift = await ac.post("/api/v1/pos/sessions/open", headers=admin, json={"opening_cash": 0})
    assert shift.status_code == 200, shift.text
    session_id = shift.json()["data"].get("session_id") or shift.json()["data"]["id"]
    sale = await ac.post(
        "/api/v1/pos/sales",
        headers=admin,
        json={
            "session_id": session_id,
            "payment_method": "cash",
            "items": [
                {"product_id": plate["id"], "quantity": 1},
                {"product_id": bottle["id"], "quantity": 1},
            ],
        },
    )
    assert sale.status_code == 200, sale.text
    number = sale.json()["data"]["reference"]
    sold = await ac.get("/api/v1/reports/tax", headers=admin)
    assert sold.status_code == 200, sold.text
    assert sold.json()["data"]["output_tax_pos"] == 2.4
    assert sold.json()["data"]["pos_sale_count"] == 1
    restored = await ac.post(
        f"/api/v1/pos/sales/{sale.json()['data']['id']}/returns",
        headers=admin,
        json={"items": [{"product_id": plate["id"], "quantity": 1}], "reason": "other"},
    )
    assert restored.status_code == 200, restored.text
    paid = await ac.get("/api/v1/reports/tax", headers=admin)
    body = paid.json()["data"]
    assert body["output_tax_pos"] == 0.4
    assert body["pos_sale_count"] == 1
    assert "comes off this till tax" in body["returns_note"]
    filing = await ac.get("/api/v1/reports/tax/filing", headers=admin)
    assert filing.status_code == 200, filing.text
    row = next(
        item
        for item in filing.json()["data"]["schedules"]["output"]
        if item.get("document_number") == number
    )
    assert row["tax_amount"] == 0.4
    assert row["gross_amount"] == 4.4
    till = await ac.get("/api/v1/reports/sales/pos", headers=admin)
    receipt = next(item for item in till.json()["data"]["rows"] if item["number"] == number)
    assert receipt["total"] == 26.4
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    hotel = await ac.get("/api/v1/reports/tax", headers=admin)
    assert hotel.json()["data"]["output_tax_pos"] == 2.4
    assert "Sales returns" in hotel.json()["data"]["returns_note"]


async def test_restaurant_till_return_comes_off_recent_sales(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    rice = await _product(ac, admin, name="Recent return rice", selling_price=1, cost_price=2, stock_qty=5)
    plate = await _product(
        ac, admin, name="Recent return plate", selling_price=20, cost_price=9, stock_qty=3, prep_station="kitchen"
    )
    bottle = await _product(ac, admin, name="Recent return bottle", selling_price=4, cost_price=6, stock_qty=2)
    recipe = await ac.post(
        "/api/v1/restaurant/recipes",
        headers=admin,
        json={
            "product_id": plate["id"],
            "name": "Recent return plate",
            "lines": [{"ingredient_id": rice["id"], "quantity": 1}],
        },
    )
    assert recipe.status_code == 200, recipe.text
    shift = await ac.post("/api/v1/pos/sessions/open", headers=admin, json={"opening_cash": 0})
    assert shift.status_code == 200, shift.text
    session_id = shift.json()["data"].get("session_id") or shift.json()["data"]["id"]
    sale = await ac.post(
        "/api/v1/pos/sales",
        headers=admin,
        json={
            "session_id": session_id,
            "payment_method": "cash",
            "items": [
                {"product_id": plate["id"], "quantity": 1},
                {"product_id": bottle["id"], "quantity": 1},
            ],
        },
    )
    assert sale.status_code == 200, sale.text
    number = sale.json()["data"]["reference"]
    sold = await ac.get("/api/v1/dashboard", headers=admin)
    assert sold.status_code == 200, sold.text
    recent = next(row for row in sold.json()["data"]["recent_sales"] if row["reference"] == number)
    assert recent["total"] == 24
    assert recent["type"] == "pos_sale"
    restored = await ac.post(
        f"/api/v1/pos/sales/{sale.json()['data']['id']}/returns",
        headers=admin,
        json={"items": [{"product_id": plate["id"], "quantity": 1}], "reason": "other"},
    )
    assert restored.status_code == 200, restored.text
    paid = await ac.get("/api/v1/dashboard", headers=admin)
    recent = next(row for row in paid.json()["data"]["recent_sales"] if row["reference"] == number)
    assert recent["total"] == 4
    till = await ac.get("/api/v1/reports/sales/pos", headers=admin)
    receipt = next(item for item in till.json()["data"]["rows"] if item["number"] == number)
    assert receipt["total"] == 24
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    hotel = await ac.get("/api/v1/dashboard", headers=admin)
    hotel_recent = next(row for row in hotel.json()["data"]["recent_sales"] if row["reference"] == number)
    assert hotel_recent["total"] == 24


async def test_restaurant_till_return_comes_off_discounts(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    rice = await _product(ac, admin, name="Discount return rice", selling_price=1, cost_price=2, stock_qty=5)
    plate = await _product(
        ac, admin, name="Discount return plate", selling_price=20, cost_price=9, stock_qty=3, prep_station="kitchen"
    )
    bottle = await _product(ac, admin, name="Discount return bottle", selling_price=4, cost_price=6, stock_qty=2)
    recipe = await ac.post(
        "/api/v1/restaurant/recipes",
        headers=admin,
        json={
            "product_id": plate["id"],
            "name": "Discount return plate",
            "lines": [{"ingredient_id": rice["id"], "quantity": 1}],
        },
    )
    assert recipe.status_code == 200, recipe.text
    shift = await ac.post("/api/v1/pos/sessions/open", headers=admin, json={"opening_cash": 0})
    assert shift.status_code == 200, shift.text
    session_id = shift.json()["data"].get("session_id") or shift.json()["data"]["id"]
    sale = await ac.post(
        "/api/v1/pos/sales",
        headers=admin,
        json={
            "session_id": session_id,
            "payment_method": "cash",
            "items": [
                {"product_id": plate["id"], "quantity": 1, "discount": 2},
                {"product_id": bottle["id"], "quantity": 1},
            ],
        },
    )
    assert sale.status_code == 200, sale.text
    number = sale.json()["data"]["reference"]
    assert sale.json()["data"]["total"] == 22
    listed = await ac.get("/api/v1/reports/sales/discounts", headers=admin)
    assert listed.status_code == 200, listed.text
    body = listed.json()["data"]
    assert body["line_discounts"] == 2
    assert body["total"] == 2
    assert "comes off this discount" in body["returns_note"]
    row = next(item for item in body["rows"] if item["number"] == number)
    assert row["amount"] == 2
    restored = await ac.post(
        f"/api/v1/pos/sales/{sale.json()['data']['id']}/returns",
        headers=admin,
        json={"items": [{"product_id": plate["id"], "quantity": 1}], "reason": "other"},
    )
    assert restored.status_code == 200, restored.text
    paid = await ac.get("/api/v1/reports/sales/discounts", headers=admin)
    after = paid.json()["data"]
    assert after["line_discounts"] == 0
    assert after["total"] == 0
    assert all(item["number"] != number for item in after["rows"])
    till = await ac.get("/api/v1/reports/sales/pos", headers=admin)
    receipt = next(item for item in till.json()["data"]["rows"] if item["number"] == number)
    assert receipt["total"] == 22
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    hotel = await ac.get("/api/v1/reports/sales/discounts", headers=admin)
    hotel_body = hotel.json()["data"]
    assert hotel_body["line_discounts"] == 2
    assert "not subtracted again" in hotel_body["returns_note"]


async def test_restaurant_bill_is_included_in_sales_by_customer(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    plate = await _product(
        ac, admin, name="Customer bill plate", selling_price=20, cost_price=4, stock_qty=3, prep_station="kitchen"
    )
    opened = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "customer_name": "Ama Guest",
            "lines": [{"product_id": plate["id"], "quantity": 1}],
        },
    )
    assert opened.status_code == 200, opened.text
    order_id = opened.json()["data"]["id"]
    done = await ac.post(f"/api/v1/restaurant/orders/{order_id}/complete", headers=admin)
    assert done.status_code == 200, done.text
    listed = await ac.get("/api/v1/reports/sales/customers", headers=admin)
    assert listed.status_code == 200, listed.text
    body = listed.json()["data"]
    guest = next(row for row in body["customers"] if row["name"] == "Ama Guest")
    assert guest["revenue"] == 20
    assert guest["invoice_count"] == 1
    assert guest["invoice_revenue"] == 20
    assert guest["pos_count"] == 0
    assert guest["sale_count"] == 1
    assert body["total_revenue"] >= 20
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    hotel = await ac.get("/api/v1/reports/sales/customers", headers=admin)
    assert all(row["name"] != "Ama Guest" for row in hotel.json()["data"]["customers"])


async def test_restaurant_bill_is_included_in_sales_by_staff(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    plate = await _product(
        ac, admin, name="Staff bill plate", selling_price=20, cost_price=4, stock_qty=3, prep_station="kitchen"
    )
    opened = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "customer_name": "Ama Staff",
            "lines": [{"product_id": plate["id"], "quantity": 1}],
        },
    )
    assert opened.status_code == 200, opened.text
    done = await ac.post(
        f"/api/v1/restaurant/orders/{opened.json()['data']['id']}/complete", headers=admin
    )
    assert done.status_code == 200, done.text
    listed = await ac.get("/api/v1/reports/sales/salesperson", headers=admin)
    assert listed.status_code == 200, listed.text
    body = listed.json()["data"]
    staff = next(row for row in body["salespeople"] if row["invoice_revenue"] == 20)
    assert staff["invoice_count"] == 1
    assert staff["pos_count"] == 0
    assert staff["sale_count"] == 1
    assert staff["revenue"] == 20
    assert staff["full_name"] != "Unknown"
    assert body["total_revenue"] >= 20
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    hotel = await ac.get("/api/v1/reports/sales/salesperson", headers=admin)
    assert all(row["revenue"] != 20 for row in hotel.json()["data"]["salespeople"])


async def test_restaurant_bill_is_included_in_sales_by_department(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    plate = await _product(
        ac, admin, name="Department bill plate", selling_price=20, cost_price=4, stock_qty=3, prep_station="kitchen"
    )
    opened = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "customer_name": "Ama Dept",
            "lines": [{"product_id": plate["id"], "quantity": 1}],
        },
    )
    assert opened.status_code == 200, opened.text
    done = await ac.post(
        f"/api/v1/restaurant/orders/{opened.json()['data']['id']}/complete", headers=admin
    )
    assert done.status_code == 200, done.text
    listed = await ac.get("/api/v1/reports/sales/by-department", headers=admin)
    assert listed.status_code == 200, listed.text
    body = listed.json()["data"]
    dept = next(row for row in body["departments"] if row["invoice_revenue"] == 20)
    assert dept["invoice_count"] == 1
    assert dept["pos_count"] == 0
    assert dept["sale_count"] == 1
    assert dept["revenue"] == 20
    assert body["total_revenue"] >= 20
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    hotel = await ac.get("/api/v1/reports/sales/by-department", headers=admin)
    assert all(row["invoice_revenue"] != 20 for row in hotel.json()["data"]["departments"])


async def test_restaurant_bill_is_included_in_sales_by_store(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    plate = await _product(
        ac, admin, name="Store bill plate", selling_price=20, cost_price=4, stock_qty=3, prep_station="kitchen"
    )
    opened = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "customer_name": "Ama Store",
            "lines": [{"product_id": plate["id"], "quantity": 1}],
        },
    )
    assert opened.status_code == 200, opened.text
    done = await ac.post(
        f"/api/v1/restaurant/orders/{opened.json()['data']['id']}/complete", headers=admin
    )
    assert done.status_code == 200, done.text
    listed = await ac.get("/api/v1/reports/sales/by-store", headers=admin)
    assert listed.status_code == 200, listed.text
    body = listed.json()["data"]
    store = next(row for row in body["stores"] if row["invoice_revenue"] == 20)
    assert store["name"] == "Unassigned"
    assert store["invoice_count"] == 1
    assert store["pos_count"] == 0
    assert store["sale_count"] == 1
    assert store["revenue"] == 20
    assert body["total_revenue"] >= 20
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    hotel = await ac.get("/api/v1/reports/sales/by-store", headers=admin)
    assert all(row["invoice_revenue"] != 20 for row in hotel.json()["data"]["stores"])


async def test_restaurant_bill_is_included_in_bill_tax(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    tenant = seed["t1"]
    db_session.add(
        m.TaxRate(
            tenant_id=tenant.id,
            name="VAT",
            rate=10,
            tax_type="vat",
            pricing_mode="exclusive",
            is_default=True,
            is_active=True,
        )
    )
    await db_session.commit()
    plate = await _product(
        ac, admin, name="Tax bill plate", selling_price=100, cost_price=4, stock_qty=3, prep_station="kitchen"
    )
    opened = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "customer_name": "Ama Tax",
            "lines": [{"product_id": plate["id"], "quantity": 1}],
        },
    )
    assert opened.status_code == 200, opened.text
    done = await ac.post(
        f"/api/v1/restaurant/orders/{opened.json()['data']['id']}/complete", headers=admin
    )
    assert done.status_code == 200, done.text
    assert done.json()["data"]["total_amount"] == 110
    number = done.json()["data"]["order_number"]
    listed = await ac.get("/api/v1/reports/tax", headers=admin)
    assert listed.status_code == 200, listed.text
    body = listed.json()["data"]
    assert body["output_tax_invoices"] == 10
    assert body["output_tax"] == 10
    assert body["output_tax_pos"] == 0
    filing = await ac.get("/api/v1/reports/tax/filing", headers=admin)
    assert filing.status_code == 200, filing.text
    row = next(
        item
        for item in filing.json()["data"]["schedules"]["output"]
        if item.get("document_number") == number
    )
    assert row["document_type"] == "table_bill"
    assert row["tax_amount"] == 10
    assert row["gross_amount"] == 110
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    hotel = await ac.get("/api/v1/reports/tax", headers=admin)
    assert hotel.json()["data"]["output_tax_invoices"] == 0
    assert hotel.json()["data"]["output_tax"] == 0


async def test_restaurant_bill_is_included_in_store_profit_and_loss(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    floor = await ac.post("/api/v1/stores", json={"name": "Profit Floor", "code": "PNL197"}, headers=admin)
    assert floor.status_code == 200, floor.text
    other = await ac.post("/api/v1/stores", json={"name": "Other Floor", "code": "PNL198"}, headers=admin)
    assert other.status_code == 200, other.text
    floor_id = floor.json()["data"]["id"]
    other_id = other.json()["data"]["id"]
    plate = await _product(
        ac, admin, name="Profit plate", selling_price=20, cost_price=4, stock_qty=3, prep_station="kitchen"
    )
    opened = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "store_id": floor_id,
            "customer_name": "Ama Profit",
            "lines": [{"product_id": plate["id"], "quantity": 1}],
        },
    )
    assert opened.status_code == 200, opened.text
    done = await ac.post(
        f"/api/v1/restaurant/orders/{opened.json()['data']['id']}/complete", headers=admin
    )
    assert done.status_code == 200, done.text
    assert done.json()["data"]["total_amount"] == 20
    listed = await ac.get(f"/api/v1/reports/profit-loss?store_id={floor_id}", headers=admin)
    assert listed.status_code == 200, listed.text
    body = listed.json()["data"]
    assert body["revenue"] == 20
    assert body["cogs"] == 4
    assert body["net_profit"] == 16
    cash = await ac.get(f"/api/v1/reports/cash-flow?store_id={floor_id}", headers=admin)
    assert cash.status_code == 200, cash.text
    assert cash.json()["data"]["inflows"] == 20
    quiet = await ac.get(f"/api/v1/reports/profit-loss?store_id={other_id}", headers=admin)
    assert quiet.json()["data"]["revenue"] == 0
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    hotel = await ac.get(f"/api/v1/reports/profit-loss?store_id={floor_id}", headers=admin)
    assert hotel.json()["data"]["revenue"] == 0


async def test_restaurant_bill_tax_is_included_on_items_sold(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    tenant = seed["t1"]
    db_session.add(
        m.TaxRate(
            tenant_id=tenant.id,
            name="VAT",
            rate=10,
            tax_type="vat",
            pricing_mode="exclusive",
            is_default=True,
            is_active=True,
        )
    )
    await db_session.commit()
    plate = await _product(
        ac, admin, name="Line tax plate", selling_price=100, cost_price=4, stock_qty=3, prep_station="kitchen"
    )
    opened = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "customer_name": "Ama Lines",
            "lines": [{"product_id": plate["id"], "quantity": 1}],
        },
    )
    assert opened.status_code == 200, opened.text
    done = await ac.post(
        f"/api/v1/restaurant/orders/{opened.json()['data']['id']}/complete", headers=admin
    )
    assert done.status_code == 200, done.text
    assert done.json()["data"]["total_amount"] == 110
    listed = await ac.get("/api/v1/reports/sales/lines", headers=admin)
    assert listed.status_code == 200, listed.text
    body = listed.json()["data"]
    row = next(item for item in body["lines"] if item["product"] == "Line tax plate")
    assert row["sales_total"] == 100
    assert row["tax"] == 10
    assert body["total_tax"] == 10
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    hotel = await ac.get("/api/v1/reports/sales/lines", headers=admin)
    assert hotel.json()["data"]["total_tax"] == 0
    assert all(item["product"] != "Line tax plate" for item in hotel.json()["data"]["lines"])


async def test_restaurant_till_return_comes_off_items_sold_tax(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    tenant = seed["t1"]
    db_session.add(
        m.TaxRate(
            tenant_id=tenant.id,
            name="VAT",
            rate=10,
            tax_type="vat",
            pricing_mode="exclusive",
            is_default=True,
            is_active=True,
        )
    )
    await db_session.commit()
    plate = await _product(
        ac, admin, name="Sold tax plate", selling_price=20, cost_price=4, stock_qty=3, prep_station="kitchen"
    )
    shift = await ac.post("/api/v1/pos/sessions/open", headers=admin, json={"opening_cash": 0})
    assert shift.status_code == 200, shift.text
    session_id = shift.json()["data"].get("session_id") or shift.json()["data"]["id"]
    sale = await ac.post(
        "/api/v1/pos/sales",
        headers=admin,
        json={
            "session_id": session_id,
            "payment_method": "cash",
            "items": [{"product_id": plate["id"], "quantity": 2}],
        },
    )
    assert sale.status_code == 200, sale.text
    number = sale.json()["data"]["reference"]
    before = await ac.get("/api/v1/reports/sales/lines", headers=admin)
    assert before.json()["data"]["total_tax"] == 4
    restored = await ac.post(
        f"/api/v1/pos/sales/{sale.json()['data']['id']}/returns",
        headers=admin,
        json={"items": [{"product_id": plate["id"], "quantity": 1}], "reason": "other"},
    )
    assert restored.status_code == 200, restored.text
    listed = await ac.get("/api/v1/reports/sales/lines", headers=admin)
    body = listed.json()["data"]
    kept = next(row for row in body["lines"] if row["product"] == "Sold tax plate")
    assert kept["quantity"] == 1
    assert kept["sales_total"] == 20
    assert kept["tax"] == 2
    assert body["total_tax"] == 2
    till = await ac.get("/api/v1/reports/sales/pos", headers=admin)
    receipt = next(item for item in till.json()["data"]["rows"] if item["number"] == number)
    assert receipt["total"] == 44
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    hotel = await ac.get("/api/v1/reports/sales/lines", headers=admin)
    hotel_body = hotel.json()["data"]
    hotel_plate = next(row for row in hotel_body["lines"] if row["product"] == "Sold tax plate")
    assert hotel_plate["tax"] == 4
    assert hotel_body["total_tax"] == 4


async def test_restaurant_till_tax_stays_off_menu_amount(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    tenant = seed["t1"]
    db_session.add(
        m.TaxRate(
            tenant_id=tenant.id,
            name="VAT",
            rate=10,
            tax_type="vat",
            pricing_mode="exclusive",
            is_default=True,
            is_active=True,
        )
    )
    await db_session.commit()
    plate = await _product(
        ac, admin, name="Menu tax plate", selling_price=20, cost_price=4, stock_qty=3, prep_station="kitchen"
    )
    shift = await ac.post("/api/v1/pos/sessions/open", headers=admin, json={"opening_cash": 0})
    assert shift.status_code == 200, shift.text
    session_id = shift.json()["data"].get("session_id") or shift.json()["data"]["id"]
    sale = await ac.post(
        "/api/v1/pos/sales",
        headers=admin,
        json={
            "session_id": session_id,
            "payment_method": "cash",
            "items": [{"product_id": plate["id"], "quantity": 2}],
        },
    )
    assert sale.status_code == 200, sale.text
    number = sale.json()["data"]["reference"]
    restored = await ac.post(
        f"/api/v1/pos/sales/{sale.json()['data']['id']}/returns",
        headers=admin,
        json={"items": [{"product_id": plate["id"], "quantity": 1}], "reason": "other"},
    )
    assert restored.status_code == 200, restored.text
    menu = await ac.get("/api/v1/reports/sales/products", headers=admin)
    row = _named_product(menu.json()["data"], "Menu tax plate")
    assert row["quantity"] == 1
    assert row["revenue"] == 20
    assert row["cost"] == 4
    assert row["profit"] == 16
    lines = await ac.get("/api/v1/reports/sales/lines", headers=admin)
    sold = next(item for item in lines.json()["data"]["lines"] if item["product"] == "Menu tax plate")
    assert sold["sales_total"] == 20
    assert sold["tax"] == 2
    assert sold["profit"] == 16
    till = await ac.get("/api/v1/reports/sales/pos", headers=admin)
    receipt = next(item for item in till.json()["data"]["rows"] if item["number"] == number)
    assert receipt["total"] == 44
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    hotel = await ac.get("/api/v1/reports/sales/products", headers=admin)
    hotel_row = _named_product(hotel.json()["data"], "Menu tax plate")
    assert hotel_row["revenue"] == 44
    assert hotel_row["profit"] == 36


async def test_restaurant_till_return_keeps_tax_out_of_dashboard_profit(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    tenant = seed["t1"]
    db_session.add(
        m.TaxRate(
            tenant_id=tenant.id,
            name="VAT",
            rate=10,
            tax_type="vat",
            pricing_mode="exclusive",
            is_default=True,
            is_active=True,
        )
    )
    await db_session.commit()
    plate = await _product(
        ac, admin, name="Profit tax plate", selling_price=20, cost_price=4, stock_qty=3, prep_station="kitchen"
    )
    before = await ac.get("/api/v1/dashboard", headers=admin)
    profit_start = _today_profit(before.json()["data"])
    sales_start = float(before.json()["data"]["comparisons"]["sales_today"])
    shift = await ac.post("/api/v1/pos/sessions/open", headers=admin, json={"opening_cash": 0})
    assert shift.status_code == 200, shift.text
    session_id = shift.json()["data"].get("session_id") or shift.json()["data"]["id"]
    sale = await ac.post(
        "/api/v1/pos/sales",
        headers=admin,
        json={
            "session_id": session_id,
            "payment_method": "cash",
            "items": [{"product_id": plate["id"], "quantity": 2}],
        },
    )
    assert sale.status_code == 200, sale.text
    restored = await ac.post(
        f"/api/v1/pos/sales/{sale.json()['data']['id']}/returns",
        headers=admin,
        json={"items": [{"product_id": plate["id"], "quantity": 1}], "reason": "other"},
    )
    assert restored.status_code == 200, restored.text
    after = await ac.get("/api/v1/dashboard", headers=admin)
    assert _today_profit(after.json()["data"]) == pytest.approx(profit_start + 16)
    assert float(after.json()["data"]["comparisons"]["sales_today"]) == pytest.approx(sales_start + 22)
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    hotel = await ac.get("/api/v1/dashboard", headers=admin)
    assert _today_profit(hotel.json()["data"]) == pytest.approx(profit_start + 32)
    assert float(hotel.json()["data"]["comparisons"]["sales_today"]) == pytest.approx(sales_start + 44)


async def test_restaurant_service_charge_is_in_dashboard_profit(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    saved = await ac.put("/api/v1/restaurant/service-charge", headers=admin, json={"percent": 10})
    assert saved.status_code == 200, saved.text
    plate = await _product(
        ac, admin, name="Service profit plate", selling_price=100, cost_price=4, stock_qty=3, prep_station="kitchen"
    )
    before = await ac.get("/api/v1/dashboard", headers=admin)
    profit_start = _today_profit(before.json()["data"])
    sales_start = float(before.json()["data"]["comparisons"]["sales_today"])
    opened = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "customer_name": "Ama Service",
            "lines": [{"product_id": plate["id"], "quantity": 1}],
        },
    )
    assert opened.status_code == 200, opened.text
    done = await ac.post(
        f"/api/v1/restaurant/orders/{opened.json()['data']['id']}/complete",
        headers=admin,
    )
    assert done.status_code == 200, done.text
    assert done.json()["data"]["total_amount"] == 110
    after = await ac.get("/api/v1/dashboard", headers=admin)
    body = after.json()["data"]
    assert _today_profit(body) == pytest.approx(profit_start + 106)
    assert float(body["comparisons"]["sales_today"]) == pytest.approx(sales_start + 110)
    ranked = next(row for row in body["top_products_by_revenue"] if row["name"] == "Service profit plate")
    assert ranked["revenue"] == 100
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    hotel = await ac.get("/api/v1/dashboard", headers=admin)
    assert _today_profit(hotel.json()["data"]) == pytest.approx(profit_start)
    assert float(hotel.json()["data"]["comparisons"]["sales_today"]) == pytest.approx(sales_start)


async def test_restaurant_till_discount_comes_off_dashboard_profit(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    plate = await _product(
        ac, admin, name="Discount profit plate", selling_price=20, cost_price=4, stock_qty=3, prep_station="kitchen"
    )
    before = await ac.get("/api/v1/dashboard", headers=admin)
    profit_start = _today_profit(before.json()["data"])
    sales_start = float(before.json()["data"]["comparisons"]["sales_today"])
    shift = await ac.post("/api/v1/pos/sessions/open", headers=admin, json={"opening_cash": 0})
    assert shift.status_code == 200, shift.text
    session_id = shift.json()["data"].get("session_id") or shift.json()["data"]["id"]
    sale = await ac.post(
        "/api/v1/pos/sales",
        headers=admin,
        json={
            "session_id": session_id,
            "payment_method": "cash",
            "discount_amount": 5,
            "items": [{"product_id": plate["id"], "quantity": 1}],
        },
    )
    assert sale.status_code == 200, sale.text
    assert sale.json()["data"]["total"] == 15
    after = await ac.get("/api/v1/dashboard", headers=admin)
    body = after.json()["data"]
    assert _today_profit(body) == pytest.approx(profit_start + 11)
    assert float(body["comparisons"]["sales_today"]) == pytest.approx(sales_start + 15)
    ranked = next(row for row in body["top_products_by_revenue"] if row["name"] == "Discount profit plate")
    assert ranked["revenue"] == 20
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    hotel = await ac.get("/api/v1/dashboard", headers=admin)
    assert _today_profit(hotel.json()["data"]) == pytest.approx(profit_start + 16)
    assert float(hotel.json()["data"]["comparisons"]["sales_today"]) == pytest.approx(sales_start + 15)


async def test_restaurant_till_discount_comes_off_items_sold(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    plate = await _product(
        ac, admin, name="Sold discount plate", selling_price=20, cost_price=4, stock_qty=3, prep_station="kitchen"
    )
    shift = await ac.post("/api/v1/pos/sessions/open", headers=admin, json={"opening_cash": 0})
    assert shift.status_code == 200, shift.text
    session_id = shift.json()["data"].get("session_id") or shift.json()["data"]["id"]
    sale = await ac.post(
        "/api/v1/pos/sales",
        headers=admin,
        json={
            "session_id": session_id,
            "payment_method": "cash",
            "discount_amount": 5,
            "items": [{"product_id": plate["id"], "quantity": 1}],
        },
    )
    assert sale.status_code == 200, sale.text
    assert sale.json()["data"]["total"] == 15
    menu = await ac.get("/api/v1/reports/sales/products", headers=admin)
    menu_row = _named_product(menu.json()["data"], "Sold discount plate")
    assert menu_row["revenue"] == 20
    assert menu_row["profit"] == 16
    listed = await ac.get("/api/v1/reports/sales/lines", headers=admin)
    body = listed.json()["data"]
    row = next(item for item in body["lines"] if item["product"] == "Sold discount plate")
    assert row["sales_total"] == 15
    assert row["discount"] == 5
    assert row["profit"] == 11
    assert body["total_sales"] == 15
    assert body["total_discount"] == 5
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    hotel = await ac.get("/api/v1/reports/sales/lines", headers=admin)
    kept = next(item for item in hotel.json()["data"]["lines"] if item["product"] == "Sold discount plate")
    assert kept["sales_total"] == 20
    assert kept["discount"] == 0
    assert kept["profit"] == 16


async def test_restaurant_till_discount_is_in_daily_discounts(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    plate = await _product(
        ac, admin, name="Day discount plate", selling_price=20, cost_price=4, stock_qty=3, prep_station="kitchen"
    )
    shift = await ac.post("/api/v1/pos/sessions/open", headers=admin, json={"opening_cash": 0})
    assert shift.status_code == 200, shift.text
    session_id = shift.json()["data"].get("session_id") or shift.json()["data"]["id"]
    sale = await ac.post(
        "/api/v1/pos/sales",
        headers=admin,
        json={
            "session_id": session_id,
            "payment_method": "cash",
            "discount_amount": 5,
            "items": [{"product_id": plate["id"], "quantity": 1}],
        },
    )
    assert sale.status_code == 200, sale.text
    assert sale.json()["data"]["total"] == 15
    daily = await ac.get("/api/v1/reports/sales/daily", headers=admin)
    assert daily.status_code == 200, daily.text
    body = daily.json()["data"]
    assert body["discounts"] == 5
    assert body["total_revenue"] == 15
    menu = await ac.get("/api/v1/reports/sales/products", headers=admin)
    menu_row = _named_product(menu.json()["data"], "Day discount plate")
    assert menu_row["revenue"] == 20
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    hotel = await ac.get("/api/v1/reports/sales/daily", headers=admin)
    assert hotel.json()["data"]["discounts"] == 0
    assert hotel.json()["data"]["total_revenue"] == 15


async def test_restaurant_waste_is_in_store_operating_expenses(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    floor = await ac.post("/api/v1/stores", json={"name": "Waste Floor", "code": "WST207"}, headers=admin)
    assert floor.status_code == 200, floor.text
    other = await ac.post("/api/v1/stores", json={"name": "Quiet Floor", "code": "WST208"}, headers=admin)
    assert other.status_code == 200, other.text
    floor_id = floor.json()["data"]["id"]
    other_id = other.json()["data"]["id"]
    room = await ac.post(
        "/api/v1/warehouses",
        json={"name": "Waste room", "code": "WWH207", "store_id": floor_id},
        headers=admin,
    )
    assert room.status_code == 200, room.text
    room_id = room.json()["data"]["id"]
    lime = await _product(ac, admin, name="Waste lime", selling_price=2, cost_price=4, stock_qty=0)
    received = await ac.post(
        "/api/v1/inventory/stock-in",
        headers=admin,
        json={"product_id": lime["id"], "quantity": 2, "warehouse_id": room_id},
    )
    assert received.status_code == 200, received.text
    dumped = await ac.post(
        "/api/v1/restaurant/waste",
        headers=admin,
        json={"product_id": lime["id"], "quantity": 1, "reason": "spoilage", "warehouse_id": room_id},
    )
    assert dumped.status_code == 200, dumped.text
    assert dumped.json()["data"]["cost_amount"] == 4
    listed = await ac.get(f"/api/v1/reports/profit-loss?store_id={floor_id}", headers=admin)
    assert listed.status_code == 200, listed.text
    body = listed.json()["data"]
    assert body["operating_expenses"] == 4
    assert body["net_profit"] == -4
    quiet = await ac.get(f"/api/v1/reports/profit-loss?store_id={other_id}", headers=admin)
    assert quiet.json()["data"]["operating_expenses"] == 0
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    hotel = await ac.get(f"/api/v1/reports/profit-loss?store_id={floor_id}", headers=admin)
    assert hotel.json()["data"]["operating_expenses"] == 0
    assert hotel.json()["data"]["net_profit"] == 0


async def test_restaurant_bill_comes_off_store_ingredient_value(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    floor = await ac.post("/api/v1/stores", json={"name": "Value Floor", "code": "VAL208"}, headers=admin)
    assert floor.status_code == 200, floor.text
    other = await ac.post("/api/v1/stores", json={"name": "Quiet Value", "code": "VAL209"}, headers=admin)
    assert other.status_code == 200, other.text
    floor_id = floor.json()["data"]["id"]
    other_id = other.json()["data"]["id"]
    warehouses = await ac.get("/api/v1/warehouses", headers=admin)
    assert warehouses.status_code == 200, warehouses.text
    room = next(row for row in warehouses.json()["data"] if row.get("store_id") == floor_id)
    plate = await _product(ac, admin, name="Value plate", selling_price=20, cost_price=4, stock_qty=0)
    received = await ac.post(
        "/api/v1/inventory/stock-in",
        headers=admin,
        json={"product_id": plate["id"], "quantity": 5, "warehouse_id": room["id"]},
    )
    assert received.status_code == 200, received.text
    opened = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "store_id": floor_id,
            "customer_name": "Ama Value",
            "lines": [{"product_id": plate["id"], "quantity": 1}],
        },
    )
    assert opened.status_code == 200, opened.text
    done = await ac.post(
        f"/api/v1/restaurant/orders/{opened.json()['data']['id']}/complete", headers=admin
    )
    assert done.status_code == 200, done.text
    listed = await ac.get(f"/api/v1/reports/inventory/valuation?store_id={floor_id}", headers=admin)
    assert listed.status_code == 200, listed.text
    body = listed.json()["data"]
    assert body["total_quantity"] == 4
    assert body["total_value"] == 16
    quiet = await ac.get(f"/api/v1/reports/inventory/valuation?store_id={other_id}", headers=admin)
    assert quiet.json()["data"]["total_value"] == 0
    loose = await _product(ac, admin, name="Loose plate", selling_price=20, cost_price=4, stock_qty=5)
    loose_order = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "store_id": floor_id,
            "customer_name": "Ama Loose",
            "lines": [{"product_id": loose["id"], "quantity": 1}],
        },
    )
    assert loose_order.status_code == 200, loose_order.text
    loose_done = await ac.post(
        f"/api/v1/restaurant/orders/{loose_order.json()['data']['id']}/complete", headers=admin
    )
    assert loose_done.status_code == 200, loose_done.text
    still = await ac.get(f"/api/v1/reports/inventory/valuation?store_id={floor_id}", headers=admin)
    assert still.json()["data"]["total_value"] == 16
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    hotel = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={
            "service_mode": "takeaway",
            "payment_method": "cash",
            "store_id": floor_id,
            "lines": [{"product_id": plate["id"], "quantity": 1}],
        },
    )
    assert hotel.status_code == 403, hotel.text


async def test_restaurant_bill_without_a_store_stays_off_a_store_filter(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    floor = await ac.post("/api/v1/stores", json={"name": "Filter Floor", "code": "FLT209"}, headers=admin)
    assert floor.status_code == 200, floor.text
    other = await ac.post("/api/v1/stores", json={"name": "Other Filter", "code": "FLT210"}, headers=admin)
    assert other.status_code == 200, other.text
    floor_id = floor.json()["data"]["id"]
    other_id = other.json()["data"]["id"]
    placed = await _product(ac, admin, name="Filter plate", selling_price=20, cost_price=4, stock_qty=3)
    loose = await _product(ac, admin, name="Loose filter plate", selling_price=100, cost_price=4, stock_qty=3)
    for product, store in ((placed, floor_id), (loose, None)):
        body = {
            "service_mode": "takeaway",
            "payment_method": "cash",
            "customer_name": "Ama Filter",
            "lines": [{"product_id": product["id"], "quantity": 1}],
        }
        if store:
            body["store_id"] = store
        opened = await ac.post("/api/v1/restaurant/orders", headers=admin, json=body)
        assert opened.status_code == 200, opened.text
        done = await ac.post(
            f"/api/v1/restaurant/orders/{opened.json()['data']['id']}/complete", headers=admin
        )
        assert done.status_code == 200, done.text
    floor_day = await ac.get(f"/api/v1/reports/sales/daily?store_id={floor_id}", headers=admin)
    assert floor_day.status_code == 200, floor_day.text
    assert floor_day.json()["data"]["total_revenue"] == 20
    other_day = await ac.get(f"/api/v1/reports/sales/daily?store_id={other_id}", headers=admin)
    assert other_day.json()["data"]["total_revenue"] == 0
    company = await ac.get("/api/v1/reports/sales/daily", headers=admin)
    assert company.json()["data"]["total_revenue"] == 120
    menu = await ac.get(f"/api/v1/reports/sales/products?store_id={floor_id}", headers=admin)
    assert menu.status_code == 200, menu.text
    products = menu.json()["data"]["products"]
    floor_row = next(row for row in products if row["name"] == "Filter plate")
    assert floor_row["revenue"] == 20
    assert all(row["name"] != "Loose filter plate" for row in products)
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    hotel = await ac.get(f"/api/v1/reports/sales/daily?store_id={floor_id}", headers=admin)
    assert hotel.json()["data"]["total_revenue"] == 0


async def test_restaurant_till_return_without_a_store_stays_off_a_store_filter(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    floor = await ac.post("/api/v1/stores", json={"name": "Return Floor", "code": "RTN210"}, headers=admin)
    assert floor.status_code == 200, floor.text
    other = await ac.post("/api/v1/stores", json={"name": "Other Return", "code": "RTN211"}, headers=admin)
    assert other.status_code == 200, other.text
    floor_id = floor.json()["data"]["id"]
    other_id = other.json()["data"]["id"]
    plate = await _product(ac, admin, name="Return filter plate", selling_price=20, cost_price=4, stock_qty=3)
    shift = await ac.post("/api/v1/pos/sessions/open", headers=admin, json={"opening_cash": 0})
    assert shift.status_code == 200, shift.text
    session_id = shift.json()["data"].get("session_id") or shift.json()["data"]["id"]
    sale = await ac.post(
        "/api/v1/pos/sales",
        headers=admin,
        json={
            "session_id": session_id,
            "payment_method": "cash",
            "items": [{"product_id": plate["id"], "quantity": 1}],
        },
    )
    assert sale.status_code == 200, sale.text
    restored = await ac.post(
        f"/api/v1/pos/sales/{sale.json()['data']['id']}/returns",
        headers=admin,
        json={"items": [{"product_id": plate["id"], "quantity": 1}], "reason": "other"},
    )
    assert restored.status_code == 200, restored.text
    floor_day = await ac.get(f"/api/v1/reports/sales/daily?store_id={floor_id}", headers=admin)
    assert floor_day.status_code == 200, floor_day.text
    assert floor_day.json()["data"]["total_revenue"] == 0
    other_day = await ac.get(f"/api/v1/reports/sales/daily?store_id={other_id}", headers=admin)
    assert other_day.json()["data"]["total_revenue"] == 0
    company = await ac.get("/api/v1/reports/sales/daily", headers=admin)
    assert company.json()["data"]["total_revenue"] == 0
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    hotel = await ac.get(f"/api/v1/reports/sales/daily?store_id={floor_id}", headers=admin)
    assert hotel.json()["data"]["total_revenue"] == 0


async def test_restaurant_till_return_follows_the_store_on_the_receipt(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    floor = await ac.post("/api/v1/stores", json={"name": "Receipt Floor", "code": "PNL211"}, headers=admin)
    assert floor.status_code == 200, floor.text
    other = await ac.post("/api/v1/stores", json={"name": "Other Receipt", "code": "PNL212"}, headers=admin)
    assert other.status_code == 200, other.text
    floor_id = floor.json()["data"]["id"]
    other_id = other.json()["data"]["id"]
    plate = await _product(ac, admin, name="Receipt return plate", selling_price=20, cost_price=4, stock_qty=3)
    shift = await ac.post("/api/v1/pos/sessions/open", headers=admin, json={"opening_cash": 0})
    assert shift.status_code == 200, shift.text
    session_id = shift.json()["data"].get("session_id") or shift.json()["data"]["id"]
    sale = await ac.post(
        "/api/v1/pos/sales",
        headers=admin,
        json={
            "session_id": session_id,
            "payment_method": "cash",
            "items": [{"product_id": plate["id"], "quantity": 1}],
        },
    )
    assert sale.status_code == 200, sale.text
    closed = await ac.post(
        f"/api/v1/pos/sessions/{session_id}/close",
        headers=admin,
        json={"actual_cash": 20},
    )
    assert closed.status_code == 200, closed.text
    refund_shift = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=admin,
        json={"opening_cash": 20, "store_id": floor_id},
    )
    assert refund_shift.status_code == 200, refund_shift.text
    restored = await ac.post(
        f"/api/v1/pos/sales/{sale.json()['data']['id']}/returns",
        headers=admin,
        json={"items": [{"product_id": plate["id"], "quantity": 1}], "reason": "other"},
    )
    assert restored.status_code == 200, restored.text
    floor_pnl = await ac.get(f"/api/v1/reports/profit-loss?store_id={floor_id}", headers=admin)
    assert floor_pnl.status_code == 200, floor_pnl.text
    body = floor_pnl.json()["data"]
    assert body["revenue"] == 0
    assert body["cogs"] == 0
    assert body["net_profit"] == 0
    other_pnl = await ac.get(f"/api/v1/reports/profit-loss?store_id={other_id}", headers=admin)
    assert other_pnl.json()["data"]["net_profit"] == 0
    company = await ac.get("/api/v1/reports/profit-loss", headers=admin)
    assert company.json()["data"]["revenue"] == 0
    assert company.json()["data"]["net_profit"] == 0
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    hotel = await ac.get(f"/api/v1/reports/profit-loss?store_id={floor_id}", headers=admin)
    assert hotel.json()["data"]["revenue"] == 0
    assert hotel.json()["data"]["net_profit"] == 0


async def test_restaurant_till_return_restocks_the_store_on_the_receipt(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    floor = await ac.post("/api/v1/stores", json={"name": "Restock Floor", "code": "VAL212"}, headers=admin)
    assert floor.status_code == 200, floor.text
    other = await ac.post("/api/v1/stores", json={"name": "Restock Other", "code": "VAL213"}, headers=admin)
    assert other.status_code == 200, other.text
    floor_id = floor.json()["data"]["id"]
    other_id = other.json()["data"]["id"]
    warehouses = await ac.get("/api/v1/warehouses", headers=admin)
    assert warehouses.status_code == 200, warehouses.text
    room = next(row for row in warehouses.json()["data"] if row.get("store_id") == floor_id)
    plate = await _product(ac, admin, name="Restock plate", selling_price=20, cost_price=4, stock_qty=0)
    received = await ac.post(
        "/api/v1/inventory/stock-in",
        headers=admin,
        json={"product_id": plate["id"], "quantity": 5, "warehouse_id": room["id"]},
    )
    assert received.status_code == 200, received.text
    shift = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=admin,
        json={"opening_cash": 0, "store_id": floor_id},
    )
    assert shift.status_code == 200, shift.text
    session_id = shift.json()["data"].get("session_id") or shift.json()["data"]["id"]
    sale = await ac.post(
        "/api/v1/pos/sales",
        headers=admin,
        json={
            "session_id": session_id,
            "payment_method": "cash",
            "items": [{"product_id": plate["id"], "quantity": 1}],
        },
    )
    assert sale.status_code == 200, sale.text
    closed = await ac.post(
        f"/api/v1/pos/sessions/{session_id}/close",
        headers=admin,
        json={"actual_cash": 20},
    )
    assert closed.status_code == 200, closed.text
    refund_shift = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=admin,
        json={"opening_cash": 20, "store_id": other_id},
    )
    assert refund_shift.status_code == 200, refund_shift.text
    restored = await ac.post(
        f"/api/v1/pos/sales/{sale.json()['data']['id']}/returns",
        headers=admin,
        json={"items": [{"product_id": plate["id"], "quantity": 1}], "reason": "other"},
    )
    assert restored.status_code == 200, restored.text
    floor_value = await ac.get(f"/api/v1/reports/inventory/valuation?store_id={floor_id}", headers=admin)
    assert floor_value.status_code == 200, floor_value.text
    assert floor_value.json()["data"]["total_quantity"] == 5
    assert floor_value.json()["data"]["total_value"] == 20
    other_value = await ac.get(f"/api/v1/reports/inventory/valuation?store_id={other_id}", headers=admin)
    assert other_value.json()["data"]["total_value"] == 0
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    denied = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={"service_mode": "takeaway", "payment_method": "cash", "lines": [{"product_id": plate["id"], "quantity": 1}]},
    )
    assert denied.status_code == 403


async def test_restaurant_till_return_is_listed_for_the_store_on_the_receipt(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    floor = await ac.post("/api/v1/stores", json={"name": "Listed Floor", "code": "RET213"}, headers=admin)
    assert floor.status_code == 200, floor.text
    other = await ac.post("/api/v1/stores", json={"name": "Listed Other", "code": "RET214"}, headers=admin)
    assert other.status_code == 200, other.text
    floor_id = floor.json()["data"]["id"]
    other_id = other.json()["data"]["id"]
    warehouses = await ac.get("/api/v1/warehouses", headers=admin)
    room = next(row for row in warehouses.json()["data"] if row.get("store_id") == floor_id)
    plate = await _product(ac, admin, name="Listed return plate", selling_price=20, cost_price=4, stock_qty=0)
    received = await ac.post(
        "/api/v1/inventory/stock-in",
        headers=admin,
        json={"product_id": plate["id"], "quantity": 2, "warehouse_id": room["id"]},
    )
    assert received.status_code == 200, received.text
    shift = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=admin,
        json={"opening_cash": 0, "store_id": floor_id},
    )
    assert shift.status_code == 200, shift.text
    session_id = shift.json()["data"].get("session_id") or shift.json()["data"]["id"]
    sale = await ac.post(
        "/api/v1/pos/sales",
        headers=admin,
        json={
            "session_id": session_id,
            "payment_method": "cash",
            "items": [{"product_id": plate["id"], "quantity": 1}],
        },
    )
    assert sale.status_code == 200, sale.text
    closed = await ac.post(
        f"/api/v1/pos/sessions/{session_id}/close",
        headers=admin,
        json={"actual_cash": 20},
    )
    assert closed.status_code == 200, closed.text
    refund_shift = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=admin,
        json={"opening_cash": 20, "store_id": other_id},
    )
    assert refund_shift.status_code == 200, refund_shift.text
    restored = await ac.post(
        f"/api/v1/pos/sales/{sale.json()['data']['id']}/returns",
        headers=admin,
        json={"items": [{"product_id": plate["id"], "quantity": 1}], "reason": "other"},
    )
    assert restored.status_code == 200, restored.text
    floor_returns = await ac.get(f"/api/v1/reports/sales/returns?store_id={floor_id}", headers=admin)
    assert floor_returns.status_code == 200, floor_returns.text
    assert floor_returns.json()["data"]["return_count"] == 1
    assert floor_returns.json()["data"]["total_amount"] == 20
    other_returns = await ac.get(f"/api/v1/reports/sales/returns?store_id={other_id}", headers=admin)
    assert other_returns.json()["data"]["return_count"] == 0
    assert other_returns.json()["data"]["total_amount"] == 0
    company = await ac.get("/api/v1/reports/sales/returns", headers=admin)
    assert company.json()["data"]["return_count"] == 1
    assert company.json()["data"]["total_amount"] == 20
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    denied = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={"service_mode": "takeaway", "payment_method": "cash", "lines": [{"product_id": plate["id"], "quantity": 1}]},
    )
    assert denied.status_code == 403


async def test_restaurant_till_return_comes_off_store_sales_today(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    floor = await ac.post("/api/v1/stores", json={"name": "Today Floor", "code": "TDY214"}, headers=admin)
    assert floor.status_code == 200, floor.text
    other = await ac.post("/api/v1/stores", json={"name": "Today Other", "code": "TDY215"}, headers=admin)
    assert other.status_code == 200, other.text
    floor_id = floor.json()["data"]["id"]
    other_id = other.json()["data"]["id"]
    warehouses = await ac.get("/api/v1/warehouses", headers=admin)
    room = next(row for row in warehouses.json()["data"] if row.get("store_id") == floor_id)
    plate = await _product(ac, admin, name="Today return plate", selling_price=20, cost_price=4, stock_qty=0)
    received = await ac.post(
        "/api/v1/inventory/stock-in",
        headers=admin,
        json={"product_id": plate["id"], "quantity": 2, "warehouse_id": room["id"]},
    )
    assert received.status_code == 200, received.text
    shift = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=admin,
        json={"opening_cash": 0, "store_id": floor_id},
    )
    assert shift.status_code == 200, shift.text
    session_id = shift.json()["data"].get("session_id") or shift.json()["data"]["id"]
    sale = await ac.post(
        "/api/v1/pos/sales",
        headers=admin,
        json={
            "session_id": session_id,
            "payment_method": "cash",
            "items": [{"product_id": plate["id"], "quantity": 1}],
        },
    )
    assert sale.status_code == 200, sale.text
    closed = await ac.post(
        f"/api/v1/pos/sessions/{session_id}/close",
        headers=admin,
        json={"actual_cash": 20},
    )
    assert closed.status_code == 200, closed.text
    refund_shift = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=admin,
        json={"opening_cash": 20, "store_id": other_id},
    )
    assert refund_shift.status_code == 200, refund_shift.text
    restored = await ac.post(
        f"/api/v1/pos/sales/{sale.json()['data']['id']}/returns",
        headers=admin,
        json={"items": [{"product_id": plate["id"], "quantity": 1}], "reason": "other"},
    )
    assert restored.status_code == 200, restored.text
    cashier = (
        await db_session.execute(select(m.User).where(m.User.email == "cashier@alpha.example.com"))
    ).scalar_one()
    db_session.add(
        m.UserStoreMembership(
            tenant_id=seed["t1"].id,
            user_id=cashier.id,
            store_id=floor_id,
            is_active=True,
        )
    )
    await db_session.commit()
    scoped = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    home = await ac.get("/api/v1/restaurant/summary", headers=scoped)
    assert home.status_code == 200, home.text
    assert home.json()["data"]["till_sales_today"] == 0
    assert home.json()["data"]["sales_today"] == 0
    company = await ac.get("/api/v1/restaurant/summary", headers=admin)
    assert company.json()["data"]["till_sales_today"] == 0
    assert company.json()["data"]["sales_today"] == 0
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    hotel = await ac.get("/api/v1/restaurant/summary", headers=admin)
    assert hotel.status_code == 403
