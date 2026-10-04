"""Daily/monthly sales and returns store filter (BR-14.1 / BR-14.5)."""

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
async def test_sales_daily_monthly_filter_by_store(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    tenant_id = seed["t1"].id
    customer = seed["party1"]

    store_a = m.Store(tenant_id=tenant_id, code="SD-A", name="Sales Daily A")
    store_b = m.Store(tenant_id=tenant_id, code="SD-B", name="Sales Daily B")
    db_session.add_all([store_a, store_b])
    await db_session.flush()

    now = datetime.utcnow()
    db_session.add_all(
        [
            m.SalesInvoice(
                tenant_id=tenant_id,
                invoice_number="INV-SD-A1",
                customer_id=customer.id,
                store_id=store_a.id,
                status="posted",
                subtotal=80,
                tax_amount=0,
                discount_amount=0,
                total_amount=80,
                posted_at=now,
            ),
            m.SalesInvoice(
                tenant_id=tenant_id,
                invoice_number="INV-SD-B1",
                customer_id=customer.id,
                store_id=store_b.id,
                status="posted",
                subtotal=35,
                tax_amount=0,
                discount_amount=0,
                total_amount=35,
                posted_at=now,
            ),
        ]
    )
    await db_session.commit()

    daily_a = await ac.get(
        f"/api/v1/reports/sales/daily?store_id={store_a.id}",
        headers=headers,
    )
    assert daily_a.status_code == 200, daily_a.text
    ddata = daily_a.json()["data"]
    assert ddata["store_id"] == store_a.id
    assert ddata["store_name"] == "Sales Daily A"
    assert abs(float(ddata["total_revenue"]) - 80) < 0.01
    assert ddata["invoice_count"] == 1

    monthly_b = await ac.get(
        f"/api/v1/reports/sales/monthly?store_id={store_b.id}",
        headers=headers,
    )
    assert monthly_b.status_code == 200, monthly_b.text
    mdata = monthly_b.json()["data"]
    assert mdata["store_id"] == store_b.id
    assert abs(float(mdata["total_revenue"]) - 35) < 0.01

    missing = await ac.get(
        "/api/v1/reports/sales/daily?store_id=00000000-0000-0000-0000-000000000000",
        headers=headers,
    )
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_sales_returns_filter_by_invoice_store(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    tenant_id = seed["t1"].id
    customer = seed["party1"]

    store_a = m.Store(tenant_id=tenant_id, code="SR-A", name="Sales Return A")
    store_b = m.Store(tenant_id=tenant_id, code="SR-B", name="Sales Return B")
    db_session.add_all([store_a, store_b])
    await db_session.flush()

    inv_a = m.SalesInvoice(
        tenant_id=tenant_id,
        invoice_number="INV-SR-A1",
        customer_id=customer.id,
        store_id=store_a.id,
        status="posted",
        subtotal=50,
        tax_amount=0,
        total_amount=50,
        posted_at=datetime.utcnow(),
    )
    inv_b = m.SalesInvoice(
        tenant_id=tenant_id,
        invoice_number="INV-SR-B1",
        customer_id=customer.id,
        store_id=store_b.id,
        status="posted",
        subtotal=40,
        tax_amount=0,
        total_amount=40,
        posted_at=datetime.utcnow(),
    )
    db_session.add_all([inv_a, inv_b])
    await db_session.flush()

    ret_a = m.SalesReturn(
        tenant_id=tenant_id,
        return_number="SR-A1",
        customer_id=customer.id,
        sales_invoice_id=inv_a.id,
        status="posted",
        reason="damaged",
        total_amount=12,
        posted_at=datetime.utcnow(),
    )
    ret_b = m.SalesReturn(
        tenant_id=tenant_id,
        return_number="SR-B1",
        customer_id=customer.id,
        sales_invoice_id=inv_b.id,
        status="posted",
        reason="other",
        total_amount=8,
        posted_at=datetime.utcnow(),
    )
    db_session.add_all([ret_a, ret_b])
    await db_session.commit()

    filtered = await ac.get(
        f"/api/v1/reports/sales/returns?store_id={store_a.id}",
        headers=headers,
    )
    assert filtered.status_code == 200, filtered.text
    data = filtered.json()["data"]
    assert data["store_id"] == store_a.id
    assert data["store_name"] == "Sales Return A"
    assert data["return_count"] == 1
    assert abs(float(data["total_amount"]) - 12) < 0.01
    assert data["returns"][0]["return_number"] == "SR-A1"
