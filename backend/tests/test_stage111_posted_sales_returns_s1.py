"""Stage 111 S1 — Posted Sales Returns Shell leaf."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_shell_posted_sales_returns_s1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "/sales?tab=returns&return_status=posted" in shell
    assert "Posted Sales Returns" in shell
    assert "return_status=draft" in shell


def test_sales_page_return_status_posted_s1():
    sales = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert "return_status" in sales
    assert "setReturnStatus" in sales
    assert "Stage 111" in sales
