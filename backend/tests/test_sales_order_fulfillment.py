"""Sales order fulfillment statuses (BR-7.3)."""

from __future__ import annotations

import pyotp
import pytest

from app import models as m
from app.inventory import apply_warehouse_stock_change
from app.stores import create_store, warehouse_for_store
from tests.conftest import auth_headers


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


async def _confirmed_order(ac, db_session, seed, admin, *, qty=2, code="FF1"):
    store = await create_store(
        db_session, tenant_id=seed["t1"].id, name=f"Fulfill {code}", code=code
    )
    await db_session.commit()
    wh = await warehouse_for_store(db_session, seed["t1"].id, store.id)
    product = await db_session.get(m.Product, seed["p1"].id)
    product.stock_qty = float(qty) + 5
    await apply_warehouse_stock_change(
        db_session,
        tenant_id=seed["t1"].id,
        warehouse_id=wh.id,
        product_id=seed["p1"].id,
        quantity_delta=float(qty) + 5,
    )
    await db_session.commit()
    created = await ac.post(
        "/api/v1/sales/orders",
        headers=admin,
        json={
            "customer_id": seed["party1"].id,
            "store_id": store.id,
            "items": [{"product_id": seed["p1"].id, "quantity": qty, "unit_price": 3}],
        },
    )
    oid = created.json()["data"]["id"]
    conf = await ac.post(f"/api/v1/sales/orders/{oid}/confirm", headers=admin, json={})
    assert conf.status_code == 200, conf.text
    return oid, conf.json()["data"]


@pytest.mark.asyncio
async def test_order_fulfillment_lifecycle(client, db_session, seeded):
    ac, seed = client
    admin = await _super(ac, seed)
    oid, body = await _confirmed_order(ac, db_session, seed, admin)
    assert body["can_process"] is True
    assert body["can_ship"] is False

    # Cannot ship before process
    early = await ac.post(f"/api/v1/sales/orders/{oid}/ship", headers=admin)
    assert early.status_code == 409

    proc = await ac.post(f"/api/v1/sales/orders/{oid}/process", headers=admin)
    assert proc.status_code == 200, proc.text
    assert proc.json()["data"]["status"] == "processing"
    assert proc.json()["data"]["processing_at"]
    assert proc.json()["data"]["can_ship"] is True
    assert proc.json()["data"]["reservation_status"] == "active"

    shipped = await ac.post(f"/api/v1/sales/orders/{oid}/ship", headers=admin)
    assert shipped.status_code == 200, shipped.text
    assert shipped.json()["data"]["status"] == "shipped"
    assert shipped.json()["data"]["can_deliver"] is True
    assert shipped.json()["data"]["can_cancel"] is False

    # Cancel blocked after ship
    blocked = await ac.post(f"/api/v1/sales/orders/{oid}/cancel", headers=admin)
    assert blocked.status_code == 409

    delivered = await ac.post(f"/api/v1/sales/orders/{oid}/deliver", headers=admin)
    assert delivered.status_code == 200, delivered.text
    data = delivered.json()["data"]
    assert data["status"] == "delivered"
    assert data["delivered_at"]
    assert data["can_invoice"] is True

    inv = await ac.post(f"/api/v1/sales/orders/{oid}/convert-invoice", headers=admin)
    assert inv.status_code == 200, inv.text
    order = await ac.get(f"/api/v1/sales/orders/{oid}", headers=admin)
    assert order.json()["data"]["status"] == "invoiced"


@pytest.mark.asyncio
async def test_cancel_while_processing_releases_reservation(client, db_session, seeded):
    ac, seed = client
    admin = await _super(ac, seed)
    oid, _ = await _confirmed_order(ac, db_session, seed, admin, qty=3, code="FF2")
    await ac.post(f"/api/v1/sales/orders/{oid}/process", headers=admin)
    cancelled = await ac.post(f"/api/v1/sales/orders/{oid}/cancel", headers=admin)
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["data"]["status"] == "cancelled"
    assert cancelled.json()["data"]["reserved_qty"] == 0
