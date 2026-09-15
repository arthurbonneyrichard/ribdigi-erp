"""SEC-M2 / SEC-M5 — httpOnly session cookie + CSRF dual-mode foundation.

Feature flag ``AUTH_HTTPONLY_COOKIES_ENABLED`` defaults **False**. When off,
login/refresh/logout behavior is unchanged (Bearer tokens in JSON body only).

When on:
- Access + refresh JWTs are also issued as ``HttpOnly`` cookies (Secure/SameSite).
- A readable CSRF cookie + ``X-CSRF-Token`` header protect cookie-authenticated
  mutating requests (double-submit).
- Authorization Bearer remains accepted (migration dual-mode). Bearer-auth
  requests do not require CSRF.

Phase C: when the flag is ON, login/2FA/refresh JSON responses null out
``access_token`` / ``refresh_token`` so clients cannot keep writing Bearer
tokens to storage. Flag OFF keeps returning JWTs in JSON (backward compat).

Phase D (SEC-M5 FIXED) lives in the SPA: principal from ``/me`` in memory —
not this module's cookies.

Phase E (SEC-M2 FIXED): automated flag-ON soak suite
(``tests/test_sec_m2_cookie_soak.py``). Production default remains OFF — ops
enable on staging/prod is a cutover step.
"""

from __future__ import annotations

import secrets
from typing import Any

from fastapi import HTTPException, Request, Response

from app.config import settings
from app.security_runtime import is_production

ACCESS_COOKIE = "ribdigi_access"
REFRESH_COOKIE = "ribdigi_refresh"
CSRF_COOKIE = "ribdigi_csrf"
CSRF_HEADER = "X-CSRF-Token"

_UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def cookies_enabled() -> bool:
    return bool(getattr(settings, "AUTH_HTTPONLY_COOKIES_ENABLED", False))


def json_auth_tokens(*, access_token: str, refresh_token: str) -> dict[str, Any]:
    """Fields for auth JSON bodies under dual-mode.

    Flag OFF: return Bearer tokens in the body (legacy localStorage clients).
    Flag ON (Phase C): return null tokens — session rides httpOnly cookies only.
    Callers still pass real JWTs into ``attach_auth_cookies_if_enabled``.
    """
    if cookies_enabled():
        return {
            "access_token": None,
            "refresh_token": None,
            "cookie_session": True,
        }
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "cookie_session": False,
    }


def cookie_secure() -> bool:
    override = getattr(settings, "AUTH_COOKIE_SECURE", None)
    if override is not None:
        return bool(override)
    return is_production()


def cookie_samesite() -> str:
    raw = (getattr(settings, "AUTH_COOKIE_SAMESITE", None) or "lax").strip().lower()
    if raw not in {"lax", "strict", "none"}:
        return "lax"
    return raw


def cookie_domain() -> str | None:
    domain = (getattr(settings, "AUTH_COOKIE_DOMAIN", None) or "").strip()
    return domain or None


def issue_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def _base_cookie_kwargs(*, httponly: bool, max_age: int) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "path": "/",
        "httponly": httponly,
        "secure": cookie_secure(),
        "samesite": cookie_samesite(),
        "max_age": max_age,
    }
    domain = cookie_domain()
    if domain:
        kwargs["domain"] = domain
    return kwargs


def set_csrf_cookie(response: Response, csrf_token: str | None = None) -> str:
    """Set/rotate the readable CSRF cookie only."""
    csrf = csrf_token or issue_csrf_token()
    refresh_max = max(60, int(settings.REFRESH_TOKEN_EXPIRE_DAYS) * 86400)
    response.set_cookie(
        CSRF_COOKIE,
        csrf,
        **_base_cookie_kwargs(httponly=False, max_age=refresh_max),
    )
    return csrf


def set_session_cookies(
    response: Response,
    *,
    access_token: str,
    refresh_token: str,
    csrf_token: str | None = None,
) -> str:
    """Attach access/refresh/CSRF cookies. Returns the CSRF token used."""
    csrf = csrf_token or issue_csrf_token()
    access_max = max(60, int(settings.ACCESS_TOKEN_EXPIRE_MINUTES) * 60)
    refresh_max = max(access_max, int(settings.REFRESH_TOKEN_EXPIRE_DAYS) * 86400)

    response.set_cookie(
        ACCESS_COOKIE,
        access_token,
        **_base_cookie_kwargs(httponly=True, max_age=access_max),
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh_token,
        **_base_cookie_kwargs(httponly=True, max_age=refresh_max),
    )
    # CSRF must be readable by JS so the SPA can mirror it into X-CSRF-Token.
    response.set_cookie(
        CSRF_COOKIE,
        csrf,
        **_base_cookie_kwargs(httponly=False, max_age=refresh_max),
    )
    return csrf


def clear_session_cookies(response: Response) -> None:
    domain = cookie_domain()
    for name in (ACCESS_COOKIE, REFRESH_COOKIE, CSRF_COOKIE):
        kwargs: dict[str, Any] = {"path": "/"}
        if domain:
            kwargs["domain"] = domain
        response.delete_cookie(name, **kwargs)


def attach_auth_cookies_if_enabled(
    response: Response,
    *,
    access_token: str,
    refresh_token: str,
) -> str | None:
    """No-op when flag is off. Returns CSRF token when cookies were set."""
    if not cookies_enabled():
        return None
    return set_session_cookies(
        response, access_token=access_token, refresh_token=refresh_token
    )


def clear_auth_cookies_if_enabled(response: Response) -> None:
    if cookies_enabled():
        clear_session_cookies(response)


def access_token_from_request(request: Request) -> str | None:
    raw = (request.cookies.get(ACCESS_COOKIE) or "").strip()
    return raw or None


def refresh_token_from_request(request: Request) -> str | None:
    raw = (request.cookies.get(REFRESH_COOKIE) or "").strip()
    return raw or None


def csrf_token_from_request(request: Request) -> str | None:
    raw = (request.cookies.get(CSRF_COOKIE) or "").strip()
    return raw or None


def assert_csrf_for_cookie_auth(request: Request) -> None:
    """Double-submit CSRF for cookie-authenticated unsafe methods."""
    method = (request.method or "GET").upper()
    if method not in _UNSAFE_METHODS:
        return
    cookie_csrf = csrf_token_from_request(request) or ""
    header_name = (getattr(settings, "AUTH_CSRF_HEADER", None) or CSRF_HEADER).strip() or CSRF_HEADER
    header_csrf = (request.headers.get(header_name) or "").strip()
    if not cookie_csrf or not header_csrf or not secrets.compare_digest(cookie_csrf, header_csrf):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "CSRF_VALIDATION_FAILED",
                "message": "CSRF token missing or mismatched for cookie session",
            },
        )
