import pytest

from app.middleware import RateLimitMiddleware, AUTH_PATH_PREFIXES
from app.rate_limit import RateLimiter, rate_limiter
from app.config import Settings


def test_production_rejects_wildcard_cors():
    try:
        Settings(
            APP_ENV="production",
            JWT_SECRET_KEY="x" * 32,
            DEBUG=False,
            CORS_ORIGINS="*",
            RATE_LIMIT_ENABLED=True,
            EMAIL_ENABLED=False,
            SMS_ENABLED=False,
        )
        assert False, "expected validation error"
    except Exception as exc:
        assert "wildcard" in str(exc).lower() or "CORS" in str(exc)


def test_production_requires_rate_limit():
    try:
        Settings(
            APP_ENV="production",
            JWT_SECRET_KEY="x" * 32,
            DEBUG=False,
            CORS_ORIGINS="https://app.example.com",
            RATE_LIMIT_ENABLED=False,
            EMAIL_ENABLED=False,
            SMS_ENABLED=False,
        )
        assert False, "expected validation error"
    except Exception as exc:
        assert "RATE_LIMIT" in str(exc)


def test_production_rejects_require_redis_with_memory():
    try:
        Settings(
            APP_ENV="production",
            JWT_SECRET_KEY="x" * 32,
            DEBUG=False,
            CORS_ORIGINS="https://app.example.com",
            RATE_LIMIT_ENABLED=True,
            RATE_LIMIT_BACKEND="memory",
            RATE_LIMIT_REQUIRE_REDIS=True,
            EMAIL_ENABLED=False,
            SMS_ENABLED=False,
        )
        assert False, "expected validation error"
    except Exception as exc:
        assert "RATE_LIMIT_REQUIRE_REDIS" in str(exc) or "memory" in str(exc).lower()


def test_auth_path_prefixes_cover_login():
    assert any(p.endswith("/auth/login") for p in AUTH_PATH_PREFIXES)
    assert any(p.endswith("/auth/refresh") for p in AUTH_PATH_PREFIXES)


