"""Stage 141 P1 — supplier payment schedule CSV export."""

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
async def test_payment_schedule_export_csv_and_bucket(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)
    tenant_id = seed["t1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)

    supplier = m.Party(
        tenant_id=tenant_id,
        name="Stage141 Schedule",
        kind="supplier",
        credit_limit=0,
        balance=250,
    )
    db_session.add(supplier)
    await db_session.flush()
    db_session.add_all(
        [
            m.PurchaseInvoice(
                tenant_id=tenant_id,
                invoice_number="PI-141-OVER",
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
            ),
            m.PurchaseInvoice(
                tenant_id=tenant_id,
                invoice_number="PI-141-UP",
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
            ),
        ]
    )
    await db_session.commit()

    exported = await ac.get(
        f"/api/v1/suppliers/{supplier.id}/payment-schedule/export", headers=headers
    )
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    text = exported.text
    header = text.splitlines()[0]
    assert "schedule_bucket" in header
    assert "early_discount_eligible" in header
    assert "PI-141-OVER" in text and "PI-141-UP" in text

    overdue_only = await ac.get(
        f"/api/v1/suppliers/{supplier.id}/payment-schedule/export?schedule_bucket=overdue",
        headers=headers,
    )
    assert overdue_only.status_code == 200, overdue_only.text
    assert "PI-141-OVER" in overdue_only.text
    assert "PI-141-UP" not in overdue_only.text


def test_payment_schedule_export_ui_p1():
    page = (ROOT / "frontend/app/credit/page.tsx").read_text(encoding="utf-8")
    assert "Stage 141" in page
    assert "/payment-schedule/export" in page
    assert "Export schedule CSV" in page
