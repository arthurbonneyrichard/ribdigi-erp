"""Rule-based AI sales + expense analysis (BR-21.5 / BR-21.6)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app import models as m
from app import ai_expenses as ai_exp
from app import expenses as expenses_svc
from tests.conftest import auth_headers


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


def test_category_keyword_suggest():
    cats = [
        m.ExpenseCategory(id="1", tenant_id="t", code="TRANS", name="Transportation"),
        m.ExpenseCategory(id="2", tenant_id="t", code="UTIL", name="Utilities"),
    ]
    hit = ai_exp.suggest_category_from_text("Uber trip downtown", cats)
    assert hit and hit["category_code"] == "TRANS"
    util = ai_exp.suggest_category_from_text("Electricity bill payment", cats)
    assert util and util["category_code"] == "UTIL"


@pytest.mark.asyncio
async def test_sales_analysis_rfm_affinity_peaks(client, db_session):
    ac, seed = client
    tid = seed["t1"].id
    customer = seed["party1"]
    product = seed["p1"]
    product_b = m.Product(
        tenant_id=tid,
        name="Alpha Gadget",
        sku="A-2",
        cost_price=1,
        selling_price=3,
        stock_qty=20,
    )
    db_session.add(product_b)
    await db_session.flush()

    for i, days_ago in enumerate((2, 5, 10)):
        inv = m.SalesInvoice(
            tenant_id=tid,
            invoice_number=f"INV-AI-S-{i}",
            customer_id=customer.id,
            status="posted",
            subtotal=10 + i,
            total_amount=10 + i,
            posted_at=datetime.utcnow() - timedelta(days=days_ago, hours=14),
        )
        db_session.add(inv)
        await db_session.flush()
        db_session.add_all(
            [
                m.SalesInvoiceItem(
                    tenant_id=tid,
                    sales_invoice_id=inv.id,
                    product_id=product.id,
                    quantity=1,
                    unit_price=5,
                    line_subtotal=5,
                    line_total=5,
                ),
                m.SalesInvoiceItem(
                    tenant_id=tid,
                    sales_invoice_id=inv.id,
                    product_id=product_b.id,
                    quantity=1,
                    unit_price=5,
                    line_subtotal=5,
                    line_total=5,
                ),
            ]
        )
    await db_session.commit()

    headers = await _mgr(ac)
    r = await ac.get("/api/v1/ai/sales/analysis", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["method"] == "rule_based"
    assert data["rfm"]["customer_count"] >= 1
    assert any(c["customer_id"] == customer.id for c in data["rfm"]["customers"])
    assert data["affinity"]
    assert data["peaks"]["hours"] or data["peaks"]["days"]
    assert "forecast_next_month" in data["trend"]
    assert "Beta" not in r.text


@pytest.mark.asyncio
async def test_expense_analysis_budget_and_unusual(client, db_session):
    ac, seed = client
    tid = seed["t1"].id
    await expenses_svc.ensure_default_categories(db_session, tid)
    cats = (
        await db_session.execute(
            select(m.ExpenseCategory).where(m.ExpenseCategory.tenant_id == tid)
        )
    ).scalars().all()
    trans = next(c for c in cats if c.code == "TRANS")
    trans.budget_amount = 50
    # Normal small expenses + one outlier
    for amt in (10, 12, 11, 200):
        db_session.add(
            m.Expense(
                tenant_id=tid,
                category_id=trans.id,
                category=trans.name,
                description="trip",
                amount=amt,
                expense_date=datetime.utcnow() - timedelta(days=1),
                status="approved",
                payee="Bolt",
                created_by=seed["mgr1"].id,
            )
        )
    await db_session.commit()

    headers = await _mgr(ac)
    r = await ac.get("/api/v1/ai/expenses/analysis", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["method"] == "rule_based"
    assert data["budget_variance_alerts"]
    assert any(a["category_id"] == trans.id for a in data["budget_variance_alerts"])
    assert data["unusual_expenses"]
    assert data["cost_optimization_suggestions"]
    assert data["ocr_categorization"]["mode"] == "keyword_suggest"


@pytest.mark.asyncio
async def test_analyses_are_tenant_scoped(client, db_session):
    ac, seed = client
    # Beta invoice should not appear in alpha RFM names
    inv = m.SalesInvoice(
        tenant_id=seed["t2"].id,
        invoice_number="INV-BETA-AI",
        customer_id=seed["party2"].id,
        status="posted",
        subtotal=999,
        total_amount=999,
        posted_at=datetime.utcnow(),
    )
    db_session.add(inv)
    await db_session.commit()
    headers = await _mgr(ac)
    r = await ac.get("/api/v1/ai/sales/analysis", headers=headers)
    assert r.status_code == 200
    assert "Beta Customer" not in r.text
    assert "INV-BETA-AI" not in r.text
