"""Per-payment liquid GL account override tests."""

import pytest
from sqlalchemy import select

from app import accounting as accounting_svc
from app import models as m


@pytest.mark.asyncio
async def test_customer_payment_override_to_bank(db_session, seeded):
    tenant_id = seeded["t1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)
    bank = await accounting_svc.get_account_by_code(db_session, tenant_id, "1010")

    party = m.Party(tenant_id=tenant_id, name="Override Cust", kind="customer", credit_limit=0, balance=50)
    db_session.add(party)
    await db_session.flush()

    payment = m.CustomerPayment(
        tenant_id=tenant_id,
        payment_number="PAY-OVR-1",
        customer_id=party.id,
        amount=40,
        payment_method="cash",  # default would be 1000
        liquid_account_id=bank.id,
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

    lines = (
        await db_session.execute(
            select(m.JournalEntryLine).where(m.JournalEntryLine.journal_entry_id == entry.id)
        )
    ).scalars().all()
    assert any(ln.account_id == bank.id and float(ln.debit) == 40 for ln in lines)
    cash = await accounting_svc.get_account_by_code(db_session, tenant_id, "1000")
    assert float(cash.balance) == 0.0
    assert float(bank.balance) == 40.0


@pytest.mark.asyncio
async def test_reject_non_settlement_override(db_session, seeded):
    tenant_id = seeded["t1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)
    revenue = await accounting_svc.get_account_by_code(db_session, tenant_id, "4000")

    with pytest.raises(Exception) as exc:
        await accounting_svc.resolve_settlement_gl(
            db_session,
            tenant_id,
            "cash",
            liquid_account_id=revenue.id,
            outflow=False,
        )
    assert "settlement" in str(exc.value.detail).lower() or "400" in str(exc.value)
