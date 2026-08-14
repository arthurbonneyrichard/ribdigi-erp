"""Pending/rejected expense Edit UI packaging (BR-9.2 / BR-9.5 occurrence)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_expense_edit_ui_wired():
    expenses = (ROOT / "frontend/app/expenses/page.tsx").read_text(encoding="utf-8")
    assert "startEdit" in expenses
    assert "saveEdit" in expenses
    assert "Edit expense" in expenses
    assert "Save changes" in expenses
    assert 'method: \'PATCH\'' in expenses or 'method: "PATCH"' in expenses
    assert "editDraft" in expenses
    # Edit shown for pending and rejected
    assert "r.status === 'pending' || r.status === 'rejected'" in expenses or (
        "pending" in expenses and "rejected" in expenses and "startEdit" in expenses
    )


def test_expense_edit_docs():
    api = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Expenses UI **Edit**" in api
    manual = (ROOT / "docs/USER_MANUAL.md").read_text(encoding="utf-8")
    assert "**Edit** that pending expense" in manual or "Edit** on pending" in manual
