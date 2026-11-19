"""Regulars found from orders, birthdays, opt-in birthday texts sent once a year."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app import sms
from tests.test_bakery_desk import _owner, _product

R = "/api/v1/bakery/regulars"


async def _order(ac, h, loaf, phone, name, qty=2):
    r = await ac.post(
        "/api/v1/bakery/orders", headers=h,
        json={"customer_name": name, "phone": phone, "due_date": (date.today() + timedelta(days=1)).isoformat(),
              "lines": [{"product_id": loaf.id, "quantity": qty}]},
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]


@pytest.mark.asyncio
async def test_regulars_come_from_orders_and_birthdays_text_once(client, seeded, db_session):
    ac, seed = client
    h = await _owner(ac, seed, db_session)
    loaf = await _product(db_session, seed, "Loaf", price=10)
    await _order(ac, h, loaf, "+233241234567", "Ama Boateng", 2)
    await _order(ac, h, loaf, "+233241234567", "Ama Boateng", 3)
    await _order(ac, h, loaf, "+233201112222", "Kofi Asare", 1)

    rows = (await ac.get(R, headers=h)).json()["data"]
    ama = next(r for r in rows if r["phone"] == "+233241234567")
    assert ama["orders"] == 2 and ama["spent"] == 50 and rows[0]["phone"] == ama["phone"]

    # Unknown phone cannot be saved; half a birthday and impossible dates are refused.
    assert (await ac.put(R, headers=h, json={"phone": "+233500000000", "texts_ok": True})).status_code == 404
    assert (await ac.put(R, headers=h, json={"phone": ama["phone"], "birth_month": 5})).status_code == 422
    assert (await ac.put(R, headers=h, json={"phone": ama["phone"], "birth_month": 2, "birth_day": 30})).status_code == 422

    today = date.today()
    ok = await ac.put(R, headers=h, json={"phone": ama["phone"], "birth_month": today.month, "birth_day": today.day, "texts_ok": True})
    assert ok.status_code == 200 and ok.json()["data"]["texts_ok"] is True
    # Kofi has a birthday today but has not said yes to texts.
    await ac.put(R, headers=h, json={"phone": "+233201112222", "birth_month": today.month, "birth_day": today.day})

    soon = (await ac.get(f"{R}/birthdays?days=7", headers=h)).json()["data"]
    assert {r["phone"] for r in soon} == {"+233241234567", "+233201112222"} and soon[0]["in_days"] == 0

    sms.clear_dev_outbox()
    first = (await ac.post(f"{R}/birthday-texts", headers=h)).json()["data"]
    assert first["birthdays_today"] == 1  # only the one who agreed
    if first["sent"]:
        assert len(sms.get_dev_outbox()) == 1 and "Happy birthday" in sms.get_dev_outbox()[0]["body"]
        again = (await ac.post(f"{R}/birthday-texts", headers=h)).json()["data"]
        assert again["sent"] == 0 and again["already_texted"] == 1
    else:
        assert first["failed"] and "reason" in first["failed"][0]


@pytest.mark.asyncio
async def test_part_payments_and_refund_by_method(client, seeded, db_session):
    from tests.test_bakery_desk import _open_till

    ac, seed = client
    h = await _owner(ac, seed, db_session)
    cake = await _product(db_session, seed, "Wedding cake", price=1000)
    await _open_till(ac, h)
    due = (date.today() + timedelta(days=10)).isoformat()
    r = await ac.post(
        "/api/v1/bakery/orders", headers=h,
        json={"customer_name": "Esi Quaye", "due_date": due, "lines": [{"product_id": cake.id, "quantity": 1}],
              "deposit": 200, "deposit_method": "cash"},
    )
    assert r.status_code == 200, r.text
    oid = r.json()["data"]["id"]
    total = r.json()["data"]["total"]

    p2 = await ac.post(f"/api/v1/bakery/orders/{oid}/part-payment", headers=h, json={"amount": 300, "method": "mobile_money"})
    assert p2.status_code == 200 and p2.json()["data"]["deposit"] == 500
    assert p2.json()["data"]["balance"] == round(total - 500, 2)
    too_much = await ac.post(f"/api/v1/bakery/orders/{oid}/part-payment", headers=h, json={"amount": total, "method": "cash"})
    assert too_much.status_code == 422

    # Cancel and refund: each part goes back the way it came (200 cash, 300 Mobile Money).
    c = await ac.post(f"/api/v1/bakery/orders/{oid}/cancel", headers=h, json={"reason": "Wedding called off", "deposit_action": "refund"})
    assert c.status_code == 200, c.text
    assert c.json()["data"]["status"] == "cancelled"

    done = await ac.post(f"/api/v1/bakery/orders/{oid}/part-payment", headers=h, json={"amount": 10})
    assert done.status_code == 409
    from sqlalchemy import select

    from app import models as m

    rows = (await db_session.execute(select(m.BakeryPayment).where(m.BakeryPayment.order_id == oid))).scalars().all()
    refunds = {p.method: float(p.amount) for p in rows if p.kind == "deposit_refund"}
    assert refunds == {"cash": -200.0, "mobile_money": -300.0}
    assert sum(float(p.amount) for p in rows) == 0  # money in and money out cancel
