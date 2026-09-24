"""Tax supply class splits: standard / zero-rated / exempt on calc + filing."""

from __future__ import annotations

from datetime import datetime

import pytest

from app import models as m
from app import tax as tax_svc
from app import tax_filings as tax_filings_svc
from app.tax import normalize_supply_class, resolve_product_tax


def test_normalize_supply_class_aliases():
    assert normalize_supply_class("zero-rated") == "zero_rated"
    assert normalize_supply_class(None, tax_exempt=True) == "exempt"
    assert normalize_supply_class("standard") == "standard"


@pytest.mark.asyncio
async def test_resolve_zero_and_exempt_are_zero_rate(db_session, seeded):
    tenant_id = seeded["t1"].id
    zero = m.Product(
        tenant_id=tenant_id,
        name="Export Rice",
        sku="ZR-1",
        selling_price=10,
        tax_supply_class="zero_rated",
        tax_exempt=False,
    )
    exempt = m.Product(
        tenant_id=tenant_id,
        name="Basic Bread",
        sku="EX-1",
        selling_price=5,
        tax_supply_class="exempt",
        tax_exempt=True,
    )
    db_session.add_all([zero, exempt])
    await db_session.commit()

    z = await resolve_product_tax(db_session, tenant_id, zero)
    e = await resolve_product_tax(db_session, tenant_id, exempt)
    assert z.supply_class == "zero_rated" and z.rate_pct == 0
    assert e.supply_class == "exempt" and e.rate_pct == 0
    assert z.compute_amounts(100) == (100.0, 0.0, 100.0)


@pytest.mark.asyncio
async def test_filing_pack_splits_supply_classes(db_session, seeded):
    tenant_id = seeded["t1"].id
    party = m.Party(tenant_id=tenant_id, name="Buyer", kind="customer", credit_limit=0)
    std = m.Product(tenant_id=tenant_id, name="Soda", sku="STD-1", selling_price=10, tax_supply_class="standard")
    zero = m.Product(tenant_id=tenant_id, name="Export", sku="ZR-2", selling_price=10, tax_supply_class="zero_rated")
    exempt = m.Product(
        tenant_id=tenant_id, name="Bread", sku="EX-2", selling_price=10, tax_supply_class="exempt", tax_exempt=True
    )
    db_session.add_all([party, std, zero, exempt])
    await db_session.flush()

    inv = m.SalesInvoice(
        tenant_id=tenant_id,
        invoice_number="INV-SUPPLY-1",
        customer_id=party.id,
        status="posted",
        subtotal=300,
        tax_amount=15,
        total_amount=315,
        paid_amount=0,
        posted_at=datetime(2026, 4, 10),
        created_by=seeded["admin1"].id,
    )
    db_session.add(inv)
    await db_session.flush()
    db_session.add_all(
        [
            m.SalesInvoiceItem(
                tenant_id=tenant_id,
                sales_invoice_id=inv.id,
                product_id=std.id,
                quantity=1,
                unit_price=100,
                tax_rate=15,
                tax_supply_class="standard",
                line_subtotal=100,
                line_total=115,
            ),
            m.SalesInvoiceItem(
                tenant_id=tenant_id,
                sales_invoice_id=inv.id,
                product_id=zero.id,
                quantity=1,
                unit_price=100,
                tax_rate=0,
                tax_supply_class="zero_rated",
                line_subtotal=100,
                line_total=100,
            ),
            m.SalesInvoiceItem(
                tenant_id=tenant_id,
                sales_invoice_id=inv.id,
                product_id=exempt.id,
                quantity=1,
                unit_price=100,
                tax_rate=0,
                tax_supply_class="exempt",
                line_subtotal=100,
                line_total=100,
            ),
        ]
    )
    await db_session.commit()

    pack = await tax_svc.tax_filing_pack(
        db_session,
        tenant_id,
        from_date=datetime(2026, 4, 1),
        to_date=datetime(2026, 4, 30, 23, 59, 59),
    )
    fb = pack["filing_boxes"]
    assert fb["taxable_outputs_net"] == 100.0
    assert fb["zero_rated_outputs_net"] == 100.0
    assert fb["exempt_outputs_net"] == 100.0

    tenant = await db_session.get(m.Tenant, tenant_id)
    tenant.tax_jurisdiction = "GH"
    tenant.tax_registration_number = "C000999"
    await db_session.commit()
    gov = tax_filings_svc.build_government_return(pack, tenant, jurisdiction="GH")
    by_code = {b["code"]: b["amount"] for b in gov["boxes"]}
    assert by_code["GH1"] == 100.0
    assert by_code["GH3"] == 100.0
    assert by_code["GH4"] == 100.0
