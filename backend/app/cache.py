"""Stage 6 P2 — Redis app-data cache for dashboard + product catalog.

Soft-fails to in-memory (or no-op when disabled). Never blocks business APIs
when Redis is unavailable. Extends the rate-limit Redis connection pattern.
"""

from __future__ import annotations

import json
import logging
import time
from threading import Lock
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)


class AppCache:
    """JSON blob cache with Redis preferred and process-memory fallback."""

    def __init__(self) -> None:
        self._redis: Any = None
        self._backend: str = "memory"
        self._init_attempted = False
        self._memory: dict[str, tuple[float, str]] = {}
        self._lock = Lock()

    @property
    def backend(self) -> str:
        return self._backend

    def reset_for_tests(self) -> None:
        with self._lock:
            self._memory.clear()
        self._redis = None
        self._backend = "memory"
        self._init_attempted = False

    async def ensure_backend(self) -> str:
        if self._init_attempted:
            return self._backend
        self._init_attempted = True
        if not settings.CACHE_ENABLED:
            self._backend = "disabled"
            return self._backend
        mode = (settings.CACHE_BACKEND or "auto").lower()
        if mode == "memory":
            self._backend = "memory"
            return self._backend
        if mode not in {"auto", "redis"}:
            logger.warning("Unknown CACHE_BACKEND=%s; using memory", mode)
            self._backend = "memory"
            return self._backend
        try:
            import redis.asyncio as redis_async

            client = redis_async.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=1.5,
                socket_timeout=1.5,
            )
            await client.ping()
            self._redis = client
            self._backend = "redis"
            logger.info("App cache using Redis at %s", settings.REDIS_URL)
        except Exception as exc:
            self._redis = None
            self._backend = "memory"
            logger.warning("Redis unavailable for app cache (%s); using in-memory fallback", exc)
        return self._backend

    def _prefix(self) -> str:
        return (settings.CACHE_REDIS_PREFIX or "ribdigi:cache").rstrip(":")

    def dashboard_key(self, tenant_id: str) -> str:
        # Architecture: dashboard:{tenant_id}:{metric} — MVP caches full summary blob
        return f"{self._prefix()}:dashboard:{tenant_id}:summary"

    def products_key(self, tenant_id: str) -> str:
        # Architecture: products:{tenant_id}:{category_id} — MVP full list = all
        return f"{self._prefix()}:products:{tenant_id}:all"

    def categories_key(self, tenant_id: str, *, tree: bool) -> str:
        kind = "tree" if tree else "flat"
        return f"{self._prefix()}:products:{tenant_id}:categories:{kind}"

    def catalog_keys(self, tenant_id: str) -> list[str]:
        return [
            self.products_key(tenant_id),
            self.categories_key(tenant_id, tree=False),
            self.categories_key(tenant_id, tree=True),
        ]

    async def get_json(self, key: str) -> Any | None:
        if not settings.CACHE_ENABLED:
            return None
        await self.ensure_backend()
        if self._backend == "disabled":
            return None
        try:
            if self._backend == "redis" and self._redis is not None:
                raw = await self._redis.get(key)
                if raw is None:
                    return None
                return json.loads(raw)
            now = time.monotonic()
            with self._lock:
                entry = self._memory.get(key)
                if not entry:
                    return None
                expires_at, payload = entry
                if expires_at < now:
                    del self._memory[key]
                    return None
                return json.loads(payload)
        except Exception as exc:
            logger.warning("App cache get failed for %s: %s", key, exc)
            return None

    async def set_json(self, key: str, value: Any, ttl_seconds: int) -> bool:
        if not settings.CACHE_ENABLED or ttl_seconds <= 0:
            return False
        await self.ensure_backend()
        if self._backend == "disabled":
            return False
        try:
            payload = json.dumps(value, default=str, separators=(",", ":"))
            if self._backend == "redis" and self._redis is not None:
                await self._redis.setex(key, int(ttl_seconds), payload)
                return True
            with self._lock:
                self._memory[key] = (time.monotonic() + float(ttl_seconds), payload)
            return True
        except Exception as exc:
            logger.warning("App cache set failed for %s: %s", key, exc)
            return False

    async def delete(self, *keys: str) -> None:
        if not keys:
            return
        if not settings.CACHE_ENABLED:
            return
        await self.ensure_backend()
        try:
            if self._backend == "redis" and self._redis is not None:
                await self._redis.delete(*keys)
            with self._lock:
                for key in keys:
                    self._memory.pop(key, None)
        except Exception as exc:
            logger.warning("App cache delete failed: %s", exc)

    async def invalidate_dashboard(self, tenant_id: str) -> None:
        await self.delete(self.dashboard_key(tenant_id))

    async def invalidate_catalog(self, tenant_id: str) -> None:
        await self.delete(*self.catalog_keys(tenant_id))

    async def invalidate_tenant(self, tenant_id: str) -> None:
        """Invalidate dashboard + catalog read models for a tenant."""
        await self.delete(self.dashboard_key(tenant_id), *self.catalog_keys(tenant_id))


app_cache = AppCache()
