"""Sales order soft inventory reservation (BR-7.3)."""

from __future__ import annotations

import pyotp
import pytest
from sqlalchemy import select

from app import models as m
from app.inventory import apply_warehouse_stock_change
from app.stores import create_store, warehouse_for_store
from tests.conftest import auth_headers


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_confirm_reserves_blocks_second_order_cancel_releases(client, db_session, seeded):
    ac, seed = client
    admin = await _super(ac, seed)

    store = await create_store(
        db_session, tenant_id=seed["t1"].id, name="Reserve Store", code="RSV"
    )
    await db_session.commit()
    wh = await warehouse_for_store(db_session, seed["t1"].id, store.id)
    product = await db_session.get(m.Product, seed["p1"].id)
    # Align consolidated qty with warehouse so allocate_unlocated does not inflate.
    product.stock_qty = 10
    await apply_warehouse_stock_change(
        db_session,
        tenant_id=seed["t1"].id,
        warehouse_id=wh.id,
        product_id=seed["p1"].id,
        quantity_delta=10,
    )
    await db_session.commit()

    cust = seed["party1"]
    o1 = await ac.post(
        "/api/v1/sales/orders",
        headers=admin,
        json={
            "customer_id": cust.id,
            "store_id": store.id,
            "delivery_address": "12 Market St",
            "items": [{"product_id": seed["p1"].id, "quantity": 10, "unit_price": 5}],
        },
    )
    assert o1.status_code == 200, o1.text
    oid1 = o1.json()["data"]["id"]
    assert o1.json()["data"]["store_id"] == store.id

    conf = await ac.post(f"/api/v1/sales/orders/{oid1}/confirm", headers=admin, json={})
    assert conf.status_code == 200, conf.text
    body = conf.json()["data"]
    assert body["status"] == "confirmed"
    assert body["reserved_qty"] == 10
    assert body["reservation_status"] == "active"

    rows = (
        await db_session.execute(
            select(m.StockReservation).where(
                m.StockReservation.sales_order_id == oid1,
                m.StockReservation.status == "active",
            )
        )
    ).scalars().all()
    assert len(rows) == 1
    assert float(rows[0].quantity) == 10

    o2 = await ac.post(
        "/api/v1/sales/orders",
        headers=admin,
        json={
            "customer_id": cust.id,
            "store_id": store.id,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 5}],
        },
    )
    oid2 = o2.json()["data"]["id"]
    blocked = await ac.post(f"/api/v1/sales/orders/{oid2}/confirm", headers=admin, json={})
    assert blocked.status_code == 409
    detail = blocked.json()["detail"]
    assert detail["code"] == "INSUFFICIENT_AVAILABLE_STOCK"

    cancelled = await ac.post(
        f"/api/v1/sales/orders/{oid1}/cancel",
        headers=admin,
        json={"reason": "Free reserved stock — reservation test"},
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["data"]["status"] == "cancelled"
    assert cancelled.json()["data"]["reserved_qty"] == 0

    ok2 = await ac.post(f"/api/v1/sales/orders/{oid2}/confirm", headers=admin, json={})
    assert ok2.status_code == 200, ok2.text
    assert ok2.json()["data"]["reserved_qty"] == 1


@pytest.mark.asyncio
async def test_invoice_post_consumes_reservation(client, db_session, seeded):
    ac, seed = client
    admin = await _super(ac, seed)

    store = await create_store(
        db_session, tenant_id=seed["t1"].id, name="Post Store", code="PST"
    )
    await db_session.commit()
    wh = await warehouse_for_store(db_session, seed["t1"].id, store.id)
    product = await db_session.get(m.Product, seed["p1"].id)
    before = 20.0
    product.stock_qty = before
    await apply_warehouse_stock_change(
        db_session,
        tenant_id=seed["t1"].id,
        warehouse_id=wh.id,
        product_id=seed["p1"].id,
        quantity_delta=20,
    )
    await db_session.commit()

    created = await ac.post(
        "/api/v1/sales/orders",
        headers=admin,
        json={
            "customer_id": seed["party1"].id,
            "store_id": store.id,
            "items": [{"product_id": seed["p1"].id, "quantity": 4, "unit_price": 10}],
        },
    )
    oid = created.json()["data"]["id"]
    await ac.post(f"/api/v1/sales/orders/{oid}/confirm", headers=admin, json={})
    inv = await ac.post(f"/api/v1/sales/orders/{oid}/convert-invoice", headers=admin)
    assert inv.status_code == 200, inv.text
    assert inv.json()["data"]["store_id"] == store.id
    iid = inv.json()["data"]["id"]

    posted = await ac.post(f"/api/v1/sales/invoices/{iid}/post", headers=admin)
    assert posted.status_code == 200, posted.text

    res = (
        await db_session.execute(
            select(m.StockReservation).where(m.StockReservation.sales_order_id == oid)
        )
    ).scalars().all()
    assert res and all(r.status == "consumed" for r in res)

    await db_session.refresh(product)
    assert float(product.stock_qty) == pytest.approx(before - 4)


@pytest.mark.asyncio
async def test_confirm_requires_store(client, db_session, seeded):
    ac, seed = client
    admin = await _super(ac, seed)
    created = await ac.post(
        "/api/v1/sales/orders",
        headers=admin,
        json={
            "customer_id": seed["party1"].id,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 2}],
        },
    )
    oid = created.json()["data"]["id"]
    missing = await ac.post(f"/api/v1/sales/orders/{oid}/confirm", headers=admin, json={})
    assert missing.status_code == 400
