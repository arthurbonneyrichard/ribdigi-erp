"""Salesperson report store filter (BR-14.1 / BR-14.5)."""

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
async def test_salesperson_report_filter_by_store(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    tenant_id = seed["t1"].id
    seller = seed["admin1"]
    customer = seed["party1"]

    store_a = m.Store(tenant_id=tenant_id, code="SP-A", name="Salesperson A")
    store_b = m.Store(tenant_id=tenant_id, code="SP-B", name="Salesperson B")
    db_session.add_all([store_a, store_b])
    await db_session.flush()

    now = datetime.utcnow()
    db_session.add_all(
        [
            m.SalesInvoice(
                tenant_id=tenant_id,
                invoice_number="INV-SP-A1",
                customer_id=customer.id,
                store_id=store_a.id,
                status="posted",
                subtotal=120,
                tax_amount=0,
                total_amount=120,
                posted_at=now,
                created_by=seller.id,
            ),
            m.SalesInvoice(
                tenant_id=tenant_id,
                invoice_number="INV-SP-B1",
                customer_id=customer.id,
                store_id=store_b.id,
                status="posted",
                subtotal=45,
                tax_amount=0,
                total_amount=45,
                posted_at=now,
                created_by=seller.id,
            ),
            m.SalesInvoice(
                tenant_id=tenant_id,
                invoice_number="INV-SP-A2",
                customer_id=customer.id,
                store_id=store_a.id,
                status="posted",
                subtotal=30,
                tax_amount=0,
                total_amount=30,
                posted_at=now,
                created_by=seller.id,
            ),
        ]
    )
    await db_session.commit()

    all_r = await ac.get("/api/v1/reports/sales/salesperson", headers=headers)
    assert all_r.status_code == 200, all_r.text
    all_data = all_r.json()["data"]
    by_id = {s["user_id"]: s for s in all_data["salespeople"] if s.get("user_id")}
    assert abs(float(by_id[seller.id]["revenue"]) - 195) < 0.01

    store_r = await ac.get(
        f"/api/v1/reports/sales/salesperson?store_id={store_a.id}",
        headers=headers,
    )
    assert store_r.status_code == 200, store_r.text
    store_data = store_r.json()["data"]
    assert store_data["store_id"] == store_a.id
    assert store_data["store_name"] == "Salesperson A"
    assert abs(float(store_data["total_revenue"]) - 150) < 0.01
    filtered = {s["user_id"]: s for s in store_data["salespeople"] if s.get("user_id")}
    assert abs(float(filtered[seller.id]["revenue"]) - 150) < 0.01
    assert filtered[seller.id]["invoice_count"] == 2

    missing = await ac.get(
        "/api/v1/reports/sales/salesperson?store_id=00000000-0000-0000-0000-000000000000",
        headers=headers,
    )
    assert missing.status_code == 404
