"""Company settings sections save on their own and do not offer self-suspend."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "frontend/app/(dashboard)/company/page.tsx"
CSS = ROOT / "frontend/app/globals.css"


def _slice(text: str, start: str, end: str) -> str:
    body = text.split(start, 1)[1]
    return body.split(end, 1)[0]


def test_company_sections_save_separately():
    page = PAGE.read_text(encoding="utf-8")
    profile = _slice(page, "async function save()", "async function saveTax()")
    assert "fiscal_year_start" not in profile
    assert "tax_jurisdiction" not in profile
    assert "inactivity_timeout_minutes" not in profile
    assert "industry:" not in profile
    assert "rememberFormatPrefs" in profile
    assert "invalidateMeCache()" in profile
    assert "company_name: String(tenant.company_name || '').trim()" in profile

    email = _slice(page, "async function saveEmail()", "async function saveSms()")
    assert "await refresh()" not in email
    assert "trimmedHost" in email
    assert "trimmedPassword" in email

    assert "async function saveStoreAllocation()" in page
    assert 'id="company-store-title"' in page
    assert "Store allocation" in page
    assert "No logo is saved yet. Choose a PNG, JPEG, WebP, or GIF up to 2 MB." in page
    assert "The government filing template is still Ghana only." in page
    assert "tenants/me/suspend" not in page
    assert 'aria-label="Suspend company"' not in page
    assert 'aria-label="Save company profile"' in page

    css = CSS.read_text(encoding="utf-8")
    company_css = css.split("/* Company page layout.", 1)[1].split("/* User management */", 1)[0]
    assert "overflow:visible" in company_css
    assert "grid-template-columns:1fr" in company_css
    assert ".company-page-actions > button" in company_css
