"""Stage 116 S1 — Posted/Sent sales invoice Shell leaves."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_shell_posted_sent_invoice_leaves_s1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "/sales?tab=invoices&status=posted" in shell
    assert "/sales?tab=invoices&status=sent" in shell
    assert "Posted Invoices" in shell
    assert "Sent Invoices" in shell


def test_sales_page_honors_posted_sent_s1():
    page = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert "Stage 116" in page
    assert "posted" in page and "sent" in page
    assert "'posted'" in page or '"posted"' in page
