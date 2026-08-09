"""Phase 4 / BR-21.5 + BR-21.6 sales and expense AI analysis."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app import ai_expenses as ai_expenses_svc
from app import ai_sales as ai_sales_svc
from app import expenses as expenses_svc
from app import models as m
from tests.conftest import auth_headers


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


@pytest.mark.asyncio
async def test_sales_analysis_rfm_affinity_peaks(db_session, seeded):
    tenant_id = seeded["t1"].id
    p1 = seeded["p1"]
    p_extra = m.Product(
        tenant_id=tenant_id,
        name="Alpha Gadget",
        sku="A-2",
        cost_price=1,
        selling_price=3,
        stock_qty=20,
    )
    db_session.add(p_extra)
    await db_session.flush()

    now = datetime.utcnow()
    for i, hour in enumerate((10, 10, 15)):
        inv = m.SalesInvoice(
            tenant_id=tenant_id,
            invoice_number=f"INV-SA-{i}",
            customer_id=seeded["party1"].id,
            status="posted",
            subtotal=30,
            total_amount=30,
            created_at=now.replace(hour=hour, minute=0, second=0) - timedelta(days=i),
            posted_at=now.replace(hour=hour, minute=0, second=0) - timedelta(days=i),
        )
        db_session.add(inv)
        await db_session.flush()
        db_session.add_all(
            [
                m.SalesInvoiceItem(
                    tenant_id=tenant_id,
                    sales_invoice_id=inv.id,
                    product_id=p1.id,
                    quantity=2,
                    unit_price=5,
                    line_total=10,
                ),
                m.SalesInvoiceItem(
                    tenant_id=tenant_id,
                    sales_invoice_id=inv.id,
                    product_id=p_extra.id,
                    quantity=4,
                    unit_price=5,
                    line_total=20,
                ),
            ]
        )
    await db_session.commit()

    data = await ai_sales_svc.analyze_sales(db_session, tenant_id, lookback_days=60)
    assert data["method"] == "rules_v1"
    assert data["summary"]["invoice_count"] >= 3
    assert data["summary"]["total_sales"] >= 90
    assert "7" in data["trend"]["forecast_totals"]
    assert data["rfm"]["count"] >= 1
    assert data["rfm"]["customers"][0]["segment"]
    assert data["product_affinity"]["pairs"]
    pair = data["product_affinity"]["pairs"][0]
    assert {pair["product_a_id"], pair["product_b_id"]} == {p1.id, p_extra.id}
    assert data["peaks"]["peak_hour"] == 10


@pytest.mark.asyncio
async def test_expense_analysis_budget_and_anomaly(db_session, seeded):
    tenant_id = seeded["t1"].id
    await expenses_svc.ensure_default_categories(db_session, tenant_id)
    cats = (
        await db_session.execute(
            select(m.ExpenseCategory).where(m.ExpenseCategory.tenant_id == tenant_id)
        )
    ).scalars().all()
    util = next(c for c in cats if c.name == "Utilities")
    util.budget_amount = 100
    await db_session.flush()

    now = datetime.utcnow()
    for amt, day in ((20, 5), (25, 4), (30, 3), (400, 1)):
        db_session.add(
            m.Expense(
                tenant_id=tenant_id,
                category_id=util.id,
                category=util.name,
                description=f"Electric bill {amt}",
                amount=amt,
                status="approved",
                expense_date=now - timedelta(days=day),
                payment_method="bank_transfer",
            )
        )
    await db_session.commit()

    data = await ai_expenses_svc.analyze_expenses(db_session, tenant_id)
    assert data["method"] == "rules_v1"
    assert data["budget_variance"]["over_budget_count"] >= 1
    assert any(a["amount"] == 400 for a in data["anomalies"])
    assert data["optimization_suggestions"]
    assert any(s["kind"] == "over_budget" for s in data["optimization_suggestions"])

    sug = ai_expenses_svc.suggest_category_from_text(
        "Receipt — Electricity Company fuel not", cats
    )
    assert sug is not None
    assert sug["name"] == "Utilities"


@pytest.mark.asyncio
async def test_sales_and_expense_analysis_api_tenant_scoped(client, db_session):
    ac, seed = client
    headers = await _mgr(ac)
    now = datetime.utcnow()
    inv = m.SalesInvoice(
        tenant_id=seed["t1"].id,
        invoice_number="INV-API-SA-1",
        customer_id=seed["party1"].id,
        status="posted",
        subtotal=50,
        total_amount=50,
        created_at=now,
        posted_at=now,
    )
    db_session.add(inv)
    db_session.add(
        m.Expense(
            tenant_id=seed["t2"].id,
            category="Utilities",
            description="Beta secret expense",
            amount=999,
            status="approved",
            expense_date=now,
            payment_method="cash",
        )
    )
    await db_session.commit()

    sales = await ac.get("/api/v1/ai/sales/analysis", headers=headers)
    assert sales.status_code == 200, sales.text
    sdata = sales.json()["data"]
    assert sdata["summary"]["invoice_count"] >= 1
    assert all("Beta" not in (c.get("customer_name") or "") for c in sdata["rfm"]["customers"])

    ex = await ac.get("/api/v1/ai/expenses/analysis", headers=headers)
    assert ex.status_code == 200, ex.text
    edata = ex.json()["data"]
    blob = str(edata)
    assert "Beta secret" not in blob
    assert edata["summary"]["total_approved"] != 999
