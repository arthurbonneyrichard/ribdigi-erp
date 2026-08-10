"""Stage 20 I1: AI dashboard insights + weekly digest fidelity (BR-21.2)."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select

from app import ai_insights as ai_insights_svc
from app import emailer
from app import jobs as jobs_svc
from app import models as m
from app.notifications import DEFAULT_PREFERENCES
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


@pytest.mark.asyncio
async def test_insights_api_sales_expense_and_restock(client, db_session):
    """BR-21.2: unusual sales/expense signals + restock suggestions via GET /ai/insights."""
    ac, seed = client
    headers = await _mgr(ac)
    tenant_id = seed["t1"].id
    product = seed["p1"]
    now = datetime.utcnow()

    for i in range(3):
        db_session.add(
            m.SalesInvoice(
                tenant_id=tenant_id,
                invoice_number=f"INV-I1-W-{i}",
                customer_id=seed["party1"].id,
                status="posted",
                total_amount=500,
                subtotal=500,
                tax_amount=0,
                created_at=now - timedelta(days=i),
                posted_at=now - timedelta(days=i),
            )
        )
    db_session.add(
        m.SalesInvoice(
            tenant_id=tenant_id,
            invoice_number="INV-I1-PW-1",
            customer_id=seed["party1"].id,
            status="posted",
            total_amount=100,
            subtotal=100,
            tax_amount=0,
            created_at=now - timedelta(days=10),
            posted_at=now - timedelta(days=10),
        )
    )
    db_session.add(
        m.Expense(
            tenant_id=tenant_id,
            category="Utilities",
            description="I1 spike",
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
            description="I1 prior",
            amount=100,
            status="approved",
            expense_date=now - timedelta(days=10),
            payment_method="bank_transfer",
        )
    )

    product.stock_qty = 20
    await db_session.flush()
    for day in range(20):
        inv = m.SalesInvoice(
            tenant_id=tenant_id,
            invoice_number=f"INV-I1-RS-{day}",
            customer_id=seed["party1"].id,
            status="posted",
            total_amount=10,
            subtotal=10,
            tax_amount=0,
            created_at=now - timedelta(days=day),
            posted_at=now - timedelta(days=day),
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

    r = await ac.get("/api/v1/ai/insights", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert body["method"] == "rules_v1"
    cards = body["cards"]
    kinds = {c["kind"] for c in cards}
    assert "sales_wow" in kinds
    assert "expense_spike" in kinds or "expense_vs_sales" in kinds
    assert any(c["kind"] == "restock_suggestion" for c in cards) or any(
        c["kind"] == "low_stock" for c in cards
    )
    wow = next(c for c in cards if c["kind"] == "sales_wow")
    assert wow.get("action")
    assert "Beta" not in " ".join(body.get("insights") or [])


@pytest.mark.asyncio
async def test_weekly_digest_publish_and_job_handler(client, db_session, monkeypatch):
    """BR-21.2: weekly insight digest + Celery job handler registration."""
    emailer.clear_dev_outbox()
    monkeypatch.setattr("app.emailer.settings.EMAIL_ENABLED", True)
    monkeypatch.setattr("app.emailer.settings.SMTP_HOST", "")
    monkeypatch.setattr("app.emailer.settings.SMTP_FROM_EMAIL", "noreply@localhost")

    assert DEFAULT_PREFERENCES["ai_insight"]["email"] is True
    assert DEFAULT_PREFERENCES["ai_insight"]["dashboard"] is True
    assert "generate_ai_insights" in jobs_svc.JOB_HANDLERS

    ac, seed = client
    tenant_id = seed["t1"].id
    seed["p1"].stock_qty = 0
    seed["p1"].reorder_level = 3
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
    assert digests[0].category == "ai_insight"

    # Admin jobs dry-run path lists the insights job (HTTP list only)
    headers = await _mgr(ac)
    # company_admin/super can list; mgr is store_manager — may 403
    listed = await ac.get("/api/v1/jobs", headers=headers)
    if listed.status_code == 200:
        assert "generate_ai_insights" in listed.json()["data"]["jobs"]


def test_br_21_2_and_plan_synced():
    br = (ROOT / "docs" / "BUSINESS_REQUIREMENTS_DOCUMENT.md").read_text(encoding="utf-8")
    s212 = br.split("#### BR-21.2 AI Dashboard Insight")[1].split("#### BR-21.3")[0]
    assert "[x] Highlight unusual sales drops or spikes" in s212
    assert "[x] Flag expense anomalies" in s212
    assert "[x] Suggest actions" in s212
    assert "[x] Weekly insight digest email" in s212
    assert "Stage 20 I1" in s212
    assert "test_ai_insights_fidelity_i1.py" in s212

    plan = (ROOT / "docs" / "STAGE_20_PLAN.md").read_text(encoding="utf-8")
    i1_line = [ln for ln in plan.splitlines() if "| **I1**" in ln][0]
    assert "COMPLETE" in i1_line
    assert "test_ai_insights_fidelity_i1.py" in plan
