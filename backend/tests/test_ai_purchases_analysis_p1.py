"""Stage 25 P1: AI purchases analysis over live PO / GRN / PI actuals (BR-21.11)."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from app import models as m
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


async def _seed_purchase_patterns(db_session, seed):
    """Rising PI spend, dominant supplier, open/partial PO, overdue PI, GRN."""
    tenant_id = seed["t1"].id
    product = seed["p1"]
    primary = m.Party(
        tenant_id=tenant_id,
        name="P1 Primary Supplier",
        kind="supplier",
        credit_limit=0,
    )
    secondary = m.Party(
        tenant_id=tenant_id,
        name="P1 Secondary Supplier",
        kind="supplier",
        credit_limit=0,
    )
    db_session.add_all([primary, secondary])
    await db_session.flush()

    now = datetime.utcnow().replace(minute=0, second=0, microsecond=0)

    # Rising posted PI spend on primary supplier (days 0..13)
    for i in range(14):
        when = (now - timedelta(days=13 - i)).replace(hour=11)
        amt = float((i + 1) * 25)
        inv = m.PurchaseInvoice(
            tenant_id=tenant_id,
            invoice_number=f"PI-P1-T-{i}",
            supplier_id=primary.id,
            status="unpaid",
            invoice_date=when,
            due_date=when + timedelta(days=14),
            subtotal=amt,
            tax_amount=0,
            total_amount=amt,
            paid_amount=0,
            created_at=when,
        )
        db_session.add(inv)

    # Small secondary supplier invoice (concentration)
    sec_when = now - timedelta(days=2)
    db_session.add(
        m.PurchaseInvoice(
            tenant_id=tenant_id,
            invoice_number="PI-P1-SEC",
            supplier_id=secondary.id,
            status="paid",
            invoice_date=sec_when,
            due_date=sec_when + timedelta(days=7),
            subtotal=20,
            total_amount=20,
            paid_amount=20,
            created_at=sec_when,
        )
    )

    # Overdue bill
    overdue_when = now - timedelta(days=20)
    db_session.add(
        m.PurchaseInvoice(
            tenant_id=tenant_id,
            invoice_number="PI-P1-OVER",
            supplier_id=primary.id,
            status="overdue",
            invoice_date=overdue_when,
            due_date=now - timedelta(days=5),
            subtotal=80,
            total_amount=80,
            paid_amount=0,
            created_at=overdue_when,
        )
    )

    # Open sent PO + partially received PO with fill gap
    sent_po = m.PurchaseOrder(
        tenant_id=tenant_id,
        po_number="PO-P1-OPEN",
        supplier_id=primary.id,
        status="sent",
        subtotal=100,
        total_amount=100,
        created_at=now - timedelta(days=3),
    )
    partial_po = m.PurchaseOrder(
        tenant_id=tenant_id,
        po_number="PO-P1-PART",
        supplier_id=secondary.id,
        status="partially_received",
        subtotal=50,
        total_amount=50,
        created_at=now - timedelta(days=5),
    )
    draft_po = m.PurchaseOrder(
        tenant_id=tenant_id,
        po_number="PO-P1-DRAFT-1",
        supplier_id=primary.id,
        status="draft",
        subtotal=10,
        total_amount=10,
        created_at=now - timedelta(days=1),
    )
    draft_po2 = m.PurchaseOrder(
        tenant_id=tenant_id,
        po_number="PO-P1-DRAFT-2",
        supplier_id=primary.id,
        status="draft",
        subtotal=10,
        total_amount=10,
        created_at=now - timedelta(days=1),
    )
    draft_po3 = m.PurchaseOrder(
        tenant_id=tenant_id,
        po_number="PO-P1-DRAFT-3",
        supplier_id=secondary.id,
        status="draft",
        subtotal=10,
        total_amount=10,
        created_at=now - timedelta(days=1),
    )
    db_session.add_all([sent_po, partial_po, draft_po, draft_po2, draft_po3])
    await db_session.flush()

    sent_item = m.PurchaseOrderItem(
        tenant_id=tenant_id,
        purchase_order_id=sent_po.id,
        product_id=product.id,
        quantity=10,
        received_qty=0,
        unit_price=10,
        line_total=100,
    )
    part_item = m.PurchaseOrderItem(
        tenant_id=tenant_id,
        purchase_order_id=partial_po.id,
        product_id=product.id,
        quantity=10,
        received_qty=4,
        unit_price=5,
        line_total=50,
    )
    db_session.add_all([sent_item, part_item])
    await db_session.flush()

    grn = m.GoodsReceipt(
        tenant_id=tenant_id,
        grn_number="GRN-P1-1",
        purchase_order_id=partial_po.id,
        supplier_id=secondary.id,
        status="posted",
        created_at=now - timedelta(days=4),
    )
    db_session.add(grn)
    await db_session.flush()
    db_session.add(
        m.GoodsReceiptItem(
            tenant_id=tenant_id,
            goods_receipt_id=grn.id,
            po_item_id=part_item.id,
            product_id=product.id,
            received_qty=4,
            accepted_qty=4,
            rejected_qty=0,
        )
    )
    await db_session.commit()
    return {"primary": primary, "secondary": secondary, "partial_po": partial_po}


@pytest.mark.asyncio
async def test_purchases_analysis_api(client, db_session):
    ac, seed = client
    headers = await _mgr(ac)
    seeded = await _seed_purchase_patterns(db_session, seed)

    r = await ac.get(
        "/api/v1/ai/purchases/analysis",
        headers=headers,
        params={"lookback_days": 90},
    )
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert body["method"] == "rules_v1"
    assert body["summary"]["purchase_order_count"] >= 5
    assert body["summary"]["grn_count"] >= 1
    assert body["summary"]["purchase_invoice_count"] >= 15
    assert body["summary"]["total_spend"] > 0
    assert body["summary"]["trend_direction"] in ("up", "flat", "down")
    assert body["trend"]["direction"] == "up"
    assert body["trend"]["daily_slope"] > 0.5
    for horizon in ("7", "14", "30"):
        assert horizon in body["trend"]["forecast_totals"]
        assert body["trend"]["forecast_totals"][horizon] >= 0

    assert body["suppliers"]["count"] >= 2
    top = body["suppliers"]["rows"][0]
    assert top["supplier_id"] == seeded["primary"].id
    assert top["spend_share"] >= 0.6
    assert any(s["supplier_id"] == seeded["secondary"].id for s in body["suppliers"]["rows"])

    assert body["purchase_orders"]["draft_count"] >= 3
    assert body["purchase_orders"]["partial_count"] >= 1
    fill = {row["po_number"]: row for row in body["purchase_orders"]["fill"]}
    assert "PO-P1-PART" in fill
    assert fill["PO-P1-PART"]["fill_pct"] == 40.0
    assert fill["PO-P1-PART"]["ordered_qty"] == 10
    assert fill["PO-P1-PART"]["received_qty"] == 4

    assert body["goods_receipts"]["count"] >= 1
    assert body["purchase_invoices"]["overdue_count"] >= 1
    overdue_nums = {row["invoice_number"] for row in body["purchase_invoices"]["overdue"]}
    assert "PI-P1-OVER" in overdue_nums

    kinds = {s["kind"] for s in body["suggestions"]}
    assert "supplier_concentration" in kinds or body["summary"]["top_supplier_spend_share"] >= 0.6
    assert "overdue_bills" in kinds
    assert "draft_po_backlog" in kinds
    assert "partial_receive_backlog" in kinds


@pytest.mark.asyncio
async def test_purchases_analysis_tenant_isolation(client, db_session):
    ac, seed = client
    headers = await _mgr(ac)
    now = datetime.utcnow()
    db_session.add(
        m.PurchaseInvoice(
            tenant_id=seed["t2"].id,
            invoice_number="PI-P1-BETA",
            supplier_id=seed["supplier2"].id,
            status="unpaid",
            invoice_date=now,
            subtotal=9999,
            total_amount=9999,
            paid_amount=0,
            created_at=now,
        )
    )
    await db_session.commit()

    r = await ac.get(
        "/api/v1/ai/purchases/analysis",
        headers=headers,
        params={"lookback_days": 30},
    )
    assert r.status_code == 200, r.text
    blob = str(r.json()["data"])
    assert "Beta Supplier" not in blob
    assert "PI-P1-BETA" not in blob
    spends = {row.get("spend") for row in r.json()["data"]["suppliers"]["rows"]}
    assert 9999 not in spends


@pytest.mark.asyncio
async def test_purchases_analysis_requires_ai_permission(client):
    ac, _seed = client
    # Cashier typically lacks ai:read — expect 403
    headers = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    r = await ac.get("/api/v1/ai/purchases/analysis", headers=headers)
    assert r.status_code in (403, 401), r.text


def test_p1_plan_and_docs_cite_stage25():
    plan = (ROOT / "docs" / "STAGE_25_PLAN.md").read_text(encoding="utf-8")
    p1_line = [ln for ln in plan.splitlines() if "| **P1** |" in ln][0]
    assert "COMPLETE" in p1_line
    assert "test_ai_purchases_analysis_p1.py" in plan
    assert (
        "P1 complete" in plan
        or "X1 next" in plan
        or "X1 complete" in plan
        or "B1 next" in plan
        or "B1 complete" in plan
        or "U1 next" in plan
        or "U1 complete" in plan
        or "D1 next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    br = (ROOT / "docs" / "BUSINESS_REQUIREMENTS_DOCUMENT.md").read_text(encoding="utf-8")
    assert "#### BR-21.11 AI Purchases Analysis" in br
    s2111 = br.split("#### BR-21.11 AI Purchases Analysis")[1].split("---")[0]
    assert "[x]" in s2111
    assert "Stage 25 P1" in s2111
    assert "test_ai_purchases_analysis_p1.py" in s2111
    assert "/ai/purchases/analysis" in s2111

    api = (ROOT / "docs" / "API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "/ai/purchases/analysis" in api
    assert "Stage 25 P1" in api or "BR-21.11" in api

    launch = (ROOT / "docs" / "LAUNCH_CHECKLIST.md").read_text(encoding="utf-8")
    assert "test_ai_purchases_analysis_p1.py" in launch

    roadmap = (ROOT / "docs" / "DEVELOPMENT_ROADMAP.md").read_text(encoding="utf-8")
    assert "Stage 25 P1" in roadmap
    assert "test_ai_purchases_analysis_p1.py" in roadmap
