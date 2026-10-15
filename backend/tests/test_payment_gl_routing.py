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


@pytest.mark.asyncio
async def test_gift_card_liquid_account_cannot_debit_cash(db_session, seeded):
    """A cash account id on a gift-card tender still posts liability 2150."""
    from fastapi import HTTPException

    from app.pos import resolve_sale_payments

    tenant_id = seeded["t1"].id
    user_id = seeded["admin1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)
    cash = await accounting_svc.get_account_by_code(db_session, tenant_id, "1000")
    liability = await accounting_svc.get_account_by_code(db_session, tenant_id, "2150")
    tenders = resolve_sale_payments(
        total=25,
        payment_method="gift_card",
        payments=[
            {
                "payment_method": "gift_card",
                "amount": 25,
                "reference": "GC-KEEP",
                "liquid_account_id": cash.id,
            }
        ],
    )
    assert tenders[0]["liquid_account_id"] is None
    tx = m.Transaction(
        tenant_id=tenant_id,
        tx_type="pos_sale",
        reference="POS-GC-LIQUID",
        subtotal=25,
        tax=0,
        total=25,
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
        payments=[
            {
                "payment_method": "gift_card",
                "amount": 25,
                "liquid_account_id": cash.id,
            }
        ],
    )
    await db_session.commit()
    lines = (
        await db_session.execute(
            select(m.JournalEntryLine).where(m.JournalEntryLine.journal_entry_id == entry.id)
        )
    ).scalars().all()
    assert any(ln.account_id == liability.id and float(ln.debit) == 25 for ln in lines)
    assert not any(ln.account_id == cash.id and float(ln.debit or 0) > 0 for ln in lines)

    momo = m.Transaction(
        tenant_id=tenant_id,
        tx_type="pos_sale",
        reference="POS-MOMO-CASH",
        subtotal=10,
        tax=0,
        total=10,
        status="completed",
        payload={"payment_method": "mobile_money"},
    )
    db_session.add(momo)
    await db_session.flush()
    with pytest.raises(HTTPException) as raised:
        await accounting_svc.post_pos_sale_journal(
            db_session,
            tenant_id=tenant_id,
            user_id=user_id,
            tx=momo,
            payment_method="mobile_money",
            payments=[
                {
                    "payment_method": "mobile_money",
                    "amount": 10,
                    "liquid_account_id": cash.id,
                }
            ],
        )
    assert raised.value.status_code == 400
    assert "till cash" in str(raised.value.detail)


def _balanced(lines) -> None:
    debit = round(sum(float(line.debit or 0) for line in lines), 2)
    credit = round(sum(float(line.credit or 0) for line in lines), 2)
    assert debit == credit
    assert debit > 0


async def _entry_lines(db_session, entry_id):
    return (
        await db_session.execute(
            select(m.JournalEntryLine).where(m.JournalEntryLine.journal_entry_id == entry_id)
        )
    ).scalars().all()


@pytest.mark.asyncio
async def test_gift_card_and_loyalty_issue_redeem_refund_and_reversal(db_session, seeded):
    """Stored value stays on 2150/2160/6100/6110. Refunds do not touch till cash."""
    from app import loyalty_gift as loyalty_gift_svc

    tenant_id = seeded["t1"].id
    user_id = seeded["admin1"].id
    cash_before_accounts = None
    card = await loyalty_gift_svc.issue_gift_card(
        db_session, tenant_id=tenant_id, user_id=user_id, amount=40
    )
    cash = await accounting_svc.get_account_by_code(db_session, tenant_id, "1000")
    liability = await accounting_svc.get_account_by_code(db_session, tenant_id, "2150")
    promo = await accounting_svc.get_account_by_code(db_session, tenant_id, "6100")
    cash_before_accounts = float(cash.balance or 0)
    assert cash_before_accounts == 0
    assert float(liability.balance or 0) == 40
    assert float(promo.balance or 0) == 40

    await loyalty_gift_svc.settle_pos_tenders(
        db_session,
        tenant_id=tenant_id,
        party_id=None,
        payments=[{"payment_method": "gift_card", "amount": 25, "reference": card.code}],
    )
    assert float(card.balance) == 15
    redeem = m.Transaction(
        tenant_id=tenant_id,
        tx_type="pos_sale",
        reference="POS-GC-REDEEM",
        subtotal=25,
        tax=0,
        total=25,
        status="completed",
        payload={"payment_method": "gift_card"},
    )
    db_session.add(redeem)
    await db_session.flush()
    redeem_entry = await accounting_svc.post_pos_sale_journal(
        db_session,
        tenant_id=tenant_id,
        user_id=user_id,
        tx=redeem,
        payment_method="gift_card",
        payments=[{"payment_method": "gift_card", "amount": 25, "liquid_account_id": cash.id}],
    )
    redeem_lines = await _entry_lines(db_session, redeem_entry.id)
    _balanced(redeem_lines)
    assert any(ln.account_id == liability.id and float(ln.debit) == 25 for ln in redeem_lines)
    assert not any(ln.account_id == cash.id and float(ln.debit or 0) > 0 for ln in redeem_lines)
    assert float(liability.balance or 0) == 15
    assert float(cash.balance or 0) == 0

    refund = m.SalesReturn(
        id="sr-gc-refund-1",
        tenant_id=tenant_id,
        return_number="SR-GC-REFUND",
        customer_id=seeded["party1"].id,
        sales_invoice_id=seeded["party1"].id,
        credit_note_number="CN-GC-REFUND",
    )
    refund_entry = await accounting_svc.post_sales_return_refund_journal(
        db_session,
        tenant_id=tenant_id,
        user_id=user_id,
        sales_return=refund,
        amount=25,
        payment_method="gift_card",
        liquid_account_id=cash.id,
    )
    refund_lines = await _entry_lines(db_session, refund_entry.id)
    _balanced(refund_lines)
    assert any(ln.account_id == liability.id and float(ln.credit) == 25 for ln in refund_lines)
    assert not any(ln.account_id == cash.id for ln in refund_lines)
    assert float(liability.balance or 0) == 40
    assert float(cash.balance or 0) == 0
    # The return has no card code, so the plastic balance is not put back.
    assert float(card.balance) == 15

    party = seeded["party1"]
    await loyalty_gift_svc.adjust_loyalty(
        db_session, tenant_id=tenant_id, party_id=party.id, delta=10
    )
    points = await accounting_svc.get_account_by_code(db_session, tenant_id, "2160")
    loyalty_promo = await accounting_svc.get_account_by_code(db_session, tenant_id, "6110")
    assert float(points.balance or 0) == 10
    assert float(loyalty_promo.balance or 0) == 10
    await loyalty_gift_svc.adjust_loyalty(
        db_session, tenant_id=tenant_id, party_id=party.id, delta=-10
    )
    assert float(party.loyalty_points or 0) == 0
    assert float(points.balance or 0) == 0
    assert float(loyalty_promo.balance or 0) == 0
    assert float(cash.balance or 0) == 0

    await loyalty_gift_svc.adjust_loyalty(
        db_session, tenant_id=tenant_id, party_id=party.id, delta=8
    )
    await loyalty_gift_svc.settle_pos_tenders(
        db_session,
        tenant_id=tenant_id,
        party_id=party.id,
        payments=[{"payment_method": "loyalty", "amount": 8}],
    )
    assert float(party.loyalty_points or 0) == 0
    assert float(points.balance or 0) == 8
    loyalty_tx = m.Transaction(
        tenant_id=tenant_id,
        tx_type="pos_sale",
        reference="POS-LOY-REDEEM",
        subtotal=8,
        tax=0,
        total=8,
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
    loyalty_lines = await _entry_lines(db_session, loyalty_entry.id)
    _balanced(loyalty_lines)
    assert any(ln.account_id == points.id and float(ln.debit) == 8 for ln in loyalty_lines)
    assert float(points.balance or 0) == 0
    loyalty_refund = m.SalesReturn(
        id="sr-loy-refund-1",
        tenant_id=tenant_id,
        return_number="SR-LOY-REFUND",
        customer_id=party.id,
        sales_invoice_id=party.id,
        credit_note_number="CN-LOY-REFUND",
    )
    loyalty_refund_entry = await accounting_svc.post_sales_return_refund_journal(
        db_session,
        tenant_id=tenant_id,
        user_id=user_id,
        sales_return=loyalty_refund,
        amount=8,
        payment_method="loyalty",
        liquid_account_id=cash.id,
    )
    loyalty_refund_lines = await _entry_lines(db_session, loyalty_refund_entry.id)
    _balanced(loyalty_refund_lines)
    assert any(ln.account_id == points.id and float(ln.credit) == 8 for ln in loyalty_refund_lines)
    assert not any(ln.account_id == cash.id for ln in loyalty_refund_lines)
    assert float(points.balance or 0) == 8
    assert float(loyalty_promo.balance or 0) == 8
    assert float(cash.balance or 0) == 0
    await db_session.commit()


@pytest.mark.asyncio
async def test_split_tender_keeps_noncash_out_of_the_drawer(db_session, seeded):
    from app.pos import apply_sale_to_session

    tenant_id = seeded["t1"].id
    user_id = seeded["admin1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)
    cash = await accounting_svc.get_account_by_code(db_session, tenant_id, "1000")
    gift = await accounting_svc.get_account_by_code(db_session, tenant_id, "2150")
    points = await accounting_svc.get_account_by_code(db_session, tenant_id, "2160")
    bank = await accounting_svc.get_account_by_code(db_session, tenant_id, "1010")
    session = m.PosSession(
        tenant_id=tenant_id,
        user_id=user_id,
        session_number="SHIFT-SPLIT-TEST",
        opening_cash=50,
        cash_sales=0,
        cash_in=0,
        cash_out=0,
        card_sales=0,
        other_sales=0,
        total_sales=0,
        sale_count=0,
    )
    tenders = [
        {"payment_method": "cash", "amount": 12},
        {"payment_method": "gift_card", "amount": 18},
        {"payment_method": "loyalty", "amount": 5},
        {"payment_method": "card", "amount": 7},
    ]
    await apply_sale_to_session(
        session, total=42, payment_method="split", payments=tenders
    )
    assert float(session.cash_sales) == 12
    assert float(session.card_sales) == 7
    assert float(session.other_sales) == 23
    assert float(session.expected_cash) == 62
    assert float(session.total_sales) == 42

    tx = m.Transaction(
        tenant_id=tenant_id,
        tx_type="pos_sale",
        reference="POS-SPLIT-1",
        subtotal=42,
        tax=0,
        total=42,
        status="completed",
        payload={"payment_method": "split"},
    )
    db_session.add(tx)
    await db_session.flush()
    entry = await accounting_svc.post_pos_sale_journal(
        db_session,
        tenant_id=tenant_id,
        user_id=user_id,
        tx=tx,
        payment_method="split",
        payments=tenders,
    )
    lines = await _entry_lines(db_session, entry.id)
    _balanced(lines)
    assert any(ln.account_id == cash.id and float(ln.debit) == 12 for ln in lines)
    assert any(ln.account_id == gift.id and float(ln.debit) == 18 for ln in lines)
    assert any(ln.account_id == points.id and float(ln.debit) == 5 for ln in lines)
    assert any(ln.account_id == bank.id and float(ln.debit) == 7 for ln in lines)
    assert float(cash.balance or 0) == 12
    await db_session.commit()


@pytest.mark.asyncio
async def test_invalid_tender_accounts_are_rejected(db_session, seeded):
    from fastapi import HTTPException

    tenant_id = seeded["t1"].id
    user_id = seeded["admin1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)
    await accounting_svc.ensure_default_accounts(db_session, seeded["t2"].id)
    cash = await accounting_svc.get_account_by_code(db_session, tenant_id, "1000")
    other_bank = await accounting_svc.get_account_by_code(db_session, seeded["t2"].id, "1010")
    revenue = await accounting_svc.get_account_by_code(db_session, tenant_id, "4000")
    gift = await accounting_svc.get_account_by_code(db_session, tenant_id, "2150")

    def _sale(reference: str) -> m.Transaction:
        row = m.Transaction(
            tenant_id=tenant_id,
            tx_type="pos_sale",
            reference=reference,
            subtotal=10,
            tax=0,
            total=10,
            status="completed",
            payload={"payment_method": "card"},
        )
        db_session.add(row)
        return row

    cross = _sale("POS-CROSS-ACCT")
    await db_session.flush()
    with pytest.raises(HTTPException) as cross_raised:
        await accounting_svc.post_pos_sale_journal(
            db_session,
            tenant_id=tenant_id,
            user_id=user_id,
            tx=cross,
            payment_method="card",
            payments=[{"payment_method": "card", "amount": 10, "liquid_account_id": other_bank.id}],
        )
    assert cross_raised.value.status_code == 404

    forged = _sale("POS-FORGED-ACCT")
    await db_session.flush()
    with pytest.raises(HTTPException) as forged_raised:
        await accounting_svc.post_pos_sale_journal(
            db_session,
            tenant_id=tenant_id,
            user_id=user_id,
            tx=forged,
            payment_method="card",
            payments=[
                {
                    "payment_method": "card",
                    "amount": 10,
                    "liquid_account_id": "00000000-0000-4000-8000-000000000099",
                }
            ],
        )
    assert forged_raised.value.status_code == 404

    wrong_kind = _sale("POS-REVENUE-ACCT")
    await db_session.flush()
    with pytest.raises(HTTPException) as kind_raised:
        await accounting_svc.post_pos_sale_journal(
            db_session,
            tenant_id=tenant_id,
            user_id=user_id,
            tx=wrong_kind,
            payment_method="bank_transfer",
            payments=[
                {
                    "payment_method": "bank_transfer",
                    "amount": 10,
                    "liquid_account_id": revenue.id,
                }
            ],
        )
    assert kind_raised.value.status_code == 400

    refund = m.SalesReturn(
        id="sr-momo-cash",
        tenant_id=tenant_id,
        return_number="SR-MOMO-CASH",
        customer_id=seeded["party1"].id,
        sales_invoice_id=seeded["party1"].id,
    )
    with pytest.raises(HTTPException) as refund_raised:
        await accounting_svc.post_sales_return_refund_journal(
            db_session,
            tenant_id=tenant_id,
            user_id=user_id,
            sales_return=refund,
            amount=10,
            payment_method="mobile_money",
            liquid_account_id=cash.id,
        )
    assert refund_raised.value.status_code == 400
    assert "till cash" in str(refund_raised.value.detail)

    gift.is_active = False
    await db_session.flush()
    inactive_sale = m.Transaction(
        tenant_id=tenant_id,
        tx_type="pos_sale",
        reference="POS-GC-INACTIVE",
        subtotal=10,
        tax=0,
        total=10,
        status="completed",
        payload={"payment_method": "gift_card"},
    )
    db_session.add(inactive_sale)
    await db_session.flush()
    cash_before = float(cash.balance or 0)
    with pytest.raises(HTTPException) as inactive_raised:
        await accounting_svc.post_pos_sale_journal(
            db_session,
            tenant_id=tenant_id,
            user_id=user_id,
            tx=inactive_sale,
            payment_method="gift_card",
        )
    assert inactive_raised.value.status_code == 400
    assert "2150" in str(inactive_raised.value.detail)
    assert float(cash.balance or 0) == cash_before


@pytest.mark.asyncio
async def test_missing_bank_account_and_noncash_drawer(db_session, seeded):
    """An inactive bank account cannot be replaced by till cash. Drawer cash ignores MoMo and bank transfer."""
    from fastapi import HTTPException

    from app.pos import apply_sale_to_session

    tenant_id = seeded["t1"].id
    user_id = seeded["admin1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)
    cash = await accounting_svc.get_account_by_code(db_session, tenant_id, "1000")
    bank = await accounting_svc.get_account_by_code(db_session, tenant_id, "1010")
    points = await accounting_svc.get_account_by_code(db_session, tenant_id, "2160")
    bank.is_active = False
    await db_session.flush()
    cash_before = float(cash.balance or 0)

    card = m.Transaction(
        tenant_id=tenant_id,
        tx_type="pos_sale",
        reference="POS-CARD-NO-BANK",
        subtotal=10,
        tax=0,
        total=10,
        status="completed",
        payload={"payment_method": "card"},
    )
    db_session.add(card)
    await db_session.flush()
    with pytest.raises(HTTPException) as card_raised:
        await accounting_svc.post_pos_sale_journal(
            db_session,
            tenant_id=tenant_id,
            user_id=user_id,
            tx=card,
            payment_method="card",
        )
    assert card_raised.value.status_code == 400
    assert "1010" in str(card_raised.value.detail)
    assert float(cash.balance or 0) == cash_before

    momo = m.Transaction(
        tenant_id=tenant_id,
        tx_type="pos_sale",
        reference="POS-MOMO-NO-BANK",
        subtotal=10,
        tax=0,
        total=10,
        status="completed",
        payload={"payment_method": "mobile_money"},
    )
    db_session.add(momo)
    await db_session.flush()
    with pytest.raises(HTTPException) as momo_raised:
        await accounting_svc.post_pos_sale_journal(
            db_session,
            tenant_id=tenant_id,
            user_id=user_id,
            tx=momo,
            payment_method="mobile_money",
        )
    assert momo_raised.value.status_code == 400
    assert float(cash.balance or 0) == cash_before

    points.is_active = False
    await db_session.flush()
    loyalty = m.Transaction(
        tenant_id=tenant_id,
        tx_type="pos_sale",
        reference="POS-LOY-NO-ACCT",
        subtotal=8,
        tax=0,
        total=8,
        status="completed",
        payload={"payment_method": "loyalty"},
    )
    db_session.add(loyalty)
    await db_session.flush()
    with pytest.raises(HTTPException) as loyalty_raised:
        await accounting_svc.post_pos_sale_journal(
            db_session,
            tenant_id=tenant_id,
            user_id=user_id,
            tx=loyalty,
            payment_method="loyalty",
            payments=[
                {
                    "payment_method": "loyalty",
                    "amount": 8,
                    "liquid_account_id": cash.id,
                }
            ],
        )
    assert loyalty_raised.value.status_code == 400
    assert "2160" in str(loyalty_raised.value.detail)
    assert float(cash.balance or 0) == cash_before

    session = m.PosSession(
        tenant_id=tenant_id,
        user_id=user_id,
        session_number="SHIFT-NONCASH-DRAWER",
        opening_cash=20,
        cash_sales=0,
        cash_in=0,
        cash_out=0,
        card_sales=0,
        other_sales=0,
        total_sales=0,
        sale_count=0,
    )
    await apply_sale_to_session(
        session,
        total=30,
        payment_method="split",
        payments=[
            {"payment_method": "cash", "amount": 4},
            {"payment_method": "mobile_money", "amount": 11},
            {"payment_method": "bank_transfer", "amount": 15},
        ],
    )
    assert float(session.cash_sales) == 4
    assert float(session.card_sales) == 0
    assert float(session.other_sales) == 26
    assert float(session.expected_cash) == 24
    assert float(session.total_sales) == 30
