"""Inventory transfers either-side store_id filter (BR-13.2 / BR-14.5)."""

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
async def test_transfers_filter_by_either_side_store(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    tenant_id = seed["t1"].id
    product = seed["p1"]

    store_a = await create_store(
        db_session, tenant_id=tenant_id, name="Xfer Store A", code="XF-A"
    )
    store_b = await create_store(
        db_session, tenant_id=tenant_id, name="Xfer Store B", code="XF-B"
    )
    store_c = await create_store(
        db_session, tenant_id=tenant_id, name="Xfer Store C", code="XF-C"
    )
    await db_session.commit()

    wh_a = await warehouse_for_store(db_session, tenant_id, store_a.id)
    await apply_warehouse_stock_change(
        db_session,
        tenant_id=tenant_id,
        warehouse_id=wh_a.id,
        product_id=product.id,
        quantity_delta=40,
    )
    product.stock_qty = float(product.stock_qty or 0) + 40
    await db_session.commit()

    a_to_b = await ac.post(
        "/api/v1/stores/transfers",
        headers=headers,
        json={
            "from_store_id": store_a.id,
            "to_store_id": store_b.id,
            "submit": True,
            "items": [{"product_id": product.id, "quantity": 4}],
        },
    )
    assert a_to_b.status_code == 200, a_to_b.text
    a_to_b_id = a_to_b.json()["data"]["id"]

    b_to_c = await ac.post(
        "/api/v1/stores/transfers",
        headers=headers,
        json={
            "from_store_id": store_b.id,
            "to_store_id": store_c.id,
            "submit": False,
            "items": [{"product_id": product.id, "quantity": 1}],
        },
    )
    assert b_to_c.status_code == 200, b_to_c.text
    b_to_c_id = b_to_c.json()["data"]["id"]

    c_to_a = await ac.post(
        "/api/v1/stores/transfers",
        headers=headers,
        json={
            "from_store_id": store_c.id,
            "to_store_id": store_a.id,
            "submit": False,
            "items": [{"product_id": product.id, "quantity": 2}],
        },
    )
    assert c_to_a.status_code == 200, c_to_a.text
    c_to_a_id = c_to_a.json()["data"]["id"]

    # store_a is source of a_to_b and destination of c_to_a — not on b_to_c
    filtered = await ac.get(
        f"/api/v1/reports/inventory/transfers?store_id={store_a.id}",
        headers=headers,
    )
    assert filtered.status_code == 200, filtered.text
    data = filtered.json()["data"]
    assert data["store_id"] == store_a.id
    assert data["store_name"] == "Xfer Store A"
    ids = {t["id"] for t in data["transfers"]}
    assert a_to_b_id in ids
    assert c_to_a_id in ids
    assert b_to_c_id not in ids
    assert data["transfer_count"] == 2

    missing = await ac.get(
        "/api/v1/reports/inventory/transfers?store_id=00000000-0000-0000-0000-000000000000",
        headers=headers,
    )
    assert missing.status_code == 404
