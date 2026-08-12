"""Stage 96 L1 — Finance / Sales / Settings leaf fidelity."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_shell_leaf_discoverability_l1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "Money Transfer" in shell
    assert "/accounting?tab=ledger#money-transfer" in shell
    assert "Income" in shell
    assert "#profit-loss" in shell
    assert "Billers" in shell
    assert "/reports?tab=salesperson" in shell
    assert "Delivery status" in shell
    assert "/sales?tab=orders" in shell
    assert "Document templates" in shell
    assert "#document-templates" in shell
    assert "Notification settings" in shell


def test_accounting_sales_company_anchors_l1():
    accounting = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert "useTabQuery" in accounting
    assert 'id="money-transfer"' in accounting
    assert 'id="profit-loss"' in accounting
    sales = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert "orderStatusFilter" in sales or "Delivery status" in sales
    company = (ROOT / "frontend/app/company/page.tsx").read_text(encoding="utf-8")
    assert 'id="document-templates"' in company
    notes = (ROOT / "frontend/app/notifications/page.tsx").read_text(encoding="utf-8")
    assert 'id="preferences"' in notes
