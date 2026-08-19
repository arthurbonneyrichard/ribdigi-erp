"""Stage 1 E13 — format helper contract (mirrors frontend/lib/format.ts)."""

from __future__ import annotations

from pathlib import Path


def test_format_helper_module_exists_with_required_exports():
    path = Path(__file__).resolve().parents[2] / "frontend" / "lib" / "format.ts"
    text = path.read_text(encoding="utf-8")
    assert "export function formatNumber" in text
    assert "export function formatDate" in text
    assert "export function formatDateTime" in text
    assert "1.234,56" in text
    assert "12h" in text
