"""Stage 101 E1 — Recurring Expenses leaf & notification deep-link honesty."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_shell_recurring_and_budgets_e1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "Recurring Expenses" in shell
    assert "/expenses#recurring" in shell
    assert "Expense Categories & Budgets" in shell or "#budgets" in shell
    assert "/expenses#budgets" in shell

    expenses = (ROOT / "frontend/app/expenses/page.tsx").read_text(encoding="utf-8")
    assert 'id="recurring"' in expenses
    assert 'id="budgets"' in expenses
    assert "scrollIntoView" in expenses


def test_notification_deeplinks_and_url_sync_e1():
    dash = (ROOT / "frontend/app/dashboard/page.tsx").read_text(encoding="utf-8")
    assert "/expenses?status=pending" in dash
    assert "/expenses#recurring" in dash
    assert "expense_approval" in dash

    notes = (ROOT / "frontend/app/notifications/page.tsx").read_text(encoding="utf-8")
    assert "useSearchParams" in notes
    assert "syncUrl" in notes
    assert "status" in notes and "group" in notes
