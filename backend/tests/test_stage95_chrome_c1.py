"""Stage 95 C1 — Chrome & settings alias fidelity."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_shell_chrome_profile_mobile_c1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "profile-menu" in shell or "profileOpen" in shell
    assert "Log out" in shell
    assert "nav-toggle" in shell
    assert "navOpen" in shell
    assert "/auth/logout" in shell or "logout" in shell

    css = (ROOT / "frontend/app/globals.css").read_text(encoding="utf-8")
    assert "nav-toggle" in css
    assert "nav-open" in css
    assert "profile-dropdown" in css or "profile-menu" in css
    assert "@media" in css and "800px" in css

    company = (ROOT / "frontend/app/company/page.tsx").read_text(encoding="utf-8")
    assert "<h1>Settings</h1>" in company
    stores = (ROOT / "frontend/app/stores/page.tsx").read_text(encoding="utf-8")
    assert "<h1>Stores</h1>" in stores
    assert "Multi-Store" not in stores.split("<h1>")[1].split("</h1>")[0]
