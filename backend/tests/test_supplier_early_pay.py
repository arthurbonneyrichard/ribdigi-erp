"""Supplier early-payment take-discount tests."""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app import accounting as accounting_svc
from app import models as m
from app import purchasing as purchasing_svc
from app.credit import purchase_invoice_early_discount


def test_purchase_invoice_early_discount_quote():
    inv = m.PurchaseInvoice(
        tenant_id="t",
        invoice_number="X",
        supplier_id="s",
        status="unpaid",
        subtotal=100,
        tax_amount=0,
        total_amount=100,
        paid_amount=0,
        approved_at=datetime.utcnow() - timedelta(days=5),
    )
    q = purchase_invoice_early_discount(inv, pct=2, days=10)
    assert q["eligible"] is True
    assert q["discount_amount"] == 2.0
    assert q["cash_to_settle"] == 98.0

    late = purchase_invoice_early_discount(
        inv, pct=2, days=10, as_of=datetime.utcnow() + timedelta(days=20)
    )
    assert late["eligible"] is False


@pytest.mark.asyncio
async def test_supplier_payment_applies_early_discount(db_session, seeded):
    tenant_id = seeded["t1"].id
    tenant = seeded["t1"]
    tenant.early_pay_discount_pct = 2
    tenant.early_pay_discount_days = 10
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)

    supplier = m.Party(
        tenant_id=tenant_id, name="Early Vendor", kind="supplier", credit_limit=0, balance=100
    )
    db_session.add(supplier)
    await db_session.flush()

    inv = m.PurchaseInvoice(
        tenant_id=tenant_id,
        invoice_number="PI-EP-1",
        supplier_id=supplier.id,
        status="unpaid",
        subtotal=100,
        tax_amount=0,
        total_amount=100,
        paid_amount=0,
        approved_at=datetime.utcnow() - timedelta(days=3),
        invoice_date=datetime.utcnow() - timedelta(days=3),
        created_by=seeded["admin1"].id,
    )
    db_session.add(inv)
    await db_session.commit()

    payment = await purchasing_svc.record_supplier_payment(
        db_session,
        tenant_id=tenant_id,
        user_id=seeded["admin1"].id,
        supplier_id=supplier.id,
        amount=98,
        purchase_invoice_id=inv.id,
        payment_method="bank_transfer",
        apply_early_discount=True,
    )
    await db_session.commit()

    assert float(payment.amount) == 98.0
    assert float(payment.early_payment_discount) == 2.0
    await db_session.refresh(inv)
    assert float(inv.paid_amount) == 100.0
    assert inv.status == "paid"
    await db_session.refresh(supplier)
    assert float(supplier.balance) == 0.0

    disc_acct = await accounting_svc.get_account_by_code(db_session, tenant_id, "4200")
    bank = await accounting_svc.get_account_by_code(db_session, tenant_id, "1010")
    assert float(disc_acct.balance) == 2.0
    assert float(bank.balance) == -98.0

    entry = (
        await db_session.execute(
            select(m.JournalEntry).where(
                m.JournalEntry.source_type == "supplier_payment",
                m.JournalEntry.source_id == payment.id,
            )
        )
    ).scalar_one()
    lines = (
        await db_session.execute(
            select(m.JournalEntryLine).where(m.JournalEntryLine.journal_entry_id == entry.id)
        )
    ).scalars().all()
    assert abs(sum(float(ln.debit) for ln in lines) - sum(float(ln.credit) for ln in lines)) < 0.01
