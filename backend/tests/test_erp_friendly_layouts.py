"""ERP friendly two-column layout packaging."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_erp_friendly_layout_css_and_pages():
    css = (ROOT / "frontend/app/globals.css").read_text(encoding="utf-8")
    assert ".erp-split" in css
    assert ".erp-form-grid" in css

    purchasing = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert 'className="erp-split"' in purchasing
    assert "Quick add supplier" in purchasing
    assert "Create purchase order" in purchasing
    # Supplier + PO live on Orders tab (side-by-side), not on every tab
    assert purchasing.index("Quick add supplier") > purchasing.index("tab === 'orders'")

    sales = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert "Create sale" in sales
    assert 'className="erp-split"' in sales

    expenses = (ROOT / "frontend/app/expenses/page.tsx").read_text(encoding="utf-8")
    assert expenses.count('className="erp-split"') >= 2

    inventory = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert 'className="erp-split"' in inventory
    assert "Brand" in inventory and "Unit of measure" in inventory
