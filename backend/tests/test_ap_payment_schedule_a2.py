"""AP payment schedule + supplier due notifications (BR-10.5 / BR-11.2)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pyotp
import pytest
from sqlalchemy import select

from app import models as m
from app import notifications as notifications_svc
from app.purchasing import purchase_invoice_status, refresh_overdue_purchase_invoices
from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


def test_purchase_invoice_status_overdue_as_of():
    due = datetime(2026, 8, 1)
    assert (
        purchase_invoice_status(100, 0, due, as_of=datetime(2026, 8, 13)) == "overdue"
    )
    assert purchase_invoice_status(100, 0, due, as_of=datetime(2026, 7, 31)) == "unpaid"
    assert purchase_invoice_status(100, 40, due, as_of=datetime(2026, 8, 13)) == "overdue"
    assert purchase_invoice_status(100, 100, due, as_of=datetime(2026, 8, 13)) == "paid"


@pytest.mark.asyncio
async def test_refresh_and_scan_ap_payment_due(client, db_session):
    ac, seed = client
    tenant_id = seed["t1"].id
    supplier = m.Party(
        tenant_id=tenant_id, name="Schedule Vendor", kind="supplier", balance=200
    )
    db_session.add(supplier)
    await db_session.flush()

    soon = m.PurchaseInvoice(
        tenant_id=tenant_id,
        invoice_number="PI-DUE-SOON",
        supplier_id=supplier.id,
        status="unpaid",
        subtotal=80,
        total_amount=80,
        paid_amount=0,
        due_date=datetime.utcnow() + timedelta(days=1),
        invoice_date=datetime.utcnow() - timedelta(days=10),
        approved_at=datetime.utcnow() - timedelta(days=10),
        created_by=seed["admin1"].id,
    )
    past = m.PurchaseInvoice(
        tenant_id=tenant_id,
        invoice_number="PI-DUE-PAST",
        supplier_id=supplier.id,
        status="unpaid",
        subtotal=120,
        total_amount=120,
        paid_amount=0,
        due_date=datetime.utcnow() - timedelta(days=5),
        invoice_date=datetime.utcnow() - timedelta(days=35),
        approved_at=datetime.utcnow() - timedelta(days=35),
        created_by=seed["admin1"].id,
    )
    paid = m.PurchaseInvoice(
        tenant_id=tenant_id,
        invoice_number="PI-DUE-PAID",
        supplier_id=supplier.id,
        status="paid",
        subtotal=50,
        total_amount=50,
        paid_amount=50,
        due_date=datetime.utcnow() + timedelta(days=1),
        created_by=seed["admin1"].id,
    )
    far = m.PurchaseInvoice(
        tenant_id=tenant_id,
        invoice_number="PI-DUE-FAR",
        supplier_id=supplier.id,
        status="unpaid",
        subtotal=10,
        total_amount=10,
        paid_amount=0,
        due_date=datetime.utcnow() + timedelta(days=30),
        created_by=seed["admin1"].id,
    )
    db_session.add_all([soon, past, paid, far])
    await db_session.commit()

    changed = await refresh_overdue_purchase_invoices(db_session, tenant_id)
    await db_session.commit()
    assert changed >= 1
    await db_session.refresh(past)
    assert past.status == "overdue"

    created = await notifications_svc.scan_payment_due(db_session, tenant_id, within_days=3)
    await db_session.commit()
    assert created >= 2  # soon + past (AP); AR may also create 0

    notes = (
        await db_session.execute(
            select(m.Notification).where(
                m.Notification.tenant_id == tenant_id,
                m.Notification.category == "payment_due",
                m.Notification.entity_type == "purchase_invoice",
            )
        )
    ).scalars().all()
    entity_ids = {n.entity_id for n in notes}
    assert soon.id in entity_ids
    assert past.id in entity_ids
    assert paid.id not in entity_ids
    assert far.id not in entity_ids
    assert any("Supplier payment due" in (n.title or "") for n in notes)

    again = await notifications_svc.scan_payment_due(db_session, tenant_id, within_days=3)
    await db_session.commit()
    assert again == 0  # dedupe unread

    headers = await _admin(ac, seed)
    # Manual scan endpoint still works
    r = await ac.post("/api/v1/notifications/scan-due", headers=headers)
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_supplier_payment_schedule_api(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    tenant_id = seed["t1"].id

    supplier = m.Party(
        tenant_id=tenant_id, name="Calendar Vendor", kind="supplier", balance=300
    )
    db_session.add(supplier)
    await db_session.flush()

    later = m.PurchaseInvoice(
        tenant_id=tenant_id,
        invoice_number="PI-SCH-2",
        supplier_id=supplier.id,
        status="unpaid",
        subtotal=90,
        total_amount=90,
        paid_amount=0,
        due_date=datetime.utcnow() + timedelta(days=10),
        created_by=seed["admin1"].id,
    )
    sooner = m.PurchaseInvoice(
        tenant_id=tenant_id,
        invoice_number="PI-SCH-1",
        supplier_id=supplier.id,
        status="partial",
        subtotal=200,
        total_amount=200,
        paid_amount=50,
        due_date=datetime.utcnow() + timedelta(days=2),
        created_by=seed["admin1"].id,
    )
    po = m.PurchaseOrder(
        tenant_id=tenant_id,
        supplier_id=supplier.id,
        po_number="PO-SCH-1",
        status="sent",
        subtotal=40,
        tax_amount=0,
        total_amount=40,
        paid_amount=0,
        due_date=datetime.utcnow() + timedelta(days=20),
        created_by=seed["admin1"].id,
    )
    db_session.add_all([later, sooner, po])
    await db_session.commit()

    r = await ac.get(
        f"/api/v1/suppliers/{supplier.id}/payment-schedule", headers=headers
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["supplier"]["id"] == supplier.id
    assert abs(float(data["total_due"]) - 280) < 0.01  # 150 + 90 + 40
    nums = [i["document_number"] for i in data["items"]]
    assert nums.index("PI-SCH-1") < nums.index("PI-SCH-2")
    assert nums.index("PI-SCH-2") < nums.index("PO-SCH-1")
    first = data["items"][0]
    assert first["document_number"] == "PI-SCH-1"
    assert abs(float(first["balance_due"]) - 150) < 0.01
    assert first["days_until_due"] is not None

    missing = await ac.get(
        "/api/v1/suppliers/00000000-0000-0000-0000-000000000000/payment-schedule",
        headers=headers,
    )
    assert missing.status_code == 404

    cashier = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    forbidden = await ac.get(
        f"/api/v1/suppliers/{supplier.id}/payment-schedule", headers=cashier
    )
    assert forbidden.status_code == 403
