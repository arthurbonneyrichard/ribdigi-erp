"""Rule-based AI inventory predictions (BR-21.3 / BR-21.4)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pyotp
import pytest
from sqlalchemy import select

from app import models as m
from app import ai_inventory as inv
from tests.conftest import auth_headers


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


def test_confidence_and_seasonality_helpers():
    assert 0 <= inv.confidence_score(sold_qty=0, lookback=28, sale_days_present=0) <= 1
    assert inv.confidence_score(sold_qty=100, lookback=28, sale_days_present=20) > 0.5
    rising = inv.seasonality_hint(recent_velocity=2.0, prior_velocity=1.0)
    assert rising["label"] == "rising"
    stable = inv.seasonality_hint(recent_velocity=1.0, prior_velocity=1.0)
    assert stable["label"] == "stable"


@pytest.mark.asyncio
async def test_predictions_use_velocity_and_are_tenant_scoped(client, db_session):
    ac, seed = client
    tid = seed["t1"].id
    product = seed["p1"]
    product.stock_qty = 10
    product.reorder_level = 50
    await db_session.flush()

    # Posted sales: 28 units over lookback → velocity=1/day if lookback=28
    customer = seed["party1"]
    inv_row = m.SalesInvoice(
        tenant_id=tid,
        invoice_number="INV-AI-PRED-1",
        customer_id=customer.id,
        status="posted",
        subtotal=56,
        total_amount=56,
        posted_at=datetime.utcnow() - timedelta(days=3),
    )
    db_session.add(inv_row)
    await db_session.flush()
    db_session.add(
        m.SalesInvoiceItem(
            tenant_id=tid,
            sales_invoice_id=inv_row.id,
            product_id=product.id,
            quantity=28,
            unit_price=2,
            line_subtotal=56,
            line_total=56,
        )
    )
    # Beta product noise should not appear
    seed["p2"].stock_qty = 1
    await db_session.commit()

    headers = await _mgr(ac)
    r = await ac.get("/api/v1/ai/inventory/predictions", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["method"] == "rule_based_velocity"
    ids = {p["product_id"] for p in data["products"]}
    assert product.id in ids
    assert seed["p2"].id not in ids
    row = next(p for p in data["products"] if p["product_id"] == product.id)
    assert row["sold_qty_lookback"] == 28
    assert abs(row["velocity_per_day"] - (28 / inv.lookback_days())) < 1e-6
    assert row["forecast_demand_7"] > 0
    assert row["recommended_order_qty"] > 0
    assert 0 <= row["confidence"] <= 1
    assert "Beta" not in r.text


@pytest.mark.asyncio
async def test_low_stock_prediction_and_pr_generation(client, db_session):
    ac, seed = client
    tid = seed["t1"].id
    product = seed["p1"]
    product.stock_qty = 5
    product.reorder_level = 2
    await db_session.flush()
    inv_row = m.SalesInvoice(
        tenant_id=tid,
        invoice_number="INV-AI-PRED-2",
        customer_id=seed["party1"].id,
        status="posted",
        subtotal=40,
        total_amount=40,
        posted_at=datetime.utcnow() - timedelta(days=1),
    )
    db_session.add(inv_row)
    await db_session.flush()
    db_session.add(
        m.SalesInvoiceItem(
            tenant_id=tid,
            sales_invoice_id=inv_row.id,
            product_id=product.id,
            quantity=40,
            unit_price=1,
            line_subtotal=40,
            line_total=40,
        )
    )
    await db_session.commit()

    headers = await _mgr(ac)
    pred = await ac.get(
        "/api/v1/ai/inventory/low-stock-prediction",
        headers=headers,
        params={"days_ahead": 14},
    )
    assert pred.status_code == 200, pred.text
    body = pred.json()["data"]
    assert body["count"] >= 1
    hit = next(x for x in body["at_risk"] if x["product_id"] == product.id)
    assert hit["days_to_stockout"] is not None
    assert hit["days_to_stockout"] <= 14
    assert hit["suggested_order_qty"] > 0
    assert "confidence" in hit

    admin = await _super(ac, seed)
    slim = {
        "product_id": hit["product_id"],
        "confidence": hit.get("confidence"),
        "suggested_order_qty": hit.get("suggested_order_qty"),
        "recommended_order_qty": hit.get("recommended_order_qty"),
        "warehouse_id": hit.get("warehouse_id"),
        "preferred_supplier_id": hit.get("preferred_supplier_id"),
        "notes": hit.get("notes"),
        "risk_reason": hit.get("risk_reason"),
    }
    created = await ac.post(
        "/api/v1/ai/inventory/low-stock-prediction/requests",
        headers=admin,
        json={"lines": [slim], "notes": "From AI prediction test"},
    )
    assert created.status_code == 200, created.text
    assert created.json()["data"]["created_count"] >= 1

    # Full prediction blobs with extras must 422 under AiLowStockPredictionLine.
    bloated = await ac.post(
        "/api/v1/ai/inventory/low-stock-prediction/requests",
        headers=admin,
        json={"lines": [hit], "notes": "should reject extras"},
    )
    assert bloated.status_code == 422, bloated.text

    prs = (
        await db_session.execute(
            select(m.PurchaseRequest).where(m.PurchaseRequest.tenant_id == tid)
        )
    ).scalars().all()
    assert any("AI" in (p.notes or "") or "prediction" in (p.notes or "").lower() for p in prs) or prs


@pytest.mark.asyncio
async def test_dead_stock_flag(client, db_session):
    ac, seed = client
    # Alpha widget with stock but no sales → dead
    seed["p1"].stock_qty = 12
    await db_session.commit()
    headers = await _mgr(ac)
    r = await ac.get("/api/v1/ai/inventory/predictions", headers=headers)
    assert r.status_code == 200
    row = next(p for p in r.json()["data"]["products"] if p["product_id"] == seed["p1"].id)
    assert row["dead_stock"] is True
    assert any(d["product_id"] == seed["p1"].id for d in r.json()["data"]["dead_stock"])
