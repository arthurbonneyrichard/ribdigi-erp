"""Company logo upload uses same-origin API helper (no CORS Failed to fetch)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_company_logo_upload_uses_api_helper():
    page = (ROOT / "frontend/app/(dashboard)/company/page.tsx").read_text(encoding="utf-8")
    assert "apiFetch('/tenants/me/logo')" in page
    assert "api('/tenants/me/logo'" in page
    assert "FormData" in page
    assert "That file is too large" in page
    assert "That file type is not allowed" in page
    assert "NEXT_PUBLIC_API_URL" not in page
    assert "billing_address" not in page
    assert "shipping_address" not in page
    assert 'placeholder="Billing address"' not in page


def test_low_stock_nav_is_inventory_not_reports():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "['Low Stock', '/inventory?tab=lowstock', 'inventory']" in shell
    assert "['Low Stock', '/reports?tab=inventory', 'reports']" not in shell
    inv = (ROOT / "frontend/app/(dashboard)/inventory/page.tsx").read_text(encoding="utf-8")
    assert "'lowstock'" in inv
    assert "/inventory/low-stock" in inv
