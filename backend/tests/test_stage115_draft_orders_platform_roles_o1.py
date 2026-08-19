"""Stage 115 O1 — Draft Orders Shell leaf + Platform Users role leaves."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_shell_draft_orders_leaf_o1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "order_status=draft" in shell
    assert "Draft Orders" in shell
    assert "/sales?tab=orders&order_status=draft" in shell


def test_platform_shell_role_leaves_o1():
    shell = (ROOT / "frontend/components/PlatformShell.tsx").read_text(encoding="utf-8")
    assert "role=platform_admin" in shell
    assert "role=platform_super_admin" in shell
    assert "Platform Admins" in shell
    assert "Platform Super Admins" in shell


def test_pages_honor_draft_orders_and_platform_roles_o1():
    sales = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert "Stage 115" in sales
    assert "draft" in sales and "order_status" in sales
    users = (ROOT / "frontend/app/platform/users/page.tsx").read_text(encoding="utf-8")
    assert "Stage 115" in users
    assert "platform_admin" in users
    assert "platform_super_admin" in users
    assert "role" in users
