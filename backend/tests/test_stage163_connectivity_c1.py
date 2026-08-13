"""Stage 163 C1 — Shell ONLINE/OFFLINE connectivity chrome."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_shell_connectivity_badge_c1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "Stage 163" in shell or "connectivity-badge" in shell
    assert "navigator.onLine" in shell
    assert "ONLINE" in shell and "OFFLINE" in shell
    assert "connectivity-badge" in shell
    assert "data-stage163-connectivity" in shell
    assert "addEventListener('online'" in shell or 'addEventListener("online"' in shell
    assert "addEventListener('offline'" in shell or 'addEventListener("offline"' in shell


def test_connectivity_css_c1():
    css = (ROOT / "frontend/app/globals.css").read_text(encoding="utf-8")
    assert ".connectivity-badge" in css
    assert ".connectivity-badge.online" in css
    assert ".connectivity-badge.offline" in css
