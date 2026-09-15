"""OpenAPI honesty tips #606–#611: frequency/format/payment aria-labels."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_frequency_format_payment_aria_ui_and_docs():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for title in (
        "Backup frequency aria OpenAPI",
        "Recurring frequency aria OpenAPI",
        "Report schedule frequency aria OpenAPI",
        "Report schedule format aria OpenAPI",
        "Report schedule report type aria OpenAPI",
        "Expense payment method aria OpenAPI",
    ):
        assert title in agents, title

    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Expense payment method" in docs
    assert "Recurring frequency" in docs
    assert "Report schedule report type" in docs
    assert "Report schedule format" in docs
    assert "Report schedule frequency" in docs
    dr = (ROOT / "docs/DR_LOGICAL_BACKUP_RUNBOOK.md").read_text(encoding="utf-8")
    assert "Backup frequency" in dr

    backup = (ROOT / "frontend/app/backup/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Backup frequency"' in backup

    expenses = (ROOT / "frontend/app/expenses/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Recurring frequency"' in expenses
    assert 'aria-label="Recurring payment method"' in expenses
    assert 'aria-label="Expense payment method"' in expenses

    reports = (ROOT / "frontend/app/reports/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Report schedule report type"' in reports
    assert 'aria-label="Report schedule format"' in reports
    assert 'aria-label="Report schedule frequency"' in reports
