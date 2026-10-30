"""Restaurant public website: one page to order food and drink (pickup or delivery) and book a table."""

from __future__ import annotations

import pytest
from datetime import datetime, timedelta

from tests.conftest import auth_headers, set_tenant_industry

pytestmark = pytest.mark.asyncio


async def _menu_item(ac, headers, name, price, station="kitchen", **extra):
    body = {"name": name, "selling_price": price, "stock_qty": 50, **extra}
    if station:
        body["prep_station"] = station
    created = await ac.post(
        "/api/v1/products",
        json=body,
        headers=headers,
    )
    assert created.status_code == 200, created.text
    return created.json()["data"]


async def _open_site(ac, headers, *, orders=True, booking=True):
    if orders:
        opened = await ac.put("/api/v1/restaurant/online-orders", headers=headers, json={"open": True})
        assert opened.status_code == 200, opened.text
    if booking:
        link = await ac.put(
            "/api/v1/restaurant/booking-link", headers=headers, json={"hostname": "eat.example", "link_kind": "new"}
        )
        assert link.status_code == 200, link.text


async def test_site_is_closed_until_orders_or_booking_open(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    closed = await ac.get("/api/v1/public/restaurant-site/alpha")
    assert closed.status_code == 404, closed.text
    # A retail company never gets a restaurant website.
    await set_tenant_industry(db_session, seed["t1"], "retail")
    assert (await ac.get("/api/v1/public/restaurant-site/alpha")).status_code == 404


async def test_site_menu_order_track_and_book(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    jollof = await _menu_item(ac, admin, "Jollof", 40, category="Mains", description="Smoky party jollof")
    sobolo = await _menu_item(ac, admin, "Sobolo", 10, station="bar", category="Drinks")
    rice = await _menu_item(ac, admin, "Rice", 2, station="")  # an ingredient, not on the menu
    await _open_site(ac, admin)

    page = await ac.get("/api/v1/public/restaurant-site/alpha")
    assert page.status_code == 200, page.text
    body = page.json()["data"]
    assert body["ordering_open"] is True and body["booking_open"] is True
    names = {row["name"]: row for row in body["menu"]}
    assert set(names) == {"Jollof", "Sobolo"}
    assert names["Jollof"]["category"] == "Mains" and names["Jollof"]["description"] == "Smoky party jollof"
    assert names["Sobolo"]["kind"] == "drink"

    off_menu = await ac.post(
        "/api/v1/public/restaurant-site/alpha/order",
        json={"service": "pickup", "customer_name": "Esi", "phone": "+233201234567",
              "lines": [{"product_id": rice["id"], "quantity": 1}]},
    )
    assert off_menu.status_code == 422, off_menu.text
    no_address = await ac.post(
        "/api/v1/public/restaurant-site/alpha/order",
        json={"service": "delivery", "customer_name": "Esi", "phone": "+233201234567",
              "lines": [{"product_id": jollof["id"], "quantity": 1}]},
    )
    assert no_address.status_code == 422, no_address.text

    placed = await ac.post(
        "/api/v1/public/restaurant-site/alpha/order",
        json={
            "service": "delivery", "customer_name": "Esi Mensah", "phone": "+233201234567",
            "pay_with": "mobile_money", "delivery_address": "12 Oxford St, Osu", "allergy": "No peanuts",
            "lines": [{"product_id": jollof["id"], "quantity": 2}, {"product_id": sobolo["id"], "quantity": 1}],
        },
    )
    assert placed.status_code == 200, placed.text
    order = placed.json()["data"]
    assert order["status_words"] == "Received" and order["service"] == "delivery"
    assert {i["name"] for i in order["items"]} == {"Jollof", "Sobolo"}

    # The restaurant sees it on its Orders board, marked as online, with the guest details.
    desk = (await ac.get("/api/v1/restaurant/orders", headers=admin)).json()["data"]
    mine = next(row for row in desk if row["id"] == order["id"])
    assert mine["channel"] and mine["service_mode"] == "delivery"
    assert mine["phone"] == "+233201234567" and mine["allergy"] == "No peanuts"
    assert mine["payment_method"] == "mobile_money"

    sent = await ac.post(f"/api/v1/restaurant/orders/{order['id']}/send", headers=admin)
    assert sent.status_code == 200, sent.text
    tracked = await ac.get(f"/api/v1/public/restaurant-site/alpha/order/{order['id']}")
    assert tracked.json()["data"]["status_words"] == "In the kitchen"

    when = (datetime.utcnow() + timedelta(days=1)).replace(microsecond=0).isoformat()
    booked = await ac.post(
        "/api/v1/public/restaurant-site/alpha/book",
        json={
            "guest_name": "Kojo", "phone": "+233241112233", "party_size": 4, "booked_for": when,
            "notes": "Window seat", "pre_order": [{"product_id": jollof["id"], "quantity": 4}],
        },
    )
    assert booked.status_code == 200, booked.text
    note = booked.json()["data"]["notes"]
    assert "Window seat" in note and "Pre-order: 4× Jollof" in note


async def test_site_respects_sold_out_and_closed_orders(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    dish = await _menu_item(ac, admin, "Banku", 30)
    await _open_site(ac, admin, orders=False)
    page = (await ac.get("/api/v1/public/restaurant-site/alpha")).json()["data"]
    assert page["ordering_open"] is False and page["booking_open"] is True
    refused = await ac.post(
        "/api/v1/public/restaurant-site/alpha/order",
        json={"service": "pickup", "customer_name": "Ama", "phone": "+233201234567",
              "lines": [{"product_id": dish["id"], "quantity": 1}]},
    )
    assert refused.status_code == 404, refused.text
    await _open_site(ac, admin, booking=False)
    marked = await ac.put("/api/v1/restaurant/sold-out", headers=admin, json={"product_ids": [dish["id"]]})
    assert marked.status_code == 200, marked.text
    sold = await ac.post(
        "/api/v1/public/restaurant-site/alpha/order",
        json={"service": "pickup", "customer_name": "Ama", "phone": "+233201234567",
              "lines": [{"product_id": dish["id"], "quantity": 1}]},
    )
    assert sold.status_code == 409, sold.text
    assert "sold out" in sold.json()["detail"]
