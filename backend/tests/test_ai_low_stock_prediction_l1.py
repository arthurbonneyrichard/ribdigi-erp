"""Stage 20 L1: AI low-stock prediction fidelity (BR-21.4)."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from app import models as m
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


async def _seed_velocity(db_session, seed, *, stock: float, qty_per_day: float, days: int = 30):
    product = seed["p1"]
    product.stock_qty = stock
    product.reserved_qty = 0
    product.reorder_level = max(stock / 2, 1)
    product.is_active = True
    await db_session.flush()
    for day in range(days):
        inv = m.SalesInvoice(
            tenant_id=seed["t1"].id,
            invoice_number=f"INV-L1-{int(stock)}-{day}",
            customer_id=seed["party1"].id,
            status="posted",
            subtotal=qty_per_day * 2,
            tax_amount=0,
            total_amount=qty_per_day * 2,
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
                quantity=qty_per_day,
                unit_price=2,
                line_total=qty_per_day * 2,
            )
        )
    await db_session.commit()
    return product


@pytest.mark.asyncio
async def test_stockout_prediction_7_to_14_days_api(client, db_session):
    """BR-21.4: predict stockouts 7–14 days ahead with confidence + suggestions."""
    ac, seed = client
    headers = await _mgr(ac)
    # 10 units/day, stock 120 → ~12 days to stockout
    product = await _seed_velocity(db_session, seed, stock=120, qty_per_day=10, days=30)

    r = await ac.get(
        "/api/v1/ai/inventory/low-stock-prediction",
        headers=headers,
        params={
            "lookback_days": 30,
            "horizon_days": 14,
            "lead_time_days": 7,
            "at_risk_only": True,
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert body["method"] == "sales_velocity_v1"
    assert body["horizon_days"] == 14
    assert body["lead_time_days"] == 7
    assert body["at_risk_count"] >= 1
    row = next(p for p in body["predictions"] if p["product_id"] == product.id)
    assert row["at_risk"] is True
    assert row["days_to_stockout"] is not None
    assert 7 <= row["days_to_stockout"] <= 14
    assert row["confidence"] > 0.3
    assert row["suggested_order_qty"] > 0
    assert row["velocity_per_day"] > 0
    assert row["seasonality_factor"] > 0
    assert row["adjusted_velocity_per_day"] > 0
    assert seed["p2"].id not in {p["product_id"] for p in body["predictions"]}


@pytest.mark.asyncio
async def test_insufficient_history_not_at_risk(client, db_session):
    """BR-21.4: no velocity history → insufficient_data, not at_risk."""
    ac, seed = client
    headers = await _mgr(ac)
    seed["p1"].stock_qty = 50
    seed["p1"].is_active = True
    await db_session.commit()

    r = await ac.get(
        "/api/v1/ai/inventory/low-stock-prediction",
        headers=headers,
        params={"at_risk_only": False, "horizon_days": 14},
    )
    assert r.status_code == 200, r.text
    row = next(p for p in r.json()["data"]["predictions"] if p["product_id"] == seed["p1"].id)
    assert row["status"] == "insufficient_data"
    assert row["at_risk"] is False


@pytest.mark.asyncio
async def test_lead_time_influences_purchase_suggestion(client, db_session):
    """BR-21.4: lead_time_days feeds suggested_order_qty."""
    ac, seed = client
    headers = await _mgr(ac)
    product = await _seed_velocity(db_session, seed, stock=40, qty_per_day=5, days=30)

    short = await ac.get(
        "/api/v1/ai/inventory/low-stock-prediction",
        headers=headers,
        params={"horizon_days": 14, "lead_time_days": 3, "at_risk_only": True},
    )
    long = await ac.get(
        "/api/v1/ai/inventory/low-stock-prediction",
        headers=headers,
        params={"horizon_days": 14, "lead_time_days": 14, "at_risk_only": True},
    )
    assert short.status_code == 200 and long.status_code == 200
    s_row = next(p for p in short.json()["data"]["predictions"] if p["product_id"] == product.id)
    l_row = next(p for p in long.json()["data"]["predictions"] if p["product_id"] == product.id)
    assert s_row["suggested_order_qty"] > 0
    assert l_row["suggested_order_qty"] >= s_row["suggested_order_qty"]


def test_br_21_4_and_plan_synced():
    br = (ROOT / "docs" / "BUSINESS_REQUIREMENTS_DOCUMENT.md").read_text(encoding="utf-8")
    s214 = br.split("#### BR-21.4 AI Low Stock Prediction")[1].split("#### BR-21.5")[0]
    assert "[x] Predict stockouts 7–14 days in advance" in s214
    assert "[x] Consider sales velocity, seasonality, lead time" in s214
    assert "[x] Confidence score on predictions" in s214
    assert "[x] Auto-generate purchase suggestions" in s214
    assert "Stage 20 L1" in s214
    assert "test_ai_low_stock_prediction_l1.py" in s214

    plan = (ROOT / "docs" / "STAGE_20_PLAN.md").read_text(encoding="utf-8")
    l1_line = [ln for ln in plan.splitlines() if "| **L1**" in ln][0]
    assert "COMPLETE" in l1_line
    assert "test_ai_low_stock_prediction_l1.py" in plan
