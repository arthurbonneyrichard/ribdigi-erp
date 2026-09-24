"""Customer sales report store filter (BR-14.1)."""

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
async def test_customer_sales_filter_by_store(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    tenant_id = seed["t1"].id
    customer = seed["party1"]

    store_a = m.Store(tenant_id=tenant_id, code="CS-A", name="Cust Sales A")
    store_b = m.Store(tenant_id=tenant_id, code="CS-B", name="Cust Sales B")
    db_session.add_all([store_a, store_b])
    await db_session.flush()

    other = m.Party(
        tenant_id=tenant_id,
        kind="customer",
        name="Other Buyer",
        email="other-cs@example.com",
    )
    db_session.add(other)
    await db_session.flush()

    async def _invoice(store_id, party_id, amount, number):
        inv = m.SalesInvoice(
            tenant_id=tenant_id,
            invoice_number=number,
            customer_id=party_id,
            store_id=store_id,
            status="posted",
            subtotal=amount,
            tax_amount=0,
            total_amount=amount,
            posted_at=datetime.utcnow(),
        )
        db_session.add(inv)

    await _invoice(store_a.id, customer.id, 100, "INV-CS-A1")
    await _invoice(store_b.id, customer.id, 40, "INV-CS-B1")
    await _invoice(store_a.id, other.id, 25, "INV-CS-A2")
    await db_session.commit()

    all_r = await ac.get("/api/v1/reports/sales/customers", headers=headers)
    assert all_r.status_code == 200, all_r.text
    all_data = all_r.json()["data"]
    by_name = {c["name"]: c for c in all_data["customers"]}
    assert abs(float(by_name[customer.name]["revenue"]) - 140) < 0.01
    assert abs(float(by_name["Other Buyer"]["revenue"]) - 25) < 0.01

    store_r = await ac.get(
        f"/api/v1/reports/sales/customers?store_id={store_a.id}",
        headers=headers,
    )
    assert store_r.status_code == 200, store_r.text
    store_data = store_r.json()["data"]
    assert store_data["store_id"] == store_a.id
    store_names = {c["name"]: c for c in store_data["customers"]}
    assert abs(float(store_names[customer.name]["revenue"]) - 100) < 0.01
    assert abs(float(store_names["Other Buyer"]["revenue"]) - 25) < 0.01
    assert abs(float(store_data["total_revenue"]) - 125) < 0.01
    assert customer.name in store_names
    assert "Other Buyer" in store_names

    store_b_r = await ac.get(
        f"/api/v1/reports/sales/customers?store_id={store_b.id}",
        headers=headers,
    )
    assert store_b_r.status_code == 200
    b_data = store_b_r.json()["data"]
    assert abs(float(b_data["total_revenue"]) - 40) < 0.01
    assert len(b_data["customers"]) == 1

    bad = await ac.get(
        "/api/v1/reports/sales/customers?store_id=00000000-0000-0000-0000-000000000000",
        headers=headers,
    )
    assert bad.status_code == 404
