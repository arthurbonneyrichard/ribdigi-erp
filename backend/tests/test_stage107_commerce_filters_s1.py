"""Stage 107 S1 — Commerce filters honesty."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_shell_commerce_filter_leaves_s1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "active_only=true" in shell
    assert "Active Customers" in shell
    assert "Active Customer Groups" in shell
    assert "Product Search" in shell
    assert "tab=products&q=" in shell or "q=" in shell


def test_sales_active_only_url_sync_s1():
    sales = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert "active_only" in sales
    assert "setActiveOnly" in sales or "activeOnlyFilter" in sales
    assert "/customers" in sales
    assert "active_only=true" in sales


def test_inventory_product_list_filters_s1():
    inv = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert "listFilterQ" in inv or "writeProductListFilters" in inv
    assert "category_id" in inv
    assert "brand_id" in inv
    assert "filteredProducts" in inv
    assert "Filter products" in inv or "Shareable URL filters" in inv
