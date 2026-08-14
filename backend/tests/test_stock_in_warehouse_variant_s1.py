"""Stock-in with warehouse + variant (BR-5.2 / BR-5.1)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pyotp
import pytest
from sqlalchemy import select

from app import models as m
from app.stores import create_store
from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_stock_in_warehouse_and_variant(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    product = seed["p1"]
    tenant_id = seed["t1"].id

    store = await create_store(
        db_session, tenant_id=tenant_id, name="Stock-In Store", code="SIS"
    )
    await db_session.flush()
    wh = (
        await db_session.execute(
            select(m.Warehouse).where(
                m.Warehouse.tenant_id == tenant_id,
                m.Warehouse.store_id == store.id,
            )
        )
    ).scalar_one()

    variant = await ac.post(
        f"/api/v1/products/{product.id}/variants",
        headers=headers,
        json={"name": "Stock-In Size", "sku": "P1-SI-S", "size": "S"},
    )
    assert variant.status_code == 200, variant.text
    vid = variant.json()["data"]["id"]

    mfg = datetime.utcnow() - timedelta(days=5)
    exp = datetime.utcnow() + timedelta(days=90)
    received = await ac.post(
        "/api/v1/inventory/stock-in",
        headers=headers,
        json={
            "product_id": product.id,
            "quantity": 8,
            "warehouse_id": wh.id,
            "variant_id": vid,
            "notes": "UI stock-in warehouse+variant",
            "batch_number": "LOT-WH-VAR-1",
            "manufacturing_date": mfg.isoformat(),
            "expiry_date": exp.isoformat(),
        },
    )
    assert received.status_code == 200, received.text
    data = received.json()["data"]
    batch = data.get("batch") or {}
    assert batch.get("batch_number") == "LOT-WH-VAR-1"
    assert batch.get("warehouse_id") == wh.id
    assert batch.get("variant_id") == vid
    assert data.get("variant", {}).get("id") == vid

    stock = (
        await db_session.execute(
            select(m.WarehouseStock).where(
                m.WarehouseStock.tenant_id == tenant_id,
                m.WarehouseStock.warehouse_id == wh.id,
                m.WarehouseStock.product_id == product.id,
            )
        )
    ).scalar_one()
    assert float(stock.quantity) >= 8

    moves = await ac.get(
        f"/api/v1/inventory/movements?product_id={product.id}&warehouse_id={wh.id}"
        f"&movement_type=stock_in",
        headers=headers,
    )
    assert moves.status_code == 200, moves.text
    rows = moves.json()["data"]["movements"]
    assert any(
        r.get("warehouse_id") == wh.id and float(r.get("quantity") or 0) == 8
        for r in rows
    ), rows[:3]

    listed = await ac.get(f"/api/v1/products/{product.id}/batches", headers=headers)
    assert listed.status_code == 200
    row = next(b for b in listed.json()["data"] if b["batch_number"] == "LOT-WH-VAR-1")
    assert row["warehouse_id"] == wh.id
    assert row["variant_id"] == vid
