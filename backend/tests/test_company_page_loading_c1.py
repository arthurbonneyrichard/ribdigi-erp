"""Company page must not stay on Loading when /tenants/me fails."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_company_page_retry_instead_of_infinite_loading():
    page = (ROOT / "frontend/app/(dashboard)/company/page.tsx").read_text(encoding="utf-8")
    assert "apiOptional('/tenants/me')" in page
    assert "loadBusy" in page
    assert "Retry" in page
    assert "Company profile could not be loaded" in page


def test_api_optional_does_not_throw():
    src = (ROOT / "frontend/lib/api.ts").read_text(encoding="utf-8")
    assert "export async function apiOptional" in src
    assert "return { data: null" in src


def test_inventory_catalog_loads_use_api_optional():
    page = (ROOT / "frontend/app/(dashboard)/inventory/page.tsx").read_text(encoding="utf-8")
    assert "apiOptional('/products')" in page
    assert "apiOptional('/catalog/categories')" in page
    assert "apiOptional('/catalog/brands')" in page
    assert "apiOptional('/catalog/units')" in page
