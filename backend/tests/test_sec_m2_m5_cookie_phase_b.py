"""SEC-M2 / SEC-M5 Phase B — cookie session client helpers (flag still default OFF)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.config import Settings

pytestmark = pytest.mark.security

ROOT = Path(__file__).resolve().parents[2]
FE = ROOT / "frontend"


def test_sec_m2_phase_b_flag_still_defaults_off():
    cfg = Settings(APP_ENV="development")
    assert cfg.AUTH_HTTPONLY_COOKIES_ENABLED is False


def test_sec_m2_phase_b_prod_example_keeps_flag_off():
    text = (ROOT / ".env.production.example").read_text(encoding="utf-8")
    assert "AUTH_HTTPONLY_COOKIES_ENABLED=false" in text


def test_sec_m2_phase_b_auth_session_helpers_exist():
    src = (FE / "lib/authSession.ts").read_text(encoding="utf-8")
    assert "persistLoginSession" in src
    assert "prefersCookieSession" in src
    assert "getBearerToken" in src
    assert "COOKIE_SESSION_MARKER" in src
    assert "cookie_session" in src
    # Must clear tokens when cookie_session is true
    assert "removeItem('token')" in src
    assert "removeItem('refresh_token')" in src
    assert "setItem(COOKIE_SESSION_MARKER" in src or 'setItem(COOKIE_SESSION_MARKER' in src


def test_sec_m2_phase_b_login_uses_persist_helper():
    page = (FE / "app/page.tsx").read_text(encoding="utf-8")
    assert "persistLoginSession" in page
    # finishLogin must not write tokens directly anymore
    assert "localStorage.setItem('token'" not in page
    assert "localStorage.setItem('refresh_token'" not in page


def test_sec_m2_phase_b_api_prefers_cookie_bearer_omit():
    api = (FE / "lib/api.ts").read_text(encoding="utf-8")
    assert "getBearerToken" in api
    assert "apiFetch" in api
    assert "credentials: 'include'" in api
    assert "from './authSession'" in api or 'from "./authSession"' in api


def test_sec_m2_phase_b_high_traffic_sites_use_apifetch():
    dashboard = (FE / "app/dashboard/page.tsx").read_text(encoding="utf-8")
    assert "apiFetch" in dashboard
    assert "localStorage.getItem('token')" not in dashboard

    pos = (FE / "app/pos/page.tsx").read_text(encoding="utf-8")
    assert "apiFetch" in pos
    assert "localStorage.getItem('token')" not in pos

    evidence = (FE / "lib/platformEvidence.ts").read_text(encoding="utf-8")
    assert "apiFetch" in evidence
    assert "localStorage.getItem('token')" not in evidence

    shell = (FE / "components/Shell.tsx").read_text(encoding="utf-8")
    assert "apiFetch" in shell
    assert "hasAuthSession" in shell
    assert "clearLoginSession" in shell


def test_sec_m2_phase_b_app_pages_have_no_raw_token_reads():
    """Phase B remainder: no raw localStorage token reads under frontend/app or components."""
    offenders = []
    for root in (FE / "app", FE / "components"):
        if not root.exists():
            continue
        for path in root.rglob("*.tsx"):
            text = path.read_text(encoding="utf-8")
            if "localStorage.getItem('token')" in text or 'localStorage.getItem("token")' in text:
                offenders.append(str(path.relative_to(FE)))
            if "localStorage.getItem('access_token')" in text:
                offenders.append(f"{path.relative_to(FE)}:access_token")
    assert offenders == [], f"raw token localStorage sites remain: {offenders}"


def test_sec_m2_phase_b_helpers_still_support_bearer_dual_mode():
    """Dual-mode: helpers may still read token when cookie session is off."""
    src = (FE / "lib/authSession.ts").read_text(encoding="utf-8")
    assert "getBearerToken" in src
    assert "localStorage.getItem('token')" in src
    api = (FE / "lib/api.ts").read_text(encoding="utf-8")
    assert "getBearerToken" in api
    assert "credentials: 'include'" in api


def test_sec_m2_phase_b_adr_documents_phase_b_open():
    adr = (ROOT / "docs/ADR_SESSION_COOKIE_DUAL_MODE.md").read_text(encoding="utf-8")
    assert "Phase B" in adr
    assert "authSession" in adr
    assert "remain **OPEN**" in adr or "still OPEN" in adr
    assert "do **not** mark M2 FIXED" in adr or "remain **OPEN**" in adr


def test_sec_m2_phase_b_honesty_surfaces_not_fixed():
    audit = (ROOT / "SECURITY_AUDIT.md").read_text(encoding="utf-8")
    assert "SEC-M2" in audit
    assert (
        "Phase B PARTIAL" in audit
        or "Phase C PARTIAL" in audit
        or "OPEN (Phase B PARTIAL" in audit
        or "OPEN (Phase C PARTIAL" in audit
    )
    # Inventory table rows must stay OPEN (not FIXED) for M2/M5
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
            assert "OPEN" in status_cell
            assert "FIXED" not in status_cell
