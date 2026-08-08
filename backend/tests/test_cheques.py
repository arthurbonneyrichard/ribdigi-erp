"""Cheque lifecycle: clearing GL + deposit/clear/bounce."""

import pytest
from sqlalchemy import select

from app import accounting as accounting_svc
from app import cheques as cheques_svc
from app import models as m
from app import sales as sales_svc


def test_cheque_routes_to_clearing_not_bank():
    assert accounting_svc.liquid_gl_for_payment_method("cheque") == ("1020", "Cheques Receivable")
    assert accounting_svc.liquid_gl_for_payment_method("check") == ("1020", "Cheques Receivable")
    assert accounting_svc.supplier_payment_credit_gl("cheque") == ("2015", "Cheques Payable")
    assert accounting_svc.pos_debit_account_for_payment_method("cheque") == (
        "1020",
        "Cheques Receivable",
    )


@pytest.mark.asyncio
async def test_received_cheque_deposit_and_bounce(db_session, seeded):
    tenant_id = seeded["t1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)

    party = m.Party(tenant_id=tenant_id, name="Cheque Customer", kind="customer", credit_limit=0, balance=500)
    db_session.add(party)
    await db_session.flush()

    inv = m.SalesInvoice(
        tenant_id=tenant_id,
        invoice_number="INV-CHQ-1",
        customer_id=party.id,
        status="posted",
        subtotal=100,
        tax_amount=0,
        total_amount=100,
        paid_amount=0,
        posted_at=__import__("datetime").datetime.utcnow(),
        created_by=seeded["admin1"].id,
    )
    db_session.add(inv)
    await db_session.flush()

    payment = await sales_svc.record_customer_payment(
        db_session,
        tenant_id=tenant_id,
        user_id=seeded["admin1"].id,
        customer_id=party.id,
        amount=100,
        sales_invoice_id=inv.id,
        payment_method="cheque",
        reference="CHQ-1001",
        cheque_number="CHQ-1001",
        bank_name="First National",
    )
    await db_session.commit()

    recv = await accounting_svc.get_account_by_code(db_session, tenant_id, "1020")
    assert float(recv.balance) == 100.0

    cheques = await cheques_svc.list_cheques(db_session, tenant_id, direction="received")
    assert len(cheques) == 1
    chq = cheques[0]
    assert chq.status == "pending"
    assert chq.cheque_number == "CHQ-1001"

    await cheques_svc.deposit_cheque(
        db_session, tenant_id=tenant_id, user_id=seeded["admin1"].id, cheque_id=chq.id
    )
    await db_session.commit()

    bank = await accounting_svc.get_account_by_code(db_session, tenant_id, "1020")
    bank1010 = await accounting_svc.get_account_by_code(db_session, tenant_id, "1010")
    assert float(bank.balance) == 0.0
    assert float(bank1010.balance) == 100.0
    assert chq.status == "deposited"

    await cheques_svc.bounce_cheque(
        db_session,
        tenant_id=tenant_id,
        user_id=seeded["admin1"].id,
        cheque_id=chq.id,
        reason="NSF",
    )
    await db_session.commit()

    assert chq.status == "bounced"
    assert float(bank1010.balance) == 0.0
    await db_session.refresh(inv)
    assert float(inv.paid_amount) == 0.0
    assert inv.status == "posted"


@pytest.mark.asyncio
async def test_issued_cheque_clear(db_session, seeded):
    tenant_id = seeded["t1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)

    supplier = m.Party(tenant_id=tenant_id, name="Vendor", kind="supplier", credit_limit=0, balance=200)
    db_session.add(supplier)
    await db_session.flush()

    payment = m.SupplierPayment(
        tenant_id=tenant_id,
        payment_number="SPY-CHQ-1",
        supplier_id=supplier.id,
        amount=80,
        payment_method="cheque",
        reference="OUT-55",
        created_by=seeded["admin1"].id,
    )
    db_session.add(payment)
    await db_session.flush()

    await accounting_svc.post_supplier_payment_journal(
        db_session,
        tenant_id=tenant_id,
        user_id=seeded["admin1"].id,
        payment=payment,
    )
    chq = await cheques_svc.create_from_supplier_payment(
        db_session,
        tenant_id=tenant_id,
        user_id=seeded["admin1"].id,
        payment=payment,
        cheque_number="OUT-55",
    )
    await db_session.commit()

    payable = await accounting_svc.get_account_by_code(db_session, tenant_id, "2015")
    assert float(payable.balance) == 80.0

    await cheques_svc.clear_cheque(
        db_session, tenant_id=tenant_id, user_id=seeded["admin1"].id, cheque_id=chq.id
    )
    await db_session.commit()

    assert chq.status == "cleared"
    assert float(payable.balance) == 0.0
    bank = await accounting_svc.get_account_by_code(db_session, tenant_id, "1010")
    # credit increases liability? Bank is asset - credit decreases balance from 0 to -80
    # post_journal: asset balance += debit - credit, so bank balance = -80
    assert float(bank.balance) == -80.0
