"""Stage 105 P1 — Permissions matrix honesty."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_shell_permissions_deeplinks_p1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "/admin/permissions#custom" in shell
    assert "/admin/permissions#system" in shell
    assert "Custom Permissions" in shell
    assert "System Permissions" in shell


def test_permissions_page_role_url_and_anchors_p1():
    page = (ROOT / "frontend/app/admin/permissions/page.tsx").read_text(encoding="utf-8")
    assert 'id="system"' in page
    assert 'id="custom"' in page
    assert "writePermissionsQuery" in page
    assert "scrollIntoView" in page
    assert "searchParams.set('role'" in page or 'searchParams.set("role"' in page
