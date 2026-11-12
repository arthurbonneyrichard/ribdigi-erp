"""Restaurant till sales rung offline book once, at menu prices, into the open shift."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from tests.conftest import auth_headers, set_tenant_industry

pytestmark = pytest.mark.asyncio


async def _setup(ac, db_session, seed):
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    dish = await ac.post(
        "/api/v1/products",
        json={"name": "Jollof plate", "selling_price": 40, "stock_qty": 50, "prep_station": "kitchen"},
        headers=admin,
    )
    assert dish.status_code == 200, dish.text
    shift = await ac.post("/api/v1/restaurant/till/shift/open", headers=admin, json={"opening_cash": 0})
    assert shift.status_code == 200, shift.text
    return admin, dish.json()["data"]["id"], shift.json()["data"]["id"]


def _sale(ref, dish_id, *, when=None, method="cash", charged=80):
    return {
        "offline_ref": ref,
        "created_at": (when or datetime.utcnow() - timedelta(minutes=20)).isoformat(),
        "service_mode": "takeaway",
        "payment_method": method,
        "charged_total": charged,
        "lines": [{"product_id": dish_id, "quantity": "2"}],
    }


async def test_offline_sale_books_once(client, db_session):
    ac, seed = client
    admin, dish, shift_id = await _setup(ac, db_session, seed)
    body = {"device_id": "till-01", "sales": [_sale("off-abc12345", dish)]}
    first = await ac.post("/api/v1/restaurant/till/offline/sync", json=body, headers=admin)
    assert first.status_code == 200, first.text
    row = first.json()["data"]["results"][0]
    assert row["status"] == "booked"
    assert row["booked_total"] == 80.0 and row["difference"] == 0.0
    assert row["no_shift"] is False
    again = await ac.post("/api/v1/restaurant/till/offline/sync", json=body, headers=admin)
    assert again.json()["data"]["results"][0]["status"] == "already_booked"
    assert again.json()["data"]["results"][0]["order_id"] == row["order_id"]
    orders = (await ac.get("/api/v1/restaurant/orders", headers=admin)).json()["data"]
    assert len([o for o in orders if o["id"] == row["order_id"]]) == 1


async def test_offline_refuses_old_future_and_wallet(client, db_session):
    ac, seed = client
    admin, dish, _ = await _setup(ac, db_session, seed)
    sales = [
        _sale("off-old000001", dish, when=datetime.utcnow() - timedelta(hours=80)),
        _sale("off-future001", dish, when=datetime.utcnow() + timedelta(hours=2)),
        _sale("off-wallet001", dish, method="wallet"),
        _sale("off-good00001", dish, charged=70),
    ]
    res = await ac.post("/api/v1/restaurant/till/offline/sync", json={"sales": sales}, headers=admin)
    assert res.status_code == 200, res.text
    by_ref = {r["offline_ref"]: r for r in res.json()["data"]["results"]}
    assert by_ref["off-old000001"]["status"] == "refused"
    assert by_ref["off-future001"]["status"] == "refused"
    assert by_ref["off-wallet001"]["status"] == "refused"
    assert by_ref["off-good00001"]["status"] == "booked"
    # The device charged 70; the menu says 80. The difference is shown, not hidden.
    assert by_ref["off-good00001"]["difference"] == 10.0


async def test_offline_sync_rejects_device_prices(client, db_session):
    ac, seed = client
    admin, dish, _ = await _setup(ac, db_session, seed)
    sale = _sale("off-price0001", dish)
    sale["lines"][0]["unit_price"] = 1
    res = await ac.post("/api/v1/restaurant/till/offline/sync", json={"sales": [sale]}, headers=admin)
    assert res.status_code == 422


async def test_offline_price_sheet_lists_dishes(client, db_session):
    ac, seed = client
    admin, dish, _ = await _setup(ac, db_session, seed)
    res = await ac.get("/api/v1/restaurant/till/offline/prices", headers=admin)
    assert res.status_code == 200, res.text
    body = res.json()["data"]
    assert body["items"][dish]["price"] == 40.0
    assert "service_percent" in body and "service_tax_percent" in body
