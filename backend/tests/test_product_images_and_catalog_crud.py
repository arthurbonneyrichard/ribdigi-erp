"""Product gallery + catalog/variant PATCH/DELETE."""

from __future__ import annotations

import io

import pytest

from app import models as m
from app.product_images import MAX_PRODUCT_IMAGES, serialize_image
from tests.conftest import auth_headers


def _png_bytes() -> bytes:
    return b"\x89PNG\r\n\x1a\n" + b"fake-png-bytes"


@pytest.mark.asyncio
async def test_product_gallery_upload_primary_and_delete(client, db_session):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    product_id = seed["p1"].id

    uploaded = await ac.post(
        f"/api/v1/products/{product_id}/images",
        headers=headers,
        files={"file": ("a.png", io.BytesIO(_png_bytes()), "image/png")},
    )
    assert uploaded.status_code == 200, uploaded.text
    first = uploaded.json()["data"]
    assert first["is_primary"] is True
    assert first["storage_key"].startswith(f"{seed['t1'].id}/product_images/")

    second = await ac.post(
        f"/api/v1/products/{product_id}/images",
        headers=headers,
        files={"file": ("b.png", io.BytesIO(_png_bytes()), "image/png")},
    )
    assert second.status_code == 200, second.text
    assert second.json()["data"]["is_primary"] is False

    listed = await ac.get(f"/api/v1/products/{product_id}/images", headers=headers)
    assert listed.status_code == 200
    images = listed.json()["data"]
    assert len(images) == 2

    promote = await ac.patch(
        f"/api/v1/products/{product_id}/images/{second.json()['data']['id']}",
        headers=headers,
        json={"is_primary": True},
    )
    assert promote.status_code == 200, promote.text
    assert promote.json()["data"]["is_primary"] is True

    product = await db_session.get(m.Product, product_id)
    await db_session.refresh(product)
    assert product.image_url == second.json()["data"]["storage_key"]

    removed = await ac.delete(
        f"/api/v1/products/{product_id}/images/{second.json()['data']['id']}",
        headers=headers,
    )
    assert removed.status_code == 200, removed.text

    product = await db_session.get(m.Product, product_id)
    await db_session.refresh(product)
    assert product.image_url == first["storage_key"]

    legacy = await ac.get(f"/api/v1/products/{product_id}/image", headers=headers)
    assert legacy.status_code == 200


@pytest.mark.asyncio
async def test_product_gallery_max_five(client):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    product_id = seed["p1"].id

    for i in range(MAX_PRODUCT_IMAGES):
        r = await ac.post(
            f"/api/v1/products/{product_id}/images",
            headers=headers,
            files={"file": (f"{i}.png", io.BytesIO(_png_bytes()), "image/png")},
        )
        assert r.status_code == 200, r.text

    overflow = await ac.post(
        f"/api/v1/products/{product_id}/images",
        headers=headers,
        files={"file": ("overflow.png", io.BytesIO(_png_bytes()), "image/png")},
    )
    assert overflow.status_code == 400


@pytest.mark.asyncio
async def test_product_gallery_tenant_isolation(client):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    foreign = await ac.get(f"/api/v1/products/{seed['p2'].id}/images", headers=headers)
    assert foreign.status_code == 404


@pytest.mark.asyncio
async def test_catalog_and_variant_patch_delete(client, db_session):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    cat = await ac.post(
        "/api/v1/catalog/categories",
        headers=headers,
        json={"code": "ACC", "name": "Accessories"},
    )
    assert cat.status_code == 200, cat.text
    cat_id = cat.json()["data"]["id"]

    patched_cat = await ac.patch(
        f"/api/v1/catalog/categories/{cat_id}",
        headers=headers,
        json={"name": "Accessories Plus"},
    )
    assert patched_cat.status_code == 200
    assert patched_cat.json()["data"]["name"] == "Accessories Plus"

    deleted_cat = await ac.delete(f"/api/v1/catalog/categories/{cat_id}", headers=headers)
    assert deleted_cat.status_code == 200
    assert deleted_cat.json()["data"]["is_active"] is False

    brand = await ac.post(
        "/api/v1/catalog/brands",
        headers=headers,
        json={"code": "ACME", "name": "Acme"},
    )
    assert brand.status_code == 200, brand.text
    brand_id = brand.json()["data"]["id"]
    patched_brand = await ac.patch(
        f"/api/v1/catalog/brands/{brand_id}",
        headers=headers,
        json={"name": "Acme Co"},
    )
    assert patched_brand.status_code == 200
    assert patched_brand.json()["data"]["name"] == "Acme Co"
    deleted_brand = await ac.delete(f"/api/v1/catalog/brands/{brand_id}", headers=headers)
    assert deleted_brand.json()["data"]["is_active"] is False

    unit = await ac.post(
        "/api/v1/catalog/units",
        headers=headers,
        json={"code": "PK", "name": "Pack"},
    )
    assert unit.status_code == 200, unit.text
    unit_id = unit.json()["data"]["id"]
    patched_unit = await ac.patch(
        f"/api/v1/catalog/units/{unit_id}",
        headers=headers,
        json={"name": "Pack of 12"},
    )
    assert patched_unit.json()["data"]["name"] == "Pack of 12"
    deleted_unit = await ac.delete(f"/api/v1/catalog/units/{unit_id}", headers=headers)
    assert deleted_unit.json()["data"]["is_active"] is False

    variant = await ac.post(
        f"/api/v1/products/{seed['p1'].id}/variants",
        headers=headers,
        json={"name": "Large", "sku": "P1-L", "size": "L", "selling_price": 12},
    )
    assert variant.status_code == 200, variant.text
    variant_id = variant.json()["data"]["id"]

    patched = await ac.patch(
        f"/api/v1/products/{seed['p1'].id}/variants/{variant_id}",
        headers=headers,
        json={"selling_price": 15.5, "color": "Blue"},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["data"]["selling_price"] == 15.5
    assert patched.json()["data"]["color"] == "Blue"

    deactivated = await ac.delete(
        f"/api/v1/products/{seed['p1'].id}/variants/{variant_id}",
        headers=headers,
    )
    assert deactivated.status_code == 200
    assert deactivated.json()["data"]["is_active"] is False

    row = await db_session.get(m.ProductVariant, variant_id)
    await db_session.refresh(row)
    assert row.is_active is False


def test_serialize_image_fields():
    row = m.ProductImage(
        id="img1",
        product_id="p1",
        storage_key="t1/product_images/x.png",
        content_type="image/png",
        sort_order=1,
        is_primary=True,
        original_filename="x.png",
        created_at=None,
    )
    data = serialize_image(row)
    assert data["storage_key"].endswith("x.png")
    assert data["is_primary"] is True
