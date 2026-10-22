"""Chrome: RIBDIGI ERP default on sidebar until company upload; greeting has no logo; documents stay name-only until upload."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_sidebar_default_logo_png_wired():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    dash = (ROOT / "frontend/app/(dashboard)/dashboard/page.tsx").read_text(encoding="utf-8")
    brand = (ROOT / "frontend/lib/chromeBrand.ts").read_text(encoding="utf-8")
    css = (ROOT / "frontend/app/globals.css").read_text(encoding="utf-8")
    receipts = (ROOT / "backend/app/receipts.py").read_text(encoding="utf-8")
    invoices = (ROOT / "backend/app/invoice_print.py").read_text(encoding="utf-8")
    png_sidebar = ROOT / "frontend/public/brand/logo-sidebar.png"
    png_dash = ROOT / "frontend/public/brand/logo-full-dark.png"
    assert png_sidebar.is_file()
    assert png_sidebar.stat().st_size > 1000
    assert png_dash.is_file()
    assert png_dash.stat().st_size > 1000
    assert "PLATFORM_SIDEBAR_LOGO" in brand
    assert "PLATFORM_DASHBOARD_LOGO" in brand
    assert "/brand/logo-sidebar.png" in brand
    assert "/brand/logo-full-dark.png" in brand
    assert "chromeLogoSrc" in shell and "PLATFORM_SIDEBAR_LOGO" in shell
    assert "chromeLogoSrc" not in dash
    assert "PLATFORM_DASHBOARD_LOGO" not in dash
    assert "dash-brand-slot" not in dash
    assert "dash-brand-logo" not in dash
    assert "brand-logo-slot" in shell
    assert "brand-logo-slot" in css
    assert "dash-brand-slot" not in css
    assert "height:50px" in css
    assert "object-fit:contain" in css or "object-fit: contain" in css
    assert ".brand-logo" in css
    # Tenant documents stay name-only until that tenant uploads a logo.
    assert "logo-sidebar.png" not in receipts
    assert "logo-full-dark.png" not in receipts
    assert "ribdigi-house-logo" not in receipts
    assert "logo-sidebar.png" not in invoices
    assert "ribdigi-house-logo" not in invoices
