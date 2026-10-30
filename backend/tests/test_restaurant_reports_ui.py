"""Restaurant reports screen: its own period report; accounting statements stay shared."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "frontend"
PAGE = (ROOT / "app/(dashboard)/restaurant/reports/page.tsx").read_text(encoding="utf-8")
NAV = (ROOT / "lib/tenantNav.ts").read_text(encoding="utf-8")


def test_reports_screen_reads_period_report():
    assert "/restaurant/reports/period?from_date=${start}&to_date=${end}" in PAGE
    for words in ("Sales by day", "Busiest hours", "Dishes and drinks", "Who took the orders", "How guests paid", "Food cost"):
        assert words in PAGE
    assert "Download CSV" in PAGE
    # Every bar carries its own readout (hover/focus), not colour alone.
    assert 'className="rd-bar-tip"' in PAGE and "tabIndex={0}" in PAGE


def test_restaurant_nav_points_reports_at_own_screen():
    start = NAV.index("export const RESTAURANT_NAV_GROUPS")
    block = NAV[start : NAV.index("];", start)]
    assert "['Reports', '/restaurant/reports', 'reports']" in block
    assert "['Profit and loss', '/reports?tab=pnl', 'reports']" in block
    assert "['Reports', '/reports', 'reports']" not in block
