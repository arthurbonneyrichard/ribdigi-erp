"""Stage 106 E1 — Expense scope & purchase settings honesty."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_shell_purchase_settings_hash_e1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "/purchasing?tab=settings#purchase-settings" in shell
    assert "Purchase Settings" in shell


def test_expense_scope_url_sync_e1():
    expenses = (ROOT / "frontend/app/expenses/page.tsx").read_text(encoding="utf-8")
    assert "writeExpenseFilters" in expenses
    assert "store_id" in expenses
    assert "department_id" in expenses
    assert "Filter expenses by store" in expenses
    assert "Filter expenses by department" in expenses


def test_purchasing_settings_scroll_e1():
    purchasing = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert 'id="purchase-settings"' in purchasing
    assert "scrollIntoView" in purchasing
    assert "purchase-settings" in purchasing
