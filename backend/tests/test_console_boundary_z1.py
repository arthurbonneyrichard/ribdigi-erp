"""Stage 87 Z1 — Console boundary hardening + soft-delete honesty."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_middleware_exists_with_principal_cookie_guard():
    mw = (ROOT / "frontend/middleware.ts").read_text(encoding="utf-8")
    assert "ribdigi_principal" in mw
    assert "/platform" in mw
    assert "/security" in mw
    assert "platform" in mw and "tenant" in mw


def test_login_sets_principal_cookie():
    login = (ROOT / "frontend/app/page.tsx").read_text(encoding="utf-8")
    assert "ribdigi_principal" in login
    assert "document.cookie" in login


def test_security_uses_platform_shell_for_house():
    page = (ROOT / "frontend/app/security/page.tsx").read_text(encoding="utf-8")
    assert "PlatformShell" in page
    assert "principal === 'platform'" in page or 'principal === "platform"' in page


def test_soft_delete_honesty_copy():
    users = (ROOT / "frontend/app/users/page.tsx").read_text(encoding="utf-8")
    assert "hard_delete_claimed" in users or "ADR-003" in users
    assert "soft" in users.lower() or "no hard delete" in users.lower()
    platform_users = (ROOT / "frontend/app/platform/users/page.tsx").read_text(encoding="utf-8")
    assert "hard_delete_claimed" in platform_users or "ADR-003" in platform_users
