"""New sales order notifications (BR-15.1)."""

from __future__ import annotations

import pyotp
import pytest
from sqlalchemy import select

from app import models as m
from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_create_and_confirm_order_emit_new_order_notifications(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    product = seed["p1"]
    product.stock_qty = float(product.stock_qty or 0) + 20
    await db_session.commit()

    stores = await ac.get("/api/v1/stores", headers=headers)
    assert stores.status_code == 200
    store_list = stores.json()["data"] or []
    if not store_list:
        created = await ac.post(
            "/api/v1/stores",
            headers=headers,
            json={"code": "SO-N1", "name": "Notify Store"},
        )
        assert created.status_code == 200, created.text
        store_id = created.json()["data"]["id"]
    else:
        store_id = store_list[0]["id"]

    created = await ac.post(
        "/api/v1/sales/orders",
        headers=headers,
        json={
            "customer_id": seed["party1"].id,
            "store_id": store_id,
            "items": [{"product_id": product.id, "quantity": 1, "unit_price": 25}],
        },
    )
    assert created.status_code == 200, created.text
    oid = created.json()["data"]["id"]
    order_number = created.json()["data"]["order_number"]

    notes = (
        await db_session.execute(
            select(m.Notification).where(
                m.Notification.tenant_id == seed["t1"].id,
                m.Notification.category == "new_order",
                m.Notification.entity_id == oid,
            )
        )
    ).scalars().all()
    assert any(n.title == "Sales order created" for n in notes), [n.title for n in notes]
    assert any(order_number in (n.message or "") for n in notes)

    conf = await ac.post(
        f"/api/v1/sales/orders/{oid}/confirm",
        headers=headers,
        json={},
    )
    assert conf.status_code == 200, conf.text

    notes2 = (
        await db_session.execute(
            select(m.Notification).where(
                m.Notification.tenant_id == seed["t1"].id,
                m.Notification.category == "new_order",
                m.Notification.entity_id == oid,
            )
        )
    ).scalars().all()
    titles = {n.title for n in notes2}
    assert "Sales order created" in titles
    assert "Sales order confirmed" in titles

    settings = await ac.get("/api/v1/notifications/settings", headers=headers)
    assert settings.status_code == 200
    assert "new_order" in (settings.json()["data"] or {})
