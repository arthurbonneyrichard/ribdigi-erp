"""Security middleware: headers and rate limiting (Redis or memory)."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.config import settings
from app.rate_limit import rate_limiter

AUTH_PATH_PREFIXES = (
    "/api/v1/auth/login",
    "/api/v1/auth/2fa/verify",
    "/api/v1/auth/password-reset",
    "/api/v1/auth/password-reset-request",
    "/api/v1/auth/verify-email",
    "/api/v1/tenants",
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("X-XSS-Protection", "0")
        response.headers.setdefault(
            "Permissions-Policy",
            "geolocation=(), microphone=(), camera=()",
        )
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        # API responses are JSON; deny active content and framing by default.
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
        )
        if settings.APP_ENV.lower() == "production":
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )
            response.headers.setdefault("Cache-Control", "no-store")
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window limiter keyed by client IP + route class (auth vs api)."""

    def __init__(self, app):
        super().__init__(app)

    def _client_ip(self, request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        if request.client:
            return request.client.host
        return "unknown"

    def _limit_for_path(self, path: str) -> int:
        if any(path.startswith(p) for p in AUTH_PATH_PREFIXES):
            return settings.RATE_LIMIT_AUTH_PER_MINUTE
        return settings.RATE_LIMIT_PER_MINUTE

    # Kept for unit tests that call the memory path directly
    def _allow(self, key: str, limit: int, window_seconds: float = 60.0) -> tuple[bool, int]:
        allowed, retry_after, _remaining = rate_limiter._memory_allow(key, limit, window_seconds)
        return allowed, retry_after

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method == "OPTIONS":
            return await call_next(request)
        if not settings.RATE_LIMIT_ENABLED:
            return await call_next(request)

        path = request.url.path
        limit = self._limit_for_path(path)
        kind = "auth" if any(path.startswith(p) for p in AUTH_PATH_PREFIXES) else "api"
        key = f"{self._client_ip(request)}:{kind}"
        allowed, retry_after, remaining = await rate_limiter.allow(key, limit)
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "success": False,
                    "data": None,
                    "message": "Rate limit exceeded. Try again shortly.",
                    "detail": "RATE_LIMIT_EXCEEDED",
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Backend": rate_limiter.backend,
                },
            )
        response = await call_next(request)
        response.headers.setdefault("X-RateLimit-Limit", str(limit))
        response.headers.setdefault("X-RateLimit-Remaining", str(remaining))
        response.headers.setdefault("X-RateLimit-Backend", rate_limiter.backend)
        return response
