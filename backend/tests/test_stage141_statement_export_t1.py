"""Stage 141 T1 — party statement CSV export."""

from __future__ import annotations

from datetime import datetime
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
async def test_customer_statement_export_csv(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)
    tenant_id = seed["t1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)

    customer = m.Party(
        tenant_id=tenant_id,
        name="Stage141 Statement Cust",
        kind="customer",
        credit_limit=1000,
        balance=50,
    )
    db_session.add(customer)
    await db_session.flush()
    db_session.add(
        m.SalesInvoice(
            tenant_id=tenant_id,
            invoice_number="INV-141-STMT",
            customer_id=customer.id,
            status="posted",
            subtotal=50,
            tax_amount=0,
            total_amount=50,
            paid_amount=0,
            posted_at=datetime.utcnow(),
            created_by=seed["admin1"].id,
        )
    )
    await db_session.commit()

    exported = await ac.get(
        f"/api/v1/credit/customers/{customer.id}/statement/export", headers=headers
    )
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    text = exported.text
    header = text.splitlines()[0]
    assert "party_name" in header and "debit" in header and "credit" in header
    assert "INV-141-STMT" in text
    assert "Stage141 Statement Cust" in text
    assert "invoice" in text


@pytest.mark.asyncio
async def test_supplier_statement_export_csv(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)
    tenant_id = seed["t1"].id
    supplier = m.Party(
        tenant_id=tenant_id,
        name="Stage141 Statement Sup",
        kind="supplier",
        credit_limit=0,
        balance=40,
    )
    db_session.add(supplier)
    await db_session.flush()
    db_session.add(
        m.PurchaseOrder(
            tenant_id=tenant_id,
            po_number="PO-141-STMT",
            supplier_id=supplier.id,
            status="sent",
            subtotal=40,
            tax_amount=0,
            total_amount=40,
            paid_amount=0,
            created_by=seed["admin1"].id,
        )
    )
    await db_session.commit()

    exported = await ac.get(
        f"/api/v1/credit/suppliers/{supplier.id}/statement/export", headers=headers
    )
    assert exported.status_code == 200, exported.text
    assert "PO-141-STMT" in exported.text
    assert "Stage141 Statement Sup" in exported.text


def test_statement_export_ui_t1():
    page = (ROOT / "frontend/app/credit/page.tsx").read_text(encoding="utf-8")
    assert "Stage 141" in page
    assert "/statement/export" in page
    assert "Export statement CSV" in page
