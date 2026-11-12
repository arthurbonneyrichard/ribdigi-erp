"""Bakery counter sales rung offline book once, wait for an open till, and never take the device's price."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from tests.test_bakery_desk import _bake, _bread, _open_till, _owner

pytestmark = pytest.mark.asyncio


def _sale(ref, product_id, *, qty=2, method="cash", charged=20, when=None):
    return {
        "offline_ref": ref,
        "created_at": (when or datetime.utcnow() - timedelta(minutes=15)).isoformat(),
        "payment_method": method,
        "charged_total": charged,
        "lines": [{"product_id": product_id, "quantity": qty}],
    }


async def test_bakery_offline_sale_waits_for_till_then_books_once(client, db_session):
    ac, seed = client
    h = await _owner(ac, seed, db_session)
    _flour, loaf, recipe = await _bread(ac, h, db_session, seed, price=10)
    await _bake(ac, h, recipe)
    body = {"device_id": "bake-01", "sales": [_sale("bk-00000001", loaf.id)]}
    waiting = await ac.post("/api/v1/bakery/till/offline/sync", json=body, headers=h)
    assert waiting.status_code == 200, waiting.text
    assert waiting.json()["data"]["results"][0]["status"] == "waiting"
    await _open_till(ac, h)
    first = await ac.post("/api/v1/bakery/till/offline/sync", json=body, headers=h)
    row = first.json()["data"]["results"][0]
    assert row["status"] == "booked", row
    assert row["booked_total"] == 20.0 and row["difference"] == 0.0
    again = await ac.post("/api/v1/bakery/till/offline/sync", json=body, headers=h)
    assert again.json()["data"]["results"][0]["status"] == "already_booked"
    assert again.json()["data"]["results"][0]["sale_id"] == row["sale_id"]


async def test_bakery_offline_refuses_old_and_wallet(client, db_session):
    ac, seed = client
    h = await _owner(ac, seed, db_session)
    _flour, loaf, recipe = await _bread(ac, h, db_session, seed, price=10)
    await _bake(ac, h, recipe)
    await _open_till(ac, h)
    sales = [
        _sale("bk-old000001", loaf.id, when=datetime.utcnow() - timedelta(hours=80)),
        _sale("bk-wallet001", loaf.id, method="wallet"),
        _sale("bk-cheap0001", loaf.id, charged=15),
    ]
    res = await ac.post("/api/v1/bakery/till/offline/sync", json={"sales": sales}, headers=h)
    by_ref = {r["offline_ref"]: r for r in res.json()["data"]["results"]}
    assert by_ref["bk-old000001"]["status"] == "refused"
    assert by_ref["bk-wallet001"]["status"] == "refused"
    assert by_ref["bk-cheap0001"]["status"] == "booked"
    assert by_ref["bk-cheap0001"]["difference"] == 5.0


async def test_bakery_offline_price_sheet(client, db_session):
    ac, seed = client
    h = await _owner(ac, seed, db_session)
    _flour, loaf, _recipe = await _bread(ac, h, db_session, seed, price=10)
    res = await ac.get("/api/v1/bakery/till/offline/prices", headers=h)
    assert res.status_code == 200, res.text
    assert res.json()["data"]["items"][loaf.id]["price"] == 10.0
