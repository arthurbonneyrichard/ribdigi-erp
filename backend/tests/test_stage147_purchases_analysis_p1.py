"""Stage 147 P1 — AI purchases analysis CSV export."""

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
async def test_purchases_analysis_export_csv(client, db_session):
    ac, seed = client
    headers = await _mgr(ac)
    supplier = seed.get("party2") or seed["party1"]
    inv = m.PurchaseInvoice(
        tenant_id=seed["t1"].id,
        invoice_number="PI-147P-1",
        supplier_id=supplier.id,
        status="posted",
        subtotal=200,
        tax_amount=0,
        total_amount=200,
        paid_amount=0,
        invoice_date=datetime.utcnow() - timedelta(days=2),
        due_date=datetime.utcnow() - timedelta(days=1),
        created_at=datetime.utcnow() - timedelta(days=2),
    )
    db_session.add(inv)
    await db_session.commit()

    exported = await ac.get("/api/v1/ai/purchases/analysis/export", headers=headers)
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    text = exported.text
    header = text.splitlines()[0]
    assert "row_type" in header and "total_spend" in header
    assert "summary" in text
    assert "PI-147P-1" in text or "supplier" in text or "200" in text


def test_purchases_analysis_export_ui_p1():
    page = (ROOT / "frontend/app/ai/page.tsx").read_text(encoding="utf-8")
    assert "Stage 147" in page
    assert "/ai/purchases/analysis/export" in page
    assert "Export purchases analysis CSV" in page
    assert 'id="purchases-analysis"' in page
