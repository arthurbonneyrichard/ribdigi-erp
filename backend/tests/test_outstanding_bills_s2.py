"""Stage 8 S2: outstanding bills for AR/AP (Credit UI contract)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pyotp
import pytest

from app import accounting as accounting_svc
from app import models as m
from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_customer_outstanding_lists_open_invoices(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    tenant_id = seed["t1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)

    customer = m.Party(
        tenant_id=tenant_id, name="AR Customer", kind="customer", credit_limit=500, balance=80
    )
    db_session.add(customer)
    await db_session.flush()

    open_inv = m.SalesInvoice(
        tenant_id=tenant_id,
        invoice_number="INV-OUT-1",
        customer_id=customer.id,
        status="posted",
        subtotal=80,
        tax_amount=0,
        total_amount=80,
        paid_amount=0,
        due_date=datetime.utcnow() + timedelta(days=14),
        posted_at=datetime.utcnow(),
        created_by=seed["admin1"].id,
    )
    paid_inv = m.SalesInvoice(
        tenant_id=tenant_id,
        invoice_number="INV-OUT-PAID",
        customer_id=customer.id,
        status="paid",
        subtotal=20,
        tax_amount=0,
        total_amount=20,
        paid_amount=20,
        due_date=datetime.utcnow() - timedelta(days=1),
        posted_at=datetime.utcnow() - timedelta(days=5),
        created_by=seed["admin1"].id,
    )
    db_session.add_all([open_inv, paid_inv])
    await db_session.commit()

    r = await ac.get(f"/api/v1/customers/{customer.id}/outstanding", headers=headers)
    assert r.status_code == 200, r.text
    rows = r.json()["data"]
    assert len(rows) == 1
    assert rows[0]["invoice_number"] == "INV-OUT-1"
    assert rows[0]["amount"] == 80.0
    assert rows[0]["document_type"] == "sales_invoice"


@pytest.mark.asyncio
async def test_supplier_outstanding_lists_open_bills(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    tenant_id = seed["t1"].id

    supplier = m.Party(
        tenant_id=tenant_id, name="AP Vendor", kind="supplier", credit_limit=0, balance=60
    )
    db_session.add(supplier)
    await db_session.flush()
    inv = m.PurchaseInvoice(
        tenant_id=tenant_id,
        invoice_number="PI-OUT-1",
        supplier_id=supplier.id,
        status="unpaid",
        subtotal=60,
        tax_amount=0,
        total_amount=60,
        paid_amount=0,
        due_date=datetime.utcnow() + timedelta(days=3),
        approved_at=datetime.utcnow(),
        created_by=seed["admin1"].id,
    )
    db_session.add(inv)
    await db_session.commit()

    r = await ac.get(f"/api/v1/suppliers/{supplier.id}/outstanding", headers=headers)
    assert r.status_code == 200, r.text
    rows = r.json()["data"]
    assert len(rows) == 1
    assert rows[0]["invoice_number"] == "PI-OUT-1"
    assert rows[0]["document_type"] == "purchase_invoice"
    assert rows[0]["amount"] == 60.0


@pytest.mark.asyncio
async def test_outstanding_rbac_and_not_found(client):
    ac, seed = client
    headers = await _admin(ac, seed)
    missing = await ac.get(
        "/api/v1/customers/00000000-0000-0000-0000-000000000099/outstanding",
        headers=headers,
    )
    assert missing.status_code == 404

    cashier = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    denied = await ac.get(
        f"/api/v1/customers/{seed['party1'].id}/outstanding", headers=cashier
    )
    assert denied.status_code == 403
