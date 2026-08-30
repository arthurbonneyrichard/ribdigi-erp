"""Phase 4 / BR-21.4 AI low stock prediction (sales velocity)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app import ai_inventory as ai_inventory_svc
from app import models as m
from tests.conftest import auth_headers


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


@pytest.mark.asyncio
async def test_predict_stockout_about_twelve_days(db_session, seeded):
    tenant_id = seeded["t1"].id
    product = seeded["p1"]
    product.stock_qty = 120
    product.reserved_qty = 0
    product.is_active = True
    await db_session.flush()

    # 10 units/day over 30 days → stockout in 12 days at stock 120
    for day in range(30):
        inv = m.SalesInvoice(
            tenant_id=tenant_id,
            invoice_number=f"INV-AI-{day}",
            customer_id=seeded["party1"].id,
            status="posted",
            subtotal=20,
            tax_amount=0,
            total_amount=20,
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
                quantity=10,
                unit_price=2,
                line_total=20,
            )
        )
    await db_session.commit()

    result = await ai_inventory_svc.predict_low_stock(
        db_session, tenant_id, lookback_days=30, horizon_days=14, at_risk_only=True
    )
    assert result["at_risk_count"] >= 1
    row = next(p for p in result["predictions"] if p["product_id"] == product.id)
    assert row["at_risk"] is True
    assert row["days_to_stockout"] is not None
    assert 10 <= row["days_to_stockout"] <= 14
    assert row["confidence"] > 0.3
    assert row["suggested_order_qty"] > 0


@pytest.mark.asyncio
async def test_insufficient_sales_history_not_at_risk(db_session, seeded):
    tenant_id = seeded["t1"].id
    product = seeded["p1"]
    product.stock_qty = 50
    await db_session.commit()

    result = await ai_inventory_svc.predict_low_stock(db_session, tenant_id, at_risk_only=False)
    row = next(p for p in result["predictions"] if p["product_id"] == product.id)
    assert row["status"] == "insufficient_data"
    assert row["at_risk"] is False


@pytest.mark.asyncio
async def test_low_stock_prediction_api_tenant_scoped(client, db_session):
    ac, seed = client
    headers = await _mgr(ac, seed)
    product = seed["p1"]
    product.stock_qty = 24
    product.company_id = seed["c1"].id
    store = m.Store(
        tenant_id=seed["t1"].id,
        company_id=seed["c1"].id,
        name="AI LS Mgr",
        code="AILS",
        manager_id=seed["mgr1"].id,
        is_active=True,
    )
    db_session.add(store)
    await db_session.flush()
    wh = m.Warehouse(
        tenant_id=seed["t1"].id,
        company_id=seed["c1"].id,
        store_id=store.id,
        name="AI LS WH",
        code="AILS-WH",
    )
    db_session.add(wh)
    await db_session.flush()
    db_session.add(
        m.WarehouseStock(
            tenant_id=seed["t1"].id,
            company_id=seed["c1"].id,
            warehouse_id=wh.id,
            product_id=product.id,
            quantity=24,
            reserved_qty=0,
            reorder_level=5,
        )
    )

    for day in range(30):
        inv = m.SalesInvoice(
            tenant_id=seed["t1"].id,
            company_id=seed["c1"].id,
            invoice_number=f"INV-API-{day}",
            customer_id=seed["party1"].id,
            status="posted",
            subtotal=4,
            total_amount=4,
            store_id=store.id,
            posted_at=datetime.utcnow() - timedelta(days=day),
            created_at=datetime.utcnow() - timedelta(days=day),
        )
        db_session.add(inv)
        await db_session.flush()
        db_session.add(
            m.SalesInvoiceItem(
                tenant_id=seed["t1"].id,
                company_id=seed["c1"].id,
                sales_invoice_id=inv.id,
                product_id=product.id,
                quantity=2,
                unit_price=2,
                line_total=4,
            )
        )
    await db_session.commit()

    r = await ac.get(
        "/api/v1/ai/inventory/low-stock-prediction",
        headers=headers,
        params={"horizon_days": 14, "at_risk_only": True},
    )
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert body["method"] == "sales_velocity_v1"
    assert body.get("scope") == "store_manager"
    ids = {p["product_id"] for p in body["predictions"]}
    assert product.id in ids
    # Beta product must not appear
    assert seed["p2"].id not in ids


@pytest.mark.asyncio
async def test_notify_predicted_stockouts_dedupes(db_session, seeded):
    tenant_id = seeded["t1"].id
    product = seeded["p1"]
    product.stock_qty = 20
    await db_session.flush()
    for day in range(20):
        inv = m.SalesInvoice(
            tenant_id=tenant_id,
            invoice_number=f"INV-N-{day}",
            customer_id=seeded["party1"].id,
            status="posted",
            subtotal=10,
            total_amount=10,
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
                quantity=5,
                unit_price=2,
                line_total=10,
            )
        )
    await db_session.commit()

    first = await ai_inventory_svc.notify_predicted_stockouts(db_session, tenant_id)
    await db_session.commit()
    assert first["notifications_created"] >= 1
    second = await ai_inventory_svc.notify_predicted_stockouts(db_session, tenant_id)
    assert second["notifications_created"] == 0

    notes = (
        await db_session.execute(
            select(m.Notification).where(
                m.Notification.tenant_id == tenant_id,
                m.Notification.title == "Predicted Stockout",
                m.Notification.entity_id == product.id,
            )
        )
    ).scalars().all()
    assert len(notes) == 1
