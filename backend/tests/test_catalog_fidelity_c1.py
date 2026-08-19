"""Stage 17 C1: catalog fidelity proof (BR-5.1) via live HTTP APIs."""

from __future__ import annotations

import io
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def _png() -> bytes:
    return b"\x89PNG\r\n\x1a\n" + b"fake-png-bytes"


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


async def _beta(ac):
    return await auth_headers(ac, email="cashier@beta.example.com", tenant_slug="beta")


@pytest.mark.asyncio
async def test_catalog_hierarchy_brand_uom_product_chain(client, tmp_path, monkeypatch):
    """Categories tree + brand + UoM + product create with FKs/details (BR-5.1)."""
    from app import storage as storage_svc

    monkeypatch.setattr(storage_svc.settings, "MEDIA_DIR", str(tmp_path))
    monkeypatch.setattr(storage_svc.settings, "STORAGE_BACKEND", "local")

    ac, seed = client
    headers = await _mgr(ac)

    parent = await ac.post(
        "/api/v1/catalog/categories",
        headers=headers,
        json={"code": "S17P", "name": "S17 Parent"},
    )
    assert parent.status_code == 200, parent.text
    parent_id = parent.json()["data"]["id"]

    child = await ac.post(
        "/api/v1/catalog/categories",
        headers=headers,
        json={"code": "S17C", "name": "S17 Child", "parent_id": parent_id},
    )
    assert child.status_code == 200, child.text
    child_id = child.json()["data"]["id"]

    tree = await ac.get("/api/v1/catalog/categories?tree=true", headers=headers)
    assert tree.status_code == 200, tree.text
    roots = tree.json()["data"]
    assert any(r.get("id") == parent_id for r in roots)
    parent_node = next(r for r in roots if r.get("id") == parent_id)
    children = parent_node.get("children") or parent_node.get("items") or []
    assert any(c.get("id") == child_id for c in children) or any(
        c.get("code") == "S17C" for c in children
    )

    brand = await ac.post(
        "/api/v1/catalog/brands",
        headers=headers,
        json={"code": "S17B", "name": "S17 Brand", "description": "Stage 17 brand"},
    )
    assert brand.status_code == 200, brand.text
    brand_id = brand.json()["data"]["id"]
    assert brand.json()["data"].get("description") == "Stage 17 brand"

    logo = await ac.post(
        f"/api/v1/catalog/brands/{brand_id}/logo",
        headers=headers,
        files={"file": ("logo.png", io.BytesIO(_png()), "image/png")},
    )
    assert logo.status_code == 200, logo.text
    assert logo.json()["data"]["has_logo"] is True

    pcs = await ac.post(
        "/api/v1/catalog/units",
        headers=headers,
        json={"code": "S17PCS", "name": "S17 Pieces"},
    )
    assert pcs.status_code == 200, pcs.text
    pcs_id = pcs.json()["data"]["id"]
    box = await ac.post(
        "/api/v1/catalog/units",
        headers=headers,
        json={
            "code": "S17BOX",
            "name": "S17 Box",
            "base_unit_id": pcs_id,
            "conversion_factor": 10,
        },
    )
    assert box.status_code == 200, box.text
    box_id = box.json()["data"]["id"]
    conv = await ac.get(
        "/api/v1/catalog/units/convert",
        headers=headers,
        params={"from_unit_id": box_id, "to_unit_id": pcs_id, "quantity": 3},
    )
    assert conv.status_code == 200, conv.text
    assert float(conv.json()["data"]["converted_quantity"]) == 30

    created = await ac.post(
        "/api/v1/products",
        headers=headers,
        json={
            "name": "S17 Catalog SKU",
            "sku": "S17-C1-SKU",
            "category_id": child_id,
            "brand_id": brand_id,
            "unit_id": pcs_id,
            "cost_price": 4,
            "selling_price": 9,
            "weight": 0.5,
            "length": 12,
            "width": 8,
            "height": 3,
            "tracks_batches": True,
            "stock_qty": 0,
        },
    )
    assert created.status_code == 200, created.text
    product = created.json()["data"]
    product_id = product["id"]
    assert product["sku"] == "S17-C1-SKU"
    assert product.get("category_id") == child_id or product.get("brand_id") == brand_id
    assert float(product.get("weight") or 0) == 0.5
    assert product.get("tracks_batches") is True

    got = await ac.get(f"/api/v1/products/{product_id}", headers=headers)
    assert got.status_code == 200, got.text
    assert got.json()["data"]["sku"] == "S17-C1-SKU"

    # Tenant isolation: beta cannot read alpha product
    beta_headers = await _beta(ac)
    denied = await ac.get(f"/api/v1/products/{product_id}", headers=beta_headers)
    assert denied.status_code in {403, 404}


