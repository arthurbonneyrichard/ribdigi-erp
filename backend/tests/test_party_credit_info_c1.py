"""Customer/supplier credit info endpoints (BR-7.1 / BR-6.1)."""

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
async def test_customer_credit_info_limit_and_open_sales(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    tenant_id = seed["t1"].id
    customer = seed["party1"]
    customer.credit_limit = 200
    customer.balance = 80
    await db_session.flush()

    inv = m.SalesInvoice(
        tenant_id=tenant_id,
        invoice_number="INV-CR-1",
        customer_id=customer.id,
        status="posted",
        subtotal=100,
        tax_amount=0,
        total_amount=100,
        paid_amount=20,
        posted_at=datetime.utcnow(),
    )
    db_session.add(inv)
    await db_session.commit()

    r = await ac.get(f"/api/v1/customers/{customer.id}/credit", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["credit_limit"] == 200
    assert data["credit_unlimited"] is False
    assert abs(float(data["outstanding_balance"]) - 80) < 0.01
    assert abs(float(data["available_credit"]) - 120) < 0.01
    assert data["is_over_limit"] is False
    assert data["open_invoice_count"] == 1
    assert abs(float(data["credit_sales"][0]["amount"]) - 80) < 0.01

    customer.balance = 250
    await db_session.commit()
    over = await ac.get(f"/api/v1/customers/{customer.id}/credit", headers=headers)
    assert over.status_code == 200
    assert over.json()["data"]["is_over_limit"] is True
    assert float(over.json()["data"]["available_credit"]) == 0

    missing = await ac.get(
        "/api/v1/customers/00000000-0000-0000-0000-000000000000/credit",
        headers=headers,
    )
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_supplier_credit_info_open_bills(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    tenant_id = seed["t1"].id

    supplier = m.Party(
        tenant_id=tenant_id, name="Credit Supplier", kind="supplier", balance=55
    )
    db_session.add(supplier)
    await db_session.flush()

    po = m.PurchaseOrder(
        tenant_id=tenant_id,
        po_number="PO-CR-1",
        supplier_id=supplier.id,
        status="received",
        total_amount=55,
        paid_amount=0,
    )
    db_session.add(po)
    await db_session.flush()
    db_session.add(
        m.PurchaseInvoice(
            tenant_id=tenant_id,
            invoice_number="PI-CR-1",
            supplier_id=supplier.id,
            purchase_order_id=po.id,
            status="unpaid",
            total_amount=55,
            paid_amount=0,
        )
    )
    await db_session.commit()

    r = await ac.get(f"/api/v1/suppliers/{supplier.id}/credit", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert abs(float(data["outstanding_balance"]) - 55) < 0.01
    assert data["open_bill_count"] == 1
    assert data["open_bills"][0]["document_type"] == "purchase_invoice"
    assert abs(float(data["open_bills"][0]["amount"]) - 55) < 0.01
