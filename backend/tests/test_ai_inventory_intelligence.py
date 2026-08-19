"""Phase 4 / BR-21.3 smart inventory intelligence (demand forecast + dead stock)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app import ai_inventory as ai_inventory_svc
from app import models as m
from tests.conftest import auth_headers


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


async def _seed_steady_sales(db_session, seeded, *, days: int = 30, qty_per_day: float = 4):
    tenant_id = seeded["t1"].id
    product = seeded["p1"]
    product.stock_qty = 80
    product.cost_price = 2.5
    product.is_active = True
    await db_session.flush()
    for day in range(days):
        inv = m.SalesInvoice(
            tenant_id=tenant_id,
            invoice_number=f"INV-FC-{day}",
            customer_id=seeded["party1"].id,
            status="posted",
            subtotal=qty_per_day * 2,
            total_amount=qty_per_day * 2,
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
async def test_demand_forecast_horizons(db_session, seeded):
    product = await _seed_steady_sales(db_session, seeded, days=30, qty_per_day=4)
    data = await ai_inventory_svc.forecast_demand(db_session, seeded["t1"].id, lookback_days=30)
    assert data["method"] == "sales_velocity_v1"
    assert data["horizons_days"] == [7, 30, 90]
    row = next(f for f in data["forecasts"] if f["product_id"] == product.id)
    assert row["status"] == "ok"
    assert row["forecast_7d"] > 0
    assert row["forecast_30d"] > row["forecast_7d"]
    assert row["forecast_90d"] > row["forecast_30d"]
    assert abs(row["forecast_30d"] - row["forecast_units"]["30"]) < 0.01
    assert row["optimal_reorder_qty"] >= 0
    assert row["seasonality"] in {"increasing", "decreasing", "stable", "unknown"}
    assert row["confidence"] > 0


@pytest.mark.asyncio
async def test_dead_stock_identification(db_session, seeded):
    tenant_id = seeded["t1"].id
    product = seeded["p1"]
    product.stock_qty = 25
    product.cost_price = 3
    product.is_active = True
    # Old sale outside 90-day dead-stock window
    inv = m.SalesInvoice(
        tenant_id=tenant_id,
        invoice_number="INV-DEAD-OLD",
        customer_id=seeded["party1"].id,
        status="posted",
        subtotal=6,
        total_amount=6,
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
    await db_session.commit()

    data = await ai_inventory_svc.identify_dead_stock(db_session, tenant_id, lookback_days=90)
    assert data["count"] >= 1
    row = next(i for i in data["items"] if i["product_id"] == product.id)
    assert row["stock_qty"] == 25
    assert row["days_without_sale"] >= 90
    assert row["estimated_carrying_cost"] == 75.0


@pytest.mark.asyncio
async def test_demand_forecast_and_dead_stock_api_tenant_scoped(client, db_session):
    ac, seed = client
    headers = await _mgr(ac)
    await _seed_steady_sales(db_session, seed, days=30, qty_per_day=3)

    # Beta product with stock but no alpha leakage
    seed["p2"].stock_qty = 99
    seed["p2"].cost_price = 10
    await db_session.commit()

    fc = await ac.get("/api/v1/ai/inventory/demand-forecast", headers=headers)
    assert fc.status_code == 200, fc.text
    body = fc.json()["data"]
    ids = {f["product_id"] for f in body["forecasts"]}
    assert seed["p1"].id in ids
    assert seed["p2"].id not in ids
    assert all("Beta" not in f["name"] for f in body["forecasts"])

    dead = await ac.get("/api/v1/ai/inventory/dead-stock?lookback_days=90", headers=headers)
    assert dead.status_code == 200, dead.text
    dead_ids = {i["product_id"] for i in dead.json()["data"]["items"]}
    assert seed["p2"].id not in dead_ids

    pred = await ac.get("/api/v1/ai/inventory/predictions", headers=headers)
    assert pred.status_code == 200, pred.text
    pdata = pred.json()["data"]
    assert "forecasts" in pdata
    assert "predictions" in pdata
    assert pdata["forecast_count"] >= 1
