"""Stage 146 F1 — AI demand forecast CSV export."""

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
async def test_demand_forecast_export_csv(client, db_session):
    ac, seed = client
    headers = await _mgr(ac)
    product = seed["p1"]
    product.stock_qty = 50
    product.is_active = True
    await db_session.flush()
    for day in range(20):
        inv = m.SalesInvoice(
            tenant_id=seed["t1"].id,
            invoice_number=f"INV-146F-{day}",
            customer_id=seed["party1"].id,
            status="posted",
            subtotal=10,
            tax_amount=0,
            total_amount=10,
            posted_at=datetime.utcnow() - timedelta(days=day),
            created_at=datetime.utcnow() - timedelta(days=day),
        )
        db_session.add(inv)
        await db_session.flush()
        db_session.add(
            m.SalesInvoiceItem(
                tenant_id=seed["t1"].id,
                sales_invoice_id=inv.id,
                product_id=product.id,
                quantity=2,
                unit_price=5,
                line_total=10,
            )
        )
    await db_session.commit()

    exported = await ac.get("/api/v1/ai/inventory/demand-forecast/export", headers=headers)
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    text = exported.text
    header = text.splitlines()[0]
    assert "forecast_7d" in header and "forecast_30d" in header and "forecast_90d" in header
    assert product.id in text


def test_demand_forecast_export_ui_f1():
    page = (ROOT / "frontend/app/ai/page.tsx").read_text(encoding="utf-8")
    assert "Stage 146" in page
    assert "/ai/inventory/demand-forecast/export" in page
    assert "Export forecast CSV" in page
    assert 'id="forecast"' in page
