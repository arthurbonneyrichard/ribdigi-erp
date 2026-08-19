"""Stage 100 R1 — Reports financial statement discoverability."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_shell_report_statement_deeplinks_r1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    for href in (
        "/reports?tab=pnl",
        "/reports?tab=cashflow",
        "/reports?tab=balancesheet",
        "/reports?tab=inventory",
        "/reports?tab=purchases",
        "/reports?tab=credit",
        "/reports?tab=tax",
        "/reports?tab=expenses",
    ):
        assert href in shell, href
    assert "Profit & Loss" in shell or "Profit &amp; Loss" in shell
    assert "Cash Flow" in shell
    assert "Balance Sheet" in shell


def test_reports_page_keeps_statement_tabs():
    reports = (ROOT / "frontend/app/reports/page.tsx").read_text(encoding="utf-8")
    assert "useTabQuery" in reports
    for tab in ("pnl", "cashflow", "balancesheet", "inventory", "purchases", "credit", "tax", "expenses"):
        assert f"'{tab}'" in reports or f'"{tab}"' in reports, tab
