"""Inventory product lookup + per-product warehouse stock (BR-18.2)."""

from __future__ import annotations

import pyotp
import pytest
from sqlalchemy import select

from app import catalog_meta as catalog_meta_svc
from app import inventory as inventory_svc
from app import models as m
from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_lookup_products_by_barcode_and_q(db_session, seeded):
    tenant_id = seeded["t1"].id
    product = seeded["p1"]
    product.barcode = "6281001999999"
    await db_session.flush()

    by_barcode = await inventory_svc.lookup_products(
        db_session, tenant_id, barcode="6281001999999"
    )
    assert by_barcode["count"] >= 1
    assert any(i["id"] == product.id for i in by_barcode["items"])

    by_q = await inventory_svc.lookup_products(db_session, tenant_id, q=product.sku)
    assert by_q["count"] >= 1
    assert any(i["sku"] == product.sku for i in by_q["items"])

    empty = await inventory_svc.lookup_products(db_session, tenant_id, q="")
    assert empty["count"] == 0


@pytest.mark.asyncio
async def test_list_product_warehouse_stock(db_session, seeded):
    tenant_id = seeded["t1"].id
    product = seeded["p1"]
    wh = m.Warehouse(
        tenant_id=tenant_id,
        code="WH-LK",
        name="Lookup WH",
        warehouse_type="main",
        is_active=True,
    )
    db_session.add(wh)
    await db_session.flush()
    await inventory_svc.get_or_create_warehouse_stock(
        db_session, tenant_id=tenant_id, warehouse_id=wh.id, product_id=product.id
    )
    stock = (
        await db_session.execute(
            select(m.WarehouseStock).where(
                m.WarehouseStock.tenant_id == tenant_id,
                m.WarehouseStock.warehouse_id == wh.id,
                m.WarehouseStock.product_id == product.id,
            )
        )
    ).scalar_one()
    stock.quantity = 7
    await db_session.flush()

    payload = await inventory_svc.list_product_warehouse_stock(
        db_session, tenant_id, product.id
    )
    assert payload["product_id"] == product.id
    assert payload["count"] >= 1
    assert any(i["warehouse_id"] == wh.id and i["quantity"] == 7 for i in payload["items"])


@pytest.mark.asyncio
async def test_inventory_lookup_routes_and_api_key(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    await catalog_meta_svc.ensure_default_catalog(db_session, seed["t1"].id)
    product = seed["p1"]
    product.barcode = "6281001888888"
    await db_session.commit()

    created = await ac.post(
        "/api/v1/api-keys",
        headers=headers,
        json={"name": "Lookup key", "permissions": {"inventory": ["read"]}},
    )
    assert created.status_code == 200, created.text
    secret = created.json()["data"]["api_key"]

    lookup = await ac.get(
        "/api/v1/inventory/products/lookup",
        params={"barcode": "6281001888888"},
        headers={"X-API-Key": secret, "X-Tenant-ID": seed["t1"].id},
    )
    assert lookup.status_code == 200, lookup.text
    body = lookup.json()["data"]
    assert body["count"] >= 1
    assert any(i["id"] == product.id for i in body["items"])

    stock = await ac.get(
        f"/api/v1/products/{product.id}/warehouse-stock",
        headers=headers,
    )
    assert stock.status_code == 200, stock.text
    assert stock.json()["data"]["product_id"] == product.id
