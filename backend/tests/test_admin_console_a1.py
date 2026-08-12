"""Stage 81 A1 — Tenant Admin RBAC console surfaces (Users / Roles / Permissions)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_admin_console_routes_exist():
    assert (ROOT / "frontend/app/users/page.tsx").is_file()
    assert (ROOT / "frontend/app/admin/roles/page.tsx").is_file()
    assert (ROOT / "frontend/app/admin/permissions/page.tsx").is_file()


def test_shell_admin_nav_lists_users_roles_permissions():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "['Users', '/users'" in shell or '"/users"' in shell or "label: 'Users'" in shell
    assert "/admin/roles" in shell
    assert "/admin/permissions" in shell
    # Stage 95 N1 — Admin section renamed User Management (MVP Navigation)
    assert "User Management" in shell or "Admin" in shell
    # Stage 81 — split labels (not combined "Users & Roles" only)
    assert "Roles" in shell and "Permissions" in shell


def test_users_page_defers_roles_permissions_to_admin_routes():
    users = (ROOT / "frontend/app/users/page.tsx").read_text(encoding="utf-8")
    assert "Admin → Roles" in users or "/admin/roles" in users
    assert "Admin → Permissions" in users or "/admin/permissions" in users
    assert "Create custom role" not in users
    assert "Permission matrix" not in users


def test_rbac_menu_maps_admin_routes_to_users_module():
    rbac = (ROOT / "backend/app/rbac.py").read_text(encoding="utf-8")
    assert '"/admin/roles": "users"' in rbac or "'/admin/roles': 'users'" in rbac
    assert '"/admin/permissions": "users"' in rbac or "'/admin/permissions': 'users'" in rbac
