"""Product sales report store/category filters (BR-14.1)."""

from __future__ import annotations

from datetime import datetime

import pyotp
import pytest

from app import models as m
from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_product_sales_filter_by_store_and_category(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    tenant_id = seed["t1"].id
    customer = seed["party1"]
    p1 = seed["p1"]

    cat_a = m.ProductCategory(tenant_id=tenant_id, code="CAT-A", name="Category A")
    cat_b = m.ProductCategory(tenant_id=tenant_id, code="CAT-B", name="Category B")
    db_session.add_all([cat_a, cat_b])
    await db_session.flush()

    p1.category_id = cat_a.id
    p2 = m.Product(
        tenant_id=tenant_id,
        sku="SKU-PSF-2",
        name="Other Cat Product",
        selling_price=20,
        cost_price=10,
        stock_qty=50,
        category_id=cat_b.id,
    )
    db_session.add(p2)
    await db_session.flush()

    store_a = m.Store(tenant_id=tenant_id, code="ST-A", name="Store A")
    store_b = m.Store(tenant_id=tenant_id, code="ST-B", name="Store B")
    db_session.add_all([store_a, store_b])
    await db_session.flush()

    async def _invoice(store_id, product, amount, number):
        inv = m.SalesInvoice(
            tenant_id=tenant_id,
            invoice_number=number,
            customer_id=customer.id,
            store_id=store_id,
            status="posted",
            subtotal=amount,
            tax_amount=0,
            total_amount=amount,
            posted_at=datetime.utcnow(),
        )
        db_session.add(inv)
        await db_session.flush()
        db_session.add(
            m.SalesInvoiceItem(
                tenant_id=tenant_id,
                sales_invoice_id=inv.id,
                product_id=product.id,
                quantity=1,
                unit_price=amount,
                line_subtotal=amount,
                line_total=amount,
            )
        )

    await _invoice(store_a.id, p1, 100, "INV-PSF-A1")
    await _invoice(store_b.id, p1, 40, "INV-PSF-B1")
    await _invoice(store_a.id, p2, 25, "INV-PSF-A2")
    await db_session.commit()

    all_r = await ac.get("/api/v1/reports/sales/products", headers=headers)
    assert all_r.status_code == 200, all_r.text
    all_data = all_r.json()["data"]
    by_sku = {p["sku"]: p for p in all_data["products"]}
    assert abs(float(by_sku[p1.sku]["revenue"]) - 140) < 0.01
    assert abs(float(by_sku["SKU-PSF-2"]["revenue"]) - 25) < 0.01
    assert by_sku[p1.sku]["category_name"] == "Category A"

    store_r = await ac.get(
        f"/api/v1/reports/sales/products?store_id={store_a.id}",
        headers=headers,
    )
    assert store_r.status_code == 200
    store_data = store_r.json()["data"]
    assert store_data["store_id"] == store_a.id
    store_skus = {p["sku"]: p for p in store_data["products"]}
    assert abs(float(store_skus[p1.sku]["revenue"]) - 100) < 0.01
    assert abs(float(store_skus["SKU-PSF-2"]["revenue"]) - 25) < 0.01
    assert abs(float(store_data["total_revenue"]) - 125) < 0.01

    cat_r = await ac.get(
        f"/api/v1/reports/sales/products?category_id={cat_a.id}",
        headers=headers,
    )
    assert cat_r.status_code == 200
    cat_data = cat_r.json()["data"]
    assert cat_data["category_id"] == cat_a.id
    assert cat_data["category_name"] == "Category A"
    assert len(cat_data["products"]) == 1
    assert cat_data["products"][0]["sku"] == p1.sku
    assert abs(float(cat_data["total_revenue"]) - 140) < 0.01

    both = await ac.get(
        f"/api/v1/reports/sales/products?store_id={store_a.id}&category_id={cat_a.id}",
        headers=headers,
    )
    assert both.status_code == 200
    both_data = both.json()["data"]
    assert len(both_data["products"]) == 1
    assert abs(float(both_data["total_revenue"]) - 100) < 0.01

    bad = await ac.get(
        "/api/v1/reports/sales/products?category_id=00000000-0000-0000-0000-000000000000",
        headers=headers,
    )
    assert bad.status_code == 404
