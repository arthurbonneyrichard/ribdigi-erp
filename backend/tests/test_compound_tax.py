"""Compound tax and reverse charge unit/integration tests."""

import pytest

from app import models as m
from app.tax import (
    compute_tax_amounts,
    compute_tax_breakdown,
    effective_rate_from_components,
    resolve_product_tax,
)
from app import sales as sales_svc


def test_compound_additive_on_net():
    detail = compute_tax_breakdown(
        100,
        0,
        "exclusive",
        components=[
            {"code": "cgst", "name": "CGST", "rate": 9, "basis": "net"},
            {"code": "sgst", "name": "SGST", "rate": 9, "basis": "net"},
        ],
    )
    assert detail["net"] == 100
    assert detail["tax"] == 18
    assert detail["gross"] == 118
    assert detail["effective_rate"] == 18
    assert len(detail["components"]) == 2
    assert detail["components"][0]["amount"] == 9
    assert detail["components"][1]["amount"] == 9


def test_compound_cascade_basis():
    # 10% on net then 5% on (net+first tax)
    detail = compute_tax_breakdown(
        100,
        0,
        "exclusive",
        components=[
            {"code": "a", "name": "A", "rate": 10, "basis": "net"},
            {"code": "b", "name": "B", "rate": 5, "basis": "compound"},
        ],
    )
    assert detail["net"] == 100
    assert detail["components"][0]["amount"] == 10
    assert detail["components"][1]["amount"] == 5.5  # 5% of 110
    assert detail["tax"] == 15.5
    assert detail["gross"] == 115.5


def test_reverse_charge_excludes_tax_from_gross():
    net, tax, gross = compute_tax_amounts(
        200, 15, "exclusive", is_reverse_charge=True
    )
    assert net == 200
    assert tax == 30
    assert gross == 200


def test_effective_rate_sums_net_legs():
    assert (
        effective_rate_from_components(
            [
                {"rate": 9, "basis": "net"},
                {"rate": 9, "basis": "net"},
                {"rate": 1, "basis": "compound"},
            ],
            0,
        )
        == 18
    )


@pytest.mark.asyncio
async def test_sales_invoice_reverse_charge_memo(db_session, seeded):
    tenant_id = seeded["t1"].id
    rate = m.TaxRate(
        tenant_id=tenant_id,
        name="RC VAT",
        rate=15,
        tax_type="vat",
        pricing_mode="exclusive",
        is_reverse_charge=True,
        is_default=True,
        is_active=True,
    )
    db_session.add(rate)
    await db_session.flush()

    product = seeded["p1"]
    product.tax_rate_id = rate.id
    product.tax_exempt = False

    party = m.Party(tenant_id=tenant_id, name="B2B", kind="customer", credit_limit=0)
    db_session.add(party)
    await db_session.flush()

    inv = await sales_svc.create_sales_invoice(
        db_session,
        tenant_id=tenant_id,
        user_id=seeded["admin1"].id,
        customer_id=party.id,
        items=[{"product_id": product.id, "quantity": 2}],
    )
    await db_session.commit()

    # selling_price=2, qty=2 => net 4, tax 0.6 memo, total charged = 4
    assert float(inv.subtotal) == 4.0
    assert float(inv.tax_amount) == 0.0
    assert float(inv.reverse_charge_tax) == 0.6
    assert float(inv.total_amount) == 4.0


@pytest.mark.asyncio
async def test_resolve_product_compound_spec(db_session, seeded):
    tenant_id = seeded["t1"].id
    rate = m.TaxRate(
        tenant_id=tenant_id,
        name="GST Split",
        rate=18,
        tax_type="gst",
        pricing_mode="exclusive",
        components=[
            {"code": "cgst", "name": "CGST", "rate": 9, "basis": "net"},
            {"code": "sgst", "name": "SGST", "rate": 9, "basis": "net"},
        ],
        is_reverse_charge=False,
        is_default=False,
        is_active=True,
    )
    db_session.add(rate)
    await db_session.flush()
    product = seeded["p1"]
    product.tax_rate_id = rate.id
    product.tax_exempt = False
    await db_session.commit()

    spec = await resolve_product_tax(db_session, tenant_id, product)
    detail = spec.compute_breakdown(100)
    assert detail["tax"] == 18
    assert len(detail["components"]) == 2
