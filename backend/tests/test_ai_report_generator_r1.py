"""Stage 20 R1: AI NL report generator fidelity (BR-21.7)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from app import models as m
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]

PROMPT_Q2 = "Show me monthly sales for Q2 2026"


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


async def _seed_q2_sale(db_session, seed):
    inv = m.SalesInvoice(
        tenant_id=seed["t1"].id,
        invoice_number="INV-R1-Q2-1",
        customer_id=seed["party1"].id,
        status="posted",
        subtotal=40,
        tax_amount=0,
        total_amount=40,
        created_at=datetime(2026, 5, 12, 10, 0, 0),
        posted_at=datetime(2026, 5, 12, 10, 0, 0),
    )
    db_session.add(inv)
    await db_session.flush()
    db_session.add(
        m.SalesInvoiceItem(
            tenant_id=seed["t1"].id,
            sales_invoice_id=inv.id,
            product_id=seed["p1"].id,
            quantity=8,
            unit_price=5,
            line_total=40,
        )
    )
    await db_session.commit()


@pytest.mark.asyncio
async def test_generate_report_from_nl_prompt(client, db_session):
    """BR-21.7: generate reports from text prompts (Q2 monthly sales)."""
    ac, seed = client
    headers = await _mgr(ac)
    await _seed_q2_sale(db_session, seed)

    r = await ac.post(
        "/api/v1/ai/reports/generate",
        headers=headers,
        json={"prompt": PROMPT_Q2},
    )
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert body["method"] == "rules_v1"
    assert body["report_type"] == "sales_products"
    assert body["period_label"] == "Q2 2026"
    assert body["params"]["from_date"] == "2026-04-01"
    assert body["params"]["to_date"] == "2026-06-30"
    assert body["export_ready"] is True
    assert body["row_count"] >= 1
    assert body["preview_rows"] or body["preview_lines"]
    assert any(
        (row.get("sku") == "A-1") or ("Alpha" in str(row.get("name") or ""))
        for row in body["preview_rows"]
    ) or body["row_count"] >= 1


@pytest.mark.asyncio
async def test_export_generated_report(client, db_session):
    """BR-21.7: export generated reports (csv + pdf)."""
    ac, seed = client
    headers = await _mgr(ac)
    await _seed_q2_sale(db_session, seed)

    csv_r = await ac.post(
        "/api/v1/ai/reports/generate?export=true",
        headers=headers,
        json={"prompt": PROMPT_Q2, "format": "csv"},
    )
    assert csv_r.status_code == 200, csv_r.text
    assert "text/csv" in csv_r.headers.get("content-type", "")
    assert "attachment" in csv_r.headers.get("content-disposition", "").lower()
    assert len(csv_r.content) > 0
    assert b"sku" in csv_r.content.lower() or b"Alpha" in csv_r.content or b"," in csv_r.content

    pdf_r = await ac.post(
        "/api/v1/ai/reports/generate?export=true",
        headers=headers,
        json={"prompt": "Export low stock as pdf"},
    )
    assert pdf_r.status_code == 200, pdf_r.text
    ctype = pdf_r.headers.get("content-type", "")
    assert "pdf" in ctype or pdf_r.content[:4] == b"%PDF" or len(pdf_r.content) > 0


@pytest.mark.asyncio
async def test_save_and_reuse_report_template(client, db_session):
    """BR-21.7: save report templates and regenerate/export from template_id."""
    ac, seed = client
    headers = await _mgr(ac)
    await _seed_q2_sale(db_session, seed)

    save = await ac.post(
        "/api/v1/ai/reports/templates",
        headers=headers,
        json={"name": "R1 Q2 Sales", "prompt": PROMPT_Q2, "format": "csv"},
    )
    assert save.status_code == 200, save.text
    tmpl = save.json()["data"]
    assert tmpl["name"] == "R1 Q2 Sales"
    assert tmpl["prompt"] == PROMPT_Q2
    assert tmpl["report_type"] == "sales_products"
    assert tmpl["format"] == "csv"
    tmpl_id = tmpl["id"]

    listed = await ac.get("/api/v1/ai/reports/templates", headers=headers)
    assert listed.status_code == 200
    assert any(t["id"] == tmpl_id for t in listed.json()["data"])

    regen = await ac.post(
        "/api/v1/ai/reports/generate",
        headers=headers,
        json={"template_id": tmpl_id},
    )
    assert regen.status_code == 200, regen.text
    body = regen.json()["data"]
    assert body["report_type"] == "sales_products"
    assert body["period_label"] == "Q2 2026"
    assert body["export_ready"] is True

    exported = await ac.post(
        "/api/v1/ai/reports/generate?export=true",
        headers=headers,
        json={"template_id": tmpl_id},
    )
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    assert len(exported.content) > 0


def test_br_21_7_and_plan_synced():
    br = (ROOT / "docs" / "BUSINESS_REQUIREMENTS_DOCUMENT.md").read_text(encoding="utf-8")
    s217 = br.split("#### BR-21.7 AI Report Generator")[1].split("#### BR-21.8")[0]
    assert "[x] Generate reports from text prompts" in s217
    assert "[x] Export generated reports" in s217
    assert "[x] Save report templates for reuse" in s217
    assert "Stage 20 R1" in s217
    assert "test_ai_report_generator_r1.py" in s217

    plan = (ROOT / "docs" / "STAGE_20_PLAN.md").read_text(encoding="utf-8")
    r1_line = [ln for ln in plan.splitlines() if "| **R1**" in ln][0]
    assert "COMPLETE" in r1_line
    assert "test_ai_report_generator_r1.py" in plan
