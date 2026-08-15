"""Sidebar default logo uses transparent SVG when no company logo."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_sidebar_default_logo_svg_wired():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    svg_path = ROOT / "frontend/public/brand/logo-sidebar.svg"
    assert svg_path.is_file()
    svg = svg_path.read_text(encoding="utf-8")
    assert svg.lstrip().startswith("<svg")
    assert "/brand/logo-sidebar.svg" in shell
    assert "companyLogoUrl || '/brand/logo-sidebar.svg'" in shell
    # Transparent default: no full-canvas opaque background rect
    assert "rect width=\"100%\"" not in svg
    assert "fill=\"#000\"" not in svg
    assert "fill=\"black\"" not in svg
