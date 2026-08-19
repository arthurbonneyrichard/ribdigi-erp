"""Stage 108 U1 — Users directory leaves discoverability."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_shell_users_directory_leaves_u1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "/users?is_active=true" in shell
    assert "/users?is_active=false" in shell
    assert "Active Users" in shell
    assert "Inactive Users" in shell


def test_platform_shell_users_directory_leaves_u1():
    shell = (ROOT / "frontend/components/PlatformShell.tsx").read_text(encoding="utf-8")
    assert "/platform/users?is_active=true" in shell
    assert "/platform/users?is_active=false" in shell
    assert "Active Users" in shell
    assert "Inactive Users" in shell


def test_users_pages_keep_is_active_url_sync_u1():
    users = (ROOT / "frontend/app/users/page.tsx").read_text(encoding="utf-8")
    assert "is_active" in users
    assert "syncUrl" in users
    platform = (ROOT / "frontend/app/platform/users/page.tsx").read_text(encoding="utf-8")
    assert "is_active" in platform
    assert "syncUrl" in platform
