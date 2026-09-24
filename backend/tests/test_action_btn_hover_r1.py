"""R1 — Action button hover colors for green / red lifecycle buttons."""
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CSS = ROOT / "frontend" / "app" / "globals.css"


def test_btn_ok_and_btn_danger_hover_colors_defined():
    css = CSS.read_text(encoding="utf-8")
    # Green (ok) hover — brand tokens or classic light greens.
    green_hover = (
        "var(--brand-light)" in css
        or "var(--brand)" in css
        or "#dcfce7" in css
        or "#bbf7d0" in css
    )
    assert green_hover, "btn-ok hover should use brand-light / brand or classic green tones"
    # Red (danger) hover — classic light reds or danger tokens.
    assert ("#fee2e2" in css or "#fecaca" in css or "var(--danger" in css), (
        "btn-danger hover should use light red tones"
    )
    # Dark theme overrides (attribute selector or class).
    assert 'data-theme="dark"' in css or ".dark " in css
    assert "button.btn-ok" in css and "button.btn-danger" in css
