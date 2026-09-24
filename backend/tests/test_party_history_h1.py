"""Customer and supplier purchase/return/payment history (BR-7.1 / BR-6.1)."""

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
async def test_customer_history_purchases_returns_payments(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    tenant_id = seed["t1"].id
    customer = seed["party1"]
    product = seed["p1"]

    inv = m.SalesInvoice(
        tenant_id=tenant_id,
        invoice_number="INV-HIST-1",
        customer_id=customer.id,
        status="posted",
        subtotal=100,
        tax_amount=0,
        total_amount=100,
        paid_amount=40,
        posted_at=datetime.utcnow(),
    )
    db_session.add(inv)
    await db_session.flush()

    ret = m.SalesReturn(
        tenant_id=tenant_id,
        return_number="SR-HIST-1",
        customer_id=customer.id,
        sales_invoice_id=inv.id,
        status="posted",
        reason="damaged",
        total_amount=20,
        credit_note_number="CN-HIST-1",
        posted_at=datetime.utcnow(),
    )
    db_session.add(ret)
    await db_session.flush()
    db_session.add(
        m.SalesReturnItem(
            tenant_id=tenant_id,
            sales_return_id=ret.id,
            product_id=product.id,
            quantity=1,
            unit_price=20,
            line_total=20,
        )
    )

    pay = m.CustomerPayment(
        tenant_id=tenant_id,
        payment_number="CPAY-HIST-1",
        customer_id=customer.id,
        sales_invoice_id=inv.id,
        amount=40,
        payment_method="cash",
    )
    db_session.add(pay)

    db_session.add(
        m.Transaction(
            tenant_id=tenant_id,
            tx_type="pos_sale",
            reference="POS-HIST-1",
            party_id=customer.id,
            subtotal=15,
            tax=0,
            total=15,
            status="posted",
            payload={},
        )
    )
    await db_session.commit()

    r = await ac.get(f"/api/v1/customers/{customer.id}/history", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["customer"]["id"] == customer.id
    assert data["summary"]["purchase_count"] >= 2
    assert data["summary"]["return_count"] == 1
    assert data["summary"]["payment_count"] == 1
    assert abs(float(data["summary"]["payment_total"]) - 40) < 0.01
    assert any(p["reference"] == "INV-HIST-1" for p in data["purchases"])
    assert any(p["type"] == "pos" for p in data["purchases"])
    assert data["returns"][0]["return_number"] == "SR-HIST-1"
    assert data["payments"][0]["payment_number"] == "CPAY-HIST-1"

    missing = await ac.get(
        "/api/v1/customers/00000000-0000-0000-0000-000000000000/history",
        headers=headers,
    )
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_supplier_history_orders_returns_payments(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    tenant_id = seed["t1"].id

    supplier = m.Party(
        tenant_id=tenant_id, name="Hist Supplier", kind="supplier", credit_limit=0
    )
    db_session.add(supplier)
    await db_session.flush()

    po = m.PurchaseOrder(
        tenant_id=tenant_id,
        po_number="PO-HIST-1",
        supplier_id=supplier.id,
        status="received",
        total_amount=80,
        paid_amount=30,
    )
    db_session.add(po)
    await db_session.flush()

    pi = m.PurchaseInvoice(
        tenant_id=tenant_id,
        invoice_number="PI-HIST-1",
        supplier_id=supplier.id,
        purchase_order_id=po.id,
        status="partial",
        total_amount=80,
        paid_amount=30,
    )
    db_session.add(pi)
    await db_session.flush()

    grn = m.GoodsReceipt(
        tenant_id=tenant_id,
        grn_number="GRN-HIST-1",
        purchase_order_id=po.id,
        supplier_id=supplier.id,
        status="posted",
    )
    db_session.add(grn)
    await db_session.flush()

    ret = m.PurchaseReturn(
        tenant_id=tenant_id,
        return_number="PR-HIST-1",
        supplier_id=supplier.id,
        purchase_order_id=po.id,
        goods_receipt_id=grn.id,
        status="posted",
        reason="damaged",
        total_amount=10,
        debit_note_number="DN-HIST-1",
        posted_at=datetime.utcnow(),
    )
    db_session.add(ret)

    db_session.add(
        m.SupplierPayment(
            tenant_id=tenant_id,
            payment_number="SPAY-HIST-1",
            supplier_id=supplier.id,
            purchase_order_id=po.id,
            amount=30,
            payment_method="bank_transfer",
        )
    )
    await db_session.commit()

    r = await ac.get(f"/api/v1/suppliers/{supplier.id}/history", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["supplier"]["id"] == supplier.id
    assert data["summary"]["purchase_count"] == 2
    assert data["summary"]["return_count"] == 1
    assert data["summary"]["payment_count"] == 1
    types = {p["type"] for p in data["purchases"]}
    assert "purchase_order" in types
    assert "purchase_invoice" in types
    assert data["returns"][0]["return_number"] == "PR-HIST-1"
    assert abs(float(data["summary"]["payment_total"]) - 30) < 0.01
