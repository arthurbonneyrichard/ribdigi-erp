"""Product CSV bulk import — template, validation, commit, tenant isolation."""

from __future__ import annotations

import pyotp
import pytest

from app.product_import import parse_csv_rows, template_csv
from tests.conftest import auth_headers


async def _admin(ac, seeded):
    code = pyotp.TOTP(seeded["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


def test_template_has_required_headers():
    text = template_csv()
    header = text.splitlines()[0]
    assert "name" in header
    assert "sku" in header
    assert "stock_qty" in header


@pytest.mark.asyncio
async def test_products_export_csv_route(client):
    ac, seeded = client
    admin = await _admin(ac, seeded)
    product = seeded["p1"]

    patched = await ac.patch(
        f"/api/v1/products/{product.id}",
        headers=admin,
        json={"barcode": "EXPORT-BC-1"},
    )
    assert patched.status_code == 200, patched.text

    exported = await ac.get("/api/v1/products/export", headers=admin)
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    body = exported.text
    assert "name,sku,barcode" in body.splitlines()[0]
    assert product.sku in body
    assert "EXPORT-BC-1" in body


def test_parse_csv_rows_skips_blank_and_requires_headers():
    rows = parse_csv_rows(
        "name,sku,selling_price\nWidget,W-1,9.99\n,,\nGadget,G-1,4.50\n"
    )
    assert len(rows) == 2
    assert rows[0]["sku"] == "W-1"
    assert rows[1]["name"] == "Gadget"


@pytest.mark.asyncio
async def test_product_import_dry_run_and_commit(client):
    ac, seeded = client
    admin = await _admin(ac, seeded)

    unit = await ac.post(
        "/api/v1/catalog/units",
        headers=admin,
        json={"code": "IMPPCS", "name": "Import Pieces"},
    )
    assert unit.status_code == 200, unit.text

    csv_ok = (
        "name,sku,barcode,category,brand,unit,cost_price,selling_price,stock_qty,reorder_level,tax_exempt,tracks_batches\n"
        "Import Water,IMP-WATER-1,IMPWATER1,,,IMPPCS,1.5,4.0,25,5,false,false\n"
        "Import Snack,IMP-SNACK-1,,,,IMPPCS,0.8,2.5,10,2,false,false\n"
    )
    dry = await ac.post(
        "/api/v1/products/import?dry_run=true",
        headers=admin,
        files={"file": ("products.csv", csv_ok, "text/csv")},
    )
    assert dry.status_code == 200, dry.text
    report = dry.json()["data"]
    assert report["can_commit"] is True
    assert report["valid_rows"] == 2
    assert report["error_rows"] == 0

    commit = await ac.post(
        "/api/v1/products/import?dry_run=false",
        headers=admin,
        files={"file": ("products.csv", csv_ok, "text/csv")},
    )
    assert commit.status_code == 200, commit.text
    body = commit.json()["data"]
    assert body["imported"] == 2
    created = {p["sku"]: p for p in body["created"]}
    assert created["IMP-WATER-1"]["stock_qty"] == 25.0
    assert created["IMP-SNACK-1"]["selling_price"] == 2.5

    listed = await ac.get("/api/v1/products", headers=admin)
    skus = {p["sku"] for p in listed.json()["data"]}
    assert "IMP-WATER-1" in skus
    assert "IMP-SNACK-1" in skus


@pytest.mark.asyncio
async def test_product_import_rejects_duplicate_sku(client):
    ac, seeded = client
    admin = await _admin(ac, seeded)

    await ac.post(
        "/api/v1/products",
        headers=admin,
        json={"name": "Existing", "sku": "DUP-SKU-1", "selling_price": 1},
    )
    csv_bad = "name,sku,selling_price\nClash,DUP-SKU-1,3\n"
    dry = await ac.post(
        "/api/v1/products/import?dry_run=true",
        headers=admin,
        files={"file": ("bad.csv", csv_bad, "text/csv")},
    )
    assert dry.status_code == 200, dry.text
    report = dry.json()["data"]
    assert report["can_commit"] is False
    assert report["error_rows"] == 1
    assert any("sku already exists" in e for e in report["rows"][0]["errors"])

    commit = await ac.post(
        "/api/v1/products/import?dry_run=false",
        headers=admin,
        files={"file": ("bad.csv", csv_bad, "text/csv")},
    )
    assert commit.status_code == 400
    detail = commit.json()["detail"]
    assert detail["code"] == "IMPORT_VALIDATION_FAILED"


@pytest.mark.asyncio
async def test_product_import_tenant_isolation(client):
    ac, seeded = client
    alpha = await _admin(ac, seeded)
    beta = await auth_headers(ac, email="cashier@beta.example.com", tenant_slug="beta")

    csv_alpha = "name,sku,selling_price\nAlpha Only,ALPHA-ONLY-1,9\n"
    r = await ac.post(
        "/api/v1/products/import?dry_run=false",
        headers=alpha,
        files={"file": ("a.csv", csv_alpha, "text/csv")},
    )
    assert r.status_code == 200, r.text

    beta_list = await ac.get("/api/v1/products", headers=beta)
    assert beta_list.status_code == 200
    skus = {p["sku"] for p in beta_list.json()["data"]}
    assert "ALPHA-ONLY-1" not in skus
