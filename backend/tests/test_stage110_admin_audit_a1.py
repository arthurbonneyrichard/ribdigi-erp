"""Stage 110 A1 — Admin Create Role hash & tenant Audit module leaves."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_shell_create_role_and_audit_module_leaves_a1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "/admin/roles#create" in shell
    assert "Create Role" in shell
    assert "/audit?module=auth" in shell
    assert "/audit?module=sales" in shell
    assert "Auth Audit" in shell
    assert "Sales Audit" in shell


def test_roles_create_anchor_a1():
    roles = (ROOT / "frontend/app/admin/roles/page.tsx").read_text(encoding="utf-8")
    assert 'id="create"' in roles
    assert "scrollIntoView" in roles
    assert "Stage 110" in roles or "#create" in roles


def test_audit_module_url_sync_a1():
    audit = (ROOT / "frontend/app/audit/page.tsx").read_text(encoding="utf-8")
    assert "module" in audit
    assert "syncUrl" in audit
    assert "Stage 110" in audit
