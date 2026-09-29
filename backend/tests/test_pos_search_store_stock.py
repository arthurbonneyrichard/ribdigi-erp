"""POS search overlays store warehouse qty and the min/reorder low-stock floor."""

from __future__ import annotations

import pyotp
import pytest
from sqlalchemy import select

from app import models as m
from app.inventory import get_or_create_warehouse_stock
from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_pos_search_uses_store_warehouse_qty_and_low_stock_floor(client, db_session):
    ac, seed = client
    admin = await _admin(ac, seed)
    cashier = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")

    store = await ac.post(
        "/api/v1/stores", headers=admin, json={"code": "POSWH", "name": "POS Warehouse Store"}
    )
    assert store.status_code == 200, store.text
    store_id = store.json()["data"]["id"]

    product = seed["p1"]
    product.stock_qty = 80
    product.reorder_level = 10
    if hasattr(product, "minimum_stock"):
        product.minimum_stock = 4
    await db_session.flush()

    wh = (
        await db_session.execute(
            select(m.Warehouse).where(
                m.Warehouse.tenant_id == seed["t1"].id,
                m.Warehouse.store_id == store_id,
            )
        )
    ).scalar_one_or_none()
    assert wh is not None
    row = await get_or_create_warehouse_stock(
        db_session, tenant_id=seed["t1"].id, warehouse_id=wh.id, product_id=product.id
    )
    row.quantity = 6
    await db_session.commit()

    company = await ac.get(
        f"/api/v1/pos/products/search?q={product.sku}",
        headers=cashier,
    )
    assert company.status_code == 200, company.text
    hit = next(r for r in company.json()["data"] if r["sku"] == product.sku)
    assert hit["stock_qty"] == 80
    assert hit["is_low_stock"] is False

    scoped = await ac.get(
        f"/api/v1/pos/products/search?q={product.sku}&store_id={store_id}",
        headers=cashier,
    )
    assert scoped.status_code == 200, scoped.text
    store_hit = next(r for r in scoped.json()["data"] if r["sku"] == product.sku)
    assert store_hit["stock_qty"] == 6
    assert store_hit["is_low_stock"] is True


@pytest.mark.asyncio
async def test_pos_search_store_id_is_tenant_and_membership_scoped(client):
    ac, seed = client
    admin = await _admin(ac, seed)
    cashier = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    beta = await auth_headers(ac, email="cashier@beta.example.com", tenant_slug="beta")

    a = await ac.post("/api/v1/stores", headers=admin, json={"code": "SA", "name": "Store A"})
    b = await ac.post("/api/v1/stores", headers=admin, json={"code": "SB", "name": "Store B"})
    assert a.status_code == 200, a.text
    assert b.status_code == 200, b.text
    store_a = a.json()["data"]["id"]
    store_b = b.json()["data"]["id"]

    assign = await ac.put(
        f"/api/v1/users/{seed['u1'].id}/stores",
        headers=admin,
        json={"store_ids": [store_a]},
    )
    assert assign.status_code == 200, assign.text

    denied = await ac.get(
        f"/api/v1/pos/products/search?q={seed['p1'].sku}&store_id={store_b}",
        headers=cashier,
    )
    assert denied.status_code == 403, denied.text
    assert denied.json()["detail"]["code"] == "STORE_ACCESS_DENIED"

    allowed = await ac.get(
        f"/api/v1/pos/products/search?q={seed['p1'].sku}&store_id={store_a}",
        headers=cashier,
    )
    assert allowed.status_code == 200, allowed.text

    foreign = await ac.get(
        f"/api/v1/pos/products/search?q={seed['p1'].sku}&store_id={store_a}",
        headers=beta,
    )
    assert foreign.status_code == 404, foreign.text
