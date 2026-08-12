"""Stage 110 E1 — Expense decision queue Shell leaves."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_shell_expense_queue_leaves_e1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "/expenses?status=approved" in shell
    assert "/expenses?status=rejected" in shell
    assert "Approved Expenses" in shell
    assert "Rejected Expenses" in shell
    assert "/expenses?status=pending" in shell


def test_expenses_page_status_url_sync_e1():
    expenses = (ROOT / "frontend/app/expenses/page.tsx").read_text(encoding="utf-8")
    assert "writeExpenseFilters" in expenses
    assert "approved" in expenses
    assert "rejected" in expenses
    assert "pending" in expenses
    assert "Stage 110" in expenses
