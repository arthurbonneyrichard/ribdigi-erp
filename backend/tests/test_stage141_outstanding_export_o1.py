"""Stage 141 O1 — outstanding bills CSV export."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pyotp
import pytest

from app import accounting as accounting_svc
from app import models as m
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_customer_outstanding_export_csv(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)
    tenant_id = seed["t1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)

    customer = m.Party(
        tenant_id=tenant_id, name="Stage141 AR", kind="customer", credit_limit=500, balance=80
    )
    db_session.add(customer)
    await db_session.flush()
    db_session.add(
        m.SalesInvoice(
            tenant_id=tenant_id,
            invoice_number="INV-141-OUT",
            customer_id=customer.id,
            status="posted",
            subtotal=80,
            tax_amount=0,
            total_amount=80,
            paid_amount=0,
            due_date=datetime.utcnow() + timedelta(days=14),
            posted_at=datetime.utcnow(),
            created_by=seed["admin1"].id,
        )
    )
    await db_session.commit()

    exported = await ac.get(
        f"/api/v1/customers/{customer.id}/outstanding/export", headers=headers
    )
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    text = exported.text
    header = text.splitlines()[0]
    assert "document_number" in header and "amount" in header
    assert "INV-141-OUT" in text
    assert "80" in text or "80.00" in text
    assert "customer" in text


@pytest.mark.asyncio
async def test_supplier_outstanding_export_csv(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)
    tenant_id = seed["t1"].id
    supplier = m.Party(
        tenant_id=tenant_id, name="Stage141 AP", kind="supplier", credit_limit=0, balance=60
    )
    db_session.add(supplier)
    await db_session.flush()
    db_session.add(
        m.PurchaseInvoice(
            tenant_id=tenant_id,
            invoice_number="PI-141-OUT",
            supplier_id=supplier.id,
            status="unpaid",
            subtotal=60,
            tax_amount=0,
            total_amount=60,
            paid_amount=0,
            due_date=datetime.utcnow() + timedelta(days=3),
            approved_at=datetime.utcnow(),
            created_by=seed["admin1"].id,
        )
    )
    await db_session.commit()

    exported = await ac.get(
        f"/api/v1/suppliers/{supplier.id}/outstanding/export", headers=headers
    )
    assert exported.status_code == 200, exported.text
    assert "PI-141-OUT" in exported.text
    assert "supplier" in exported.text


def test_outstanding_export_ui_o1():
    page = (ROOT / "frontend/app/credit/page.tsx").read_text(encoding="utf-8")
    assert "Stage 141" in page
    assert "/outstanding/export" in page
    assert "Export outstanding CSV" in page
