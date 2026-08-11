"""Stage 25 B1: Business Insights surface cites all four actuals (BR-21.2)."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from app import models as m
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


async def _seed_four_actuals(db_session, seed):
    tenant_id = seed["t1"].id
    product = seed["p1"]
    product.stock_qty = 1
    product.reorder_level = 10
    customer = seed["party1"]
    supplier = m.Party(tenant_id=tenant_id, name="B1 Supplier", kind="supplier")
    db_session.add(supplier)
    await db_session.flush()

    now = datetime.utcnow().replace(minute=0, second=0, microsecond=0)

    # Sales spike this week vs prior
    for i in range(3):
        when = now - timedelta(days=i)
        db_session.add(
            m.SalesInvoice(
                tenant_id=tenant_id,
                invoice_number=f"INV-B1-W-{i}",
                customer_id=customer.id,
                status="posted",
                subtotal=400,
                total_amount=400,
                created_at=when,
                posted_at=when,
            )
        )
    db_session.add(
        m.SalesInvoice(
            tenant_id=tenant_id,
            invoice_number="INV-B1-PW",
            customer_id=customer.id,
            status="posted",
            subtotal=80,
            total_amount=80,
            created_at=now - timedelta(days=10),
            posted_at=now - timedelta(days=10),
        )
    )

    # Purchase spend spike + overdue
    for i in range(2):
        when = now - timedelta(days=i)
        db_session.add(
            m.PurchaseInvoice(
                tenant_id=tenant_id,
                invoice_number=f"PI-B1-W-{i}",
                supplier_id=supplier.id,
                status="unpaid",
                invoice_date=when,
                due_date=when + timedelta(days=14),
                subtotal=300,
                total_amount=300,
                paid_amount=0,
                created_at=when,
            )
        )
    db_session.add(
        m.PurchaseInvoice(
            tenant_id=tenant_id,
            invoice_number="PI-B1-PW",
            supplier_id=supplier.id,
            status="paid",
            invoice_date=now - timedelta(days=10),
            due_date=now - timedelta(days=3),
            subtotal=40,
            total_amount=40,
            paid_amount=40,
            created_at=now - timedelta(days=10),
        )
    )
    db_session.add(
        m.PurchaseInvoice(
            tenant_id=tenant_id,
            invoice_number="PI-B1-OVER",
            supplier_id=supplier.id,
            status="overdue",
            invoice_date=now - timedelta(days=20),
            due_date=now - timedelta(days=5),
            subtotal=90,
            total_amount=90,
            paid_amount=0,
            created_at=now - timedelta(days=20),
        )
    )

    # Draft PO backlog (no committed open PO)
    for i in range(3):
        db_session.add(
            m.PurchaseOrder(
                tenant_id=tenant_id,
                po_number=f"PO-B1-D-{i}",
                supplier_id=supplier.id,
                status="draft",
                subtotal=10,
                total_amount=10,
                created_at=now - timedelta(days=1),
            )
        )

    # Expense spike
    db_session.add(
        m.Expense(
            tenant_id=tenant_id,
            category="Utilities",
            description="B1 spike",
            amount=700,
            status="approved",
            expense_date=now - timedelta(days=1),
            payment_method="bank_transfer",
        )
    )
    db_session.add(
        m.Expense(
            tenant_id=tenant_id,
            category="Utilities",
            description="B1 prior",
            amount=100,
            status="approved",
            expense_date=now - timedelta(days=10),
            payment_method="bank_transfer",
        )
    )
    await db_session.commit()


@pytest.mark.asyncio
async def test_business_insights_four_actuals(client, db_session):
    ac, seed = client
    headers = await _mgr(ac)
    await _seed_four_actuals(db_session, seed)

    r = await ac.get("/api/v1/ai/insights", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert body["method"] == "rules_v1"
    assert body["actuals"] == ["inventory", "sales", "purchases", "expenses"]
    cards = body["cards"]
    assert cards
    for c in cards:
        assert "domains" in c
        assert isinstance(c["domains"], list)

    kinds = {c["kind"] for c in cards}
    assert "sales_wow" in kinds
    assert "expense_spike" in kinds or "expense_vs_sales" in kinds
    assert "purchase_spend_wow" in kinds or "purchase_overdue_bills" in kinds
    assert "purchase_overdue_bills" in kinds
    assert "low_stock" in kinds or "stockout_without_open_po" in kinds
    assert "purchase_draft_po_backlog" in kinds

    covered = set(body["actuals_covered"])
    assert "sales" in covered
    assert "purchases" in covered
    assert "expenses" in covered
    assert "inventory" in covered

    purch = next(c for c in cards if "purchase" in c["kind"] or "purchases" in c["domains"])
    assert "purchases" in purch["domains"]
    assert "LLM" in (body.get("note") or "") or "rule" in (body.get("note") or "").lower()


@pytest.mark.asyncio
async def test_business_insights_tenant_isolation(client, db_session):
    ac, seed = client
    headers = await _mgr(ac)
    now = datetime.utcnow()
    db_session.add(
        m.PurchaseInvoice(
            tenant_id=seed["t2"].id,
            invoice_number="PI-B1-BETA",
            supplier_id=seed["supplier2"].id,
            status="overdue",
            invoice_date=now,
            due_date=now - timedelta(days=1),
            subtotal=7777,
            total_amount=7777,
            paid_amount=0,
        )
    )
    await db_session.commit()

    r = await ac.get("/api/v1/ai/insights", headers=headers)
    assert r.status_code == 200, r.text
    blob = str(r.json()["data"])
    assert "PI-B1-BETA" not in blob
    assert "7777" not in blob


def test_b1_plan_and_docs_cite_stage25():
    plan = (ROOT / "docs" / "STAGE_25_PLAN.md").read_text(encoding="utf-8")
    b1_line = [ln for ln in plan.splitlines() if "| **B1** |" in ln][0]
    assert "COMPLETE" in b1_line
    assert "test_ai_business_insights_b1.py" in plan
    assert (
        "B1 next" in plan
        or "B1 complete" in plan
        or "U1 next" in plan
        or "U1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H25x next" in plan
    )

    br = (ROOT / "docs" / "BUSINESS_REQUIREMENTS_DOCUMENT.md").read_text(encoding="utf-8")
    s212 = br.split("#### BR-21.2 AI Dashboard Insight")[1].split("#### BR-21.3")[0]
    assert "Stage 25 B1" in s212
    assert "test_ai_business_insights_b1.py" in s212
    assert "purchases" in s212.lower()

    api = (ROOT / "docs" / "API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "actuals_covered" in api or "Stage 25 B1" in api
    assert "/ai/insights" in api

    launch = (ROOT / "docs" / "LAUNCH_CHECKLIST.md").read_text(encoding="utf-8")
    assert "test_ai_business_insights_b1.py" in launch

    roadmap = (ROOT / "docs" / "DEVELOPMENT_ROADMAP.md").read_text(encoding="utf-8")
    assert "Stage 25 B1" in roadmap
    assert "test_ai_business_insights_b1.py" in roadmap
