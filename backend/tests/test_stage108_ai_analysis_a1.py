"""Stage 108 A1 — AI analysis leaves honesty."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_shell_ai_analysis_leaves_a1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    for href in (
        "/ai#sales-analysis",
        "/ai#expense-analysis",
        "/ai#purchases-analysis",
        "/ai#cross-domain",
        "/ai#document",
        "/ai#customer",
        "/ai#report-generator",
        "/ai#low-stock",
    ):
        assert href in shell, href
    assert "AI Sales Analysis" in shell
    assert "AI Low Stock" in shell


def test_ai_page_analysis_anchors_a1():
    ai = (ROOT / "frontend/app/ai/page.tsx").read_text(encoding="utf-8")
    for anchor in (
        'id="sales-analysis"',
        'id="expense-analysis"',
        'id="purchases-analysis"',
        'id="cross-domain"',
        'id="document"',
        'id="customer"',
        'id="report-generator"',
        'id="low-stock"',
    ):
        assert anchor in ai, anchor
    assert "scrollIntoView" in ai
    assert "Stage 108" in ai or "sales-analysis" in ai
