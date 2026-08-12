"""Stage 109 R1 — Report / tax / movements period & dimension URL sync."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_reports_period_dimension_url_sync_r1():
    reports = (ROOT / "frontend/app/reports/page.tsx").read_text(encoding="utf-8")
    assert "writeReportFilters" in reports
    assert "from_date" in reports
    assert "to_date" in reports
    assert "store_id" in reports
    assert "branch_id" in reports
    assert "category_id" in reports
    assert "Report from date" in reports or "aria-label=\"Report from date\"" in reports


def test_tax_filing_period_url_sync_r1():
    tax = (ROOT / "frontend/app/tax/page.tsx").read_text(encoding="utf-8")
    assert "writeTaxPeriodUrl" in tax
    assert "from_date" in tax
    assert "to_date" in tax
    assert "Tax filing from date" in tax or "aria-label=\"Tax filing from date\"" in tax


def test_inventory_movements_dates_url_sync_r1():
    inv = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert "syncMovementFiltersUrl" in inv
    assert "from_date" in inv
    assert "to_date" in inv
    assert "movement_type" in inv
    assert "Movements from date" in inv or "aria-label=\"Movements from date\"" in inv
