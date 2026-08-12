"""Stage 108 C1 — Credit statement surfaces discoverability."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_shell_credit_statement_leaves_c1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "/credit#party-actions" in shell
    assert "/credit#by-party" in shell
    assert "/credit#statement" in shell
    assert "Credit Party Actions" in shell or "Party Actions" in shell
    assert "Credit Statement" in shell


def test_credit_page_statement_anchors_c1():
    credit = (ROOT / "frontend/app/credit/page.tsx").read_text(encoding="utf-8")
    assert 'id="party-actions"' in credit
    assert 'id="by-party"' in credit
    assert 'id="statement"' in credit
    assert "scrollIntoView" in credit
    assert "Stage 108" in credit or "party-actions" in credit
