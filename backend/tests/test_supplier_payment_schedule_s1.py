"""Stage 8 S1: supplier payment schedule (BR-11.2)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pyotp
import pytest

from app import accounting as accounting_svc
from app import models as m
from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_supplier_payment_schedule_buckets_and_early_pay(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    tenant_id = seed["t1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)
    seed["t1"].early_pay_discount_pct = 2
    seed["t1"].early_pay_discount_days = 10

    supplier = m.Party(
        tenant_id=tenant_id,
        name="Schedule Vendor",
        kind="supplier",
        credit_limit=0,
        balance=250,
    )
    db_session.add(supplier)
    await db_session.flush()

    overdue = m.PurchaseInvoice(
        tenant_id=tenant_id,
        invoice_number="PI-SCHED-OVER",
        supplier_id=supplier.id,
        status="unpaid",
        subtotal=100,
        tax_amount=0,
        total_amount=100,
        paid_amount=0,
        due_date=datetime.utcnow() - timedelta(days=5),
        approved_at=datetime.utcnow() - timedelta(days=20),
        invoice_date=datetime.utcnow() - timedelta(days=20),
        created_by=seed["admin1"].id,
    )
    upcoming = m.PurchaseInvoice(
        tenant_id=tenant_id,
        invoice_number="PI-SCHED-UP",
        supplier_id=supplier.id,
        status="unpaid",
        subtotal=150,
        tax_amount=0,
        total_amount=150,
        paid_amount=0,
        due_date=datetime.utcnow() + timedelta(days=7),
        approved_at=datetime.utcnow() - timedelta(days=2),
        invoice_date=datetime.utcnow() - timedelta(days=2),
        created_by=seed["admin1"].id,
    )
    db_session.add_all([overdue, upcoming])
    await db_session.commit()

    r = await ac.get(f"/api/v1/suppliers/{supplier.id}/payment-schedule", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert body["supplier_id"] == supplier.id
    assert body["total_due"] == 250.0
    assert body["overdue_total"] == 100.0
    assert body["upcoming_total"] == 150.0
    assert len(body["items"]) == 2
    assert body["items"][0]["invoice_number"] == "PI-SCHED-OVER"
    assert body["items"][0]["schedule_bucket"] == "overdue"
    assert body["items"][0]["is_overdue"] is True
    assert body["items"][1]["invoice_number"] == "PI-SCHED-UP"
    assert body["items"][1]["schedule_bucket"] == "upcoming"
    assert body["items"][1]["early_discount"]["eligible"] is True
    assert body["items"][1]["early_discount"]["discount_amount"] == 3.0

    flat = await ac.get(f"/api/v1/suppliers/{supplier.id}/outstanding", headers=headers)
    assert flat.status_code == 200
    assert len(flat.json()["data"]) == 2


@pytest.mark.asyncio
async def test_supplier_payment_schedule_tenant_isolation(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    supplier = m.Party(
        tenant_id=seed["t1"].id, name="Alpha Sched", kind="supplier", credit_limit=0
    )
    db_session.add(supplier)
    await db_session.commit()

    missing = await ac.get(
        f"/api/v1/suppliers/{supplier.id}/payment-schedule",
        headers={**headers, "X-Tenant-ID": seed["t2"].id},
    )
    assert missing.status_code == 403

    cashier = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    denied = await ac.get(
        f"/api/v1/suppliers/{supplier.id}/payment-schedule", headers=cashier
    )
    assert denied.status_code == 403


@pytest.mark.asyncio
async def test_supplier_payment_schedule_not_found(client):
    ac, seed = client
    headers = await _admin(ac, seed)
    r = await ac.get(
        "/api/v1/suppliers/00000000-0000-0000-0000-000000000099/payment-schedule",
        headers=headers,
    )
    assert r.status_code == 404
