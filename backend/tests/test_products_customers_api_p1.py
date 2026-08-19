"""Stage 19 P1: Products + Customers API fidelity (BR-18.2–18.3)."""

from __future__ import annotations

import io
from pathlib import Path

import pyotp
import pytest

from app import barcodes as barcode_svc
from app import catalog_meta as catalog_meta_svc
from app import models as m
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_products_catalog_crud_import_stock_barcode_jwt(client, db_session):
    """BR-18.2: catalog CRUD, import, stock levels, barcode lookup via JWT."""
    ac, seed = client
    headers = await _mgr(ac)
    await catalog_meta_svc.ensure_default_catalog(db_session, seed["t1"].id)
    await db_session.commit()

    cat = await ac.post(
        "/api/v1/catalog/categories",
        headers=headers,
        json={"code": "S19P1C", "name": "S19 P1 Cat"},
    )
    assert cat.status_code == 200, cat.text
    cat_id = cat.json()["data"]["id"]
    await ac.patch(
        f"/api/v1/catalog/categories/{cat_id}",
        headers=headers,
        json={"name": "S19 P1 Cat Updated"},
    )

    brand = await ac.post(
        "/api/v1/catalog/brands",
        headers=headers,
        json={"code": "S19P1B", "name": "S19 P1 Brand"},
    )
    assert brand.status_code == 200, brand.text
    brand_id = brand.json()["data"]["id"]

    unit = await ac.post(
        "/api/v1/catalog/units",
        headers=headers,
        json={"code": "S19P1U", "name": "S19 P1 Unit"},
    )
    assert unit.status_code == 200, unit.text
    unit_id = unit.json()["data"]["id"]

    code = barcode_svc.generate_ean13(body12="200111222333")
    created = await ac.post(
        "/api/v1/products",
        headers=headers,
        json={
            "name": "S19 P1 Product",
            "sku": "S19-P1-SKU",
            "barcode": code,
            "category_id": cat_id,
            "brand_id": brand_id,
            "unit_id": unit_id,
            "cost_price": 3,
            "selling_price": 7,
            "stock_qty": 0,
        },
    )
    assert created.status_code == 200, created.text
    product_id = created.json()["data"]["id"]

    got = await ac.get(f"/api/v1/products/{product_id}", headers=headers)
    assert got.status_code == 200, got.text
    assert got.json()["data"]["sku"] == "S19-P1-SKU"
    assert "stock_qty" in got.json()["data"]

    patched = await ac.patch(
        f"/api/v1/products/{product_id}",
        headers=headers,
        json={"selling_price": 8, "is_active": True},
    )
    assert patched.status_code == 200, patched.text

    stock_in = await ac.post(
        "/api/v1/inventory/stock-in",
        headers=headers,
        json={"product_id": product_id, "quantity": 5, "notes": "S19 P1 stock"},
    )
    assert stock_in.status_code == 200, stock_in.text

    wh = await ac.get(f"/api/v1/products/{product_id}/warehouse-stock", headers=headers)
    assert wh.status_code == 200, wh.text
    wh_data = wh.json()["data"]
    assert wh_data["product_id"] == product_id
    assert float(wh_data.get("stock_qty") or wh_data.get("available_qty") or 0) >= 5
    assert isinstance(wh_data.get("warehouses"), list)

    listed = await ac.get("/api/v1/products", headers=headers)
    assert listed.status_code == 200, listed.text
    assert any(p["id"] == product_id for p in listed.json()["data"])

    tmpl = await ac.get("/api/v1/products/import/template", headers=headers)
    assert tmpl.status_code == 200
    assert "name,sku" in tmpl.text

    csv_body = (
        "name,sku,barcode,category_code,brand_code,unit_code,cost_price,selling_price,reorder_level,stock_qty,tracks_batches\n"
        "S19 Import,S19-P1-IMP,,GEN,,PCS,1,2,1,0,false\n"
    )
    dry = await ac.post(
        "/api/v1/products/import?dry_run=true",
        headers=headers,
        files={"file": ("products.csv", io.BytesIO(csv_body.encode()), "text/csv")},
    )
    assert dry.status_code == 200, dry.text
    assert dry.json()["data"]["dry_run"] is True
    assert dry.json()["data"]["valid_rows"] >= 1

    lookup = await ac.get(
        f"/api/v1/inventory/products/lookup?q={code}&barcode={code}",
        headers=headers,
    )
    assert lookup.status_code == 200, lookup.text
    ids = {row["product_id"] for row in lookup.json()["data"]}
    assert product_id in ids

    soft = await ac.patch(
        f"/api/v1/products/{product_id}",
        headers=headers,
        json={"is_active": False},
    )
    assert soft.status_code == 200, soft.text
    assert soft.json()["data"]["is_active"] is False


