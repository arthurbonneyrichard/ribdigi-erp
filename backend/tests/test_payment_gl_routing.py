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
    assert accounting_svc.pos_debit_account_for_payment_method("gift_card") == (
        "2150",
        "Gift Cards Outstanding",
    )
    assert accounting_svc.pos_debit_account_for_payment_method("loyalty") == (
        "2160",
        "Loyalty Points Outstanding",
    )


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


@pytest.mark.asyncio
async def test_gift_card_and_loyalty_do_not_debit_cash(db_session, seeded):
    from app import loyalty_gift as loyalty_gift_svc

    tenant_id = seeded["t1"].id
    user_id = seeded["admin1"].id
    card = await loyalty_gift_svc.issue_gift_card(
        db_session, tenant_id=tenant_id, user_id=user_id, amount=40
    )
    cash = await accounting_svc.get_account_by_code(db_session, tenant_id, "1000")
    liability = await accounting_svc.get_account_by_code(db_session, tenant_id, "2150")
    promo = await accounting_svc.get_account_by_code(db_session, tenant_id, "6100")
    assert float(cash.balance or 0) == 0
    assert float(liability.balance or 0) == 40
    assert float(promo.balance or 0) == 40

    tx = m.Transaction(
        tenant_id=tenant_id,
        tx_type="pos_sale",
        reference="POS-GC-1",
        subtotal=40,
        tax=0,
        total=40,
        status="completed",
        payload={"payment_method": "gift_card"},
    )
    db_session.add(tx)
    await db_session.flush()
    entry = await accounting_svc.post_pos_sale_journal(
        db_session,
        tenant_id=tenant_id,
        user_id=user_id,
        tx=tx,
        payment_method="gift_card",
    )
    await db_session.commit()
    lines = (
        await db_session.execute(
            select(m.JournalEntryLine).where(m.JournalEntryLine.journal_entry_id == entry.id)
        )
    ).scalars().all()
    assert any(ln.account_id == liability.id and float(ln.debit) == 40 for ln in lines)
    assert not any(ln.account_id == cash.id and float(ln.debit or 0) > 0 for ln in lines)

    party = seeded["party1"]
    await loyalty_gift_svc.adjust_loyalty(
        db_session, tenant_id=tenant_id, party_id=party.id, delta=15
    )
    points = await accounting_svc.get_account_by_code(db_session, tenant_id, "2160")
    assert float(points.balance or 0) == 15
    loyalty_tx = m.Transaction(
        tenant_id=tenant_id,
        tx_type="pos_sale",
        reference="POS-LOY-1",
        subtotal=15,
        tax=0,
        total=15,
        status="completed",
        payload={"payment_method": "loyalty"},
    )
    db_session.add(loyalty_tx)
    await db_session.flush()
    loyalty_entry = await accounting_svc.post_pos_sale_journal(
        db_session,
        tenant_id=tenant_id,
        user_id=user_id,
        tx=loyalty_tx,
        payment_method="loyalty",
    )
    await db_session.commit()
    loyalty_lines = (
        await db_session.execute(
            select(m.JournalEntryLine).where(m.JournalEntryLine.journal_entry_id == loyalty_entry.id)
        )
    ).scalars().all()
    assert any(ln.account_id == points.id and float(ln.debit) == 15 for ln in loyalty_lines)
    assert not any(ln.account_id == cash.id and float(ln.debit or 0) > 0 for ln in loyalty_lines)
