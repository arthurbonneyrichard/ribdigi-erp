"""Security middleware: headers, rate limiting, and HTTP metrics."""

from __future__ import annotations

import ipaddress
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.config import settings
from app.rate_limit import rate_limiter


_TRUSTED_NETS_CACHE: tuple[str, tuple] = ("", ())


def _trusted_proxy_nets() -> tuple:
    """TRUSTED_PROXY_IPS parsed once per value: single addresses and CIDR ranges (Docker networks)."""
    global _TRUSTED_NETS_CACHE
    raw = settings.TRUSTED_PROXY_IPS or ""
    if _TRUSTED_NETS_CACHE[0] == raw:
        return _TRUSTED_NETS_CACHE[1]
    nets = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            nets.append(ipaddress.ip_network(part, strict=False))
        except ValueError:
            continue
    _TRUSTED_NETS_CACHE = (raw, tuple(nets))
    return _TRUSTED_NETS_CACHE[1]


def _is_trusted_proxy(hop: str, nets: tuple) -> bool:
    try:
        addr = ipaddress.ip_address(hop)
    except ValueError:
        return False
    return any(addr in net for net in nets)


def client_ip_from_request(request: Request) -> str:
    """Rate-limit IP: rightmost XFF hop, or the trusted-proxy walk when configured.

    Proxies append to X-Forwarded-For, so only the right-hand end is written by our own proxies;
    anything to the left came from the caller and is never used while a nearer hop exists.
    """
    peer = request.client.host if request.client else ""
    hops = [part.strip() for part in (request.headers.get("x-forwarded-for") or "").split(",") if part.strip()]
    nets = _trusted_proxy_nets()
    # X-Forwarded-For is only believed when the connection itself came from a proxy. A caller that
    # reached us directly (a public peer, or with TRUSTED_PROXY_IPS set any peer not listed) is
    # judged by its own address, whatever header it sends. Behind uvicorn's proxy-header handling
    # (FORWARDED_ALLOW_IPS = the Docker network) the peer is already the real visitor here.
    if peer and not (nets and _is_trusted_proxy(peer, nets)):
        try:
            peer_addr = ipaddress.ip_address(peer)
        except ValueError:
            peer_addr = None
        if peer_addr is not None and (nets or peer_addr.is_global):
            return peer
    if nets:
        for hop in reversed(hops):
            if not _is_trusted_proxy(hop, nets):
                return hop
        return peer or (hops[-1] if hops else "unknown")
    if hops:
        # Without a configured proxy list, skip private/loopback hops (Docker-network proxies such as
        # Traefik and the Next.js /api proxy) and use the nearest public address. Anything to its left
        # was written by the caller and is ignored.
        for hop in reversed(hops):
            try:
                if ipaddress.ip_address(hop).is_global:
                    return hop
            except ValueError:
                continue
        return hops[-1]
    return peer or "unknown"

STOREFRONT_WRITE_PREFIXES = (
    "/api/v1/storefront/cart",
    "/api/v1/storefront/checkout",
    "/api/v1/storefront/payments/webhook",
)

STOREFRONT_PUBLIC_PREFIXES = (
    "/api/v1/storefront/bootstrap",
    "/api/v1/storefront/orders",
    "/api/v1/storefront/account",
    # Restaurant website (menu, online orders, bookings): guests get their own bucket too.
    "/api/v1/public/restaurant-site",
    "/api/v1/public/menu",
    # Hotel booking page: same reasoning, guests on their own bucket away from staff.
    "/api/v1/public/hotel-booking",
)

AUTH_PATH_PREFIXES = (
    "/api/v1/auth/login",
    "/api/v1/auth/staff-login",
    "/api/v1/auth/refresh",
    "/api/v1/auth/2fa/verify",
    "/api/v1/auth/webauthn/login",
    "/api/v1/auth/password-reset",
    "/api/v1/auth/password-reset-request",
    "/api/v1/auth/verify-email",
    "/api/v1/auth/resend-verification",
    "/api/v1/tenants",
    "/api/v1/storefront/account/login",
    "/api/v1/storefront/account/register",
)