def test_rate_limit_headers_and_tenant_buckets(monkeypatch):
    """X-RateLimit-* headers; buckets isolate by X-Tenant-ID."""
    from fastapi.testclient import TestClient
    from app.main import app

    monkeypatch.setattr("app.middleware.settings.RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr("app.middleware.settings.RATE_LIMIT_PER_MINUTE", 2)
    monkeypatch.setattr("app.middleware.settings.RATE_LIMIT_AUTH_PER_MINUTE", 2)
    monkeypatch.setattr("app.rate_limit.settings.RATE_LIMIT_BACKEND", "memory")
    monkeypatch.setattr("app.rate_limit.settings.RATE_LIMIT_REQUIRE_REDIS", False)
    rate_limiter.reset_for_tests()

    client = TestClient(app)
    first = client.get("/api/v1/health", headers={"X-Tenant-ID": "tenant-alpha"})
    assert first.status_code == 200
    assert "X-RateLimit-Limit" in first.headers
    assert "X-RateLimit-Remaining" in first.headers
    assert "X-RateLimit-Backend" in first.headers
    assert first.headers.get("Cross-Origin-Opener-Policy") == "same-origin"

    assert client.get("/api/v1/health", headers={"X-Tenant-ID": "tenant-alpha"}).status_code == 200
    blocked = client.get("/api/v1/health", headers={"X-Tenant-ID": "tenant-alpha"})
    assert blocked.status_code == 429
    assert blocked.json()["detail"] == "RATE_LIMIT_EXCEEDED"
    assert "Retry-After" in blocked.headers
    assert blocked.headers.get("X-RateLimit-Remaining") == "0"

    other = client.get("/api/v1/health", headers={"X-Tenant-ID": "tenant-beta"})
    assert other.status_code == 200
    assert int(other.headers.get("X-RateLimit-Remaining", "0")) >= 0


def test_rate_limit_allows_under_cap(monkeypatch):
    mw = RateLimitMiddleware(app=None)
    monkeypatch.setattr("app.middleware.settings.RATE_LIMIT_PER_MINUTE", 3)
    monkeypatch.setattr("app.middleware.settings.RATE_LIMIT_AUTH_PER_MINUTE", 2)
    key = "127.0.0.1:api"
    assert mw._allow(key, 3)[0] is True
    assert mw._allow(key, 3)[0] is True
    assert mw._allow(key, 3)[0] is True
    assert mw._allow(key, 3)[0] is False


def test_security_headers_on_root():
    from fastapi.testclient import TestClient
    from app.main import app
    from app.rate_limit import rate_limiter

    rate_limiter.reset_for_tests()
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert "default-src 'none'" in response.headers.get("Content-Security-Policy", "")
    assert "X-RateLimit-Limit" in response.headers
    assert "X-RateLimit-Backend" in response.headers


@pytest.mark.asyncio
async def test_memory_backend_remaining(monkeypatch):
    monkeypatch.setattr("app.rate_limit.settings.RATE_LIMIT_BACKEND", "memory")
    monkeypatch.setattr("app.rate_limit.settings.RATE_LIMIT_REQUIRE_REDIS", False)
    limiter = RateLimiter()
    limiter.reset_for_tests()
    allowed, retry, remaining = await limiter.allow("t:api", 2)
    assert allowed is True
    assert remaining == 1
    allowed, retry, remaining = await limiter.allow("t:api", 2)
    assert allowed is True
    assert remaining == 0
    allowed, retry, remaining = await limiter.allow("t:api", 2)
    assert allowed is False
    assert remaining == 0
    assert retry >= 1


@pytest.mark.asyncio
async def test_redis_backend_via_fake(monkeypatch):
    """Simulate Redis EVAL sliding window with an in-process fake."""

    class FakeRedis:
        def __init__(self):
            self.zsets: dict[str, dict[str, float]] = {}

        async def ping(self):
            return True

        async def eval(self, script, numkeys, *args):
            key = args[0]
            window_start = float(args[1])
            limit = int(args[2])
            now = float(args[3])
            member = args[4]
            window = int(args[5])
            bucket = self.zsets.setdefault(key, {})
            for m, score in list(bucket.items()):
                if score <= window_start:
                    del bucket[m]
            count = len(bucket)
            if count >= limit:
                oldest = min(bucket.values()) if bucket else now
                retry = max(int(window - (now - oldest)) + 1, 1)
                return [0, retry, count]
            bucket[member] = now
            return [1, 0, count + 1]

    fake = FakeRedis()
    limiter = RateLimiter()
    limiter._init_attempted = True
    limiter._backend = "redis"
    limiter._redis = fake

    assert (await limiter.allow("ip:auth", 2))[0] is True
    assert (await limiter.allow("ip:auth", 2))[0] is True
    allowed, retry, remaining = await limiter.allow("ip:auth", 2)
    assert allowed is False
    assert remaining == 0
    assert retry >= 1


@pytest.mark.asyncio
async def test_auto_falls_back_when_redis_ping_fails(monkeypatch):
    class Boom:
        async def ping(self):
            raise ConnectionError("down")

    class BoomMod:
        @staticmethod
        def from_url(*args, **kwargs):
            return Boom()

    monkeypatch.setattr("app.rate_limit.settings.RATE_LIMIT_BACKEND", "auto")
    monkeypatch.setattr("app.rate_limit.settings.RATE_LIMIT_REQUIRE_REDIS", False)
    monkeypatch.setitem(__import__("sys").modules, "redis.asyncio", BoomMod())

    limiter = RateLimiter()
    # force import path inside ensure_backend
    import types
    import sys

    fake_pkg = types.ModuleType("redis")
    fake_async = types.ModuleType("redis.asyncio")

    def from_url(*a, **k):
        return Boom()

    fake_async.from_url = from_url
    sys.modules["redis"] = fake_pkg
    sys.modules["redis.asyncio"] = fake_async

    backend = await limiter.ensure_backend()
    assert backend == "memory"
    allowed, _, _ = await limiter.allow("x:api", 1)
    assert allowed is True
