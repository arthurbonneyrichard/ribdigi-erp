"""Store sales report aggregation tests."""

from datetime import datetime

import pytest

from app import models as m
from app import reports as reports_svc


@pytest.mark.asyncio
async def test_sales_by_store_aggregates_invoice_and_pos(db_session, seeded):
    tenant_id = seeded["t1"].id
    store = m.Store(
        tenant_id=tenant_id,
        name="Main Street",
        code="MAIN",
        address=None,
        phone=None,
        is_active=True,
    )
    db_session.add(store)
    await db_session.flush()

    party = m.Party(tenant_id=tenant_id, name="Walk-in", kind="customer", credit_limit=0)
    db_session.add(party)
    await db_session.flush()

    inv = m.SalesInvoice(
        tenant_id=tenant_id,
        invoice_number="INV-STORE-1",
        customer_id=party.id,
        status="posted",
        subtotal=100,
        tax_amount=10,
        total_amount=110,
        paid_amount=0,
        store_id=store.id,
        posted_at=datetime.utcnow(),
        created_by=seeded["admin1"].id,
    )
    db_session.add(inv)

    session = m.PosSession(
        tenant_id=tenant_id,
        store_id=store.id,
        user_id=seeded["u1"].id,
        session_number="POS-S1",
        status="open",
        opening_cash=0,
    )
    db_session.add(session)
    await db_session.flush()

    tx = m.Transaction(
        tenant_id=tenant_id,
        tx_type="pos_sale",
        reference="POS-1",
        session_id=session.id,
        subtotal=40,
        tax=0,
        total=40,
        status="completed",
        payload={},
    )
    db_session.add(tx)
    await db_session.commit()

    result = await reports_svc.sales_by_store(db_session, tenant_id)
    by_id = {s["store_id"]: s for s in result["stores"] if s.get("store_id")}
    assert store.id in by_id
    row = by_id[store.id]
    assert row["invoice_count"] == 1
    assert row["invoice_revenue"] == 110.0
    assert row["pos_count"] == 1
    assert row["pos_revenue"] == 40.0
    assert row["revenue"] == 150.0
    assert result["total_revenue"] == 150.0
