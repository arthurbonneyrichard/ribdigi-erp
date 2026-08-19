"""Stage 147 S1 — AI sales analysis CSV export."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from app import models as m
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


@pytest.mark.asyncio
async def test_sales_analysis_export_csv(client, db_session):
    ac, seed = client
    headers = await _mgr(ac)
    product = seed["p1"]
    inv = m.SalesInvoice(
        tenant_id=seed["t1"].id,
        invoice_number="INV-147S-1",
        customer_id=seed["party1"].id,
        status="posted",
        subtotal=50,
        tax_amount=0,
        total_amount=50,
        posted_at=datetime.utcnow() - timedelta(days=1),
        created_at=datetime.utcnow() - timedelta(days=1),
    )
    db_session.add(inv)
    await db_session.flush()
    db_session.add(
        m.SalesInvoiceItem(
            tenant_id=seed["t1"].id,
            sales_invoice_id=inv.id,
            product_id=product.id,
            quantity=5,
            unit_price=10,
            line_total=50,
        )
    )
    await db_session.commit()

    exported = await ac.get("/api/v1/ai/sales/analysis/export", headers=headers)
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    text = exported.text
    header = text.splitlines()[0]
    assert "row_type" in header and "total_sales" in header and "rfm_segment" in header
    assert "summary" in text
    assert "peak" in text


def test_sales_analysis_export_ui_s1():
    page = (ROOT / "frontend/app/ai/page.tsx").read_text(encoding="utf-8")
    assert "Stage 147" in page
    assert "/ai/sales/analysis/export" in page
    assert "Export sales analysis CSV" in page
    assert 'id="sales-analysis"' in page
