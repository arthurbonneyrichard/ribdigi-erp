"""Stage 232 U1 — Credit titles + Accounting AR/AP cross-links."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_credit_page_ar_ap_titles_u1():
    credit = (ROOT / "frontend/app/credit/page.tsx").read_text(encoding="utf-8")
    assert "Accounts Receivable" in credit
    assert "Accounts Payable" in credit
    assert "Stage 232" in credit


def test_accounting_page_ar_ap_cross_links_u1():
    accounting = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert 'id="ar-ap-surface"' in accounting
    assert "/accounting/receivables" in accounting
    assert "/accounting/payables" in accounting
    assert "Accounts Receivable" in accounting
    assert "Accounts Payable" in accounting


def test_surface_mvp_doc_u1():
    doc = (ROOT / "docs/AR_AP_ACCOUNTING_SURFACE_MVP.md").read_text(encoding="utf-8")
    assert "new_ar_ap_engine_claimed" in doc
    assert "Accounts Receivable" in doc
    assert "Accounts Payable" in doc
