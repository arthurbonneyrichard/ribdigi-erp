"""Stage 20 V1: Smart inventory intelligence fidelity (BR-21.3)."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from app import models as m
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


async def _seed_steady_sales(db_session, seed, *, days: int = 30, qty_per_day: float = 4):
    tenant_id = seed["t1"].id
    product = seed["p1"]
    product.stock_qty = 80
    product.cost_price = 2.5
    product.reorder_level = 20
    product.is_active = True
    await db_session.flush()
    for day in range(days):
        inv = m.SalesInvoice(
            tenant_id=tenant_id,
            invoice_number=f"INV-V1-FC-{day}",
            customer_id=seed["party1"].id,
            status="posted",
            subtotal=qty_per_day * 2,
            total_amount=qty_per_day * 2,
            tax_amount=0,
            posted_at=datetime.utcnow() - timedelta(days=day),
            created_at=datetime.utcnow() - timedelta(days=day),
        )
        db_session.add(inv)
        await db_session.flush()
        db_session.add(
            m.SalesInvoiceItem(
                tenant_id=tenant_id,
                sales_invoice_id=inv.id,
                product_id=product.id,
                quantity=qty_per_day,
                unit_price=2,
                line_total=qty_per_day * 2,
            )
        )
    await db_session.commit()
    return product


@pytest.mark.asyncio
async def test_demand_forecast_reorder_and_seasonality_api(client, db_session):
    """BR-21.3: 7/30/90 demand forecast, optimal reorder qty, seasonality."""
    ac, seed = client
    headers = await _mgr(ac)
    product = await _seed_steady_sales(db_session, seed, days=30, qty_per_day=4)

    fc = await ac.get(
        "/api/v1/ai/inventory/demand-forecast?lookback_days=30",
        headers=headers,
    )
    assert fc.status_code == 200, fc.text
    body = fc.json()["data"]
    assert body["method"] == "sales_velocity_v1"
    assert body["horizons_days"] == [7, 30, 90]
    row = next(f for f in body["forecasts"] if f["product_id"] == product.id)
    assert row["status"] == "ok"
    assert row["forecast_7d"] > 0
    assert row["forecast_30d"] > row["forecast_7d"]
    assert row["forecast_90d"] > row["forecast_30d"]
    assert row["optimal_reorder_qty"] >= 0
    assert row["seasonality"] in {"increasing", "decreasing", "stable", "unknown"}
    assert row["confidence"] > 0
    assert seed["p2"].id not in {f["product_id"] for f in body["forecasts"]}


@pytest.mark.asyncio
async def test_dead_stock_identification_api(client, db_session):
    """BR-21.3: dead stock with no sales in lookback window."""
    ac, seed = client
    headers = await _mgr(ac)
    tenant_id = seed["t1"].id
    product = seed["p1"]
    product.stock_qty = 25
    product.cost_price = 3
    product.is_active = True

    inv = m.SalesInvoice(
        tenant_id=tenant_id,
        invoice_number="INV-V1-DEAD-OLD",
        customer_id=seed["party1"].id,
        status="posted",
        subtotal=6,
        total_amount=6,
        tax_amount=0,
        posted_at=datetime.utcnow() - timedelta(days=120),
        created_at=datetime.utcnow() - timedelta(days=120),
    )
    db_session.add(inv)
    await db_session.flush()
    db_session.add(
        m.SalesInvoiceItem(
            tenant_id=tenant_id,
            sales_invoice_id=inv.id,
            product_id=product.id,
            quantity=2,
            unit_price=3,
            line_total=6,
        )
    )
    seed["p2"].stock_qty = 99
    await db_session.commit()

    dead = await ac.get(
        "/api/v1/ai/inventory/dead-stock?lookback_days=90",
        headers=headers,
    )
    assert dead.status_code == 200, dead.text
    data = dead.json()["data"]
    assert data["count"] >= 1
    row = next(i for i in data["items"] if i["product_id"] == product.id)
    assert row["stock_qty"] == 25
    assert row["days_without_sale"] >= 90
    assert row["estimated_carrying_cost"] == 75.0
    assert seed["p2"].id not in {i["product_id"] for i in data["items"]}


@pytest.mark.asyncio
async def test_inventory_predictions_bundle_api(client, db_session):
    """BR-21.3: combined predictions endpoint includes forecasts."""
    ac, seed = client
    headers = await _mgr(ac)
    await _seed_steady_sales(db_session, seed, days=30, qty_per_day=3)

    pred = await ac.get("/api/v1/ai/inventory/predictions", headers=headers)
    assert pred.status_code == 200, pred.text
    pdata = pred.json()["data"]
    assert "forecasts" in pdata
    assert "predictions" in pdata
    assert pdata["forecast_count"] >= 1


def test_br_21_3_and_plan_synced():
    br = (ROOT / "docs" / "BUSINESS_REQUIREMENTS_DOCUMENT.md").read_text(encoding="utf-8")
    s213 = br.split("#### BR-21.3 Smart Inventory Intelligence")[1].split("#### BR-21.4")[0]
    assert "[x] Demand forecasting per product (7-day, 30-day, 90-day)" in s213
    assert "[x] Optimal reorder quantity recommendations" in s213
    assert "[x] Seasonality detection" in s213
    assert "[x] Dead stock identification" in s213
    assert "Stage 20 V1" in s213
    assert "test_ai_inventory_intel_v1.py" in s213

    plan = (ROOT / "docs" / "STAGE_20_PLAN.md").read_text(encoding="utf-8")
    v1_line = [ln for ln in plan.splitlines() if "| **V1**" in ln][0]
    assert "COMPLETE" in v1_line
    assert "test_ai_inventory_intel_v1.py" in plan
