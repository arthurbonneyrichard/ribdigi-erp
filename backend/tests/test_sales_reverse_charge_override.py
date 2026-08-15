"""Sales invoice header reverse-charge override (BR-12.2 purchase parity)."""

from __future__ import annotations

import pyotp
import pytest

from app import models as m
from app import sales as sales_svc
from tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_sales_header_rc_forces_memo_with_standard_rate(db_session, seeded):
    tenant_id = seeded["t1"].id
    rate = m.TaxRate(
        tenant_id=tenant_id,
        name="Std VAT",
        rate=15,
        tax_type="vat",
        pricing_mode="exclusive",
        is_reverse_charge=False,
        is_default=True,
        is_active=True,
    )
    db_session.add(rate)
    await db_session.flush()

    product = seeded["p1"]
    product.tax_rate_id = rate.id
    product.tax_exempt = False
    # selling_price on seed p1 is typically 2
    party = m.Party(tenant_id=tenant_id, name="RC Buyer", kind="customer", credit_limit=0)
    db_session.add(party)
    await db_session.flush()

    inv = await sales_svc.create_sales_invoice(
        db_session,
        tenant_id=tenant_id,
        user_id=seeded["admin1"].id,
        customer_id=party.id,
        is_reverse_charge=True,
        items=[{"product_id": product.id, "quantity": 10, "unit_price": 100, "tax_rate": 15}],
    )
    await db_session.commit()

    assert inv.is_reverse_charge is True
    assert float(inv.subtotal) == 1000.0
    assert float(inv.tax_amount) == 0.0
    assert float(inv.reverse_charge_tax) == 150.0
    assert float(inv.total_amount) == 1000.0

    items = await sales_svc.list_invoice_items(db_session, tenant_id, inv.id)
    assert items
    assert all(bool(i.is_reverse_charge) for i in items)


@pytest.mark.asyncio
async def test_sales_header_rc_api(client):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    headers = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    created = await ac.post(
        "/api/v1/sales/invoices",
        headers=headers,
        json={
            "customer_id": seed["party1"].id,
            "is_reverse_charge": True,
            "items": [
                {
                    "product_id": seed["p1"].id,
                    "quantity": 2,
                    "unit_price": 50,
                    "tax_rate": 10,
                }
            ],
        },
    )
    assert created.status_code == 200, created.text
    inv = created.json()["data"]
    assert inv["is_reverse_charge"] is True
    assert inv["tax_amount"] == 0
    assert inv["reverse_charge_tax"] == 10  # 2 * 50 * 10%
    assert inv["subtotal"] == 100
    assert inv["total_amount"] == 100
    assert all(i["is_reverse_charge"] for i in inv["items"])
