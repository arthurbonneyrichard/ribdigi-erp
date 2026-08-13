"""Stage 232 R1 — Accounting receivables / payables routes."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_accounting_receivables_route_r1():
    page = (ROOT / "frontend/app/accounting/receivables/page.tsx").read_text(encoding="utf-8")
    assert "Accounts Receivable" in page
    assert "/credit?kind=receivable" in page
    assert "router.replace" in page


def test_accounting_payables_route_r1():
    page = (ROOT / "frontend/app/accounting/payables/page.tsx").read_text(encoding="utf-8")
    assert "Accounts Payable" in page
    assert "/credit?kind=payable" in page
    assert "router.replace" in page


def test_shell_classifies_accounting_subpaths_finance():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "path.startsWith('/accounting/')" in shell
