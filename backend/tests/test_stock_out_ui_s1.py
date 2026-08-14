"""Manual stock-out with reference_type (BR-5.2)."""

from __future__ import annotations

import pyotp
import pytest
from sqlalchemy import select

from app import models as m
from app.inventory import apply_stock_change
from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_stock_out_requires_reference_type(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    product = seed["p1"]

    missing = await ac.post(
        "/api/v1/inventory/stock-out",
        headers=headers,
        json={"product_id": product.id, "quantity": 1},
    )
    assert missing.status_code == 400, missing.text
    assert "reference_type must be one of" in missing.text

    bad = await ac.post(
        "/api/v1/inventory/stock-out",
        headers=headers,
        json={"product_id": product.id, "quantity": 1, "reference_type": "sales"},
    )
    assert bad.status_code == 400, bad.text


@pytest.mark.asyncio
async def test_stock_out_records_reference_and_reduces_qty(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    product = seed["p1"]
    tenant_id = seed["t1"].id
    before = float(product.stock_qty or 0)

    await apply_stock_change(
        db_session,
        tenant_id=tenant_id,
        product_id=product.id,
        quantity_delta=5,
        movement_type="stock_in",
        user_id=seed["super"].id,
        allow_negative=False,
    )
    await db_session.commit()
    before = before + 5

    out = await ac.post(
        "/api/v1/inventory/stock-out",
        headers=headers,
        json={
            "product_id": product.id,
            "quantity": 2,
            "reference_type": "sale",
            "reference_id": "inv-demo-001",
            "notes": "UI stock-out hello",
        },
    )
    assert out.status_code == 200, out.text
    body = out.json()["data"]
    assert body["reference_type"] == "sale"
    assert body["reference_id"] == "inv-demo-001"
    assert body["stock_qty"] == before - 2

    mv = await ac.get(
        f"/api/v1/inventory/movements?product_id={product.id}&movement_type=stock_out",
        headers=headers,
    )
    assert mv.status_code == 200, mv.text
    rows = mv.json()["data"]["movements"]
    hit = next(
        r
        for r in rows
        if r.get("reference_type") == "sale" and r.get("reference_id") == "inv-demo-001"
    )
    assert hit["movement_type"] == "stock_out"
    assert float(hit["quantity"]) == -2
    assert hit["notes"] == "UI stock-out hello"


@pytest.mark.asyncio
async def test_stock_out_warehouse_scoped(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    tenant_id = seed["t1"].id
    product = seed["p1"]

    store = m.Store(tenant_id=tenant_id, code="SO-S", name="Stock Out Store")
    db_session.add(store)
    await db_session.flush()
    wh = m.Warehouse(
        tenant_id=tenant_id, code="WH-SO", name="WH Stock Out", store_id=store.id
    )
    db_session.add(wh)
    await db_session.flush()

    await apply_stock_change(
        db_session,
        tenant_id=tenant_id,
        product_id=product.id,
        quantity_delta=4,
        movement_type="stock_in",
        user_id=seed["super"].id,
        warehouse_id=wh.id,
        allow_negative=False,
    )
    await db_session.commit()

    out = await ac.post(
        "/api/v1/inventory/stock-out",
        headers=headers,
        json={
            "product_id": product.id,
            "quantity": 1,
            "reference_type": "damage",
            "warehouse_id": wh.id,
            "notes": "Warehouse damage issue",
        },
    )
    assert out.status_code == 200, out.text
    assert out.json()["data"]["reference_type"] == "damage"
    assert out.json()["data"]["warehouse_id"] == wh.id

    stock = (
        await db_session.execute(
            select(m.WarehouseStock).where(
                m.WarehouseStock.tenant_id == tenant_id,
                m.WarehouseStock.warehouse_id == wh.id,
                m.WarehouseStock.product_id == product.id,
            )
        )
    ).scalar_one()
    assert float(stock.quantity) == 3
