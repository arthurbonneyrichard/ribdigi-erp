"""Stock adjustment coded reasons (BR-5.2)."""

from __future__ import annotations

import pyotp
import pytest

from app import models as m
from app.inventory import STOCK_ADJUSTMENT_REASONS, apply_stock_change
from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_stock_adjust_requires_coded_reason(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    product = seed["p1"]
    before = float(product.stock_qty or 0)

    bad = await ac.post(
        f"/api/v1/inventory/adjust/{product.id}",
        headers=headers,
        json={"quantity": -1, "reason": "adjustment"},
    )
    assert bad.status_code == 400, bad.text
    assert "reason must be one of" in bad.text

    missing = await ac.post(
        f"/api/v1/inventory/adjust/{product.id}",
        headers=headers,
        json={"quantity": -1},
    )
    assert missing.status_code == 422

    ok = await ac.post(
        f"/api/v1/inventory/adjust/{product.id}",
        headers=headers,
        json={"quantity": -1, "reason": "damage", "notes": "Shelf leak"},
    )
    assert ok.status_code == 200, ok.text
    body = ok.json()["data"]
    assert body["reason"] == "damage"
    assert body["stock_qty"] == before - 1

    mv = await ac.get(
        f"/api/v1/inventory/movements?product_id={product.id}&reason=damage",
        headers=headers,
    )
    assert mv.status_code == 200, mv.text
    data = mv.json()["data"]
    assert data["reason"] == "damage"
    assert data["count"] >= 1
    hit = next(r for r in data["movements"] if r.get("reason") == "damage")
    assert hit["movement_type"] == "adjustment"
    assert hit["notes"] == "Shelf leak"
    assert hit["quantity"] == -1


@pytest.mark.asyncio
async def test_stock_adjust_warehouse_scoped(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    tenant_id = seed["t1"].id
    product = seed["p1"]

    store = m.Store(tenant_id=tenant_id, code="ADJ-S", name="Adjust Store")
    db_session.add(store)
    await db_session.flush()
    wh = m.Warehouse(
        tenant_id=tenant_id, code="WH-ADJ", name="WH Adjust", store_id=store.id
    )
    db_session.add(wh)
    await db_session.flush()

    await apply_stock_change(
        db_session,
        tenant_id=tenant_id,
        product_id=product.id,
        quantity_delta=5,
        movement_type="stock_in",
        user_id=seed["super"].id,
        warehouse_id=wh.id,
        allow_negative=False,
    )
    await db_session.commit()

    adj = await ac.post(
        f"/api/v1/inventory/adjust/{product.id}",
        headers=headers,
        json={"quantity": -2, "reason": "theft", "warehouse_id": wh.id},
    )
    assert adj.status_code == 200, adj.text
    assert adj.json()["data"]["reason"] == "theft"
    assert adj.json()["data"]["warehouse_id"] == wh.id

    from sqlalchemy import select

    row = (
        await db_session.execute(
            select(m.WarehouseStock).where(
                m.WarehouseStock.tenant_id == tenant_id,
                m.WarehouseStock.warehouse_id == wh.id,
                m.WarehouseStock.product_id == product.id,
            )
        )
    ).scalar_one()
    assert float(row.quantity) == 3

    filtered = await ac.get(
        f"/api/v1/reports/inventory/movements?warehouse_id={wh.id}&reason=theft",
        headers=headers,
    )
    assert filtered.status_code == 200, filtered.text
    fdata = filtered.json()["data"]
    assert fdata["count"] >= 1
    assert all(r["reason"] == "theft" for r in fdata["movements"])
    assert STOCK_ADJUSTMENT_REASONS == {"damage", "theft", "expiry", "found", "lost"}
