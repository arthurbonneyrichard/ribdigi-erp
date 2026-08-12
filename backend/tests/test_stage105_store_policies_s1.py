"""Stage 105 S1 — Store policy leaves (FEFO / reorder)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_shell_store_policy_leaves_s1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "/stores#fefo" in shell
    assert "/stores#reorder" in shell
    assert "FEFO Policy" in shell
    assert "Reorder Policies" in shell


def test_stores_page_policy_anchors_s1():
    stores = (ROOT / "frontend/app/stores/page.tsx").read_text(encoding="utf-8")
    assert 'id="fefo"' in stores
    assert 'id="reorder"' in stores
    assert "writeStoresQuery" in stores
    assert "store_id" in stores
    assert "scrollIntoView" in stores
