"""Sidebar default logo uses the RIBDIGI brand PNG wordmark when no company logo."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_sidebar_default_logo_png_wired():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    css = (ROOT / "frontend/app/globals.css").read_text(encoding="utf-8")
    png_path = ROOT / "frontend/public/brand/logo-sidebar.png"
    assert png_path.is_file()
    assert png_path.stat().st_size > 1000
    assert "/brand/logo-sidebar.png" in shell
    assert "companyLogoUrl || '/brand/logo-sidebar.png'" in shell
    # Wide wordmark sizing (logo is ~3:1); keep within sidebar brand slot
    assert "max-height:50px" in css or "max-height: 50px" in css
    assert ".brand-logo" in css
    assert "object-fit:contain" in css or "object-fit: contain" in css