@pytest.mark.asyncio
async def test_customers_groups_balance_history_jwt(client):
    """BR-18.3: customers/groups CRUD, balance field, purchase history via JWT."""
    ac, seed = client
    headers = await _mgr(ac)

    group = await ac.post(
        "/api/v1/customers/groups",
        headers=headers,
        json={"name": "S19 P1 Group", "discount_percent": 3},
    )
    assert group.status_code == 200, group.text
    group_id = group.json()["data"]["id"]

    patched_g = await ac.patch(
        f"/api/v1/customers/groups/{group_id}",
        headers=headers,
        json={"discount_percent": 4},
    )
    assert patched_g.status_code == 200, patched_g.text

    created = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={
            "name": "S19 P1 Buyer",
            "code": "S19-P1-CUST",
            "party_type": "registered",
            "customer_group_id": group_id,
            "credit_limit": 1000,
        },
    )
    assert created.status_code == 200, created.text
    customer = created.json()["data"]
    customer_id = customer["id"]
    assert "balance" in customer

    detail = await ac.get(f"/api/v1/customers/{customer_id}", headers=headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()["data"]["code"] == "S19-P1-CUST"
    assert "balance" in detail.json()["data"]

    inv = await ac.post(
        "/api/v1/sales/invoices",
        headers=headers,
        json={
            "customer_id": customer_id,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 5}],
        },
    )
    assert inv.status_code == 200, inv.text

    history = await ac.get(f"/api/v1/customers/{customer_id}/history", headers=headers)
    assert history.status_code == 200, history.text
    assert len(history.json()["data"]["invoices"]) >= 1

    soft = await ac.delete(f"/api/v1/customers/{customer_id}", headers=headers)
    assert soft.status_code == 200, soft.text
    assert soft.json()["data"]["status"] == "inactive"


@pytest.mark.asyncio
async def test_api_key_read_products_and_customers(client, db_session):
    """JWT-equivalent read via X-API-Key for inventory + sales modules."""
    ac, seed = client
    admin = await _admin(ac, seed)
    await catalog_meta_svc.ensure_default_catalog(db_session, seed["t1"].id)
    await db_session.commit()

    created = await ac.post(
        "/api/v1/api-keys",
        headers=admin,
        json={
            "name": "Stage19 P1 reader",
            "permissions": {"inventory": ["read"], "sales": ["read"]},
        },
    )
    assert created.status_code == 200, created.text
    secret = created.json()["data"]["api_key"]
    key_headers = {"X-API-Key": secret, "X-Tenant-ID": seed["t1"].id}

    products = await ac.get("/api/v1/products", headers=key_headers)
    assert products.status_code == 200, products.text

    customers = await ac.get("/api/v1/customers", headers=key_headers)
    assert customers.status_code == 200, customers.text

    denied = await ac.post(
        "/api/v1/products",
        headers=key_headers,
        json={"name": "Nope", "sku": "S19-P1-DENY", "selling_price": 1, "cost_price": 1},
    )
    assert denied.status_code == 403


def test_br_18_2_18_3_and_plan_synced():
    br = (ROOT / "docs" / "BUSINESS_REQUIREMENTS_DOCUMENT.md").read_text(encoding="utf-8")
    p18_2 = br.split("#### BR-18.2 Products API")[1].split("#### BR-18.3")[0]
    assert "[x] CRUD operations for products, categories, brands, units" in p18_2
    assert "[x] Bulk import/export" in p18_2
    assert "[x] Stock level queries" in p18_2
    assert "[x] Barcode lookup" in p18_2
    assert "Stage 19 P1" in p18_2

    p18_3 = br.split("#### BR-18.3 Customers API")[1].split("#### BR-18.4")[0]
    assert "[x] CRUD operations for customers and customer groups" in p18_3
    assert "[x] Balance inquiry" in p18_3
    assert "[x] Purchase history" in p18_3
    assert "Stage 19 P1" in p18_3

    plan = (ROOT / "docs" / "STAGE_19_PLAN.md").read_text(encoding="utf-8")
    p1_line = [ln for ln in plan.splitlines() if "| **P1**" in ln][0]
    assert "COMPLETE" in p1_line
    assert "test_products_customers_api_p1.py" in plan
