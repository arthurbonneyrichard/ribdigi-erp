"""Retail till, 15 Nov 2026: held sales, layaway (money held until collected), serial numbers,
and a Mobile Money prompt paying a till sale once."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app import models as m
from tests.test_pos_till_returns import _admin, _fresh_shift


async def _balance(db_session, tenant_id, code) -> float:
    value = (
        await db_session.execute(select(m.Account.balance).where(m.Account.tenant_id == tenant_id, m.Account.code == code))
    ).scalar_one_or_none()
    return round(float(value or 0), 2)


@pytest.mark.asyncio
async def test_held_sale_is_parked_and_picked_up_once(client, db_session):
    ac, seed = client
    h = await _admin(ac, seed)
    product = seed["p1"]
    held = await ac.post(
        "/api/v1/pos/held",
        headers=h,
        json={"label": "Lady in red", "items": [{"product_id": product.id, "quantity": 2, "unit_price": 10, "name": "Soap"}]},
    )
    assert held.status_code == 200, held.text
    held_id = held.json()["data"]["id"]
    assert held.json()["data"]["total"] == 20
    listed = (await ac.get("/api/v1/pos/held", headers=h)).json()["data"]
    assert any(r["id"] == held_id for r in listed)
    taken = await ac.post(f"/api/v1/pos/held/{held_id}/take", headers=h, json={})
    assert taken.status_code == 200, taken.text
    assert taken.json()["data"]["cart"]["items"][0]["name"] == "Soap"
    again = await ac.post(f"/api/v1/pos/held/{held_id}/take", headers=h, json={})
    assert again.status_code == 404


@pytest.mark.asyncio
async def test_layaway_holds_goods_and_money_until_paid_in_full(client, db_session):
    ac, seed = client
    h = await _admin(ac, seed)
    tenant_id = seed["t1"].id
    product = seed["p1"]
    product.stock_qty = 10
    product.selling_price = 100
    await db_session.commit()

    opened = await ac.post(
        "/api/v1/pos/layaways",
        headers=h,
        json={"customer_name": "Akosua", "phone": "+233241234567", "items": [{"product_id": product.id, "quantity": 2}], "deposit": 50},
    )
    assert opened.status_code == 200, opened.text
    lay = opened.json()["data"]
    total = lay["total"]
    assert lay["paid"] == 50 and lay["status"] == "open"
    await db_session.refresh(product)
    assert float(product.stock_qty) == 8  # set aside, cannot be sold twice
    assert await _balance(db_session, tenant_id, "2155") == 50  # money held, not a sale
    sales_before = await _balance(db_session, tenant_id, "4000")

    too_much = await ac.post(f"/api/v1/pos/layaways/{lay['id']}/payments", headers=h, json={"amount": total})
    assert too_much.status_code == 422
    done = await ac.post(f"/api/v1/pos/layaways/{lay['id']}/payments", headers=h, json={"amount": round(total - 50, 2)})
    assert done.status_code == 200, done.text
    assert done.json()["data"]["status"] == "completed"
    assert await _balance(db_session, tenant_id, "2155") == 0
    assert round(await _balance(db_session, tenant_id, "4000") - sales_before, 2) == round(total - lay["tax"], 2)


@pytest.mark.asyncio
async def test_cancelled_layaway_puts_goods_back_and_keeps_only_the_fee(client, db_session):
    ac, seed = client
    h = await _admin(ac, seed)
    tenant_id = seed["t1"].id
    product = seed["p1"]
    product.stock_qty = 5
    product.selling_price = 40
    await db_session.commit()
    lay = (
        await ac.post(
            "/api/v1/pos/layaways",
            headers=h,
            json={"customer_name": "Yaw", "phone": "+233201234567", "items": [{"product_id": product.id, "quantity": 1}], "deposit": 30},
        )
    ).json()["data"]
    other_before = await _balance(db_session, tenant_id, "4400")
    cancel = await ac.post(
        f"/api/v1/pos/layaways/{lay['id']}/cancel", headers=h, json={"reason": "Customer changed mind", "keep": 5}
    )
    assert cancel.status_code == 200, cancel.text
    assert cancel.json()["data"]["status"] == "cancelled"
    await db_session.refresh(product)
    assert float(product.stock_qty) == 5
    assert round(await _balance(db_session, tenant_id, "4400") - other_before, 2) == 5
    assert await _balance(db_session, tenant_id, "2155") == 0


@pytest.mark.asyncio
async def test_serial_numbered_goods_are_received_and_sold_by_serial(client, db_session):
    ac, seed = client
    h = await _admin(ac, seed)
    product = seed["p1"]
    product.tracks_serials = True
    product.selling_price = 900
    await db_session.commit()

    missing = await ac.post("/api/v1/inventory/stock-in", headers=h, json={"product_id": product.id, "quantity": 2, "serials": ["IMEI-1"]})
    assert missing.status_code == 422
    ok = await ac.post(
        "/api/v1/inventory/stock-in", headers=h, json={"product_id": product.id, "quantity": 2, "serials": ["imei-1", "IMEI-2"]}
    )
    assert ok.status_code == 200, ok.text
    dup = await ac.post("/api/v1/inventory/stock-in", headers=h, json={"product_id": product.id, "quantity": 1, "serials": ["IMEI-1"]})
    assert dup.status_code == 409

    session_id = await _fresh_shift(ac, h)
    no_serial = await ac.post(
        "/api/v1/pos/sales", headers=h,
        json={"session_id": session_id, "payment_method": "cash", "items": [{"product_id": product.id, "quantity": 1, "unit_price": 900}]},
    )
    assert no_serial.status_code == 422
    sold = await ac.post(
        "/api/v1/pos/sales", headers=h,
        json={"session_id": session_id, "payment_method": "cash", "items": [{"product_id": product.id, "quantity": 1, "unit_price": 900, "serials": ["IMEI-2"]}]},
    )
    assert sold.status_code == 200, sold.text
    found = (await ac.get("/api/v1/inventory/serials?q=imei-2", headers=h)).json()["data"]
    assert found[0]["status"] == "sold" and found[0]["sold_ref"]
    sale_id = sold.json()["data"]["id"]
    back = await ac.post(
        f"/api/v1/pos/sales/{sale_id}/returns", headers=h,
        json={"items": [{"product_id": product.id, "quantity": 1, "serials": ["IMEI-1"]}], "reason": "defective"},
    )
    assert back.status_code == 409  # IMEI-1 was never sold on this receipt
    back = await ac.post(
        f"/api/v1/pos/sales/{sale_id}/returns", headers=h,
        json={"items": [{"product_id": product.id, "quantity": 1, "serials": ["IMEI-2"]}], "reason": "customer_change"},
    )
    assert back.status_code == 200, back.text
    found = (await ac.get("/api/v1/inventory/serials?q=imei-2", headers=h)).json()["data"]
    assert found[0]["status"] == "in_stock"
    resell = await ac.post(
        "/api/v1/pos/sales", headers=h,
        json={"session_id": session_id, "payment_method": "cash", "items": [{"product_id": product.id, "quantity": 1, "unit_price": 900, "serials": ["IMEI-2"]}]},
    )
    assert resell.status_code == 200, resell.text  # back on the shelf, so it can be sold again


@pytest.mark.asyncio
async def test_mobile_money_prompt_pays_one_till_sale(client, db_session):
    ac, seed = client
    h = await _admin(ac, seed)
    product = seed["p1"]
    product.stock_qty = float(product.stock_qty or 0) + 5
    product.selling_price = 25
    await db_session.commit()
    session_id = await _fresh_shift(ac, h)
    sent = await ac.post("/api/v1/pos/momo", headers=h, json={"amount": 25, "phone": "0551234567", "provider": "airteltigo"})
    assert sent.status_code == 200, sent.text
    ref = sent.json()["data"]["reference"]
    body = {
        "session_id": session_id,
        "payment_method": "split",
        "items": [{"product_id": product.id, "quantity": 1, "unit_price": 25}],
        "payments": [{"payment_method": "mobile_money", "amount": 25, "reference": ref}],
    }
    first = await ac.post("/api/v1/pos/sales", headers=h, json=body)
    assert first.status_code == 200, first.text
    second = await ac.post("/api/v1/pos/sales", headers=h, json=body)
    assert second.status_code == 409
