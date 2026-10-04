"""Deep /health readiness checks (DB / Redis / Celery broker)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

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


@pytest.mark.asyncio
async def test_deep_health_and_ready_with_sqlite(client, monkeypatch):
    ac, _seed = client
    monkeypatch.setattr("app.config.settings.CELERY_TASK_ALWAYS_EAGER", True)
    monkeypatch.setattr("app.health.settings.CELERY_TASK_ALWAYS_EAGER", True)
    monkeypatch.setattr("app.config.settings.RATE_LIMIT_REQUIRE_REDIS", False)
    monkeypatch.setattr("app.health.settings.RATE_LIMIT_REQUIRE_REDIS", False)

    async def _redis_ok():
        return {"status": "ok", "latency_ms": 0.1, "required": False}

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
        return {"status": "error", "latency_ms": 1.0, "error": "OperationalError", "required": True}

    async def _redis_ok():
        return {"status": "ok", "latency_ms": 0.1, "required": False}

    async def _celery_ok():
        return {"status": "ok", "mode": "eager", "latency_ms": 0.1, "required": True}

    monkeypatch.setattr("app.health.check_database", _db_down)
    monkeypatch.setattr("app.health.check_redis", _redis_ok)
    monkeypatch.setattr("app.health.check_celery_broker", _celery_ok)

    r = await ac.get("/api/v1/health/ready")
    assert r.status_code == 503
    body = r.json()
    assert body["success"] is False
    assert body["data"]["status"] == "error"
    assert body["data"]["checks"]["database"]["status"] == "error"
