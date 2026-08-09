"""Phase 4 / BR-21.2 AI dashboard insights."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app import ai_insights as ai_insights_svc
from app import emailer
from app import models as m
from app.notifications import DEFAULT_PREFERENCES
from tests.conftest import auth_headers


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


def test_ai_insight_pref_defaults():
    assert DEFAULT_PREFERENCES["ai_insight"]["dashboard"] is True
    assert DEFAULT_PREFERENCES["ai_insight"]["email"] is True


@pytest.mark.asyncio
async def test_sales_spike_and_expense_anomaly_insights(db_session, seeded):
    tenant_id = seeded["t1"].id
    now = datetime.utcnow()

    # Strong this-week sales vs quiet prior week
    for i in range(3):
        db_session.add(
            m.SalesInvoice(
                tenant_id=tenant_id,
                invoice_number=f"INV-W-{i}",
                customer_id=seeded["party1"].id,
                status="posted",
                total_amount=500,
                subtotal=500,
                created_at=now - timedelta(days=i),
                posted_at=now - timedelta(days=i),
            )
        )
    db_session.add(
        m.SalesInvoice(
            tenant_id=tenant_id,
            invoice_number="INV-PW-1",
            customer_id=seeded["party1"].id,
            status="posted",
            total_amount=100,
            subtotal=100,
            created_at=now - timedelta(days=10),
            posted_at=now - timedelta(days=10),
        )
    )

    # Expense spike this week
    db_session.add(
        m.Expense(
            tenant_id=tenant_id,
            category="Utilities",
            description="Spike",
            amount=800,
            status="approved",
            expense_date=now - timedelta(days=1),
            payment_method="bank_transfer",
        )
    )
    db_session.add(
        m.Expense(
            tenant_id=tenant_id,
            category="Utilities",
            description="Prior",
            amount=100,
            status="approved",
            expense_date=now - timedelta(days=10),
            payment_method="bank_transfer",
        )
    )
    await db_session.commit()

    data = await ai_insights_svc.generate_insights(db_session, tenant_id)
    kinds = {c["kind"] for c in data["insights"]}
    assert "sales_wow" in kinds
    assert "expense_spike" in kinds or "expense_vs_sales" in kinds
    assert data["summaries"]
    wow = next(c for c in data["insights"] if c["kind"] == "sales_wow")
    assert wow["metrics"]["change_pct"] >= 25
    assert wow.get("action")


@pytest.mark.asyncio
async def test_restock_suggestion_insight(db_session, seeded):
    tenant_id = seeded["t1"].id
    product = seeded["p1"]
    product.stock_qty = 20
    await db_session.flush()
    for day in range(20):
        inv = m.SalesInvoice(
            tenant_id=tenant_id,
            invoice_number=f"INV-RS-{day}",
            customer_id=seeded["party1"].id,
            status="posted",
            total_amount=10,
            subtotal=10,
            created_at=datetime.utcnow() - timedelta(days=day),
            posted_at=datetime.utcnow() - timedelta(days=day),
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

    data = await ai_insights_svc.generate_insights(db_session, tenant_id)
    restock = [c for c in data["insights"] if c["kind"] == "restock_suggestion"]
    assert restock
    assert any(product.id == c.get("entity_id") for c in restock)
    assert "Restock" in restock[0]["title"] or "restock" in restock[0]["summary"].lower()


@pytest.mark.asyncio
async def test_insights_api_returns_cards(client, db_session):
    ac, seed = client
    headers = await _mgr(ac)
    seed["p1"].stock_qty = 0
    seed["p1"].reorder_level = 5
    await db_session.commit()

    r = await ac.get("/api/v1/ai/insights", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert "cards" in body
    assert isinstance(body["insights"], list)
    assert body["method"] == "rules_v1"
    assert any(c["kind"] == "low_stock" for c in body["cards"])
    assert "Beta" not in " ".join(body["insights"])


@pytest.mark.asyncio
async def test_publish_weekly_digest(db_session, seeded, monkeypatch):
    emailer.clear_dev_outbox()
    monkeypatch.setattr("app.emailer.settings.EMAIL_ENABLED", True)
    monkeypatch.setattr("app.emailer.settings.SMTP_HOST", "")
    monkeypatch.setattr("app.emailer.settings.SMTP_FROM_EMAIL", "noreply@localhost")

    tenant_id = seeded["t1"].id
    seeded["p1"].stock_qty = 0
    seeded["p1"].reorder_level = 3
    await db_session.commit()

    first = await ai_insights_svc.publish_insights(db_session, tenant_id)
    await db_session.commit()
    assert first["insight_count"] >= 1
    assert first["weekly_digest_sent"] is True

    second = await ai_insights_svc.publish_insights(db_session, tenant_id)
    assert second["weekly_digest_sent"] is False

    digests = (
        await db_session.execute(
            select(m.Notification).where(
                m.Notification.tenant_id == tenant_id,
                m.Notification.title == "Weekly AI Insight Digest",
            )
        )
    ).scalars().all()
    assert len(digests) == 1
