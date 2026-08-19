"""Stage 112 S1 — Stores Cash Drawer #cash-drawer Shell leaf + hash scroll."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_shell_cash_drawer_leaf_s1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "/stores#cash-drawer" in shell
    assert "Cash Drawer" in shell


def test_stores_cash_drawer_anchor_s1():
    stores = (ROOT / "frontend/app/stores/page.tsx").read_text(encoding="utf-8")
    assert 'id="cash-drawer"' in stores
    assert "scrollIntoView" in stores
    assert "Stage 112" in stores
    assert "Cash drawer" in stores
