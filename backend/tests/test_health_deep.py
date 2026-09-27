"""Public /health probes stay generic; deep checks are platform-ops only."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.rate_limit import rate_limiter


INFRA_LEAKS = (
    "redis",
    "celery",
    "postgres",
    "build_id",
    "release_channel",
    "RIBDIGI_BUILD",
    "checks",
)


def test_shallow_health_is_tenant_safe():
    rate_limiter.reset_for_tests()
    client = TestClient(app)
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    payload = response.json()
    body = payload["data"]
    assert body["status"] == "ok"
    assert body["message"] == "System is operating normally."
    blob = response.text.lower()
    for leak in INFRA_LEAKS:
        assert leak not in blob
    assert "service" not in body
    assert "deep" not in body


@pytest.mark.asyncio
async def test_deep_query_ignored_without_platform_auth(client, monkeypatch):
    ac, _seed = client
    monkeypatch.setattr("app.config.settings.CELERY_TASK_ALWAYS_EAGER", True)
    monkeypatch.setattr("app.health.settings.CELERY_TASK_ALWAYS_EAGER", True)

    deep = await ac.get("/api/v1/health?deep=true")
    assert deep.status_code == 200, deep.text
    data = deep.json()["data"]
    assert data["status"] == "ok"
    assert "checks" not in data
    assert "build_id" not in data

    ready = await ac.get("/api/v1/health/ready")
    assert ready.status_code == 200, ready.text
    assert "checks" not in ready.json()["data"]


@pytest.mark.asyncio
async def test_ready_503_is_tenant_safe(client, monkeypatch):
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
    assert body["data"]["message"] == "System is temporarily unavailable."
    assert "checks" not in body["data"]
    assert "OperationalError" not in r.text
