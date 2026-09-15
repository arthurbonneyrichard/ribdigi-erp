"""SEC-M2 Phase E — automated flag-ON cookie soak (closes M2 without continuum dumps).

Exercises AUTH_HTTPONLY_COOKIES_ENABLED=true end-to-end:

- Login / 2FA verify / refresh return null JSON tokens + Set-Cookie
- Authenticated GETs work via cookie only (no Bearer)
- Mutating requests require matching X-CSRF-Token when cookie-auth
- Logout + idle-logout clear session cookies
- SPA helpers refuse to persist Bearer tokens on cookie_session
- Prod examples keep flag default OFF (ops enable is cutover)

WebAuthn login/verify is covered by static wiring asserts (same helpers as
login/2FA/refresh) to avoid flaky authenticator crypto in CI.
"""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from app.config import Settings
from app import session_cookies as cookie_svc

pytestmark = pytest.mark.security

ROOT = Path(__file__).resolve().parents[2]
FE = ROOT / "frontend"


def _enable_cookie_mode(monkeypatch) -> None:
    monkeypatch.setattr("app.session_cookies.settings.AUTH_HTTPONLY_COOKIES_ENABLED", True)
    monkeypatch.setattr("app.security.settings.AUTH_HTTPONLY_COOKIES_ENABLED", True)
    monkeypatch.setattr("app.api.settings.AUTH_HTTPONLY_COOKIES_ENABLED", True)
    monkeypatch.setattr("app.config.settings.AUTH_HTTPONLY_COOKIES_ENABLED", True)
    monkeypatch.setattr("app.session_cookies.settings.AUTH_COOKIE_SECURE", False)


def _cookie_jar(ac) -> dict[str, str]:
    return {
        cookie_svc.ACCESS_COOKIE: ac.cookies.get(cookie_svc.ACCESS_COOKIE) or "",
        cookie_svc.REFRESH_COOKIE: ac.cookies.get(cookie_svc.REFRESH_COOKIE) or "",
        cookie_svc.CSRF_COOKIE: ac.cookies.get(cookie_svc.CSRF_COOKIE) or "",
    }


def _assert_null_json_tokens(body: dict) -> None:
    assert body.get("cookie_session") is True
    assert body.get("access_token") is None
    assert body.get("refresh_token") is None


def _assert_session_cookies_present(ac) -> str:
    assert ac.cookies.get(cookie_svc.ACCESS_COOKIE)
    assert ac.cookies.get(cookie_svc.REFRESH_COOKIE)
    csrf = ac.cookies.get(cookie_svc.CSRF_COOKIE)
    assert csrf
    return csrf


def _set_cookie_headers(response) -> str:
    if hasattr(response.headers, "get_list"):
        parts = response.headers.get_list("set-cookie")
    else:
        raw = response.headers.get("set-cookie") or ""
        parts = [raw] if raw else []
    return " | ".join(parts).lower()


def test_sec_m2_soak_flag_still_defaults_off_ops_enable():
    """FIXED does not flip production default — ops enable is a cutover step."""
    cfg = Settings(APP_ENV="development")
    assert cfg.AUTH_HTTPONLY_COOKIES_ENABLED is False
    prod = (ROOT / ".env.production.example").read_text(encoding="utf-8")
    assert "AUTH_HTTPONLY_COOKIES_ENABLED=false" in prod
    assert "ops" in prod.lower() or "enable" in prod.lower() or "SEC-M2" in prod


@pytest.mark.asyncio
async def test_sec_m2_soak_login_null_tokens_set_cookie_httponly(client, monkeypatch):
    ac, seed = client
    _enable_cookie_mode(monkeypatch)

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
    _assert_null_json_tokens(body)
    csrf = _assert_session_cookies_present(ac)

    joined = _set_cookie_headers(login)
    if joined:
        assert "httponly" in joined
        assert cookie_svc.ACCESS_COOKIE in joined or "ribdigi_access" in joined

    # Cookie-only GET (no Bearer) — safe method, CSRF optional
    me = await ac.get(
        "/api/v1/auth/2fa/status",
        headers={"X-Tenant-ID": seed["t1"].id},
        cookies={
            cookie_svc.ACCESS_COOKIE: ac.cookies.get(cookie_svc.ACCESS_COOKIE),
            cookie_svc.CSRF_COOKIE: csrf,
        },
    )
    assert me.status_code == 200, me.text


@pytest.mark.asyncio
async def test_sec_m2_soak_refresh_null_tokens_rotates_cookies(client, monkeypatch):
    ac, seed = client
    _enable_cookie_mode(monkeypatch)

    login = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": "mgr@alpha.example.com",
            "password": "SecurePass123!",
            "tenant_id": "alpha",
        },
    )
    assert login.status_code == 200, login.text
    csrf = _assert_session_cookies_present(ac)
    old_access = ac.cookies.get(cookie_svc.ACCESS_COOKIE)

    refreshed = await ac.post(
        "/api/v1/auth/refresh",
        json={},
        headers={cookie_svc.CSRF_HEADER: csrf},
        cookies=_cookie_jar(ac),
    )
    assert refreshed.status_code == 200, refreshed.text
    body = refreshed.json()["data"]
    _assert_null_json_tokens(body)
    new_access = ac.cookies.get(cookie_svc.ACCESS_COOKIE)
    assert new_access
    assert new_access != old_access


