"""Stage 20 S1: AI sales analysis fidelity (BR-21.5)."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from app import models as m
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


async def _seed_sales_patterns(db_session, seed):
    """Rising daily totals, basket affinity, peak hour=10, two RFM customers."""
    tenant_id = seed["t1"].id
    p1 = seed["p1"]
    p2 = m.Product(
        tenant_id=tenant_id,
        name="S1 Bundle Mate",
        sku="S1-BUNDLE",
        cost_price=1,
        selling_price=5,
        stock_qty=50,
        is_active=True,
    )
    db_session.add(p2)
    champ = seed["party1"]
    at_risk = m.Party(
        tenant_id=tenant_id,
        name="S1 At Risk Customer",
        kind="customer",
        credit_limit=50,
    )
    db_session.add(at_risk)
    await db_session.flush()

    now = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
    # Rising trend: day-offset i has amount (i+1)*20 at hour 10 (peak) or 15
    for i in range(14):
        when = now - timedelta(days=13 - i)
        when = when.replace(hour=10 if i % 3 else 15)
        amt = float((i + 1) * 20)
        inv = m.SalesInvoice(
            tenant_id=tenant_id,
            invoice_number=f"INV-S1-T-{i}",
            customer_id=champ.id,
            status="posted",
            subtotal=amt,
            tax_amount=0,
            total_amount=amt,
            created_at=when,
            posted_at=when,
        )
        db_session.add(inv)
        await db_session.flush()
        # Affinity: both products on most invoices
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
                    product_id=p2.id,
                    quantity=2,
                    unit_price=(amt - 10) / 2 if amt > 10 else 5,
                    line_total=amt - 10,
                ),
            ]
        )

    # Older sparse purchases for at-risk RFM profile
    old = now - timedelta(days=45)
    for j in range(3):
        when = old - timedelta(days=j * 5)
        when = when.replace(hour=11)
        inv = m.SalesInvoice(
            tenant_id=tenant_id,
            invoice_number=f"INV-S1-R-{j}",
            customer_id=at_risk.id,
            status="posted",
            subtotal=15,
            tax_amount=0,
            total_amount=15,
            created_at=when,
            posted_at=when,
        )
        db_session.add(inv)
        await db_session.flush()
        db_session.add(
            m.SalesInvoiceItem(
                tenant_id=tenant_id,
                sales_invoice_id=inv.id,
                product_id=p1.id,
                quantity=1,
                unit_price=15,
                line_total=15,
            )
        )

    await db_session.commit()
    return {"p2": p2, "at_risk": at_risk, "champ": champ}


@pytest.mark.asyncio
async def test_sales_trend_rfm_affinity_peaks_api(client, db_session):
    """BR-21.5: trend forecast, RFM, affinity, peak hour/day via /ai/sales/analysis."""
    ac, seed = client
    headers = await _mgr(ac)
    seeded = await _seed_sales_patterns(db_session, seed)

    r = await ac.get(
        "/api/v1/ai/sales/analysis",
        headers=headers,
        params={"lookback_days": 90},
    )
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert body["method"] == "rules_v1"
    assert body["summary"]["invoice_count"] >= 14
    assert body["summary"]["total_sales"] > 0
    assert body["summary"]["trend_direction"] in ("up", "flat", "down")
    assert body["trend"]["direction"] == body["summary"]["trend_direction"]
    # Rising series should forecast upward
    assert body["trend"]["direction"] == "up"
    assert body["trend"]["daily_slope"] > 0.5
    for horizon in ("7", "14", "30"):
        assert horizon in body["trend"]["forecast_totals"]
        assert body["trend"]["forecast_totals"][horizon] > 0

    assert body["rfm"]["count"] >= 2
    segments = {c["customer_id"]: c["segment"] for c in body["rfm"]["customers"]}
    assert seeded["champ"].id in segments
    assert seeded["at_risk"].id in segments
    assert segments[seeded["champ"].id]
    assert body["rfm"]["segment_counts"]
    champ_row = next(c for c in body["rfm"]["customers"] if c["customer_id"] == seeded["champ"].id)
    assert champ_row["frequency"] >= 14
    assert champ_row["r_score"] >= 1
    assert champ_row["f_score"] >= 1
    assert champ_row["m_score"] >= 1

    pairs = body["product_affinity"]["pairs"]
    assert pairs
    assert body["product_affinity"]["baskets_with_2plus_lines"] >= 1
    pair_ids = {pairs[0]["product_a_id"], pairs[0]["product_b_id"]}
    assert seed["p1"].id in pair_ids
    assert seeded["p2"].id in pair_ids
    assert pairs[0]["co_occurrence_count"] >= 1
    assert pairs[0]["support"] > 0

    assert body["peaks"]["peak_hour"] == 10
    assert body["peaks"]["peak_weekday"] is not None
    assert body["peaks"]["peak_weekday_label"] in (
        "Mon",
        "Tue",
        "Wed",
        "Thu",
        "Fri",
        "Sat",
        "Sun",
    )
    assert any(h["hour"] == 10 and h["invoice_count"] > 0 for h in body["peaks"]["by_hour"])
    assert body["peaks"]["by_weekday"]


@pytest.mark.asyncio
async def test_sales_analysis_tenant_isolation(client, db_session):
    """BR-21.5: analysis stays on caller's tenant (no Beta leakage)."""
    ac, seed = client
    headers = await _mgr(ac)
    now = datetime.utcnow()
    db_session.add(
        m.SalesInvoice(
            tenant_id=seed["t2"].id,
            invoice_number="INV-S1-BETA",
            customer_id=seed["party2"].id,
            status="posted",
            subtotal=9999,
            total_amount=9999,
            created_at=now,
            posted_at=now,
        )
    )
    await db_session.commit()

    r = await ac.get("/api/v1/ai/sales/analysis", headers=headers, params={"lookback_days": 30})
    assert r.status_code == 200, r.text
    blob = str(r.json()["data"])
    assert "Beta Customer" not in blob
    assert "INV-S1-BETA" not in blob
    assert 9999 not in {
        c.get("monetary") for c in r.json()["data"]["rfm"]["customers"]
    }


def test_br_21_5_and_plan_synced():
    br = (ROOT / "docs" / "BUSINESS_REQUIREMENTS_DOCUMENT.md").read_text(encoding="utf-8")
    s215 = br.split("#### BR-21.5 AI Sales Analysis")[1].split("#### BR-21.6")[0]
    assert "[x] Sales trend forecasting" in s215
    assert "[x] Customer segmentation (RFM analysis)" in s215
    assert "[x] Product affinity analysis (frequently bought together)" in s215
    assert "[x] Peak hour/day predictions" in s215
    assert "Stage 20 S1" in s215
    assert "test_ai_sales_analysis_s1.py" in s215

    plan = (ROOT / "docs" / "STAGE_20_PLAN.md").read_text(encoding="utf-8")
    s1_line = [ln for ln in plan.splitlines() if "| **S1**" in ln][0]
    assert "COMPLETE" in s1_line
    assert "test_ai_sales_analysis_s1.py" in plan
