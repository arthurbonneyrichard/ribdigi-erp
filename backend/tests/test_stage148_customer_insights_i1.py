"""Stage 148 I1 — AI customer insights CSV export."""

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
async def test_customer_insights_export_csv(client, db_session):
    ac, seed = client
    headers = await _mgr(ac)
    customer = seed["party1"]
    inv = m.SalesInvoice(
        tenant_id=seed["t1"].id,
        invoice_number="INV-148I-1",
        customer_id=customer.id,
        status="posted",
        subtotal=80,
        tax_amount=0,
        total_amount=80,
        paid_amount=80,
        posted_at=datetime.utcnow() - timedelta(days=3),
        created_at=datetime.utcnow() - timedelta(days=3),
    )
    db_session.add(inv)
    await db_session.commit()

    exported = await ac.get(
        "/api/v1/ai/customers/insights/export?lookback_days=180", headers=headers
    )
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    text = exported.text
    header = text.splitlines()[0]
    assert "row_type" in header and "customer_id" in header and "churn_band" in header
    assert "summary" in text
    assert customer.id in text or customer.name in text


def test_customer_insights_export_ui_i1():
    page = (ROOT / "frontend/app/ai/page.tsx").read_text(encoding="utf-8")
    assert "Stage 148" in page
    assert "/ai/customers/insights/export" in page
    assert "Export customer insights CSV" in page
    assert 'id="customer"' in page
