"""Stage 113 S1 — Shipped/Delivered Orders, Paid Invoices, Transfer status Shell leaves."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_shell_fulfillment_and_transfer_leaves_s1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "order_status=shipped" in shell
    assert "order_status=delivered" in shell
    assert "Shipped Orders" in shell
    assert "Delivered Orders" in shell
    assert "status=paid" in shell
    assert "Paid Invoices" in shell
    assert "status=draft" in shell or "transfers&status=draft" in shell
    assert "transfers&status=requested" in shell
    assert "transfers&status=in_transit" in shell
    assert "transfers&status=received" in shell
    assert "transfers&status=cancelled" in shell
    assert "In-transit Transfers" in shell
    assert "Received Transfers" in shell


def test_sales_and_reports_url_sync_s1():
    sales = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert "Stage 113" in sales
    assert "shipped" in sales and "delivered" in sales
    assert "order_status" in sales
    assert "paid" in sales
    reports = (ROOT / "frontend/app/reports/page.tsx").read_text(encoding="utf-8")
    assert "Stage 113" in reports
    assert "writeReportFilters" in reports
    assert "transferStatus" in reports
    assert 'value="in_transit"' in reports
    assert 'value="received"' in reports
