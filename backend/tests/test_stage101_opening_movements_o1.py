"""Stage 101 O1 — Opening Stock & Movements Shell discoverability."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_shell_opening_movements_and_categories_o1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "Opening Stock" in shell
    assert "/inventory?tab=opening" in shell
    assert "Movements" in shell
    assert "/inventory?tab=movements" in shell
    assert "Catalog Categories" in shell
    assert "/inventory?tab=catalog#categories" in shell

    inventory = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert 'id="categories"' in inventory
    assert "syncMovementTypeUrl" in inventory
    assert "movement_type" in inventory
    assert "scrollIntoView" in inventory
