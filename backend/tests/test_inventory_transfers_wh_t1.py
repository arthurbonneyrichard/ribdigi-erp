"""Warehouse-to-warehouse transfers via inventory aliases (BR-5.2 / BR-5.4)."""

from __future__ import annotations

import pyotp
import pytest

from app import models as m
from app.inventory import apply_warehouse_stock_change
from app.stores import create_store, warehouse_for_store
from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_inventory_same_store_warehouse_transfer_lifecycle(client, db_session, seeded):
    ac, seed = client
    admin = await _admin(ac, seed)
    tenant_id = seed["t1"].id
    product = seed["p1"]

    store = await create_store(
        db_session, tenant_id=tenant_id, name="Xfer Store", code="XFS"
    )
    await db_session.flush()
    wh_a = await warehouse_for_store(db_session, tenant_id, store.id)
    wh_b = m.Warehouse(
        tenant_id=tenant_id,
        code="XFS-B",
        name="Xfer Store B WH",
        store_id=store.id,
    )
    db_session.add(wh_b)
    await db_session.flush()

    await apply_warehouse_stock_change(
        db_session,
        tenant_id=tenant_id,
        warehouse_id=wh_a.id,
        product_id=product.id,
        quantity_delta=15,
    )
    await db_session.commit()

    created = await ac.post(
        "/api/v1/inventory/stock-transfers",
        headers=admin,
        json={
            "from_warehouse_id": wh_a.id,
            "to_warehouse_id": wh_b.id,
            "submit": True,
            "notes": "same-store WH move",
            "items": [{"product_id": product.id, "quantity": 4}],
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()["data"]
    tid = body["id"]
    assert body["from_warehouse_id"] == wh_a.id
    assert body["to_warehouse_id"] == wh_b.id
    assert body["from_store_id"] == store.id
    assert body["to_store_id"] == store.id
    assert body["approval_steps_required"] == 1
    assert body["status"] == "requested"
    assert body["fully_approved"] is False
    assert body["can_ship"] is False

    early = await ac.post(f"/api/v1/inventory/stock-transfers/{tid}/ship", headers=admin)
    assert early.status_code == 409

    approved = await ac.post(
        f"/api/v1/inventory/stock-transfers/{tid}/approve", headers=admin
    )
    assert approved.status_code == 200, approved.text
    abody = approved.json()["data"]
    assert abody["fully_approved"] is True
    assert abody["can_ship"] is True
    assert abody["awaiting_approval"] is None

    shipped = await ac.post(
        f"/api/v1/inventory/stock-transfers/{tid}/ship", headers=admin
    )
    assert shipped.status_code == 200, shipped.text
    assert shipped.json()["data"]["status"] == "in_transit"

    received = await ac.post(
        f"/api/v1/inventory/stock-transfers/{tid}/receive", headers=admin
    )
    assert received.status_code == 200, received.text
    rbody = received.json()["data"]
    assert rbody["status"] == "received"
    assert float(rbody["items"][0]["received_qty"]) == 4

    after_b = await ac.get(
        f"/api/v1/inventory/warehouse-stock?warehouse_id={wh_b.id}&include_zero=true",
        headers=admin,
    )
    qb = float(
        next(i for i in after_b.json()["data"]["items"] if i["product_id"] == product.id)[
            "quantity"
        ]
    )
    assert qb == 4


@pytest.mark.asyncio
async def test_inventory_transfer_rejects_same_warehouse(client, db_session, seeded):
    ac, seed = client
    admin = await _admin(ac, seed)
    tenant_id = seed["t1"].id
    store = await create_store(
        db_session, tenant_id=tenant_id, name="Same WH Store", code="SWS"
    )
    await db_session.commit()
    wh = await warehouse_for_store(db_session, tenant_id, store.id)

    bad = await ac.post(
        "/api/v1/inventory/stock-transfers",
        headers=admin,
        json={
            "from_warehouse_id": wh.id,
            "to_warehouse_id": wh.id,
            "submit": True,
            "items": [{"product_id": seed["p1"].id, "quantity": 1}],
        },
    )
    assert bad.status_code == 400, bad.text
    assert "warehouses must differ" in bad.text


@pytest.mark.asyncio
async def test_stores_transfer_still_requires_different_stores(client, db_session, seeded):
    ac, seed = client
    admin = await _admin(ac, seed)
    tenant_id = seed["t1"].id
    store = await create_store(
        db_session, tenant_id=tenant_id, name="Solo Store", code="SOL"
    )
    await db_session.commit()

    bad = await ac.post(
        "/api/v1/stores/transfers",
        headers=admin,
        json={
            "from_store_id": store.id,
            "to_store_id": store.id,
            "submit": True,
            "items": [{"product_id": seed["p1"].id, "quantity": 1}],
        },
    )
    assert bad.status_code == 400, bad.text
    assert "stores must differ" in bad.text
