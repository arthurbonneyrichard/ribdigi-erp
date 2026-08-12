"""Stage 117 P1 — Permissions ?role= Shell leaves."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_shell_permissions_role_leaves_p1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "/admin/permissions?role=cashier" in shell
    assert "/admin/permissions?role=company_admin" in shell
    assert "/admin/permissions?role=store_manager" in shell
    assert "/admin/permissions?role=accountant" in shell
    assert "/admin/permissions?role=inventory_officer" in shell
    assert "/admin/permissions?role=sales_officer" in shell
    assert "/admin/permissions?role=super_admin" in shell
    assert "Cashier Permissions" in shell
    assert "Super Admin Permissions" in shell


def test_permissions_page_honors_role_query_p1():
    page = (ROOT / "frontend/app/admin/permissions/page.tsx").read_text(encoding="utf-8")
    assert "Stage 117" in page
    assert "writePermissionsQuery" in page
    assert "role" in page
