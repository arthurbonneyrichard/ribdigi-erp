"""Stage 162 S1 — Stock / Stores / Warehouse distinct parents via classifier."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_shell_stock_stores_warehouse_parents_s1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "id: 'stock'" in shell or "\"stock\"" in shell
    assert "id: 'stores'" in shell or "'stores'" in shell
    assert "id: 'warehouse'" in shell or "'warehouse'" in shell
    assert "tab === 'stock'" in shell or "['stock'" in shell or '"stock"' in shell
    assert "#warehouses" in shell
    assert "/inventory?tab=ops" in shell or "tab=ops" in shell
    assert "/inventory?tab=transfers" in shell or "tab=transfers" in shell
