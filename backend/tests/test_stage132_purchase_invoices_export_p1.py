"""Stage 132 P1 — purchase invoice register CSV export."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from app import models as m
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_purchase_invoices_export_csv(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)

    supplier = m.Party(
        tenant_id=seed["t1"].id, name="Stage132 Supplier", kind="supplier", credit_limit=0
    )
    db_session.add(supplier)
    await db_session.flush()

    db_session.add_all(
        [
            m.PurchaseInvoice(
                tenant_id=seed["t1"].id,
                invoice_number="PINV-132-DRAFT",
                supplier_id=supplier.id,
                status="draft",
                subtotal=10,
                tax_amount=0,
                total_amount=10,
            ),
            m.PurchaseInvoice(
                tenant_id=seed["t1"].id,
                invoice_number="PINV-132-UNPAID",
                supplier_id=supplier.id,
                status="unpaid",
                subtotal=25,
                tax_amount=0,
                total_amount=25,
            ),
        ]
    )
    await db_session.commit()

    exported = await ac.get(
        "/api/v1/purchasing/invoices/export?status=draft", headers=headers
    )
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    header = exported.text.splitlines()[0]
    assert "invoice_number" in header and "status" in header
    assert "items" not in header
    assert "PINV-132-DRAFT" in exported.text
    assert "PINV-132-UNPAID" not in exported.text

    outstanding = await ac.get(
        "/api/v1/purchasing/invoices/export?status=outstanding", headers=headers
    )
    assert outstanding.status_code == 200, outstanding.text
    assert "PINV-132-UNPAID" in outstanding.text
    assert "PINV-132-DRAFT" not in outstanding.text


def test_purchasing_invoices_export_ui_p1():
    page = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert "Stage 132" in page
    assert "/purchasing/invoices/export" in page
    assert "Export invoices CSV" in page
