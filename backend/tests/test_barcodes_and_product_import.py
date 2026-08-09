"""Barcode generation/validation and product CSV import."""

from __future__ import annotations

import io

import pytest
from fastapi import HTTPException

from app import barcodes as barcode_svc
from app import catalog_meta as catalog_meta_svc
from app import models as m
from app.product_import import template_csv
from tests.conftest import auth_headers


def test_ean13_check_digit_and_formats():
    code = barcode_svc.generate_ean13(body12="200123456789")
    assert len(code) == 13
    assert barcode_svc.is_valid_ean13(code)
    assert barcode_svc.detect_barcode_format(code) == "ean13"
    # Known valid UPC-A: 036000291452
    assert barcode_svc.is_valid_upca("036000291452")
    assert barcode_svc.detect_barcode_format("RDABC12AB34CD") == "code128"
    with pytest.raises(HTTPException):
        barcode_svc.validate_barcode("not\nvalid")
    assert barcode_svc.validate_barcode("") is None


def test_ean8_valid_known():
    # 96385074 is a commonly cited valid EAN-8
    assert barcode_svc.is_valid_ean8("96385074")
    assert barcode_svc.validate_barcode("96385074") == "96385074"


def test_category_tree_nesting():
    from datetime import datetime

    now = datetime.utcnow()
    rows = [
        m.ProductCategory(
            id="r1", parent_id=None, code="ROOT", name="Root", is_active=True, created_at=now
        ),
        m.ProductCategory(
            id="c1", parent_id="r1", code="CHILD", name="Child", is_active=True, created_at=now
        ),
        m.ProductCategory(
            id="c2", parent_id="c1", code="LEAF", name="Leaf", is_active=True, created_at=now
        ),
    ]
    tree = catalog_meta_svc.build_category_tree(rows)
    assert tree[0]["code"] == "ROOT"
    assert tree[0]["children"][0]["code"] == "CHILD"
    assert tree[0]["children"][0]["children"][0]["code"] == "LEAF"
    flat = catalog_meta_svc.flatten_category_tree(tree)
    assert [x["depth"] for x in flat] == [0, 1, 2]


@pytest.mark.asyncio
async def test_generate_product_and_variant_barcode(client, db_session):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    product_id = seed["p1"].id

    gen = await ac.post(
        f"/api/v1/products/{product_id}/barcode/generate?format=code128",
        headers=headers,
    )
    assert gen.status_code == 200, gen.text
    barcode = gen.json()["data"]["barcode"]
    assert barcode
    assert barcode.startswith("RD")

    # Idempotent without force
    again = await ac.post(
        f"/api/v1/products/{product_id}/barcode/generate?format=code128",
        headers=headers,
    )
    assert again.json()["data"]["barcode"] == barcode

    force = await ac.post(
        f"/api/v1/products/{product_id}/barcode/generate?format=ean13&force=true",
        headers=headers,
    )
    assert force.status_code == 200, force.text
    assert barcode_svc.is_valid_ean13(force.json()["data"]["barcode"])

    variant = await ac.post(
        f"/api/v1/products/{product_id}/variants",
        headers=headers,
        json={"name": "XL", "sku": "P1-XL-BC"},
    )
    assert variant.status_code == 200, variant.text
    vid = variant.json()["data"]["id"]
    vgen = await ac.post(
        f"/api/v1/products/{product_id}/variants/{vid}/barcode/generate",
        headers=headers,
    )
    assert vgen.status_code == 200, vgen.text
    assert vgen.json()["data"]["barcode"]

    # Duplicate barcode rejected
    clash = await ac.patch(
        f"/api/v1/products/{product_id}/variants/{vid}",
        headers=headers,
        json={"barcode": force.json()["data"]["barcode"]},
    )
    assert clash.status_code == 409


@pytest.mark.asyncio
async def test_pos_search_matches_barcode(client, db_session):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    code = "2001234567893"  # may be invalid check digit — generate properly
    code = barcode_svc.generate_ean13(body12="200123456789")
    product = await db_session.get(m.Product, seed["p1"].id)
    product.barcode = code
    await db_session.commit()

    # Cashier has POS read
    pos_headers = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    found = await ac.get(
        f"/api/v1/pos/products/search?q={code}",
        headers=pos_headers,
    )
    assert found.status_code == 200, found.text
    ids = {row["product_id"] for row in found.json()["data"]}
    assert seed["p1"].id in ids


@pytest.mark.asyncio
async def test_product_csv_import_dry_run_and_commit(client, db_session):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    tmpl = await ac.get("/api/v1/products/import/template", headers=headers)
    assert tmpl.status_code == 200
    assert "name,sku" in tmpl.text
    assert template_csv().startswith("name,sku")

    # ensure default category GEN exists
    await catalog_meta_svc.ensure_default_catalog(db_session, seed["t1"].id)
    await db_session.commit()

    csv_body = (
        "name,sku,barcode,category_code,brand_code,unit_code,cost_price,selling_price,reorder_level,stock_qty,tracks_batches\n"
        "Imported A,IMP-A,,GEN,,PCS,1,3,2,4,false\n"
        "Bad Row,,,\n"
        "Imported B,IMP-B,96385074,GEN,,PCS,2,4,1,0,false\n"
    )
    dry = await ac.post(
        "/api/v1/products/import?dry_run=true",
        headers=headers,
        files={"file": ("products.csv", io.BytesIO(csv_body.encode()), "text/csv")},
    )
    assert dry.status_code == 200, dry.text
    data = dry.json()["data"]
    assert data["dry_run"] is True
    assert data["valid_rows"] == 2
    assert data["error_rows"] == 1
    assert data["created"] == []

    committed = await ac.post(
        "/api/v1/products/import?dry_run=false",
        headers=headers,
        files={"file": ("products.csv", io.BytesIO(csv_body.encode()), "text/csv")},
    )
    assert committed.status_code == 200, committed.text
    result = committed.json()["data"]
    assert result["valid_rows"] == 2
    assert len(result["created"]) == 2

    listed = await ac.get("/api/v1/products", headers=headers)
    skus = {p["sku"] for p in listed.json()["data"]}
    assert "IMP-A" in skus and "IMP-B" in skus

    product_a = next(p for p in listed.json()["data"] if p["sku"] == "IMP-A")
    assert float(product_a["stock_qty"]) == 4


@pytest.mark.asyncio
async def test_category_tree_endpoint_and_cycle_guard(client):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    parent = await ac.post(
        "/api/v1/catalog/categories",
        headers=headers,
        json={"code": "ELEC", "name": "Electronics"},
    )
    assert parent.status_code == 200, parent.text
    parent_id = parent.json()["data"]["id"]
    child = await ac.post(
        "/api/v1/catalog/categories",
        headers=headers,
        json={"code": "PHONE", "name": "Phones", "parent_id": parent_id},
    )
    assert child.status_code == 200, child.text
    child_id = child.json()["data"]["id"]

    tree = await ac.get("/api/v1/catalog/categories?tree=true", headers=headers)
    assert tree.status_code == 200
    nodes = tree.json()["data"]
    elec = next(n for n in nodes if n["id"] == parent_id)
    assert any(c["id"] == child_id for c in elec["children"])

    cycle = await ac.patch(
        f"/api/v1/catalog/categories/{parent_id}",
        headers=headers,
        json={"parent_id": child_id},
    )
    assert cycle.status_code == 400
