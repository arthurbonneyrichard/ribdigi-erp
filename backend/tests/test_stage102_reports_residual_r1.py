"""Stage 102 R1 — Remaining Reports tab Shell discoverability."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_shell_residual_report_tabs_r1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    for href in (
        "/reports?tab=summary",
        "/reports?tab=sales",
        "/reports?tab=customers",
        "/reports?tab=stores",
        "/reports?tab=transfers",
        "/reports?tab=schedules",
    ):
        assert href in shell, href
    assert "Report Schedules" in shell or "schedules" in shell
    # Stage 100 statement leaves remain; do not remove
    assert "/reports?tab=pnl" in shell


def test_reports_page_still_has_residual_tabs():
    reports = (ROOT / "frontend/app/reports/page.tsx").read_text(encoding="utf-8")
    for tab in ("summary", "sales", "customers", "stores", "transfers", "schedules"):
        assert f"'{tab}'" in reports or f'"{tab}"' in reports, tab
