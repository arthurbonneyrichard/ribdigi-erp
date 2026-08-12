"""Stage 115 P1 — Purchase invoice unpaid/partial/cancelled Shell leaves."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_shell_purchase_invoice_status_leaves_p1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "/purchasing?tab=invoices&status=unpaid" in shell
    assert "/purchasing?tab=invoices&status=partial" in shell
    assert "/purchasing?tab=invoices&status=cancelled" in shell
    assert "Unpaid Purchases" in shell
    assert "Partial Purchases" in shell
    assert "Cancelled Purchases" in shell


def test_purchasing_page_honors_pi_statuses_p1():
    page = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert "Stage 115" in page
    assert "unpaid" in page and "partial" in page and "cancelled" in page
    assert "status" in page
