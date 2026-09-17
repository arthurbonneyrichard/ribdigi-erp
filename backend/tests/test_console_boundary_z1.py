"""Stage 87 Z1 — Console boundary hardening + soft-delete honesty.

SEC-M5 Phase D: principal cookie is no longer a trusted console boundary;
Shell / PlatformShell derive principal from authenticated GET /me.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_middleware_clears_legacy_principal_cookie_not_trusted():
    mw = (ROOT / "frontend/middleware.ts").read_text(encoding="utf-8")
    assert "ribdigi_principal" in mw
    assert "Phase D" in mw or "SEC-M5" in mw or "/me" in mw
    # Must not redirect based on forgeable principal cookie
    assert "principal === 'platform'" not in mw
    assert 'principal === "platform"' not in mw
    assert "/security" in mw or "isPublic" in mw


def test_login_uses_persist_helper_not_raw_principal_cookie():
    login = (ROOT / "frontend/app/page.tsx").read_text(encoding="utf-8")
    assert "persistLoginSession" in login
    assert "ribdigi_principal" not in login
    auth = (ROOT / "frontend/lib/authSession.ts").read_text(encoding="utf-8")
    assert "applyPrincipalFromMe" in auth or "setMemoryPrincipal" in auth
    assert "document.cookie = `ribdigi_principal=" not in auth


def test_security_uses_platform_shell_for_house():
    page = (ROOT / "frontend/app/security/page.tsx").read_text(encoding="utf-8")
    assert "PlatformShell" in page
    assert "principal === 'platform'" in page or 'principal === "platform"' in page
    assert "applyPrincipalFromMe" in page or "api('/me')" in page


def test_soft_delete_honesty_copy():
    users = (ROOT / "frontend/app/users/page.tsx").read_text(encoding="utf-8")
    assert "hard_delete_claimed" in users or "ADR-003" in users
    assert "soft" in users.lower() or "no hard delete" in users.lower()
    platform_users = (ROOT / "frontend/app/platform/users/page.tsx").read_text(encoding="utf-8")
    assert "hard_delete_claimed" in platform_users or "ADR-003" in platform_users
