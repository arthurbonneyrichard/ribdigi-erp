"""SEC-M2 / SEC-M5 Phase C — omit JWTs from JSON when httpOnly cookies are ON.

Flag default remains OFF: legacy clients still receive access/refresh in JSON.
When ON: login / refresh return null tokens + cookie_session=true; cookies carry
the session. Does **not** close SEC-M2 (staging soak still required) or SEC-M5.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.config import Settings
from app import session_cookies as cookie_svc

pytestmark = pytest.mark.security

ROOT = Path(__file__).resolve().parents[2]


def test_sec_m2_phase_c_flag_still_defaults_off():
    cfg = Settings(APP_ENV="development")
    assert cfg.AUTH_HTTPONLY_COOKIES_ENABLED is False


def test_sec_m2_phase_c_json_auth_tokens_helper_dual_mode(monkeypatch):
    monkeypatch.setattr("app.session_cookies.settings.AUTH_HTTPONLY_COOKIES_ENABLED", False)
    off = cookie_svc.json_auth_tokens(access_token="a", refresh_token="r")
    assert off == {"access_token": "a", "refresh_token": "r", "cookie_session": False}

    monkeypatch.setattr("app.session_cookies.settings.AUTH_HTTPONLY_COOKIES_ENABLED", True)
    on = cookie_svc.json_auth_tokens(access_token="a", refresh_token="r")
    assert on == {"access_token": None, "refresh_token": None, "cookie_session": True}


@pytest.mark.asyncio
async def test_sec_m2_phase_c_flag_off_login_still_returns_json_tokens(client, monkeypatch):
    ac, seed = client
    monkeypatch.setattr("app.session_cookies.settings.AUTH_HTTPONLY_COOKIES_ENABLED", False)
    monkeypatch.setattr("app.security.settings.AUTH_HTTPONLY_COOKIES_ENABLED", False)
    monkeypatch.setattr("app.api.settings.AUTH_HTTPONLY_COOKIES_ENABLED", False)

    login = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": "mgr@alpha.example.com",
            "password": "SecurePass123!",
            "tenant_id": "alpha",
        },
    )
    assert login.status_code == 200, login.text
    body = login.json()["data"]
    assert body.get("cookie_session") is False
    assert body.get("access_token")
    assert body.get("refresh_token")
    assert cookie_svc.ACCESS_COOKIE not in ac.cookies


@pytest.mark.asyncio
async def test_sec_m2_phase_c_flag_on_login_omits_json_tokens(client, monkeypatch):
    ac, seed = client
    monkeypatch.setattr("app.session_cookies.settings.AUTH_HTTPONLY_COOKIES_ENABLED", True)
    monkeypatch.setattr("app.security.settings.AUTH_HTTPONLY_COOKIES_ENABLED", True)
    monkeypatch.setattr("app.api.settings.AUTH_HTTPONLY_COOKIES_ENABLED", True)
    monkeypatch.setattr("app.session_cookies.settings.AUTH_COOKIE_SECURE", False)

    login = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": "mgr@alpha.example.com",
            "password": "SecurePass123!",
            "tenant_id": "alpha",
        },
    )
    assert login.status_code == 200, login.text
    body = login.json()["data"]
    assert body.get("cookie_session") is True
    assert body.get("access_token") is None
    assert body.get("refresh_token") is None
    assert body.get("token_type") == "Bearer"
    assert body.get("user")
    assert cookie_svc.ACCESS_COOKIE in ac.cookies
    assert cookie_svc.REFRESH_COOKIE in ac.cookies
    assert cookie_svc.CSRF_COOKIE in ac.cookies


@pytest.mark.asyncio
async def test_sec_m2_phase_c_flag_on_refresh_omits_json_tokens(client, monkeypatch):
    ac, seed = client
    monkeypatch.setattr("app.session_cookies.settings.AUTH_HTTPONLY_COOKIES_ENABLED", True)
    monkeypatch.setattr("app.security.settings.AUTH_HTTPONLY_COOKIES_ENABLED", True)
    monkeypatch.setattr("app.api.settings.AUTH_HTTPONLY_COOKIES_ENABLED", True)
    monkeypatch.setattr("app.session_cookies.settings.AUTH_COOKIE_SECURE", False)

    login = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": "mgr@alpha.example.com",
            "password": "SecurePass123!",
            "tenant_id": "alpha",
        },
    )
    assert login.status_code == 200, login.text
    csrf = ac.cookies.get(cookie_svc.CSRF_COOKIE)
    assert csrf

    refreshed = await ac.post(
        "/api/v1/auth/refresh",
        json={},
        headers={cookie_svc.CSRF_HEADER: csrf},
        cookies={
            cookie_svc.REFRESH_COOKIE: ac.cookies.get(cookie_svc.REFRESH_COOKIE),
            cookie_svc.CSRF_COOKIE: csrf,
        },
    )
    assert refreshed.status_code == 200, refreshed.text
    body = refreshed.json()["data"]
    assert body.get("cookie_session") is True
    assert body.get("access_token") is None
    assert body.get("refresh_token") is None
    # Rotated cookies present
    assert cookie_svc.ACCESS_COOKIE in ac.cookies
    assert cookie_svc.REFRESH_COOKIE in ac.cookies


@pytest.mark.asyncio
async def test_sec_m2_phase_c_flag_off_refresh_still_returns_json_tokens(client, monkeypatch):
    ac, seed = client
    monkeypatch.setattr("app.session_cookies.settings.AUTH_HTTPONLY_COOKIES_ENABLED", False)
    monkeypatch.setattr("app.security.settings.AUTH_HTTPONLY_COOKIES_ENABLED", False)
    monkeypatch.setattr("app.api.settings.AUTH_HTTPONLY_COOKIES_ENABLED", False)

    login = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": "mgr@alpha.example.com",
            "password": "SecurePass123!",
            "tenant_id": "alpha",
        },
    )
    assert login.status_code == 200, login.text
    refresh = login.json()["data"]["refresh_token"]
    assert refresh

    refreshed = await ac.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert refreshed.status_code == 200, refreshed.text
    body = refreshed.json()["data"]
    assert body.get("cookie_session") is False
    assert body.get("access_token")
    assert body.get("refresh_token")


def test_sec_m2_phase_c_persist_login_still_skips_ls_on_cookie_session():
    src = (ROOT / "frontend/lib/authSession.ts").read_text(encoding="utf-8")
    assert "persistLoginSession" in src
    assert "isCookieSessionResponse" in src
    assert "removeItem('token')" in src
    assert "cookie_session" in src


def test_sec_m2_phase_c_adr_and_honesty_still_open():
    adr = (ROOT / "docs/ADR_SESSION_COOKIE_DUAL_MODE.md").read_text(encoding="utf-8")
    assert "Phase C" in adr
    assert "remain **OPEN**" in adr or "still OPEN" in adr
    assert "do **not** mark M2 FIXED" in adr or "remain **OPEN**" in adr

    audit = (ROOT / "SECURITY_AUDIT.md").read_text(encoding="utf-8")
    assert "SEC-M2" in audit
    assert "Phase C" in audit or "PARTIAL" in audit or "Phase D" in audit
    for line in audit.splitlines():
        cells = [c.strip() for c in line.split("|")]
        if len(cells) < 5:
            continue
        finding_id = cells[1] if len(cells) > 1 else ""
        status_cell = cells[4] if len(cells) > 4 else ""
        if finding_id == "SEC-M2":
            assert "OPEN" in status_cell
            assert "FIXED" not in status_cell
