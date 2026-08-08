"""Multi-currency credit: exchange rates, invoice FX, settlement gain/loss."""

from datetime import datetime

import pytest
from sqlalchemy import select

from app import accounting as accounting_svc
from app import fx as fx_svc
from app import models as m
from app import sales as sales_svc


@pytest.mark.asyncio
async def test_upsert_exchange_rate(db_session, seeded):
    tenant_id = seeded["t1"].id
    row = await fx_svc.upsert_rate(
        db_session, tenant_id=tenant_id, currency_code="usd", rate_to_base=15.5
    )
    await db_session.commit()
    assert row.currency_code == "USD"
    assert float(row.rate_to_base) == 15.5
    cur, rate = await fx_svc.resolve_rate(db_session, tenant_id, "USD")
    assert cur == "USD" and rate == 15.5


@pytest.mark.asyncio
async def test_foreign_invoice_posts_base_ar_and_fx_on_payment(db_session, seeded):
    tenant_id = seeded["t1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)
    await fx_svc.upsert_rate(db_session, tenant_id=tenant_id, currency_code="USD", rate_to_base=10)

    party = m.Party(tenant_id=tenant_id, name="FX Buyer", kind="customer", credit_limit=0, balance=0)
    db_session.add(party)
    await db_session.flush()

    product = seeded["p1"]
    inv = await sales_svc.create_sales_invoice(
        db_session,
        tenant_id=tenant_id,
        user_id=seeded["admin1"].id,
        customer_id=party.id,
        currency="USD",
        exchange_rate=10,
        items=[{"product_id": product.id, "quantity": 1, "unit_price": 100, "tax_rate": 0}],
    )
    inv = await sales_svc.post_sales_invoice(
        db_session, tenant_id=tenant_id, user_id=seeded["admin1"].id, invoice_id=inv.id
    )
    await db_session.commit()

    assert inv.currency == "USD"
    assert float(inv.exchange_rate) == 10
    assert float(inv.total_amount) == 100
    await db_session.refresh(party)
    assert float(party.balance) == 1000.0  # base

    ar = await accounting_svc.get_account_by_code(db_session, tenant_id, "1100")
    assert float(ar.balance) == 1000.0

    payment = await sales_svc.record_customer_payment(
        db_session,
        tenant_id=tenant_id,
        user_id=seeded["admin1"].id,
        customer_id=party.id,
        amount=100,
        sales_invoice_id=inv.id,
        payment_method="cash",
        exchange_rate=10.5,  # stronger USD → FX gain
    )
    await db_session.commit()

    assert float(payment.fx_gain_loss) == 50.0
    fx = await accounting_svc.get_account_by_code(db_session, tenant_id, "4300")
    cash = await accounting_svc.get_account_by_code(db_session, tenant_id, "1000")
    assert float(fx.balance) == 50.0
    assert float(cash.balance) == 1050.0
    await db_session.refresh(inv)
    assert inv.status == "paid"
    await db_session.refresh(party)
    assert float(party.balance) == 0.0

    entry = (
        await db_session.execute(
            select(m.JournalEntry).where(
                m.JournalEntry.source_type == "customer_payment",
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
