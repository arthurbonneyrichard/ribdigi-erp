"""Stage 133 R1 — sales return register CSV export."""

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
async def test_returns_export_csv(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)

    inv = m.SalesInvoice(
        tenant_id=seed["t1"].id,
        invoice_number="INV-133-RET",
        customer_id=seed["party1"].id,
        status="posted",
        subtotal=50,
        tax_amount=0,
        total_amount=50,
    )
    db_session.add(inv)
    await db_session.flush()

    db_session.add_all(
        [
            m.SalesReturn(
                tenant_id=seed["t1"].id,
                return_number="SR-133-DRAFT",
                customer_id=seed["party1"].id,
                sales_invoice_id=inv.id,
                status="draft",
                reason="other",
                subtotal=5,
                tax_amount=0,
                total_amount=5,
            ),
            m.SalesReturn(
                tenant_id=seed["t1"].id,
                return_number="SR-133-POSTED",
                customer_id=seed["party1"].id,
                sales_invoice_id=inv.id,
                status="posted",
                reason="defective",
                subtotal=8,
                tax_amount=0,
                total_amount=8,
            ),
        ]
    )
    await db_session.commit()

    exported = await ac.get(
        "/api/v1/sales/returns/export?status=posted", headers=headers
    )
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    header = exported.text.splitlines()[0]
    assert "return_number" in header and "status" in header
    assert "items" not in header
    assert "SR-133-POSTED" in exported.text
    assert "SR-133-DRAFT" not in exported.text


def test_returns_export_ui_r1():
    page = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert "Stage 133" in page
    assert "downloadPipelineExport" in page
    assert "Export returns CSV" in page
