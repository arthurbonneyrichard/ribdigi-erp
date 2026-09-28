"""Inventory catalog manage tabs: no BR- codes; compact list + drawer pattern."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "frontend/app/(dashboard)/inventory/page.tsx"


def _section(text: str, tab: str, nxt: str) -> str:
    start = text.find(f"{{tab === '{tab}' && (")
    end = text.find(f"{{tab === '{nxt}' && (")
    assert start >= 0 and end > start, (tab, nxt, start, end)
    return text[start:end]


def test_brands_units_variants_ui_matches_categories_pattern():
    page = PAGE.read_text(encoding="utf-8")
    brands = _section(page, "brands", "units")
    units = _section(page, "units", "variants")
    variants = _section(page, "variants", "batches")

    for chunk, add in (
        (brands, "Add brand"),
        (units, "Add unit"),
        (variants, "Add variant"),
    ):
        assert "BR-" not in chunk
        assert add in chunk
        assert "cat-panel" in chunk
        assert "cat-table" in chunk
        assert "Edit" in chunk
        assert "Deactivate" in chunk
        assert "Activate" in chunk
        assert "inv-drawer" in chunk

    assert "<h2" in brands and "Brands" in brands
    assert "<h2" in units and "Units" in units
    assert "<h2" in variants and "Variants" in variants
    assert "Main unit" in units
    assert "Parent product" in variants
    assert "Create variant" in variants
    assert "code: brandCode.trim()" not in page
    assert "code: unitCode.trim()" not in page
    assert "Category created" in page
    assert "Brand created" in page
    assert "Unit created" in page
