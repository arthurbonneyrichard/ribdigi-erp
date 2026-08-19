"""Stage 116 U1 — Inventory/Sales Officer Users Shell role leaves."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_shell_officer_role_leaves_u1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "role=inventory_officer" in shell
    assert "role=sales_officer" in shell
    assert "Inventory Officer Users" in shell
    assert "Sales Officer Users" in shell


def test_users_page_and_rbac_honor_officer_roles_u1():
    users = (ROOT / "frontend/app/users/page.tsx").read_text(encoding="utf-8")
    assert "Stage 116" in users
    assert "role" in users
    rbac = (ROOT / "backend/app/rbac.py").read_text(encoding="utf-8")
    assert "inventory_officer" in rbac
    assert "sales_officer" in rbac
