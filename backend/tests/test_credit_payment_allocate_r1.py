"""Stage 14 R1: allocate customer/supplier payments to a selected invoice/bill."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app import models as m
from app.inventory import apply_stock_change
from tests.conftest import auth_headers


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


@pytest.mark.asyncio
async def test_customer_payment_explicit_vs_auto_allocate(client, db_session):
    ac, seed = client
    headers = await _mgr(ac)
    tenant_id = seed["t1"].id
    product_id = seed["p1"].id

    await apply_stock_change(
        db_session,
        tenant_id=tenant_id,
        product_id=product_id,
        quantity_delta=50,
        movement_type="stock_in",
        user_id=seed["mgr1"].id,
    )
    await db_session.commit()

    cust = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "R1 AR Customer", "credit_limit": 5000},
    )
    assert cust.status_code == 200, cust.text
    customer_id = cust.json()["data"]["id"]

    async def _posted_invoice(qty: float, unit: float) -> str:
        created = await ac.post(
            "/api/v1/sales/invoices",
            headers=headers,
            json={
                "customer_id": customer_id,
                "items": [
                    {
                        "product_id": product_id,
                        "quantity": qty,
                        "unit_price": unit,
                        "tax_rate": 0,
                    }
                ],
            },
        )
        assert created.status_code == 200, created.text
        inv_id = created.json()["data"]["id"]
        posted = await ac.post(f"/api/v1/sales/invoices/{inv_id}/post", headers=headers)
        assert posted.status_code == 200, posted.text
        return inv_id

    older_id = await _posted_invoice(1, 100)  # 100
    newer_id = await _posted_invoice(1, 40)  # 40

    older = (
        await db_session.execute(select(m.SalesInvoice).where(m.SalesInvoice.id == older_id))
    ).scalar_one()
    newer = (
        await db_session.execute(select(m.SalesInvoice).where(m.SalesInvoice.id == newer_id))
    ).scalar_one()
    # Keep both non-overdue so auto-allocate (posted/partial) still picks them up
    older.due_date = datetime.utcnow() + timedelta(days=1)
    newer.due_date = datetime.utcnow() + timedelta(days=20)
    await db_session.commit()

    # Explicit pay newer only — older remains open
    pay_new = await ac.post(
        f"/api/v1/customers/{customer_id}/payments",
        headers=headers,
        json={
            "customer_id": customer_id,
            "amount": 40,
            "sales_invoice_id": newer_id,
            "payment_method": "cash",
            "apply_early_discount": False,
        },
    )
    assert pay_new.status_code == 200, pay_new.text

    newer_after = await ac.get(f"/api/v1/sales/invoices/{newer_id}", headers=headers)
    older_after = await ac.get(f"/api/v1/sales/invoices/{older_id}", headers=headers)
    assert float(newer_after.json()["data"]["paid_amount"] or 0) == pytest.approx(40)
    assert float(older_after.json()["data"]["paid_amount"] or 0) == pytest.approx(0)

    # Auto-allocate remainder → oldest open due date (older invoice)
    pay_auto = await ac.post(
        f"/api/v1/customers/{customer_id}/payments",
        headers=headers,
        json={
            "customer_id": customer_id,
            "amount": 100,
            "payment_method": "cash",
            "apply_early_discount": False,
        },
    )
    assert pay_auto.status_code == 200, pay_auto.text
    older_paid = await ac.get(f"/api/v1/sales/invoices/{older_id}", headers=headers)
    assert float(older_paid.json()["data"]["paid_amount"] or 0) == pytest.approx(100)

    # Wrong customer invoice rejected
    other = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "R1 Other", "credit_limit": 500},
    )
    other_id = other.json()["data"]["id"]
    bad = await ac.post(
        f"/api/v1/customers/{other_id}/payments",
        headers=headers,
        json={
            "customer_id": other_id,
            "amount": 10,
            "sales_invoice_id": older_id,
            "payment_method": "cash",
        },
    )
    assert bad.status_code == 400, bad.text


@pytest.mark.asyncio
async def test_supplier_payment_allocate_to_selected_bill(client, db_session):
    ac, seed = client
    headers = await _mgr(ac)
    product_id = seed["p1"].id

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=headers,
        json={"name": "R1 AP Supplier"},
    )
    assert supplier.status_code == 200, supplier.text
    supplier_id = supplier.json()["data"]["id"]

    async def _approved_bill(qty: float, unit: float) -> str:
        created = await ac.post(
            "/api/v1/purchasing/invoices",
            headers=headers,
            json={
                "supplier_id": supplier_id,
                "items": [
                    {
                        "product_id": product_id,
                        "quantity": qty,
                        "unit_price": unit,
                        "tax_rate": 0,
                    }
                ],
            },
        )
        assert created.status_code == 200, created.text
        inv_id = created.json()["data"]["id"]
        approved = await ac.post(
            f"/api/v1/purchasing/invoices/{inv_id}/approve", headers=headers
        )
        assert approved.status_code == 200, approved.text
        return inv_id

    bill_a = await _approved_bill(1, 80)
    bill_b = await _approved_bill(1, 25)

    a_row = (
        await db_session.execute(select(m.PurchaseInvoice).where(m.PurchaseInvoice.id == bill_a))
    ).scalar_one()
    b_row = (
        await db_session.execute(select(m.PurchaseInvoice).where(m.PurchaseInvoice.id == bill_b))
    ).scalar_one()
    a_row.due_date = datetime.utcnow() - timedelta(days=5)
    b_row.due_date = datetime.utcnow() + timedelta(days=5)
    await db_session.commit()

    # Pay later bill explicitly
    pay_b = await ac.post(
        f"/api/v1/suppliers/{supplier_id}/payments",
        headers=headers,
        json={
            "supplier_id": supplier_id,
            "amount": 25,
            "purchase_invoice_id": bill_b,
            "payment_method": "bank_transfer",
            "apply_early_discount": False,
        },
    )
    assert pay_b.status_code == 200, pay_b.text

    b_after = await ac.get(f"/api/v1/purchasing/invoices/{bill_b}", headers=headers)
    a_after = await ac.get(f"/api/v1/purchasing/invoices/{bill_a}", headers=headers)
    assert float(b_after.json()["data"]["paid_amount"] or 0) == pytest.approx(25)
    assert float(a_after.json()["data"]["paid_amount"] or 0) == pytest.approx(0)

    # Auto oldest-first settles bill A
    pay_auto = await ac.post(
        f"/api/v1/suppliers/{supplier_id}/payments",
        headers=headers,
        json={
            "supplier_id": supplier_id,
            "amount": 80,
            "payment_method": "bank_transfer",
            "apply_early_discount": False,
        },
    )
    assert pay_auto.status_code == 200, pay_auto.text
    a_paid = await ac.get(f"/api/v1/purchasing/invoices/{bill_a}", headers=headers)
    assert float(a_paid.json()["data"]["paid_amount"] or 0) == pytest.approx(80)
