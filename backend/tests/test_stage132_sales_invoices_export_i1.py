"""Stage 132 I1 — sales invoice register CSV export."""

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
async def test_sales_invoices_export_csv(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)

    db_session.add_all(
        [
            m.SalesInvoice(
                tenant_id=seed["t1"].id,
                invoice_number="INV-132-DRAFT",
                customer_id=seed["party1"].id,
                status="draft",
                subtotal=10,
                tax_amount=0,
                total_amount=10,
            ),
            m.SalesInvoice(
                tenant_id=seed["t1"].id,
                invoice_number="INV-132-POSTED",
                customer_id=seed["party1"].id,
                status="posted",
                subtotal=20,
                tax_amount=0,
                total_amount=20,
            ),
        ]
    )
    await db_session.commit()

    exported = await ac.get(
        "/api/v1/sales/invoices/export?status=draft", headers=headers
    )
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    header = exported.text.splitlines()[0]
    assert "invoice_number" in header and "status" in header
    assert "items" not in header
    assert "INV-132-DRAFT" in exported.text
    assert "INV-132-POSTED" not in exported.text

    unpaid = await ac.get(
        "/api/v1/sales/invoices/export?status=unpaid", headers=headers
    )
    assert unpaid.status_code == 200, unpaid.text
    assert "INV-132-POSTED" in unpaid.text
    assert "INV-132-DRAFT" not in unpaid.text


def test_sales_invoices_export_ui_i1():
    page = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert "Stage 132" in page
    assert "/sales/invoices/export" in page
    assert "Export invoices CSV" in page