@pytest.mark.asyncio
async def test_variants_barcode_images_batches(client, tmp_path, monkeypatch):
    """Variants SKU, barcode generate, multi-image primary, batch/expiry via stock-in."""
    from app import storage as storage_svc

    monkeypatch.setattr(storage_svc.settings, "MEDIA_DIR", str(tmp_path))
    monkeypatch.setattr(storage_svc.settings, "STORAGE_BACKEND", "local")

    ac, seed = client
    headers = await _mgr(ac)

    created = await ac.post(
        "/api/v1/products",
        headers=headers,
        json={
            "name": "S17 Variant Host",
            "sku": "S17-C1-VAR",
            "cost_price": 2,
            "selling_price": 5,
            "tracks_batches": True,
            "stock_qty": 0,
        },
    )
    assert created.status_code == 200, created.text
    product_id = created.json()["data"]["id"]

    variant = await ac.post(
        f"/api/v1/products/{product_id}/variants",
        headers=headers,
        json={"name": "Red M", "sku": "S17-C1-VAR-RED", "size": "M", "color": "Red"},
    )
    assert variant.status_code == 200, variant.text
    variant_id = variant.json()["data"]["id"]
    assert variant.json()["data"]["sku"] == "S17-C1-VAR-RED"

    barcode = await ac.post(
        f"/api/v1/products/{product_id}/barcode/generate?format=code128",
        headers=headers,
    )
    assert barcode.status_code == 200, barcode.text
    assert barcode.json()["data"].get("barcode")

    vbar = await ac.post(
        f"/api/v1/products/{product_id}/variants/{variant_id}/barcode/generate",
        headers=headers,
    )
    assert vbar.status_code == 200, vbar.text

    img1 = await ac.post(
        f"/api/v1/products/{product_id}/images",
        headers=headers,
        files={"file": ("a.png", io.BytesIO(_png()), "image/png")},
    )
    assert img1.status_code == 200, img1.text
    assert img1.json()["data"]["is_primary"] is True
    img2 = await ac.post(
        f"/api/v1/products/{product_id}/images",
        headers=headers,
        files={"file": ("b.png", io.BytesIO(_png()), "image/png")},
    )
    assert img2.status_code == 200, img2.text
    promote = await ac.patch(
        f"/api/v1/products/{product_id}/images/{img2.json()['data']['id']}",
        headers=headers,
        json={"is_primary": True},
    )
    assert promote.status_code == 200, promote.text
    assert promote.json()["data"]["is_primary"] is True

    expiry = (datetime.utcnow() + timedelta(days=90)).strftime("%Y-%m-%d")
    mfg = (datetime.utcnow() - timedelta(days=5)).strftime("%Y-%m-%d")
    stock_in = await ac.post(
        "/api/v1/inventory/stock-in",
        headers=headers,
        json={
            "product_id": product_id,
            "quantity": 15,
            "batch_number": "S17-BATCH-1",
            "manufacturing_date": mfg,
            "expiry_date": expiry,
            "notes": "Stage 17 C1 batch",
        },
    )
    assert stock_in.status_code == 200, stock_in.text

    batches = await ac.get(f"/api/v1/products/{product_id}/batches", headers=headers)
    assert batches.status_code == 200, batches.text
    rows = batches.json()["data"]
    assert any(b.get("batch_number") == "S17-BATCH-1" for b in rows)

    expiring = await ac.get("/api/v1/inventory/batches/expiring?days=120", headers=headers)
    assert expiring.status_code == 200, expiring.text
    assert expiring.json()["data"]["count"] >= 1


def test_inventory_ui_surfaces_catalog_tabs():
    page = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    for token in ("categories", "brands", "variants", "batches", "Barcode", "catalog/categories"):
        assert token in page, token


def test_catalog_c1_docs():
    plan = (ROOT / "docs/STAGE_17_PLAN.md").read_text(encoding="utf-8")
    assert "| **C1**" in plan
    assert "test_catalog_fidelity_c1.py" in plan
    assert "COMPLETE" in plan
    br = (ROOT / "docs/BUSINESS_REQUIREMENTS_DOCUMENT.md").read_text(encoding="utf-8")
    assert "Stage 17 C1" in br
    assert "[x] **Categories:**" in br
