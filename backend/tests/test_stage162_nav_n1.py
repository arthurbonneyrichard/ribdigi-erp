"""Stage 162 N1 — approved expandable Shell navigation parents."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_shell_approved_expandable_parents_n1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "Stage 162" in shell
    assert "APPROVED_NAV_GROUPS" in shell
    assert "nav-group-toggle" in shell
    assert "classifyNavLink" in shell
    for label in (
        "Inventory",
        "Stock",
        "Sales",
        "Purchase",
        "Finance & Accounts",
        "People",
        "Stores",
        "Warehouse",
        "Report",
        "Settings",
        "User Management",
    ):
        assert label in shell, label
    assert "Commerce" not in shell
    assert "Operations" not in shell
    css = (ROOT / "frontend/app/globals.css").read_text(encoding="utf-8")
    assert ".nav-group-toggle" in css
