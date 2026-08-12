"""Stage 114 Q1 — Residual sales quote/order/invoice Shell status leaves."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_shell_sales_residual_leaves_q1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "quote_status=sent" in shell
    assert "quote_status=rejected" in shell
    assert "quote_status=expired" in shell
    assert "Sent Quotations" in shell
    assert "Rejected Quotations" in shell
    assert "Expired Quotations" in shell
    assert "order_status=cancelled" in shell
    assert "Cancelled Orders" in shell
    assert "status=unpaid" in shell
    assert "status=partial" in shell
    assert "/sales?tab=invoices&status=cancelled" in shell
    assert "Unpaid Invoices" in shell
    assert "Partial Invoices" in shell
    assert "Cancelled Invoices" in shell


def test_sales_page_honors_residual_statuses_q1():
    page = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert "Stage 114" in page
    assert "sent" in page and "rejected" in page and "expired" in page
    assert "cancelled" in page
    assert "unpaid" in page and "partial" in page
    assert "quote_status" in page and "order_status" in page
