"""Stage 104 A1 — Ledger journal & cheque filter honesty."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_shell_ledger_cheque_filter_leaves_a1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "status=unposted" in shell
    assert "status=posted" in shell
    assert "Unposted Journals" in shell
    assert "Posted Journals" in shell
    assert "cheque_status=pending" in shell
    assert "cheque_direction=received" in shell
    assert "cheque_direction=issued" in shell
    assert "Pending Cheques" in shell


def test_accounting_page_journal_cheque_url_sync_a1():
    accounting = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert "writeAccountingQuery" in accounting
    assert "cheque_direction" in accounting
    assert "cheque_status" in accounting
    assert "chequeDirectionFilter" in accounting
    assert "chequeStatusFilter" in accounting
    assert "/accounting/cheques?" in accounting or "chequeParams" in accounting
    assert "Journal status filter" in accounting
    assert "Cheque direction filter" in accounting
