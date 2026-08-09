"""Deep health checks for ops readiness (Stage 5 H5)."""

from __future__ import annotations

import time
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.security_runtime import security_posture


CheckResult = dict[str, Any]


def _ms_since(start: float) -> float:
    return round((time.perf_counter() - start) * 1000.0, 2)


async def check_database(session_factory: async_sessionmaker[AsyncSession]) -> CheckResult:
    start = time.perf_counter()
    try:
        async with session_factory() as db:
            await db.execute(text("SELECT 1"))
        return {"status": "ok", "latency_ms": _ms_since(start)}
    except Exception as exc:
        return {
            "status": "error",
            "latency_ms": _ms_since(start),
            "error": type(exc).__name__,
        }


async def check_redis() -> CheckResult:
    """Ping Redis. Optional unless RATE_LIMIT_REQUIRE_REDIS is set."""
    start = time.perf_counter()
    url = (settings.REDIS_URL or "").strip()
    if not url:
        return {"status": "skipped", "reason": "REDIS_URL unset"}
    try:
        import redis.asyncio as redis_async

        client = redis_async.from_url(
            url,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=1.5,
            socket_timeout=1.5,
        )
        try:
            await client.ping()
        finally:
            await client.aclose()
        return {"status": "ok", "latency_ms": _ms_since(start)}
    except Exception as exc:
        required = bool(settings.RATE_LIMIT_REQUIRE_REDIS)
        return {
            "status": "error" if required else "degraded",
            "latency_ms": _ms_since(start),
            "error": type(exc).__name__,
            "required": required,
        }


async def check_celery_broker() -> CheckResult:
    """Probe Celery broker connectivity (RabbitMQ/Redis URL)."""
    start = time.perf_counter()
    if not settings.CELERY_ENABLED:
        return {"status": "skipped", "reason": "CELERY_ENABLED=false"}
    if settings.CELERY_TASK_ALWAYS_EAGER:
        return {"status": "ok", "mode": "eager", "latency_ms": _ms_since(start)}
    broker = settings.celery_broker_url
    if not broker:
        return {"status": "skipped", "reason": "broker URL unset"}
    try:
        from kombu import Connection

        with Connection(broker, connect_timeout=1.5) as conn:
            conn.ensure_connection(max_retries=1, timeout=1.5)
        return {
            "status": "ok",
            "latency_ms": _ms_since(start),
            "broker_scheme": broker.split(":", 1)[0],
        }
    except Exception as exc:
        return {
            "status": "degraded",
            "latency_ms": _ms_since(start),
            "error": type(exc).__name__,
            "broker_scheme": broker.split(":", 1)[0],
        }


def _aggregate_status(checks: dict[str, CheckResult]) -> str:
    statuses = [c.get("status") for c in checks.values()]
    if "error" in statuses:
        # Only database error (or required redis) should be hard-error overall.
        db = checks.get("database", {}).get("status")
        redis = checks.get("redis", {})
        if db == "error":
            return "error"
        if redis.get("status") == "error" and redis.get("required"):
            return "error"
        return "degraded"
    if "degraded" in statuses:
        return "degraded"
    return "ok"


async def assemble_health(
    *,
    deep: bool,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> tuple[dict[str, Any], int]:
    """Build health payload. Returns (body, http_status)."""
    body: dict[str, Any] = {
        "status": "ok",
        "service": "ribdigi-erp",
        "deep": bool(deep),
        **security_posture(),
    }
    if not deep:
        return body, 200

    from app.db import SessionLocal

    factory = session_factory or SessionLocal
    checks = {
        "database": await check_database(factory),
        "redis": await check_redis(),
        "celery_broker": await check_celery_broker(),
    }
    body["checks"] = checks
    body["status"] = _aggregate_status(checks)
    http_status = 503 if body["status"] == "error" else 200
    return body, http_status
