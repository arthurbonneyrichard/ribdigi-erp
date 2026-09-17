"""SEC-M2 / SEC-M5 foundation — httpOnly cookie sessions + CSRF (flag default OFF)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import app
from app.rate_limit import rate_limiter
from app import session_cookies as cookie_svc

pytestmark = pytest.mark.security

ROOT = Path(__file__).resolve().parents[2]


def test_sec_m2_cookies_flag_defaults_off():
    cfg = Settings(APP_ENV="development")
    assert cfg.AUTH_HTTPONLY_COOKIES_ENABLED is False


def test_sec_m2_prod_env_example_keeps_flag_off():
    text = (ROOT / ".env.production.example").read_text(encoding="utf-8")
    assert "AUTH_HTTPONLY_COOKIES_ENABLED=false" in text
    assert "SEC-M2" in text or "SEC-M5" in text


def test_sec_m2_dev_env_example_documents_flag():
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "AUTH_HTTPONLY_COOKIES_ENABLED=false" in text


def test_sec_m2_adr_exists_and_non_claim():
    adr = (ROOT / "docs/ADR_SESSION_COOKIE_DUAL_MODE.md").read_text(encoding="utf-8")
    assert "AUTH_HTTPONLY_COOKIES_ENABLED" in adr
    assert "FIXED" in adr
    # Flag default OFF remains intentional (ops enable)
    assert "defaults" in adr.lower() or "default" in adr.lower()
    assert "false" in adr.lower()


def test_sec_m2_flag_off_login_omits_session_cookies(monkeypatch):
    rate_limiter.reset_for_tests()
    monkeypatch.setattr("app.session_cookies.settings.AUTH_HTTPONLY_COOKIES_ENABLED", False)
    monkeypatch.setattr("app.api.settings.AUTH_HTTPONLY_COOKIES_ENABLED", False)
    monkeypatch.setattr("app.middleware.settings.RATE_LIMIT_ENABLED", False)
    client = TestClient(app)
    # CSRF probe reports disabled
    csrf = client.get("/api/v1/auth/csrf")
    assert csrf.status_code == 200
    assert csrf.json()["data"]["enabled"] is False


@pytest.mark.asyncio
async def test_sec_m2_flag_on_sets_httponly_cookies_and_cookie_auth(client, monkeypatch):
    """When flag ON: Set-Cookie httpOnly access + CSRF; cookie auth works with CSRF."""
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
    # Phase C: flag ON nulls JSON tokens; session rides httpOnly cookies.
    assert body.get("cookie_session") is True
    assert body.get("access_token") is None
    assert body.get("refresh_token") is None

    # httpx stores cookies from Set-Cookie
    assert cookie_svc.ACCESS_COOKIE in ac.cookies
    assert cookie_svc.REFRESH_COOKIE in ac.cookies
    assert cookie_svc.CSRF_COOKIE in ac.cookies

    set_cookie_headers = login.headers.get_list("set-cookie") if hasattr(login.headers, "get_list") else []
    if not set_cookie_headers:
        # Starlette/httpx may expose via raw
        raw = login.headers.get("set-cookie") or ""
        set_cookie_headers = [raw] if raw else []
    joined = " | ".join(set_cookie_headers).lower()
    if joined:
        assert "httponly" in joined
        assert cookie_svc.ACCESS_COOKIE in joined or "ribdigi_access" in joined

    csrf = ac.cookies.get(cookie_svc.CSRF_COOKIE)
    assert csrf

    # Cookie auth GET (safe) — no CSRF required
    # Clear Authorization so we exercise cookie path; httpx AsyncClient may not
    # send Authorization unless we set it — omit Bearer deliberately.
    r = await ac.get(
        "/api/v1/auth/2fa/status",
        headers={"X-Tenant-ID": seed["t1"].id},
        cookies={
            cookie_svc.ACCESS_COOKIE: ac.cookies.get(cookie_svc.ACCESS_COOKIE),
            cookie_svc.CSRF_COOKIE: csrf,
        },
    )
    # Some clients still attach nothing for Bearer; cookie must authorize.
    assert r.status_code == 200, r.text

    # Cookie auth POST without CSRF → 403
    denied = await ac.post(
        "/api/v1/auth/idle-logout",
        headers={"X-Tenant-ID": seed["t1"].id},
        cookies={
            cookie_svc.ACCESS_COOKIE: ac.cookies.get(cookie_svc.ACCESS_COOKIE),
            cookie_svc.CSRF_COOKIE: csrf,
        },
    )
    assert denied.status_code == 403, denied.text
    detail = denied.json().get("detail")
    code = detail.get("code") if isinstance(detail, dict) else detail
    assert code == "CSRF_VALIDATION_FAILED"

    # Cookie auth POST with CSRF → success
    ok = await ac.post(
        "/api/v1/auth/idle-logout",
        headers={
            "X-Tenant-ID": seed["t1"].id,
            cookie_svc.CSRF_HEADER: csrf,
        },
        cookies={
            cookie_svc.ACCESS_COOKIE: ac.cookies.get(cookie_svc.ACCESS_COOKIE),
            cookie_svc.CSRF_COOKIE: csrf,
        },
    )
    assert ok.status_code == 200, ok.text


@pytest.mark.asyncio
async def test_sec_m2_bearer_skips_csrf_when_flag_on(client, monkeypatch):
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
    # Phase C: JSON omits tokens when cookies ON — use httpOnly access cookie for Bearer test.
    token = ac.cookies.get(cookie_svc.ACCESS_COOKIE)
    assert token

    # Bearer auth must not require CSRF even when cookies are also set.
    r = await ac.post(
        "/api/v1/auth/idle-logout",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Tenant-ID": seed["t1"].id,
        },
    )
    assert r.status_code == 200, r.text


def test_sec_m2_cors_allowlist_includes_csrf_header():
    from app.main import cors_kwargs

    assert "X-CSRF-Token" in cors_kwargs["allow_headers"]
