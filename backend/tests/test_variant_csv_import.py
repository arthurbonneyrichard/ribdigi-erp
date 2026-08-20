"""Product variant CSV import (create/upsert catalog fields; no stock writes)."""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from app.variant_import import TEMPLATE_COLUMNS, template_csv
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def _csv(body: str) -> dict:
    return {"file": ("variants.csv", io.BytesIO(body.encode()), "text/csv")}


@pytest.mark.asyncio
async def test_variant_csv_import_template_dry_run_commit_and_upsert(client):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    product_id = seed["p1"].id

    tmpl = await ac.get("/api/v1/products/variants/import/template", headers=headers)
    assert tmpl.status_code == 200, tmpl.text
    assert "text/csv" in tmpl.headers.get("content-type", "")
    header = tmpl.text.splitlines()[0]
    for col in TEMPLATE_COLUMNS:
        assert col in header
    assert template_csv().startswith("product_sku,")

    csv_body = (
        "product_sku,product_id,name,sku,barcode,size,color,flavor,cost_price,selling_price,is_active\n"
        f"A-1,{product_id},Large,A-1-L,,L,Blue,Mint,1.10,2.75,true\n"
        "A-1,,Missing sku row,,,,,\n"
        "UNKNOWN,,Ghost,A-1-G,,S,,,,,\n"
    )
    dry = await ac.post(
        "/api/v1/products/variants/import?dry_run=true",
        headers=headers,
        files=_csv(csv_body),
    )
    assert dry.status_code == 200, dry.text
    data = dry.json()["data"]
    assert data["dry_run"] is True
    assert data["valid_rows"] == 1
    assert data["create_count"] == 1
    assert data["update_count"] == 0
    assert data["error_rows"] == 2
    assert data["created"] == []
    listed = await ac.get(f"/api/v1/products/{product_id}/variants", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["data"] == [] or all(v["sku"] != "A-1-L" for v in listed.json()["data"])

    committed = await ac.post(
        "/api/v1/products/variants/import?dry_run=false",
        headers=headers,
        files=_csv(csv_body),
    )
    assert committed.status_code == 200, committed.text
    result = committed.json()["data"]
    assert result["valid_rows"] == 1
    assert len(result["created"]) == 1
    created = result["created"][0]
    assert created["sku"] == "A-1-L"
    assert created["size"] == "L"
    assert created["color"] == "Blue"
    assert created["flavor"] == "Mint"
    assert float(created["selling_price"]) == 2.75
    assert float(created["stock_qty"]) == 0

    upsert_body = (
        "product_sku,name,sku,size,color,flavor,selling_price,is_active\n"
        "A-1,Large updated,A-1-L,XL,Red,Vanilla,3.25,true\n"
    )
    upsert = await ac.post(
        "/api/v1/products/variants/import?dry_run=false",
        headers=headers,
        files=_csv(upsert_body),
    )
    assert upsert.status_code == 200, upsert.text
    up = upsert.json()["data"]
    assert up["create_count"] == 0
    assert up["update_count"] == 1
    assert up["updated"][0]["name"] == "Large updated"
    assert up["updated"][0]["size"] == "XL"
    assert up["updated"][0]["color"] == "Red"
    assert up["updated"][0]["flavor"] == "Vanilla"
    assert float(up["updated"][0]["selling_price"]) == 3.25
    assert float(up["updated"][0]["stock_qty"]) == 0


@pytest.mark.asyncio
async def test_variant_csv_import_rejects_product_sku_clash_and_foreign_tenant(client):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    clash = await ac.post(
        "/api/v1/products/variants/import?dry_run=true",
        headers=headers,
        files=_csv("product_sku,name,sku\nA-1,Same as product,A-1\n"),
    )
    assert clash.status_code == 200, clash.text
    errors = clash.json()["data"]["errors"]
    assert clash.json()["data"]["valid_rows"] == 0
    assert any("sku already used by a product" in e for row in errors for e in row["errors"])

    beta = await auth_headers(ac, email="cashier@beta.example.com", tenant_slug="beta")
    foreign = await ac.post(
        "/api/v1/products/variants/import?dry_run=false",
        headers=beta,
        files=_csv("product_sku,name,sku\nA-1,Beta leak,A-1-X\n"),
    )
    assert foreign.status_code in {200, 403}
    if foreign.status_code == 200:
        data = foreign.json()["data"]
        assert data["valid_rows"] == 0
        assert data["created"] == []

    listed = await ac.get(f"/api/v1/products/{seed['p1'].id}/variants", headers=headers)
    assert listed.status_code == 200
    assert all(v["sku"] != "A-1-X" for v in listed.json()["data"])


@pytest.mark.asyncio
async def test_variant_csv_import_ignores_stock_qty_from_export_shape(client):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    csv_body = (
        "product_id,product_sku,product_name,name,sku,barcode,size,color,flavor,"
        "cost_price,selling_price,stock_qty,is_active\n"
        f"{seed['p1'].id},A-1,Alpha Widget,Export Shape,A-1-EXP,,M,Green,,1,4,99,true\n"
    )
    committed = await ac.post(
        "/api/v1/products/variants/import?dry_run=false",
        headers=headers,
        files=_csv(csv_body),
    )
    assert committed.status_code == 200, committed.text
    created = committed.json()["data"]["created"][0]
    assert created["sku"] == "A-1-EXP"
    assert created["color"] == "Green"
    assert float(created["stock_qty"]) == 0


def test_variant_import_routes_and_ui_when_mounted():
    from app.api import api

    paths = {getattr(r, "path", "") for r in api.routes}
    assert any(p.endswith("/products/variants/import") for p in paths)
    assert any(p.endswith("/products/variants/import/template") for p in paths)
    assert template_csv().splitlines()[0] == ",".join(TEMPLATE_COLUMNS)

    # Host/repo checkout only — Docker backend bind-mounts ./backend, not frontend.
    page = ROOT / "frontend/app/inventory/page.tsx"
    if page.exists():
        text = page.read_text(encoding="utf-8")
        assert "/products/variants/import" in text
        assert "Download variant template" in text
        assert "Import variants (CSV)" in text
        assert "Flavor (optional)" in text
    docs = ROOT / "docs/API_DOCUMENTATION.md"
    if docs.exists():
        assert "/products/variants/import" in docs.read_text(encoding="utf-8")