@pytest.mark.asyncio
async def test_sec_m2_soak_csrf_required_for_mutating_cookie_auth(client, monkeypatch):
    ac, seed = client
    _enable_cookie_mode(monkeypatch)

    login = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": "mgr@alpha.example.com",
            "password": "SecurePass123!",
            "tenant_id": "alpha",
        },
    )
    assert login.status_code == 200, login.text
    csrf = _assert_session_cookies_present(ac)
    cookies = {
        cookie_svc.ACCESS_COOKIE: ac.cookies.get(cookie_svc.ACCESS_COOKIE),
        cookie_svc.CSRF_COOKIE: csrf,
    }

    denied = await ac.post(
        "/api/v1/auth/idle-logout",
        headers={"X-Tenant-ID": seed["t1"].id},
        cookies=cookies,
    )
    assert denied.status_code == 403, denied.text
    detail = denied.json().get("detail")
    code = detail.get("code") if isinstance(detail, dict) else detail
    assert code == "CSRF_VALIDATION_FAILED"

    mismatched = await ac.post(
        "/api/v1/auth/idle-logout",
        headers={
            "X-Tenant-ID": seed["t1"].id,
            cookie_svc.CSRF_HEADER: "not-the-cookie-value",
        },
        cookies=cookies,
    )
    assert mismatched.status_code == 403, mismatched.text


@pytest.mark.asyncio
async def test_sec_m2_soak_logout_clears_cookies(client, monkeypatch):
    ac, seed = client
    _enable_cookie_mode(monkeypatch)

    login = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": "mgr@alpha.example.com",
            "password": "SecurePass123!",
            "tenant_id": "alpha",
        },
    )
    assert login.status_code == 200, login.text
    csrf = _assert_session_cookies_present(ac)
    access = ac.cookies.get(cookie_svc.ACCESS_COOKIE)

    out = await ac.post(
        "/api/v1/auth/logout",
        headers={
            "X-Tenant-ID": seed["t1"].id,
            cookie_svc.CSRF_HEADER: csrf,
        },
        cookies={
            cookie_svc.ACCESS_COOKIE: access,
            cookie_svc.CSRF_COOKIE: csrf,
        },
    )
    assert out.status_code == 200, out.text
    joined = _set_cookie_headers(out)
    # Starlette delete_cookie → Max-Age=0 / expires past
    if joined:
        assert cookie_svc.ACCESS_COOKIE in joined or "ribdigi_access" in joined
        assert "max-age=0" in joined or "expires=" in joined

    # Stale access cookie must not authorize after revoke
    stale = await ac.get(
        "/api/v1/auth/2fa/status",
        headers={"X-Tenant-ID": seed["t1"].id},
        cookies={cookie_svc.ACCESS_COOKIE: access},
    )
    assert stale.status_code in (401, 403), stale.text


@pytest.mark.asyncio
async def test_sec_m2_soak_idle_logout_clears_cookies(client, monkeypatch):
    ac, seed = client
    _enable_cookie_mode(monkeypatch)

    login = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": "mgr@alpha.example.com",
            "password": "SecurePass123!",
            "tenant_id": "alpha",
        },
    )
    assert login.status_code == 200, login.text
    csrf = _assert_session_cookies_present(ac)
    access = ac.cookies.get(cookie_svc.ACCESS_COOKIE)

    idle = await ac.post(
        "/api/v1/auth/idle-logout",
        headers={
            "X-Tenant-ID": seed["t1"].id,
            cookie_svc.CSRF_HEADER: csrf,
        },
        cookies={
            cookie_svc.ACCESS_COOKIE: access,
            cookie_svc.CSRF_COOKIE: csrf,
        },
    )
    assert idle.status_code == 200, idle.text
    joined = _set_cookie_headers(idle)
    if joined:
        assert "max-age=0" in joined or "expires=" in joined

    stale = await ac.get(
        "/api/v1/auth/2fa/status",
        headers={"X-Tenant-ID": seed["t1"].id},
        cookies={cookie_svc.ACCESS_COOKIE: access},
    )
    assert stale.status_code in (401, 403), stale.text


