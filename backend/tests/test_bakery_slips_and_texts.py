"""Order slip, production sheet and the 'your order is ready' text."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app import sms
from tests.test_bakery_desk import _bread, _open_till, _order, _owner


@pytest.mark.asyncio
async def test_order_slip_sheet_and_ready_text(client, seeded, db_session):
    ac, seed = client
    h = await _owner(ac, seed, db_session)
    _flour, loaf, _recipe = await _bread(ac, h, db_session, seed)
    await _open_till(ac, h)
    r = await ac.post(
        "/api/v1/bakery/orders", headers=h,
        json={
            "customer_name": "Ama Boateng", "phone": "+233241234567",
            "due_date": (date.today() + timedelta(days=1)).isoformat(),
            "lines": [{"product_id": loaf.id, "quantity": 4, "note": "Happy birthday Kofi"}],
            "deposit": 10, "deposit_method": "cash",
        },
    )
    assert r.status_code == 200, r.text
    order = r.json()["data"]

    slip = await ac.get(f"/api/v1/bakery/orders/{order['id']}/print", headers=h)
    assert slip.status_code == 200
    assert "Happy birthday Kofi" in slip.text and order["order_number"] in slip.text
    assert "To pay on collection" in slip.text

    sheet = await ac.get("/api/v1/bakery/production-sheet/print", headers=h)
    assert sheet.status_code == 200
    assert "Production sheet" in sheet.text and "Happy birthday Kofi" in sheet.text

    sms.clear_dev_outbox()
    ready = await ac.post(f"/api/v1/bakery/orders/{order['id']}/ready", headers=h, json={})
    assert ready.status_code == 200, ready.text
    texted = ready.json()["data"]["customer_texted"]
    assert "sent" in texted
    if texted["sent"]:
        assert any(o["to"].endswith("233241234567") and order["order_number"] in o["body"] for o in sms.get_dev_outbox())


@pytest.mark.asyncio
async def test_ready_without_phone_still_works(client, seeded, db_session):
    ac, seed = client
    h = await _owner(ac, seed, db_session)
    _flour, loaf, _recipe = await _bread(ac, h, db_session, seed)
    order = await _order(ac, h, loaf)
    ready = await ac.post(f"/api/v1/bakery/orders/{order['id']}/ready", headers=h, json={})
    assert ready.status_code == 200
    assert ready.json()["data"]["status"] == "ready"
    assert ready.json()["data"]["customer_texted"]["sent"] is False
