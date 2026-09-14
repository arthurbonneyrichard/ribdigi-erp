"""SEC-M2 / SEC-M5 Phase D — replace UX-only ribdigi_principal with /me memory.

Closes SEC-M5 when principal is derived from authenticated login JSON / GET /me
in memory, LS principal is cleared and never treated as auth, and the forgeable
JS principal cookie is no longer set or used as a console boundary.

Does **not** close SEC-M2 (flag still default OFF; staging soak required).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.config import Settings

pytestmark = pytest.mark.security

ROOT = Path(__file__).resolve().parents[2]
FE = ROOT / "frontend"


def test_sec_m5_phase_d_flag_still_defaults_off():
    cfg = Settings(APP_ENV="development")
    assert cfg.AUTH_HTTPONLY_COOKIES_ENABLED is False


def test_sec_m5_phase_d_prod_example_keeps_flag_off():
    text = (ROOT / ".env.production.example").read_text(encoding="utf-8")
    assert "AUTH_HTTPONLY_COOKIES_ENABLED=false" in text


def test_sec_m5_phase_d_auth_session_memory_principal():
    src = (FE / "lib/authSession.ts").read_text(encoding="utf-8")
    assert "getMemoryPrincipal" in src
    assert "setMemoryPrincipal" in src
    assert "applyPrincipalFromMe" in src
    assert "clearPrincipalCookie" in src
    assert "Phase D" in src or "SEC-M5" in src
    # Must not write forgeable principal cookie from JS anymore
    assert "document.cookie = `ribdigi_principal=" not in src
    assert "document.cookie = 'ribdigi_principal=" not in src
    # Must clear LS principal (never treat as auth)
    assert "removeItem('principal')" in src
    # Logout clears memory + cookie
    assert "setMemoryPrincipal(null)" in src
    assert "clearPrincipalCookie()" in src
    # hasAuthSession body must not treat principal as session proof
    body = src.split("export function hasAuthSession(): boolean {")[1].split("}")[0]
    assert "getMemoryPrincipal" not in body
    assert "principal" not in body
    assert "localStorage.getItem('token')" in body or 'localStorage.getItem("token")' in body
    assert "prefersCookieSession" in body


def test_sec_m5_phase_d_persist_does_not_set_ls_principal_as_auth():
    src = (FE / "lib/authSession.ts").read_text(encoding="utf-8")
    persist = src.split("export function persistLoginSession")[1].split(
        "export function clearLoginSession"
    )[0]
    assert "setItem('principal'" not in persist
    assert "setMemoryPrincipal" in persist
    assert "removeItem('principal')" in persist
    assert "clearPrincipalCookie" in persist


def test_sec_m5_phase_d_middleware_does_not_trust_principal_cookie():
    mw = (FE / "middleware.ts").read_text(encoding="utf-8")
    assert "Phase D" in mw or "SEC-M5" in mw
    assert "GET /me" in mw or "/me" in mw
    # Must not redirect based on forgeable principal cookie value
    assert "principal === 'platform'" not in mw
    assert 'principal === "platform"' not in mw
    assert "principal === 'tenant'" not in mw
    # Still clears stale cookie if present
    assert "ribdigi_principal" in mw
    assert "maxAge: 0" in mw or "maxAge:0" in mw


def test_sec_m5_phase_d_shells_apply_principal_from_me():
    shell = (FE / "components/Shell.tsx").read_text(encoding="utf-8")
    assert "applyPrincipalFromMe" in shell
    assert "api('/me')" in shell or 'api("/me")' in shell

    platform = (FE / "components/PlatformShell.tsx").read_text(encoding="utf-8")
    assert "applyPrincipalFromMe" in platform
    assert "api('/me')" in platform or 'api("/me")' in platform


def test_sec_m5_phase_d_login_uses_persist_not_raw_principal_cookie():
    page = (FE / "app/page.tsx").read_text(encoding="utf-8")
    assert "persistLoginSession" in page
    assert "ribdigi_principal" not in page
    assert "document.cookie" not in page


def test_sec_m5_phase_d_no_app_reads_ls_principal_as_auth():
    offenders = []
    for root in (FE / "app", FE / "components", FE / "lib"):
        if not root.exists():
            continue
        for path in list(root.rglob("*.ts")) + list(root.rglob("*.tsx")):
            text = path.read_text(encoding="utf-8")
            if "localStorage.getItem('principal')" in text or 'localStorage.getItem("principal")' in text:
                offenders.append(str(path.relative_to(FE)))
            if "getItem('ribdigi_principal')" in text:
                offenders.append(f"{path.relative_to(FE)}:cookie-get")
    assert offenders == [], f"LS/cookie principal auth reads remain: {offenders}"


def test_sec_m5_phase_d_adr_and_honesty_m5_fixed_m2_open():
    adr = (ROOT / "docs/ADR_SESSION_COOKIE_DUAL_MODE.md").read_text(encoding="utf-8")
    assert "Phase D" in adr
    assert "SEC-M5" in adr

    audit = (ROOT / "SECURITY_AUDIT.md").read_text(encoding="utf-8")
    for line in audit.splitlines():
        cells = [c.strip() for c in line.split("|")]
        if len(cells) < 5:
            continue
        finding_id = cells[1] if len(cells) > 1 else ""
        status_cell = cells[4] if len(cells) > 4 else ""
        if finding_id == "SEC-M2":
            assert "OPEN" in status_cell
            assert "FIXED" not in status_cell
        if finding_id == "SEC-M5":
            assert "FIXED" in status_cell
            assert "OPEN" not in status_cell
