"""Stage 99 L1 — Inventory lifecycle leaf discoverability."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_shell_inventory_lifecycle_leaves():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "Variants" in shell
    assert "/inventory?tab=variants" in shell
    assert "Batches" in shell
    assert "/inventory?tab=batches" in shell
    assert "Expiry" in shell
    assert "/inventory?tab=expiry" in shell
    assert "Stock Adjustments" in shell
    assert "/inventory?tab=ops" in shell
    assert "Catalog Brands" in shell
    assert "#brands" in shell
    assert "Catalog Units" in shell
    assert "#units" in shell


def test_catalog_brand_unit_anchors():
    inventory = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert 'id="brands"' in inventory
    assert 'id="units"' in inventory
