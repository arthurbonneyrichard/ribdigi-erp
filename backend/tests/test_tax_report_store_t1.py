"""Tax report / filing store filter (BR-12.3 / BR-14.5)."""

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
async def test_tax_report_filters_output_by_store(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    tenant_id = seed["t1"].id
    customer = seed["party1"]

    store_a = m.Store(tenant_id=tenant_id, code="TAX-A", name="Tax Store A")
    store_b = m.Store(tenant_id=tenant_id, code="TAX-B", name="Tax Store B")
    db_session.add_all([store_a, store_b])
    await db_session.flush()

    now = datetime.utcnow()
    db_session.add_all(
        [
            m.SalesInvoice(
                tenant_id=tenant_id,
                invoice_number="INV-TAX-A1",
                customer_id=customer.id,
                store_id=store_a.id,
                status="posted",
                subtotal=100,
                tax_amount=15,
                discount_amount=0,
                total_amount=115,
                posted_at=now,
            ),
            m.SalesInvoice(
                tenant_id=tenant_id,
                invoice_number="INV-TAX-B1",
                customer_id=customer.id,
                store_id=store_b.id,
                status="posted",
                subtotal=40,
                tax_amount=6,
                discount_amount=0,
                total_amount=46,
                posted_at=now,
            ),
        ]
    )
    await db_session.commit()

    filtered = await ac.get(
        f"/api/v1/reports/tax?store_id={store_a.id}",
        headers=headers,
    )
    assert filtered.status_code == 200, filtered.text
    data = filtered.json()["data"]
    assert data["store_id"] == store_a.id
    assert data["store_name"] == "Tax Store A"
    assert abs(float(data["output_tax_invoices"]) - 15) < 0.01
    assert abs(float(data["output_tax"]) - 15) < 0.01
    assert data["invoice_count"] == 1

    other = await ac.get(
        f"/api/v1/reports/tax?store_id={store_b.id}",
        headers=headers,
    )
    assert other.status_code == 200, other.text
    odata = other.json()["data"]
    assert abs(float(odata["output_tax_invoices"]) - 6) < 0.01
    assert odata["invoice_count"] == 1

    filing = await ac.get(
        f"/api/v1/reports/tax/filing?store_id={store_a.id}",
        headers=headers,
    )
    assert filing.status_code == 200, filing.text
    fdata = filing.json()["data"]
    assert fdata["store_id"] == store_a.id
    assert abs(float(fdata["output_tax_invoices"]) - 15) < 0.01

    missing = await ac.get(
        "/api/v1/reports/tax?store_id=00000000-0000-0000-0000-000000000000",
        headers=headers,
    )
    assert missing.status_code == 404
