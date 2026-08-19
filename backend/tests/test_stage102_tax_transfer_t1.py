"""Stage 102 T1 — Tax filing / company tax / inter-store transfer honesty."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_shell_tax_company_transfer_deeplinks_t1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "/tax#calculator" in shell
    assert "/tax#filing" in shell
    assert "/tax#rates" in shell
    assert "Tax Calculator" in shell
    assert "Tax Filing Pack" in shell
    assert "/company#tax" in shell
    assert "Company Tax" in shell
    assert "/stores#transfers" in shell
    assert "Inter-store Transfers" in shell


def test_tax_company_stores_anchors_t1():
    tax = (ROOT / "frontend/app/tax/page.tsx").read_text(encoding="utf-8")
    assert 'id="calculator"' in tax
    assert 'id="filing"' in tax
    assert 'id="rates"' in tax
    assert "scrollIntoView" in tax

    company = (ROOT / "frontend/app/company/page.tsx").read_text(encoding="utf-8")
    assert 'id="tax"' in company
    assert "scrollIntoView" in company

    stores = (ROOT / "frontend/app/stores/page.tsx").read_text(encoding="utf-8")
    assert 'id="transfers"' in stores
    assert "scrollIntoView" in stores
