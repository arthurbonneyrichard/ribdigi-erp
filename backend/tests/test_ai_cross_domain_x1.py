"""Stage 25 X1: cross-domain AI analysis (Inv + Sales + Purch + Exp)."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from app import models as m
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


async def _seed_cross_domain(db_session, seed):
    """Sales rising, purchases lagging, expenses heavy, overdue PI, low stock."""
    tenant_id = seed["t1"].id
    product = seed["p1"]
    product.stock_qty = 2
    product.reorder_level = 20
    product.reorder_qty = 30
    customer = seed["party1"]
    supplier = m.Party(
        tenant_id=tenant_id,
        name="X1 Supplier",
        kind="supplier",
        credit_limit=0,
    )
    db_session.add(supplier)
    await db_session.flush()

    now = datetime.utcnow().replace(minute=0, second=0, microsecond=0)

    # Rising sales (posted invoices)
    for i in range(14):
        when = (now - timedelta(days=13 - i)).replace(hour=10)
        amt = float((i + 1) * 40)
        inv = m.SalesInvoice(
            tenant_id=tenant_id,
            invoice_number=f"INV-X1-{i}",
            customer_id=customer.id,
            status="posted",
            subtotal=amt,
            tax_amount=0,
            total_amount=amt,
            created_at=when,
            posted_at=when,
        )
        db_session.add(inv)
        await db_session.flush()
        db_session.add(
            m.SalesInvoiceItem(
                tenant_id=tenant_id,
                sales_invoice_id=inv.id,
                product_id=product.id,
                quantity=2,
                unit_price=amt / 2,
                line_total=amt,
            )
        )

    # Flat/low purchase spend vs sales + overdue bill
    for i in range(3):
        when = now - timedelta(days=20 + i)
        db_session.add(
            m.PurchaseInvoice(
                tenant_id=tenant_id,
                invoice_number=f"PI-X1-{i}",
                supplier_id=supplier.id,
                status="unpaid" if i else "overdue",
                invoice_date=when,
                due_date=now - timedelta(days=3),
                subtotal=50,
                total_amount=50,
                paid_amount=0,
                created_at=when,
            )
        )

    # No open POs (stockout_without_open_po) — only a draft
    db_session.add(
        m.PurchaseOrder(
            tenant_id=tenant_id,
            po_number="PO-X1-DRAFT",
            supplier_id=supplier.id,
            status="draft",
            subtotal=10,
            total_amount=10,
            created_at=now - timedelta(days=1),
        )
    )

    # Heavy approved expenses this week
    for i in range(4):
        db_session.add(
            m.Expense(
                tenant_id=tenant_id,
                category="Utilities",
                description=f"X1 exp {i}",
                amount=400,
                status="approved",
                expense_date=now - timedelta(days=i),
                payment_method="bank_transfer",
            )
        )
    # Quiet prior week expenses
    db_session.add(
        m.Expense(
            tenant_id=tenant_id,
            category="Utilities",
            description="X1 prior",
            amount=50,
            status="approved",
            expense_date=now - timedelta(days=10),
            payment_method="bank_transfer",
        )
    )

    await db_session.commit()
    return {"supplier": supplier, "product": product}


@pytest.mark.asyncio
async def test_cross_domain_analysis_api(client, db_session):
    ac, seed = client
    headers = await _mgr(ac)
    await _seed_cross_domain(db_session, seed)

    r = await ac.get(
        "/api/v1/ai/cross-domain/analysis",
        headers=headers,
        params={"lookback_days": 90},
    )
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert body["method"] == "rules_v1"
    assert body["summary"]["domains_analyzed"] == [
        "inventory",
        "sales",
        "purchases",
        "expenses",
    ]
    assert body["summary"]["domains_with_activity"] >= 3
    assert body["summary"]["total_sales"] > 0
    assert body["summary"]["total_approved_expenses"] > 0

    for key in ("inventory", "sales", "purchases", "expenses"):
        assert key in body["domains"]
        assert body["domains"][key]["summary"]
        assert body["domains"][key]["endpoint"].startswith("GET /ai/")

    assert body["domains"]["sales"]["summary"]["trend_direction"] == "up"
    assert body["domains"]["purchases"]["summary"]["overdue_invoice_count"] >= 1
    assert body["domains"]["expenses"]["summary"]["total_approved"] > 0

    kinds = {s["kind"] for s in body["cross_signals"]}
    assert kinds, "expected at least one synthesis signal"
    # Seed targets several of these
    assert kinds & {
        "sales_up_purchases_lag",
        "stockout_without_open_po",
        "stockout_with_open_po",
        "expenses_heavy_vs_sales",
        "purchase_spend_vs_sales",
        "cash_pressure",
        "supplier_concentration_with_growth",
        "dead_stock_with_soft_sales",
    }
    for sig in body["cross_signals"]:
        assert sig["domains"]
        assert sig["severity"] in ("high", "medium", "low")
        assert "Prophet" not in (sig.get("summary") or "")
    assert "Prophet" in body["note"] or "LLM" in body["note"]


@pytest.mark.asyncio
async def test_cross_domain_tenant_isolation(client, db_session):
    ac, seed = client
    headers = await _mgr(ac)
    now = datetime.utcnow()
    db_session.add(
        m.SalesInvoice(
            tenant_id=seed["t2"].id,
            invoice_number="INV-X1-BETA",
            customer_id=seed["party2"].id,
            status="posted",
            subtotal=8888,
            total_amount=8888,
            created_at=now,
            posted_at=now,
        )
    )
    await db_session.commit()

    r = await ac.get(
        "/api/v1/ai/cross-domain/analysis",
        headers=headers,
        params={"lookback_days": 30},
    )
    assert r.status_code == 200, r.text
    blob = str(r.json()["data"])
    assert "INV-X1-BETA" not in blob
    assert "8888" not in blob


@pytest.mark.asyncio
async def test_cross_domain_requires_ai_permission(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    r = await ac.get("/api/v1/ai/cross-domain/analysis", headers=headers)
    assert r.status_code in (403, 401), r.text


def test_x1_plan_and_docs_cite_stage25():
    plan = (ROOT / "docs" / "STAGE_25_PLAN.md").read_text(encoding="utf-8")
    x1_line = [ln for ln in plan.splitlines() if "| **X1** |" in ln][0]
    assert "COMPLETE" in x1_line
    assert "test_ai_cross_domain_x1.py" in plan
    assert (
        "P1 complete" in plan
        or "X1 complete" in plan
        or "B1 next" in plan
        or "B1 complete" in plan
        or "U1 next" in plan
        or "U1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H25x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
        or "ADR-056" in plan
    )

    br = (ROOT / "docs" / "BUSINESS_REQUIREMENTS_DOCUMENT.md").read_text(encoding="utf-8")
    assert "#### BR-21.12 Cross-Domain AI Analysis" in br
    s2112 = br.split("#### BR-21.12 Cross-Domain AI Analysis")[1].split("---")[0]
    assert "[x]" in s2112
    assert "Stage 25 X1" in s2112
    assert "test_ai_cross_domain_x1.py" in s2112
    assert "/ai/cross-domain/analysis" in s2112

    api = (ROOT / "docs" / "API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "/ai/cross-domain/analysis" in api
    assert "Stage 25 X1" in api or "BR-21.12" in api

    launch = (ROOT / "docs" / "LAUNCH_CHECKLIST.md").read_text(encoding="utf-8")
    assert "test_ai_cross_domain_x1.py" in launch

    roadmap = (ROOT / "docs" / "DEVELOPMENT_ROADMAP.md").read_text(encoding="utf-8")
    assert "Stage 25 X1" in roadmap
    assert "test_ai_cross_domain_x1.py" in roadmap
