"""BR-6.1 per-supplier early-pay discount terms."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app import accounting as accounting_svc
from app import models as m
from app import purchasing as purchasing_svc
from app.credit import early_pay_settings, resolve_early_pay_settings
from tests.conftest import auth_headers


def test_resolve_early_pay_prefers_supplier_override():
    tenant = m.Tenant(
        slug="t",
        company_name="T",
        early_pay_discount_pct=1,
        early_pay_discount_days=5,
    )
    supplier = m.Party(
        tenant_id="x",
        name="S",
        kind="supplier",
        early_pay_discount_pct=3,
        early_pay_discount_days=12,
    )
    ep = resolve_early_pay_settings(tenant, supplier)
    assert ep["source"] == "supplier"
    assert ep["early_pay_discount_pct"] == 3
    assert ep["early_pay_discount_days"] == 12
    assert ep["enabled"] is True

    inherit = m.Party(tenant_id="x", name="S2", kind="supplier")
    fallback = resolve_early_pay_settings(tenant, inherit)
    assert fallback["source"] == "tenant"
    assert fallback["early_pay_discount_pct"] == 1

    disabled = m.Party(
        tenant_id="x",
        name="S3",
        kind="supplier",
        early_pay_discount_pct=0,
        early_pay_discount_days=0,
    )
    off = resolve_early_pay_settings(tenant, disabled)
    assert off["source"] == "supplier"
    assert off["enabled"] is False
    assert early_pay_settings(tenant)["enabled"] is True


@pytest.mark.asyncio
async def test_supplier_override_used_for_payment_and_quote(client, db_session):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    tenant = await db_session.get(m.Tenant, seed["t1"].id)
    tenant.early_pay_discount_pct = 1
    tenant.early_pay_discount_days = 5
    await db_session.commit()

    created = await ac.post(
        "/api/v1/suppliers",
        headers=headers,
        json={
            "name": "Override Vendor",
            "early_pay_discount_pct": 5,
            "early_pay_discount_days": 10,
            "credit_limit": 0,
        },
    )
    assert created.status_code == 200, created.text
    supplier = created.json()["data"]
    assert supplier["early_pay_discount_pct"] == 5
    assert supplier["early_pay_discount_days"] == 10
    supplier_id = supplier["id"]

    await accounting_svc.ensure_default_accounts(db_session, seed["t1"].id)
    inv = m.PurchaseInvoice(
        tenant_id=seed["t1"].id,
        invoice_number="PI-SUP-EP-1",
        supplier_id=supplier_id,
        status="unpaid",
        subtotal=200,
        tax_amount=0,
        total_amount=200,
        paid_amount=0,
        approved_at=datetime.utcnow() - timedelta(days=2),
        invoice_date=datetime.utcnow() - timedelta(days=2),
        created_by=seed["mgr1"].id,
    )
    db_session.add(inv)
    party = await db_session.get(m.Party, supplier_id)
    party.balance = 200
    await db_session.commit()
    invoice_id = str(inv.id)

    quote = await ac.get(
        f"/api/v1/credit/purchase-invoices/{invoice_id}/early-discount",
        headers=headers,
    )
    assert quote.status_code == 200, quote.text
    q = quote.json()["data"]
    assert q["source"] == "supplier"
    assert q["eligible"] is True
    assert q["discount_pct"] == 5
    assert q["discount_amount"] == 10.0
    assert q["cash_to_settle"] == 190.0

    payment = await purchasing_svc.record_supplier_payment(
        db_session,
        tenant_id=seed["t1"].id,
        user_id=seed["mgr1"].id,
        supplier_id=supplier_id,
        amount=190,
        purchase_invoice_id=invoice_id,
        payment_method="bank_transfer",
        apply_early_discount=True,
    )
    await db_session.commit()
    assert float(payment.early_payment_discount) == 10.0

    cleared = await ac.patch(
        f"/api/v1/suppliers/{supplier_id}",
        headers=headers,
        json={"early_pay_discount_pct": None, "early_pay_discount_days": None},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["data"]["early_pay_discount_pct"] is None
    assert cleared.json()["data"]["early_pay_discount_days"] is None

    inv2 = m.PurchaseInvoice(
        tenant_id=seed["t1"].id,
        invoice_number="PI-SUP-EP-2",
        supplier_id=supplier_id,
        status="unpaid",
        subtotal=100,
        tax_amount=0,
        total_amount=100,
        paid_amount=0,
        approved_at=datetime.utcnow() - timedelta(days=1),
        invoice_date=datetime.utcnow() - timedelta(days=1),
        created_by=seed["mgr1"].id,
    )
    db_session.add(inv2)
    await db_session.commit()
    quote_inherit = await ac.get(
        f"/api/v1/credit/purchase-invoices/{inv2.id}/early-discount",
        headers=headers,
    )
    assert quote_inherit.status_code == 200, quote_inherit.text
    qi = quote_inherit.json()["data"]
    assert qi["source"] == "tenant"
    assert qi["discount_pct"] == 1


@pytest.mark.asyncio
async def test_supplier_zero_override_disables_tenant_early_pay(db_session, seeded):
    tenant_id = seeded["t1"].id
    tenant = seeded["t1"]
    tenant.early_pay_discount_pct = 2
    tenant.early_pay_discount_days = 10
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)

    supplier = m.Party(
        tenant_id=tenant_id,
        name="No Discount Vendor",
        kind="supplier",
        credit_limit=0,
        balance=100,
        early_pay_discount_pct=0,
        early_pay_discount_days=0,
    )
    db_session.add(supplier)
    await db_session.flush()
    inv = m.PurchaseInvoice(
        tenant_id=tenant_id,
        invoice_number="PI-EP-OFF",
        supplier_id=supplier.id,
        status="unpaid",
        subtotal=100,
        tax_amount=0,
        total_amount=100,
        paid_amount=0,
        approved_at=datetime.utcnow() - timedelta(days=3),
        invoice_date=datetime.utcnow() - timedelta(days=3),
        created_by=seeded["admin1"].id,
    )
    db_session.add(inv)
    await db_session.commit()

    payment = await purchasing_svc.record_supplier_payment(
        db_session,
        tenant_id=tenant_id,
        user_id=seeded["admin1"].id,
        supplier_id=supplier.id,
        amount=98,
        purchase_invoice_id=inv.id,
        payment_method="bank_transfer",
        apply_early_discount=True,
    )
    await db_session.commit()
    assert float(payment.early_payment_discount) == 0.0
    await db_session.refresh(inv)
    assert float(inv.paid_amount) == 98.0
    assert inv.status == "partial"
