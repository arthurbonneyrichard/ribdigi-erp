"""Purchase-side reverse charge self-assessment."""

from datetime import datetime

import pytest
from sqlalchemy import select

from app import accounting as accounting_svc
from app import models as m
from app import purchasing as purchasing_svc
from app import tax as tax_svc


@pytest.mark.asyncio
async def test_purchase_rc_invoice_totals_and_journal(db_session, seeded):
    tenant_id = seeded["t1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)

    supplier = m.Party(tenant_id=tenant_id, name="RC Vendor", kind="supplier", credit_limit=0, balance=0)
    db_session.add(supplier)
    await db_session.flush()

    product = seeded["p1"]
    inv = await purchasing_svc.create_purchase_invoice(
        db_session,
        tenant_id=tenant_id,
        user_id=seeded["admin1"].id,
        supplier_id=supplier.id,
        is_reverse_charge=True,
        items=[
            {
                "product_id": product.id,
                "quantity": 10,
                "unit_price": 100,
                "tax_rate": 15,
            }
        ],
    )
    await db_session.flush()

    assert float(inv.subtotal) == 1000.0
    assert float(inv.tax_amount) == 0.0
    assert float(inv.reverse_charge_tax) == 150.0
    assert float(inv.total_amount) == 1000.0
    assert inv.is_reverse_charge is True

    inv = await purchasing_svc.approve_purchase_invoice(
        db_session,
        tenant_id=tenant_id,
        user_id=seeded["admin1"].id,
        invoice_id=inv.id,
    )
    await db_session.commit()

    assert inv.ap_posted is True
    assert float(supplier.balance) == 1000.0

    entry = (
        await db_session.execute(
            select(m.JournalEntry).where(
                m.JournalEntry.tenant_id == tenant_id,
                m.JournalEntry.source_type == "purchase_invoice",
                m.JournalEntry.source_id == inv.id,
            )
        )
    ).scalar_one()
    lines = (
        await db_session.execute(
            select(m.JournalEntryLine).where(m.JournalEntryLine.journal_entry_id == entry.id)
        )
    ).scalars().all()
    by_account = {}
    for ln in lines:
        acct = (
            await db_session.execute(select(m.Account).where(m.Account.id == ln.account_id))
        ).scalar_one()
        by_account[acct.code] = (float(ln.debit), float(ln.credit))

    assert by_account["1200"] == (1000.0, 0.0)
    assert by_account["1300"] == (150.0, 0.0)
    assert by_account["2000"] == (0.0, 1000.0)
    assert by_account["2100"] == (0.0, 150.0)


@pytest.mark.asyncio
async def test_purchase_rc_in_filing_pack(db_session, seeded):
    tenant_id = seeded["t1"].id
    supplier = m.Party(tenant_id=tenant_id, name="Filing RC Vendor", kind="supplier", credit_limit=0)
    db_session.add(supplier)
    await db_session.flush()

    pi = m.PurchaseInvoice(
        tenant_id=tenant_id,
        invoice_number="PI-RC-1",
        supplier_id=supplier.id,
        status="unpaid",
        subtotal=200,
        tax_amount=0,
        reverse_charge_tax=30,
        is_reverse_charge=True,
        total_amount=200,
        paid_amount=0,
        invoice_date=datetime(2026, 4, 5),
        created_by=seeded["admin1"].id,
    )
    db_session.add(pi)
    await db_session.commit()

    pack = await tax_svc.tax_filing_pack(
        db_session,
        tenant_id,
        from_date=datetime(2026, 4, 1),
        to_date=datetime(2026, 4, 30, 23, 59, 59),
    )
    boxes = {b["code"]: b["amount"] for b in pack["filing_boxes"]["boxes"]}
    assert boxes["reverse_charge_tax"] == 30.0
    assert boxes["input_tax"] == 30.0
    assert boxes["output_tax"] == 30.0
    assert boxes["net_tax_payable"] == 0.0
    assert pack["schedules"]["input"][0]["reverse_charge_tax"] == 30.0
    assert pack["schedules"]["input"][0]["is_reverse_charge"] is True
