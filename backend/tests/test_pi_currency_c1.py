"""Purchase invoice transaction currency / FX (BR-2.6)."""

from __future__ import annotations

import pytest

from app import accounting as accounting_svc
from app import fx as fx_svc
from app import models as m
from app import purchasing as purchasing_svc


@pytest.mark.asyncio
async def test_manual_purchase_invoice_stores_currency_and_rate(db_session, seeded):
    tenant_id = seeded["t1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)
    await fx_svc.upsert_rate(db_session, tenant_id=tenant_id, currency_code="USD", rate_to_base=12.5)

    supplier = m.Party(
        tenant_id=tenant_id,
        name="FX Supplier",
        kind="supplier",
        credit_limit=0,
        balance=0,
    )
    db_session.add(supplier)
    await db_session.flush()

    product = seeded["p1"]
    inv = await purchasing_svc.create_purchase_invoice(
        db_session,
        tenant_id=tenant_id,
        user_id=seeded["admin1"].id,
        supplier_id=supplier.id,
        currency="usd",
        exchange_rate=12.5,
        items=[{"product_id": product.id, "quantity": 2, "unit_price": 40, "tax_rate": 0}],
    )
    await db_session.commit()

    assert inv.currency == "USD"
    assert float(inv.exchange_rate) == 12.5
    assert float(inv.total_amount) == 80.0
