"""Stage 107 P1 — POS sections honesty."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_shell_pos_section_hashes_p1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "/pos#shift" in shell
    assert "/pos#cart" in shell
    assert "/pos#receipt" in shell
    assert "POS Shift" in shell
    assert "POS Cart" in shell
    assert "POS Receipt" in shell


def test_pos_page_section_anchors_p1():
    pos = (ROOT / "frontend/app/pos/page.tsx").read_text(encoding="utf-8")
    assert 'id="shift"' in pos
    assert 'id="cart"' in pos
    assert 'id="receipt"' in pos
    assert 'id="sessions"' in pos
    assert "scrollIntoView" in pos
    assert "shift" in pos and "cart" in pos and "receipt" in pos
