"""Stage 117 A1 — Platform audit ?module= PlatformShell leaves."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_platform_shell_audit_module_leaves_a1():
    shell = (ROOT / "frontend/components/PlatformShell.tsx").read_text(encoding="utf-8")
    assert "module=platform_tenants" in shell
    assert "module=platform_plans" in shell
    assert "module=platform_users" in shell
    assert "module=platform_settings" in shell
    assert "module=platform_email" in shell
    assert "Tenants Audit" in shell
    assert "Plans Audit" in shell
    assert "Platform Users Audit" in shell
    assert "Settings Audit" in shell
    assert "Email Audit" in shell


def test_platform_audit_page_honors_module_a1():
    page = (ROOT / "frontend/app/platform/audit/page.tsx").read_text(encoding="utf-8")
    assert "Stage 117" in page
    assert "module" in page
    assert "syncUrl" in page
