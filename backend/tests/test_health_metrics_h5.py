"""Stage 5 H5: deep /health readiness checks + Prometheus /metrics."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import metrics as metrics_svc
from app.main import app
from app.rate_limit import rate_limiter


def test_shallow_health_unchanged():
    rate_limiter.reset_for_tests()
    client = TestClient(app)
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["status"] == "ok"
    assert body["service"] == "ribdigi-erp"
    assert body["deep"] is False
    assert "checks" not in body
    assert "security" in body


@pytest.mark.asyncio
async def test_deep_health_and_ready_with_sqlite(client, monkeypatch):
    ac, _seed = client
    monkeypatch.setattr("app.config.settings.CELERY_TASK_ALWAYS_EAGER", True)
    monkeypatch.setattr("app.health.settings.CELERY_TASK_ALWAYS_EAGER", True)
    monkeypatch.setattr("app.config.settings.RATE_LIMIT_REQUIRE_REDIS", False)
    monkeypatch.setattr("app.health.settings.RATE_LIMIT_REQUIRE_REDIS", False)

    # Force redis check to skipped/degraded path without requiring a live Redis.
    async def _redis_ok():
        return {"status": "ok", "latency_ms": 0.1}

    monkeypatch.setattr("app.health.check_redis", _redis_ok)

    deep = await ac.get("/api/v1/health?deep=true")
    assert deep.status_code == 200, deep.text
    data = deep.json()["data"]
    assert data["deep"] is True
    assert data["checks"]["database"]["status"] == "ok"
    assert data["checks"]["redis"]["status"] == "ok"
    assert data["checks"]["celery_broker"]["status"] == "ok"
    assert data["status"] == "ok"

    ready = await ac.get("/api/v1/health/ready")
    assert ready.status_code == 200, ready.text
    assert ready.json()["data"]["deep"] is True
    assert ready.json()["data"]["checks"]["database"]["status"] == "ok"


@pytest.mark.asyncio
async def test_deep_health_503_when_database_down(client, monkeypatch):
    ac, _seed = client

    async def _db_down(_factory):
        return {"status": "error", "latency_ms": 1.0, "error": "OperationalError"}

    async def _redis_ok():
        return {"status": "ok", "latency_ms": 0.1}

    async def _celery_ok():
        return {"status": "ok", "mode": "eager", "latency_ms": 0.1}

    monkeypatch.setattr("app.health.check_database", _db_down)
    monkeypatch.setattr("app.health.check_redis", _redis_ok)
    monkeypatch.setattr("app.health.check_celery_broker", _celery_ok)

    r = await ac.get("/api/v1/health/ready")
    assert r.status_code == 503
    body = r.json()
    assert body["success"] is False
    assert body["data"]["status"] == "error"
    assert body["data"]["checks"]["database"]["status"] == "error"


def test_metrics_prometheus_text():
    rate_limiter.reset_for_tests()
    metrics_svc.reset_for_tests()
    client = TestClient(app)
    assert client.get("/api/v1/health").status_code == 200
    metrics = client.get("/api/v1/metrics")
    assert metrics.status_code == 200
    assert "text/plain" in metrics.headers.get("content-type", "")
    text = metrics.text
    assert "ribdigi_up 1" in text
    assert "ribdigi_http_requests_total" in text
    assert 'path_group="/api/v1/health"' in text or "ribdigi_http_request_duration" in text


def test_metrics_can_be_disabled(monkeypatch):
    rate_limiter.reset_for_tests()
    monkeypatch.setattr("app.config.settings.METRICS_ENABLED", False)
    monkeypatch.setattr("app.metrics.settings.METRICS_ENABLED", False)
    client = TestClient(app)
    assert client.get("/api/v1/metrics").status_code == 404
