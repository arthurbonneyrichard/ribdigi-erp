"""Distributed rate limiting with Redis sliding window and memory fallback."""

from __future__ import annotations

import logging
import time
import uuid
from collections import defaultdict, deque
from threading import Lock
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)


class RateLimiter:
    """Sliding-window limiter. Prefers Redis; falls back to process memory."""

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()
        self._redis: Any = None
        self._backend: str = "memory"
        self._init_attempted = False

    @property
    def backend(self) -> str:
        return self._backend

    async def ensure_backend(self) -> str:
        if self._init_attempted:
            return self._backend
        self._init_attempted = True
        mode = (settings.RATE_LIMIT_BACKEND or "auto").lower()
        if mode == "memory":
            self._backend = "memory"
            return self._backend
        if mode not in {"auto", "redis"}:
            logger.warning("Unknown RATE_LIMIT_BACKEND=%s; using memory", mode)
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
            logger.info("Rate limiter using Redis at %s", settings.REDIS_URL)
        except Exception as exc:
            self._redis = None
            self._backend = "memory"
            if mode == "redis" or (
                settings.APP_ENV.lower() == "production" and settings.RATE_LIMIT_REQUIRE_REDIS
            ):
                raise RuntimeError(
                    f"Redis rate limiter required but unavailable: {exc}"
                ) from exc
            logger.warning("Redis unavailable for rate limiting (%s); using in-memory fallback", exc)
        return self._backend

    def reset_for_tests(self) -> None:
        with self._lock:
            self._hits.clear()
        self._redis = None
        self._backend = "memory"
        self._init_attempted = False

    def _memory_allow(self, key: str, limit: int, window_seconds: float = 60.0) -> tuple[bool, int, int]:
        now = time.monotonic()
        with self._lock:
            bucket = self._hits[key]
            while bucket and now - bucket[0] > window_seconds:
                bucket.popleft()
            if len(bucket) >= limit:
                retry_after = int(window_seconds - (now - bucket[0])) + 1
                return False, max(retry_after, 1), 0
            bucket.append(now)
            remaining = max(limit - len(bucket), 0)
            return True, 0, remaining

    async def _redis_allow(self, key: str, limit: int, window_seconds: float = 60.0) -> tuple[bool, int, int]:
        assert self._redis is not None
        now = time.time()
        window_start = now - window_seconds
        redis_key = f"{settings.RATE_LIMIT_REDIS_PREFIX}:{key}"
        member = f"{now}:{uuid.uuid4().hex}"
        # Atomic sliding-window check + increment
        script = """
        redis.call('ZREMRANGEBYSCORE', KEYS[1], 0, ARGV[1])
        local count = redis.call('ZCARD', KEYS[1])
        if count >= tonumber(ARGV[2]) then
          local oldest = redis.call('ZRANGE', KEYS[1], 0, 0, 'WITHSCORES')
          local retry = tonumber(ARGV[5])
          if oldest[2] then
            retry = math.floor(tonumber(ARGV[5]) - (tonumber(ARGV[3]) - tonumber(oldest[2]))) + 1
            if retry < 1 then retry = 1 end
          end
          return {0, retry, count}
        end
        redis.call('ZADD', KEYS[1], ARGV[3], ARGV[4])
        redis.call('EXPIRE', KEYS[1], tonumber(ARGV[5]) + 1)
        return {1, 0, count + 1}
        """
        result = await self._redis.eval(
            script,
            1,
            redis_key,
            str(window_start),
            str(limit),
            str(now),
            member,
            str(int(window_seconds)),
        )
        allowed = int(result[0]) == 1
        retry_after = int(result[1] or 0)
        count = int(result[2] or 0)
        remaining = max(limit - count, 0) if allowed else 0
        return allowed, max(retry_after, 0), remaining

    async def allow(self, key: str, limit: int, window_seconds: float = 60.0) -> tuple[bool, int, int]:
        """Return (allowed, retry_after_seconds, remaining)."""
        await self.ensure_backend()
        if self._backend == "redis" and self._redis is not None:
            try:
                return await self._redis_allow(key, limit, window_seconds)
            except Exception as exc:
                logger.warning("Redis rate limit error; falling back to memory: %s", exc)
                self._backend = "memory"
                self._redis = None
        return self._memory_allow(key, limit, window_seconds)


rate_limiter = RateLimiter()
