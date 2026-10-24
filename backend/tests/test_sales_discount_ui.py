"""Sales Create sale line + header discount UI packaging."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_sales_discount_ui_wired():
    sales = (ROOT / "frontend/app/(dashboard)/sales/page.tsx").read_text(encoding="utf-8")
    assert "lineDiscount" in sales
    assert "headerDiscount" in sales
    assert "discount_type: headerDiscountType" in sales
    assert "discount_type: lineDiscountType" in sales
    assert 'aria-label="Line discount"' in sales
    assert 'aria-label="Header discount"' in sales
    assert '<th className="col-num">Discount</th>' in sales
    assert "selected.discount_amount" in sales

    api_docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert (
        "Sales **Create sale** UI **Line quantity** / **Line unit price** / "
        "**Line discount** + **Header discount**"
        in api_docs
    )


def test_sales_discount_br_marked():
    brd = (ROOT / "docs/BUSINESS_REQUIREMENTS_DOCUMENT.md").read_text(encoding="utf-8")
    assert "Line + header discounts on create" in brd
    assert "Sales Create sale + detail KPI" in brd
