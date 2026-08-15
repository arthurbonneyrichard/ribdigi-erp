"""Recurring schedule Edit UI packaging (BR-9.5 template PATCH)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_recurring_schedule_edit_ui_wired():
    expenses = (ROOT / "frontend/app/expenses/page.tsx").read_text(encoding="utf-8")
    assert "Edit schedule" in expenses
    assert "Save schedule" in expenses
    assert "startRecurringEdit" in expenses
    assert "saveRecurringEdit" in expenses
    assert "recEditId" in expenses
    assert "recurringManageFilter" in expenses
    assert 'aria-label="Recurring expense status filter"' in expenses
    assert "managedRecurring" in expenses
    assert "[inactive]" in expenses


def test_recurring_update_schema_has_template_fields():
    schemas = (ROOT / "backend/app/schemas.py").read_text(encoding="utf-8")
    # Find RecurringExpenseUpdate block
    block = schemas.split("class RecurringExpenseUpdate", 1)[1].split("class ", 1)[0]
    assert "amount" in block
    assert "payee" in block
    assert "clear_payee" in block
    assert "frequency" in block
