"""Stage 109 S1 — Sales document status Shell leaves."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_shell_sales_status_leaves_s1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "quote_status=draft" in shell
    assert "quote_status=accepted" in shell
    assert "order_status=confirmed" in shell
    assert "order_status=processing" in shell
    assert "return_status=draft" in shell
    assert "Draft Quotations" in shell
    assert "Confirmed Orders" in shell
    assert "Draft Sales Returns" in shell


def test_sales_page_status_url_params_s1():
    sales = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert "quote_status" in sales
    assert "order_status" in sales
    assert "return_status" in sales
    assert "writeQueryParam" in sales