# Till print agents poll about once a second. One shop address can hold several, so they get
# their own bucket (room for about 20) instead of using up the shop's other requests.
PRINT_AGENT_PREFIX = "/api/v1/printers/agent/"
PRINT_AGENT_PER_MINUTE = 1500


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
    """Sliding-window limiter keyed by client IP + route class + tenant scope.

    Tenant scope uses ``X-Tenant-ID`` when present so API buckets are isolated
    per tenant on shared egress IPs (BR-18.1). Plan-tier caps remain deferred.
    """

    def __init__(self, app):
        super().__init__(app)

    def _client_ip(self, request: Request) -> str:
        return client_ip_from_request(request)

    def _tenant_scope(self, request: Request) -> str:
        if any(request.url.path.startswith(p) for p in AUTH_PATH_PREFIXES):
            # The header is caller-controlled: on sign-in routes a new value per request would open
            # a fresh bucket each time, so every auth request from one IP shares one bucket.
            return "anon"
        raw = (request.headers.get("x-tenant-id") or "").strip()
        return raw or "anon"

    def _limit_for_path(self, path: str, method: str = "GET") -> int:
        if path.startswith(PRINT_AGENT_PREFIX):
            return PRINT_AGENT_PER_MINUTE
        if any(path.startswith(p) for p in AUTH_PATH_PREFIXES):
            return settings.RATE_LIMIT_AUTH_PER_MINUTE
        if any(path.startswith(p) for p in STOREFRONT_WRITE_PREFIXES + STOREFRONT_PUBLIC_PREFIXES):
            # Shoppers browse many pages; cart and checkout changes get the tighter write limit.
            if method.upper() in {"GET", "HEAD"}:
                return settings.RATE_LIMIT_READ_PER_MINUTE
            return settings.RATE_LIMIT_PER_MINUTE
        if method.upper() in {"GET", "HEAD"}:
            return settings.RATE_LIMIT_READ_PER_MINUTE
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
        # Tills ask the liveness check to decide online/offline; a busy shop network must not make
        # them look offline. The deep readiness check (/health/ready) stays limited.
        if (
            path == "/api/v1/health"
            and request.method in {"GET", "HEAD"}
            and request.query_params.get("deep", "").lower() not in {"1", "true", "yes"}
        ):
            return await call_next(request)
        method = request.method.upper()
        limit = self._limit_for_path(path, method)
        scope = self._tenant_scope(request)
        if path.startswith(PRINT_AGENT_PREFIX):
            # The tenant header means nothing here, so it cannot be used to open more buckets.
            kind, scope = "print-agent", "anon"
        elif any(path.startswith(p) for p in AUTH_PATH_PREFIXES):
            kind = "auth"
        elif any(path.startswith(p) for p in STOREFRONT_WRITE_PREFIXES + STOREFRONT_PUBLIC_PREFIXES):
            # Own bucket: shop visitors must not share a counter with staff using the ERP.
            kind = "storefront-read" if method in {"GET", "HEAD"} else "storefront-write"
        elif method in {"GET", "HEAD"}:
            kind = "read"
        else:
            kind = "api"
        key = f"{self._client_ip(request)}:{kind}:{scope}"
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
                },
            )
        response = await call_next(request)
        response.headers.setdefault("X-RateLimit-Limit", str(limit))
        response.headers.setdefault("X-RateLimit-Remaining", str(remaining))
        return response


class MetricsMiddleware(BaseHTTPMiddleware):
    """Record coarse HTTP counters for /api/v1/metrics."""

    async def dispatch(self, request: Request, call_next) -> Response:
        from app import metrics as metrics_svc

        if not metrics_svc.metrics_enabled():
            return await call_next(request)
        start = time.perf_counter()
        response = await call_next(request)
        metrics_svc.observe_request(
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_seconds=time.perf_counter() - start,
        )
        return response
