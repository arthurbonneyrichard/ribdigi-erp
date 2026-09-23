"""Catalog create/edit/save used by Company Admin inventory forms."""

from __future__ import annotations

import pytest

from tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_catalog_saves_product_category_brand_unit(client):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    cat = await ac.post(
        "/api/v1/catalog/categories",
        headers=headers,
        json={"code": "BEV", "name": "Beverages"},
    )
    assert cat.status_code == 200, cat.text
    cat_id = cat.json()["data"]["id"]

    brand = await ac.post(
        "/api/v1/catalog/brands",
        headers=headers,
        json={"code": "ACME", "name": "Acme"},
    )
    assert brand.status_code == 200, brand.text
    brand_id = brand.json()["data"]["id"]

    unit = await ac.post(
        "/api/v1/catalog/units",
        headers=headers,
        json={"code": "BTL", "name": "Bottle"},
    )
    assert unit.status_code == 200, unit.text
    unit_id = unit.json()["data"]["id"]

    created = await ac.post(
        "/api/v1/products",
        headers=headers,
        json={
            "name": "Cola 500ml",
            "sku": "COLA-500",
            "selling_price": 5,
            "cost_price": 2,
            "category_id": cat_id,
            "brand_id": brand_id,
            "unit_id": unit_id,
            "description": "Retail cola",
            "tax_supply_class": "standard",
        },
    )
    assert created.status_code == 200, created.text
    product_id = created.json()["data"]["id"]
    assert created.json()["data"]["sku"] == "COLA-500"

    patched = await ac.patch(
        f"/api/v1/products/{product_id}",
        headers=headers,
        json={"name": "Cola 500ml (retail)"},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["data"]["name"] == "Cola 500ml (retail)"

    variant = await ac.post(
        f"/api/v1/products/{product_id}/variants",
        headers=headers,
        json={"name": "Single", "sku": "COLA-500-S", "selling_price": 5, "cost_price": 2},
    )
    assert variant.status_code == 200, variant.text

    dup = await ac.post(
        "/api/v1/catalog/units",
        headers=headers,
        json={"code": "BTL", "name": "Bottle 2"},
    )
    assert dup.status_code == 409, dup.text

    cashier = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    denied = await ac.post(
        "/api/v1/products",
        headers=cashier,
        json={"name": "Nope", "sku": "NOPE-1", "selling_price": 1, "cost_price": 1},
    )
    assert denied.status_code == 403, denied.text

    beta = await auth_headers(ac, email="cashier@beta.example.com", tenant_slug="beta")
    isolated = await ac.get(f"/api/v1/products/{product_id}", headers=beta)
    assert isolated.status_code in {403, 404}, isolated.text


@pytest.mark.asyncio
async def test_company_admin_can_load_tenant_profile(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    got = await ac.get("/api/v1/tenants/me", headers=headers)
    assert got.status_code == 200, got.text
    assert got.json()["data"]["slug"] == "alpha"


@pytest.mark.asyncio
async def test_catalog_create_unauthorized(client):
    ac, _seed = client
    denied = await ac.post("/api/v1/products", json={"name": "X", "sku": "X-1"})
    assert denied.status_code == 401, denied.text
