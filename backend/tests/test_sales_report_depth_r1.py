"""Stage 4 R1: sales report depth — customers, product filters, comparative (BR-14.1)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app import models as m
from app.stores import create_store
from tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_daily_comparative_and_customer_sales(client, db_session):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    tenant_id = seed["t1"].id
    customer = seed["party1"]
    today = datetime.utcnow().replace(hour=12, minute=0, second=0, microsecond=0)
    yesterday = today - timedelta(days=1)

    db_session.add_all(
        [
            m.SalesInvoice(
                tenant_id=tenant_id,
                invoice_number="INV-R1-TODAY",
                customer_id=customer.id,
                status="posted",
                subtotal=100,
                tax_amount=10,
                discount_amount=5,
                total_amount=110,
                posted_at=today,
            ),
            m.SalesInvoice(
                tenant_id=tenant_id,
                invoice_number="INV-R1-YDAY",
                customer_id=customer.id,
                status="posted",
                subtotal=40,
                tax_amount=0,
                total_amount=40,
                posted_at=yesterday,
            ),
        ]
    )
    await db_session.commit()

    daily = await ac.get(
        "/api/v1/reports/sales/daily",
        headers=headers,
        params={"date": today.date().isoformat()},
    )
    assert daily.status_code == 200, daily.text
    body = daily.json()["data"]
    assert body["total_revenue"] == pytest.approx(110.0)
    assert body["previous_day_revenue"] == pytest.approx(40.0)
    assert body["change_pct"] == pytest.approx(175.0)
    assert body["discounts"] == pytest.approx(5.0)

    customers = await ac.get("/api/v1/reports/sales/customers", headers=headers)
    assert customers.status_code == 200, customers.text
    data = customers.json()["data"]
    assert data["customer_count"] >= 1
    top = data["customers"][0]
    assert top["customer_id"] == customer.id
    assert top["sale_count"] >= 2
    assert top["revenue"] >= 150


@pytest.mark.asyncio
async def test_product_sales_store_and_category_filters(client, db_session):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    tenant_id = seed["t1"].id

    cat_a = m.ProductCategory(tenant_id=tenant_id, name="Cat A", code="CA")
    cat_b = m.ProductCategory(tenant_id=tenant_id, name="Cat B", code="CB")
    db_session.add_all([cat_a, cat_b])
    await db_session.flush()

    p_a = seed["p1"]
    p_a.category_id = cat_a.id
    p_b = m.Product(
        tenant_id=tenant_id,
        name="Beta Widget",
        sku="B-R1",
        cost_price=1,
        selling_price=8,
        stock_qty=20,
        category_id=cat_b.id,
    )
    db_session.add(p_b)
    await db_session.flush()

    store_a = await create_store(db_session, tenant_id=tenant_id, code="R1A", name="R1 Store A")
    store_b = await create_store(db_session, tenant_id=tenant_id, code="R1B", name="R1 Store B")
    await db_session.flush()

    now = datetime.utcnow()
    inv_a = m.SalesInvoice(
        tenant_id=tenant_id,
        invoice_number="INV-R1-A",
        customer_id=seed["party1"].id,
        store_id=store_a.id,
        status="posted",
        subtotal=20,
        tax_amount=0,
        total_amount=20,
        posted_at=now,
    )
    inv_b = m.SalesInvoice(
        tenant_id=tenant_id,
        invoice_number="INV-R1-B",
        customer_id=seed["party1"].id,
        store_id=store_b.id,
        status="posted",
        subtotal=80,
        tax_amount=0,
        total_amount=80,
        posted_at=now,
    )
    db_session.add_all([inv_a, inv_b])
    await db_session.flush()
    db_session.add_all(
        [
            m.SalesInvoiceItem(
                tenant_id=tenant_id,
                sales_invoice_id=inv_a.id,
                product_id=p_a.id,
                quantity=2,
                unit_price=10,
                line_total=20,
            ),
            m.SalesInvoiceItem(
                tenant_id=tenant_id,
                sales_invoice_id=inv_b.id,
                product_id=p_b.id,
                quantity=10,
                unit_price=8,
                line_total=80,
            ),
        ]
    )
    await db_session.commit()

    by_store = await ac.get(
        "/api/v1/reports/sales/products",
        headers=headers,
        params={"store_id": store_a.id},
    )
    assert by_store.status_code == 200, by_store.text
    products = by_store.json()["data"]["products"]
    ids = {p["product_id"] for p in products}
    assert p_a.id in ids
    assert p_b.id not in ids

    by_cat = await ac.get(
        "/api/v1/reports/sales/products",
        headers=headers,
        params={"category_id": cat_b.id},
    )
    assert by_cat.status_code == 200, by_cat.text
    cat_ids = {p["product_id"] for p in by_cat.json()["data"]["products"]}
    assert p_b.id in cat_ids
    assert p_a.id not in cat_ids

    foreign = await ac.get(
        "/api/v1/reports/sales/products",
        headers=headers,
        params={"store_id": "00000000-0000-0000-0000-000000000099"},
    )
    assert foreign.status_code == 404


@pytest.mark.asyncio
async def test_sales_customers_exportable(client):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    listed = await ac.get("/api/v1/reports/exportable", headers=headers)
    assert listed.status_code == 200
    assert "sales_customers" in listed.json()["data"]["types"]
