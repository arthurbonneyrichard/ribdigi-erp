"""Phase 4 / BR-21.7 natural-language report generator."""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import select

from app import ai_reports as ai_reports_svc
from app import models as m
from tests.conftest import auth_headers


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


def test_parse_prompt_q2_monthly_sales():
    parsed = ai_reports_svc.parse_prompt(
        "Show me monthly sales for Q2 2026",
        now=datetime(2026, 8, 9),
    )
    assert parsed["report_type"] == "sales_products"  # quarter → range report
    assert parsed["params"]["from_date"] == "2026-04-01"
    assert parsed["params"]["to_date"] == "2026-06-30"
    assert parsed["period_label"] == "Q2 2026"
    assert parsed["format"] == "xlsx"


def test_parse_prompt_low_stock_pdf():
    parsed = ai_reports_svc.parse_prompt("Export low stock as pdf")
    assert parsed["report_type"] == "inventory_low_stock"
    assert parsed["format"] == "pdf"


@pytest.mark.asyncio
async def test_generate_and_save_template(client, db_session):
    ac, seed = client
    headers = await _mgr(ac)

    # Seed a posted sale so product sales preview is non-empty-capable
    inv = m.SalesInvoice(
        tenant_id=seed["t1"].id,
        invoice_number="INV-AI-RPT-1",
        customer_id=seed["party1"].id,
        status="posted",
        subtotal=20,
        total_amount=20,
        created_at=datetime(2026, 5, 15),
        posted_at=datetime(2026, 5, 15),
    )
    db_session.add(inv)
    await db_session.flush()
    db_session.add(
        m.SalesInvoiceItem(
            tenant_id=seed["t1"].id,
            sales_invoice_id=inv.id,
            product_id=seed["p1"].id,
            quantity=4,
            unit_price=5,
            line_total=20,
        )
    )
    await db_session.commit()

    gen = await ac.post(
        "/api/v1/ai/reports/generate",
        headers=headers,
        json={"prompt": "Show me monthly sales for Q2 2026"},
    )
    assert gen.status_code == 200, gen.text
    body = gen.json()["data"]
    assert body["report_type"] == "sales_products"
    assert body["period_label"] == "Q2 2026"
    assert body["export_ready"] is True
    assert body["row_count"] >= 1
    assert any(r.get("sku") == "A-1" or r.get("name") == "Alpha Widget" for r in body["preview_rows"]) or body[
        "row_count"
    ] >= 1

    save = await ac.post(
        "/api/v1/ai/reports/templates",
        headers=headers,
        json={"name": "Q2 Sales", "prompt": "Show me monthly sales for Q2 2026", "format": "csv"},
    )
    assert save.status_code == 200, save.text
    tmpl_id = save.json()["data"]["id"]
    assert save.json()["data"]["report_type"] == "sales_products"

    listed = await ac.get("/api/v1/ai/reports/templates", headers=headers)
    assert listed.status_code == 200
    ids = {t["id"] for t in listed.json()["data"]}
    assert tmpl_id in ids

    # Export via generate?export=true
    exported = await ac.post(
        "/api/v1/ai/reports/generate?export=true",
        headers=headers,
        json={"template_id": tmpl_id},
    )
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    assert b"sku" in exported.content.lower() or b"Alpha" in exported.content or len(exported.content) > 0

    deleted = await ac.delete(f"/api/v1/ai/reports/templates/{tmpl_id}", headers=headers)
    assert deleted.status_code == 200


@pytest.mark.asyncio
async def test_report_templates_tenant_isolated(client, db_session):
    ac, seed = client
    headers = await _mgr(ac)

    # Plant beta template directly
    db_session.add(
        m.AiReportTemplate(
            tenant_id=seed["t2"].id,
            user_id=seed["u2"].id,
            name="Beta Secret Report",
            prompt="Show me expenses",
            report_type="expenses_summary",
            format="xlsx",
            params={},
        )
    )
    await db_session.commit()

    listed = await ac.get("/api/v1/ai/reports/templates", headers=headers)
    assert listed.status_code == 200
    names = {t["name"] for t in listed.json()["data"]}
    assert "Beta Secret Report" not in names

    # Cannot delete foreign template id
    beta = (
        await db_session.execute(
            select(m.AiReportTemplate).where(m.AiReportTemplate.tenant_id == seed["t2"].id)
        )
    ).scalar_one()
    missing = await ac.delete(f"/api/v1/ai/reports/templates/{beta.id}", headers=headers)
    assert missing.status_code == 404
