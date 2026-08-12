"""Stage 113 C1 — Bounced/Cancelled Cheques Shell leaves."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_shell_cheque_exception_leaves_c1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "cheque_status=bounced#cheques" in shell
    assert "cheque_status=cancelled#cheques" in shell
    assert "Bounced Cheques" in shell
    assert "Cancelled Cheques" in shell


def test_accounting_page_honors_bounced_cancelled_c1():
    page = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert "Stage 113" in page
    assert "bounced" in page and "cancelled" in page
    assert "cheque_status" in page
    assert 'id="cheques"' in page or "#cheques" in page
