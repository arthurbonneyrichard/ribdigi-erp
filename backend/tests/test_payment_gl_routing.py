"""Payment method → Cash/Bank GL routing tests."""

import pytest
from sqlalchemy import select

from app import accounting as accounting_svc
from app import models as m


def test_liquid_gl_routing_matrix():
    assert accounting_svc.liquid_gl_for_payment_method("cash") == ("1000", "Cash")
    assert accounting_svc.liquid_gl_for_payment_method(None) == ("1000", "Cash")
    assert accounting_svc.liquid_gl_for_payment_method("bank_transfer") == ("1010", "Bank")
    assert accounting_svc.liquid_gl_for_payment_method("card") == ("1010", "Bank")
    assert accounting_svc.liquid_gl_for_payment_method("wallet") == ("1010", "Bank")
    assert accounting_svc.liquid_gl_for_payment_method("cheque") == ("1020", "Cheques Receivable")
    assert accounting_svc.liquid_gl_for_payment_method("check") == ("1020", "Cheques Receivable")
    assert accounting_svc.supplier_payment_credit_gl("cheque") == ("2015", "Cheques Payable")
    assert accounting_svc.pos_debit_account_for_payment_method("credit") == ("1100", "AR")
    assert accounting_svc.pos_debit_account_for_payment_method("card") == ("1010", "Bank")
    assert accounting_svc.pos_debit_account_for_payment_method("cash") == ("1000", "Cash")


@pytest.mark.asyncio
async def test_customer_payment_bank_transfer_hits_1010(db_session, seeded):
    tenant_id = seeded["t1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)
    party = m.Party(tenant_id=tenant_id, name="Payer", kind="customer", credit_limit=0, balance=200)
    db_session.add(party)
    await db_session.flush()

    payment = m.CustomerPayment(
        tenant_id=tenant_id,
        payment_number="PAY-BANK-1",
        customer_id=party.id,
        amount=75,
        payment_method="bank_transfer",
        created_by=seeded["admin1"].id,
    )
    db_session.add(payment)
    await db_session.flush()

    entry = await accounting_svc.post_customer_payment_journal(
        db_session,
        tenant_id=tenant_id,
        user_id=seeded["admin1"].id,
        payment=payment,
    )
    await db_session.commit()

    bank = await accounting_svc.get_account_by_code(db_session, tenant_id, "1010")
    lines = (
        await db_session.execute(
            select(m.JournalEntryLine).where(m.JournalEntryLine.journal_entry_id == entry.id)
        )
    ).scalars().all()
    by_acct = {ln.account_id: ln for ln in lines}
    assert bank.id in by_acct
    assert float(by_acct[bank.id].debit) == 75.0
    assert float(bank.balance) == 75.0


@pytest.mark.asyncio
async def test_expense_cash_still_hits_1000(db_session, seeded):
    tenant_id = seeded["t1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)
    expense = m.Expense(
        tenant_id=tenant_id,
        category="Supplies",
        description="Pens",
        amount=20,
        payment_method="cash",
        status="approved",
        created_by=seeded["admin1"].id,
    )
    db_session.add(expense)
    await db_session.flush()

    entry = await accounting_svc.post_expense_journal(
        db_session,
        tenant_id=tenant_id,
        user_id=seeded["admin1"].id,
        expense=expense,
    )
    await db_session.commit()

    cash = await accounting_svc.get_account_by_code(db_session, tenant_id, "1000")
    lines = (
        await db_session.execute(
            select(m.JournalEntryLine).where(m.JournalEntryLine.journal_entry_id == entry.id)
        )
    ).scalars().all()
    assert any(ln.account_id == cash.id and float(ln.credit) == 20 for ln in lines)


@pytest.mark.asyncio
async def test_pos_card_sale_debits_bank(db_session, seeded):
    tenant_id = seeded["t1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)
    tx = m.Transaction(
        tenant_id=tenant_id,
        tx_type="pos_sale",
        reference="POS-CARD-1",
        subtotal=90,
        tax=10,
        total=100,
        status="completed",
        payload={"payment_method": "card"},
    )
    db_session.add(tx)
    await db_session.flush()

    entry = await accounting_svc.post_pos_sale_journal(
        db_session,
        tenant_id=tenant_id,
        user_id=seeded["admin1"].id,
        tx=tx,
        payment_method="card",
    )
    await db_session.commit()

    bank = await accounting_svc.get_account_by_code(db_session, tenant_id, "1010")
    lines = (
        await db_session.execute(
            select(m.JournalEntryLine).where(m.JournalEntryLine.journal_entry_id == entry.id)
        )
    ).scalars().all()
    assert any(ln.account_id == bank.id and float(ln.debit) == 100 for ln in lines)
