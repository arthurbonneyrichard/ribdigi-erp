"""Inventory transfer + stock count year-series numbering (BR-5.2 / BR-20.4)."""

from __future__ import annotations

from datetime import datetime

import pyotp
import pytest
from sqlalchemy import select

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
async def test_inventory_transfer_and_count_numbering(client, db_session, seeded):
    ac, seed = client
    admin = await _admin(ac, seed)
    year = datetime.utcnow().year
    tenant_id = seed["t1"].id
    product = seed["p1"]

    settings = await ac.patch(
        "/api/v1/inventory/settings",
        headers=admin,
        json={
            "stock_transfer_numbering": {"prefix": "TR", "next_number": 21},
            "stock_count_numbering": {"prefix": "SC", "next_number": 31},
        },
    )
    assert settings.status_code == 200, settings.text
    data = settings.json()["data"]
    assert data["stock_transfer_numbering"]["preview"] == f"TR-{year}-0021"
    assert data["stock_count_numbering"]["preview"] == f"SC-{year}-0031"
    assert "fefo_strict_warehouse" in data

    store = await create_store(
        db_session, tenant_id=tenant_id, name="Num Store", code="NUM"
    )
    await db_session.flush()
    wh_a = await warehouse_for_store(db_session, tenant_id, store.id)
    wh_b = m.Warehouse(
        tenant_id=tenant_id,
        code="NUM-B",
        name="Num Store B WH",
        store_id=store.id,
    )
    db_session.add(wh_b)
    await apply_warehouse_stock_change(
        db_session,
        tenant_id=tenant_id,
        warehouse_id=wh_a.id,
        product_id=product.id,
        quantity_delta=10,
    )
    await db_session.commit()

    xfer = await ac.post(
        "/api/v1/inventory/stock-transfers",
        headers=admin,
        json={
            "from_warehouse_id": wh_a.id,
            "to_warehouse_id": wh_b.id,
            "submit": False,
            "items": [{"product_id": product.id, "quantity": 1}],
        },
    )
    assert xfer.status_code == 200, xfer.text
    assert xfer.json()["data"]["transfer_number"] == f"TR-{year}-0021"

    count = await ac.post(
        "/api/v1/inventory/stock-counts",
        headers=admin,
        json={"warehouse_id": wh_a.id, "product_ids": [product.id]},
    )
    assert count.status_code == 200, count.text
    assert count.json()["data"]["count_number"] == f"SC-{year}-0031"

    nxt = await ac.get("/api/v1/inventory/settings", headers=admin)
    assert nxt.status_code == 200
    body = nxt.json()["data"]
    assert body["stock_transfer_numbering"]["preview"] == f"TR-{year}-0022"
    assert body["stock_count_numbering"]["preview"] == f"SC-{year}-0032"
