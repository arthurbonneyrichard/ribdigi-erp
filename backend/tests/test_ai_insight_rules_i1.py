"""BR-21.2 composed insight rules: sales spike/drop, expense anomalies, restock actions."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app import ai as ai_svc
from app import expenses as expenses_svc
from app import models as m
from tests.conftest import auth_headers


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


def test_sales_spike_drop_notes_from_dashboard_comparisons():
    notes = ai_svc.build_insight_notes(
        {
            "low_stock": 0,
            "total_expenses": 0,
            "total_sales": 100,
            "comparisons": {
                "sales_today_pct": 40.0,
                "sales_mtd_pct": -30.0,
            },
            "daily_sales": [{"sales": 10} for _ in range(7)]
            + [{"sales": 40} for _ in range(7)],
        }
    )
    joined = " ".join(notes)
    assert "Sales spike 40%" in joined
    assert "Sales drop -30%" in joined
    assert "last 7 days vs prior 7" in joined


@pytest.mark.asyncio
async def test_insights_compose_expense_anomaly_and_restock_action(client, db_session):
    ac, seed = client
    tid = seed["t1"].id

    await expenses_svc.ensure_default_categories(db_session, tid)
    cats = (
        await db_session.execute(
            select(m.ExpenseCategory).where(m.ExpenseCategory.tenant_id == tid)
        )
    ).scalars().all()
    trans = next(c for c in cats if c.code == "TRANS")
    trans.budget_amount = 40
    for amt in (8, 9, 10, 180):
        db_session.add(
            m.Expense(
                tenant_id=tid,
                category_id=trans.id,
                category=trans.name,
                description="trip",
                amount=amt,
                expense_date=datetime.utcnow() - timedelta(days=1),
                status="approved",
                payee="CabCo",
                created_by=seed["mgr1"].id,
            )
        )

    product = seed["p1"]
    product.stock_qty = 2
    product.reorder_level = 10
    # Prior window: low volume; recent window: high volume → rising seasonality
    now = datetime.utcnow()
    prior_inv = m.SalesInvoice(
        tenant_id=tid,
        invoice_number="INV-AI-RULES-PRIOR",
        customer_id=seed["party1"].id,
        status="posted",
        subtotal=4,
        total_amount=4,
        posted_at=now - timedelta(days=20),
    )
    recent_inv = m.SalesInvoice(
        tenant_id=tid,
        invoice_number="INV-AI-RULES-RECENT",
        customer_id=seed["party1"].id,
        status="posted",
        subtotal=40,
        total_amount=40,
        posted_at=now - timedelta(days=2),
    )
    db_session.add_all([prior_inv, recent_inv])
    await db_session.flush()
    db_session.add(
        m.SalesInvoiceItem(
            tenant_id=tid,
            sales_invoice_id=prior_inv.id,
            product_id=product.id,
            quantity=2,
            unit_price=2,
            line_subtotal=4,
            line_total=4,
        )
    )
    db_session.add(
        m.SalesInvoiceItem(
            tenant_id=tid,
            sales_invoice_id=recent_inv.id,
            product_id=product.id,
            quantity=20,
            unit_price=2,
            line_subtotal=40,
            line_total=40,
        )
    )
    await db_session.commit()

    headers = await _mgr(ac)
    response = await ac.get("/api/v1/ai/insights", headers=headers)
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["source"] == "rule_based"
    assert data.get("signals")
    kinds = {s.get("kind") for s in data["signals"]}
    joined = " ".join(data.get("insights") or [])
    assert (
        "expense_anomaly" in kinds
        or "over budget" in joined.lower()
        or "Unusual expense" in joined
    )
    assert "action" in kinds or "Restock" in joined
    assert "Beta" not in joined
