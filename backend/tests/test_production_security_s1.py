"""Stage 5 S1: production security gate — rate limit, headers, CORS, OpenAPI."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import app
from app.rate_limit import rate_limiter
from app.security_runtime import is_production, openapi_enabled, security_posture

pytestmark = pytest.mark.security


def test_production_accepts_secure_defaults():
    cfg = Settings(
        APP_ENV="production",
        JWT_SECRET_KEY="x" * 32,
        DEBUG=False,
        CORS_ORIGINS="https://app.example.com,https://admin.example.com",
        RATE_LIMIT_ENABLED=True,
        RATE_LIMIT_BACKEND="redis",
        RATE_LIMIT_REQUIRE_REDIS=True,
        EMAIL_ENABLED=False,
        SMS_ENABLED=False,
    )
    assert cfg.cors_origins == ["https://app.example.com", "https://admin.example.com"]
    assert cfg.RATE_LIMIT_REQUIRE_REDIS is True


def test_production_rejects_empty_cors():
    with pytest.raises(Exception) as exc:
        Settings(
            APP_ENV="production",
            JWT_SECRET_KEY="x" * 32,
            DEBUG=False,
            CORS_ORIGINS="  ,  ",
            RATE_LIMIT_ENABLED=True,
            EMAIL_ENABLED=False,
            SMS_ENABLED=False,
        )
    assert "CORS" in str(exc.value)


def test_production_rejects_debug_true():
    with pytest.raises(Exception) as exc:
        Settings(
            APP_ENV="production",
            JWT_SECRET_KEY="x" * 32,
            DEBUG=True,
            CORS_ORIGINS="https://app.example.com",
            RATE_LIMIT_ENABLED=True,
            EMAIL_ENABLED=False,
            SMS_ENABLED=False,
        )
    assert "DEBUG" in str(exc.value)


def test_openapi_disabled_when_production(monkeypatch):
    monkeypatch.setattr("app.security_runtime.settings.APP_ENV", "production")
    assert is_production() is True
    assert openapi_enabled() is False
    posture = security_posture()
    assert posture["security"]["openapi_enabled"] is False
    assert posture["security"]["cors_allows_wildcard"] is False


def test_health_exposes_security_posture_and_headers():
    rate_limiter.reset_for_tests()
    client = TestClient(app)
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["status"] == "ok"
    assert body["security"]["rate_limit_enabled"] is True
    assert "rate_limit_backend" in body["security"]
    assert "openapi_enabled" in body["security"]
    assert body["security"]["cors_allows_wildcard"] is False

    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert "default-src 'none'" in response.headers.get("Content-Security-Policy", "")
    assert response.headers.get("Cross-Origin-Opener-Policy") == "same-origin"
    assert "X-RateLimit-Limit" in response.headers
    assert "X-RateLimit-Remaining" in response.headers
    assert "X-RateLimit-Backend" in response.headers


def test_production_adds_hsts_and_no_store(monkeypatch):
    rate_limiter.reset_for_tests()
    monkeypatch.setattr("app.middleware.settings.APP_ENV", "production")
    client = TestClient(app)
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert "max-age=31536000" in response.headers.get("Strict-Transport-Security", "")
    assert response.headers.get("Cache-Control") == "no-store"


def test_rate_limit_429_headers(monkeypatch):
    rate_limiter.reset_for_tests()
    monkeypatch.setattr("app.middleware.settings.RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr("app.middleware.settings.RATE_LIMIT_PER_MINUTE", 2)
    monkeypatch.setattr("app.middleware.settings.RATE_LIMIT_AUTH_PER_MINUTE", 2)
    client = TestClient(app)
    assert client.get("/api/v1/health").status_code == 200
    assert client.get("/api/v1/health").status_code == 200
    blocked = client.get("/api/v1/health")
    assert blocked.status_code == 429
    assert blocked.json()["detail"] == "RATE_LIMIT_EXCEEDED"
    assert "Retry-After" in blocked.headers
    assert blocked.headers.get("X-RateLimit-Remaining") == "0"