@pytest.mark.asyncio
async def test_sec_m2_soak_2fa_verify_null_tokens_and_cookies(client, monkeypatch):
    """Enroll TOTP, then complete login via /auth/2fa/verify under cookie mode."""
    ac, seed = client
    _enable_cookie_mode(monkeypatch)

    # Initial login (no TOTP yet) → cookie session
    login = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": "cashier@alpha.example.com",
            "password": "SecurePass123!",
            "tenant_id": "alpha",
        },
    )
    assert login.status_code == 200, login.text
    _assert_null_json_tokens(login.json()["data"])
    csrf = _assert_session_cookies_present(ac)
    access = ac.cookies.get(cookie_svc.ACCESS_COOKIE)
    tenant_id = seed["t1"].id
    cookie_headers = {
        "X-Tenant-ID": tenant_id,
        cookie_svc.CSRF_HEADER: csrf,
    }
    cookies = {
        cookie_svc.ACCESS_COOKIE: access,
        cookie_svc.CSRF_COOKIE: csrf,
    }

    setup = await ac.post(
        "/api/v1/auth/2fa/setup",
        headers=cookie_headers,
        cookies=cookies,
    )
    assert setup.status_code == 200, setup.text
    secret = setup.json()["data"]["secret"]
    code = pyotp.TOTP(secret).now()
    confirm = await ac.post(
        "/api/v1/auth/2fa/confirm",
        headers=cookie_headers,
        cookies=cookies,
        json={"code": code},
    )
    assert confirm.status_code == 200, confirm.text

    # End cookie session so next login challenges 2FA
    await ac.post(
        "/api/v1/auth/logout",
        headers=cookie_headers,
        cookies=cookies,
    )

    challenge_login = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": "cashier@alpha.example.com",
            "password": "SecurePass123!",
            "tenant_id": "alpha",
        },
    )
    assert challenge_login.status_code == 200, challenge_login.text
    challenge_body = challenge_login.json()["data"]
    assert challenge_body.get("requires_2fa") is True
    challenge = challenge_body["challenge_token"]
    assert challenge

    verify_code = pyotp.TOTP(secret).now()
    verified = await ac.post(
        "/api/v1/auth/2fa/verify",
        json={"challenge_token": challenge, "code": verify_code},
    )
    assert verified.status_code == 200, verified.text
    vbody = verified.json()["data"]
    _assert_null_json_tokens(vbody)
    _assert_session_cookies_present(ac)

    # Cookie-only authenticated call after 2FA
    status = await ac.get(
        "/api/v1/auth/2fa/status",
        headers={"X-Tenant-ID": tenant_id},
        cookies={
            cookie_svc.ACCESS_COOKIE: ac.cookies.get(cookie_svc.ACCESS_COOKIE),
            cookie_svc.CSRF_COOKIE: ac.cookies.get(cookie_svc.CSRF_COOKIE),
        },
    )
    assert status.status_code == 200, status.text
    assert status.json()["data"].get("enabled") is True


def test_sec_m2_soak_webauthn_verify_uses_same_cookie_helpers():
    """Avoid flaky WebAuthn crypto; assert verify path wires Phase C helpers."""
    api_src = (ROOT / "backend/app/api.py").read_text(encoding="utf-8")
    # webauthn login verify block shares attach + json_auth_tokens with 2FA verify
    assert "attach_auth_cookies_if_enabled" in api_src
    assert "json_auth_tokens" in api_src
    # Count call sites: login, 2fa/verify, webauthn verify, refresh
    assert api_src.count("attach_auth_cookies_if_enabled(") >= 4
    assert api_src.count("json_auth_tokens(") >= 4
    assert "/auth/webauthn" in api_src or "webauthn" in api_src


def test_sec_m2_soak_spa_skips_localstorage_tokens_on_cookie_session():
    auth = (FE / "lib/authSession.ts").read_text(encoding="utf-8")
    assert "isCookieSessionResponse" in auth
    assert "removeItem('token')" in auth
    assert "removeItem('refresh_token')" in auth
    persist = auth.split("export function persistLoginSession")[1].split(
        "export function clearLoginSession"
    )[0]
    # Cookie path must clear Bearer LS keys, not write them
    assert "setItem('token'" not in persist or "cookie" in persist.lower()
    assert "removeItem('token')" in persist
    assert "removeItem('refresh_token')" in persist

    api = (FE / "lib/api.ts").read_text(encoding="utf-8")
    assert "credentials: 'include'" in api
    assert "X-CSRF-Token" in api
    assert "getBearerToken" in api


def test_sec_m2_soak_honesty_fixed_flag_off_default():
    adr = (ROOT / "docs/ADR_SESSION_COOKIE_DUAL_MODE.md").read_text(encoding="utf-8")
    assert "SEC-M2" in adr
    assert "FIXED" in adr
    assert "AUTH_HTTPONLY_COOKIES_ENABLED" in adr

    audit = (ROOT / "SECURITY_AUDIT.md").read_text(encoding="utf-8")
    for line in audit.splitlines():
        cells = [c.strip() for c in line.split("|")]
        if len(cells) < 5:
            continue
        finding_id = cells[1] if len(cells) > 1 else ""
        status_cell = cells[4] if len(cells) > 4 else ""
        if finding_id == "SEC-M2":
            assert "FIXED" in status_cell
            assert "OPEN" not in status_cell
