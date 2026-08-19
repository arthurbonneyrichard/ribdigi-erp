"""Stage 16 R2: Credit + Tax packaging into Reports (no parallel engines)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from app import models as m
from app.report_export import EXPORTABLE, build_report_payload, flatten_report
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


@pytest.mark.asyncio
async def test_credit_aging_exportable_and_http(client, db_session):
    ac, seed = client
    headers = await _mgr(ac)
    tenant_id = seed["t1"].id

    assert "credit_aging" in EXPORTABLE

    today = datetime.utcnow()
    db_session.add(
        m.SalesInvoice(
            tenant_id=tenant_id,
            invoice_number="INV-S16-R2-AR",
            customer_id=seed["party1"].id,
            status="posted",
            subtotal=120,
            tax_amount=0,
            total_amount=120,
            paid_amount=0,
            due_date=today,
            posted_at=today,
            created_by=seed["mgr1"].id,
        )
    )
    await db_session.commit()

    aging = await ac.get("/api/v1/credit/aging?kind=receivable", headers=headers)
    assert aging.status_code == 200, aging.text
    assert float(aging.json()["data"]["total_due"]) >= 120

    exportable = await ac.get("/api/v1/reports/exportable", headers=headers)
    assert exportable.status_code == 200
    assert "credit_aging" in exportable.json()["data"]["types"]
    assert "tax" in exportable.json()["data"]["types"]
    assert "tax_filing" in exportable.json()["data"]["types"]

    exported = await ac.get(
        "/api/v1/reports/export",
        headers=headers,
        params={"report_type": "credit_aging", "format": "csv", "kind": "receivable"},
    )
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    body = exported.text
    assert "INV-S16-R2-AR" in body or "total_due" in body.lower() or seed["party1"].name in body

    payload = await build_report_payload(
        db_session, tenant_id, "credit_aging", kind="receivable"
    )
    assert payload["kind"] == "receivable"
    rows, lines, title = flatten_report("credit_aging", payload)
    assert title == "Credit Aging"
    assert rows
    assert any("Total due" in ln or "total" in ln.lower() for ln in lines) or lines


@pytest.mark.asyncio
async def test_tax_reports_surfaced_via_reports_export(client, db_session):
    ac, seed = client
    headers = await _mgr(ac)

    tax = await ac.get("/api/v1/reports/tax", headers=headers)
    assert tax.status_code == 200, tax.text

    filing = await ac.get("/api/v1/reports/tax/filing", headers=headers)
    assert filing.status_code == 200, filing.text

    csv_tax = await ac.get(
        "/api/v1/reports/export",
        headers=headers,
        params={"report_type": "tax", "format": "csv"},
    )
    assert csv_tax.status_code == 200, csv_tax.text


def test_reports_ui_packages_credit_and_tax_tabs():
    page = (ROOT / "frontend/app/reports/page.tsx").read_text(encoding="utf-8")
    assert "'credit'" in page
    assert "'tax'" in page
    assert "/credit/aging" in page
    assert "/reports/tax" in page
    assert 'href="/credit"' in page
    assert 'href="/tax"' in page
    assert "credit_aging" in page
    assert "Open Credit module" in page
    assert "Open Tax module" in page


def test_reports_r2_docs_mention_packaging():
    manual = (ROOT / "docs/USER_MANUAL.md").read_text(encoding="utf-8")
    assert "Stage 16 R2" in manual
    assert "Reports → Credit" in manual
    assert "Reports → Tax" in manual
    plan = (ROOT / "docs/STAGE_16_PLAN.md").read_text(encoding="utf-8")
    assert "| **R2**" in plan
    assert "test_credit_tax_reports_r2.py" in plan
    assert "COMPLETE" in plan
