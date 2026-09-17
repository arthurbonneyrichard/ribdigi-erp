"""SEC-L2 — public /health must not expose security posture flags."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.rate_limit import rate_limiter

pytestmark = pytest.mark.security

_POSTURE_KEYS = {
    "security",
    "env",
    "rate_limit_enabled",
    "rate_limit_backend",
    "openapi_enabled",
    "cors_allows_wildcard",
    "cors_origins",
    "debug",
}


def _assert_no_public_posture(payload: dict) -> None:
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    assert isinstance(data, dict)
    for key in _POSTURE_KEYS:
        assert key not in data, f"public health must not expose {key!r}"
        assert key not in payload, f"public health envelope must not expose {key!r}"


def test_public_shallow_health_omits_security_posture():
    rate_limiter.reset_for_tests()
    client = TestClient(app)
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    data = body["data"]
    assert data["status"] == "ok"
    assert data["service"] == "ribdigi-erp"
    assert data["deep"] is False
    assert "checks" not in data
    _assert_no_public_posture(body)


@pytest.mark.asyncio
async def test_public_deep_and_ready_omit_security_posture(client, monkeypatch):
    ac, _seed = client
    monkeypatch.setattr("app.config.settings.CELERY_TASK_ALWAYS_EAGER", True)
    monkeypatch.setattr("app.health.settings.CELERY_TASK_ALWAYS_EAGER", True)
    monkeypatch.setattr("app.config.settings.RATE_LIMIT_REQUIRE_REDIS", False)
    monkeypatch.setattr("app.health.settings.RATE_LIMIT_REQUIRE_REDIS", False)

    async def _redis_ok():
        return {"status": "ok", "latency_ms": 0.1}

    monkeypatch.setattr("app.health.check_redis", _redis_ok)

    deep = await ac.get("/api/v1/health?deep=true")
    assert deep.status_code == 200, deep.text
    deep_body = deep.json()
    assert deep_body["data"]["deep"] is True
    assert deep_body["data"]["checks"]["database"]["status"] == "ok"
    _assert_no_public_posture(deep_body)

    ready = await ac.get("/api/v1/health/ready")
    assert ready.status_code == 200, ready.text
    ready_body = ready.json()
    assert ready_body["data"]["deep"] is True
    assert "database" in ready_body["data"]["checks"]
    _assert_no_public_posture(ready_body)


@pytest.mark.asyncio
async def test_assemble_health_opt_in_posture():
    """Authenticated House surfaces may still request posture via the flag."""
    from app import health as health_svc

    body, status = await health_svc.assemble_health(
        deep=False,
        include_security_posture=True,
    )
    assert status == 200
    assert "security" in body
    assert "env" in body
    assert "rate_limit_enabled" in body["security"]

    public, _ = await health_svc.assemble_health(
        deep=False,
        include_security_posture=False,
    )
    assert "security" not in public
    assert "env" not in public