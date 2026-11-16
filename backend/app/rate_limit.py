"""Distributed rate limiting with Redis sliding window and memory fallback."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections import defaultdict, deque
from threading import Lock
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

# After a Redis error, wait this long before trying Redis again (counting in memory meanwhile).
REDIS_RETRY_SECONDS = 15.0


class RateLimitBackendUnavailable(RuntimeError):
    """Redis was expected but is not answering, and the caller asked to fail closed."""


class RateLimiter:
    """Sliding-window limiter. Prefers Redis; falls back to process memory."""

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()
        self._redis: Any = None
        self._backend: str = "memory"
        self._init_attempted = False
        self._retry_at = 0.0
        # True once Redis has answered (or RATE_LIMIT_BACKEND=redis): a later memory count is degraded.
        self._redis_expected = False
        self._lock_async: asyncio.Lock | None = None
        self._lock_loop = None

    @property
    def degraded(self) -> bool:
        """Redis should be counting but this worker is on its own memory counts."""
        return self._redis_expected and self._backend != "redis"

    @property
    def backend(self) -> str:
        return self._backend

    def _init_lock(self) -> asyncio.Lock:
        loop = asyncio.get_running_loop()
        if self._lock_async is None or self._lock_loop is not loop:
            self._lock_async = asyncio.Lock()
            self._lock_loop = loop
        return self._lock_async

    async def ensure_backend(self) -> str:
        if self._init_attempted:
            return self._backend
        if self._retry_at and time.monotonic() < self._retry_at:
            return self._backend
        # Requests arriving while the first Redis connect is in flight wait for it, instead of
        # slipping through on this worker's empty memory counts.
        async with self._init_lock():
            if self._init_attempted:
                return self._backend
            if self._retry_at and time.monotonic() < self._retry_at:
                return self._backend
            try:
                return await self._connect()
            finally:
                # Marked only once the attempt is over (a failed Redis attempt re-clears it below),
                # so nobody takes the fast path while the connect is still in flight.
                if not self._retry_at or time.monotonic() >= self._retry_at:
                    self._init_attempted = True

    async def _connect(self) -> str:
        mode = (settings.RATE_LIMIT_BACKEND or "auto").lower()
        if mode == "redis":
            self._redis_expected = True
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
            self._redis_expected = True
            self._retry_at = 0.0
            from urllib.parse import urlparse

            parsed = urlparse(settings.REDIS_URL or "")
            host = parsed.hostname or "redis"
            port = f":{parsed.port}" if parsed.port else ""
            logger.info(
                "Rate limiter using Redis at %s://%s%s",
                parsed.scheme or "redis",
                host,
                port,
            )
        except Exception as exc:
            self._redis = None
            self._backend = "memory"
            if self._redis_expected:
                # Redis worked before (or is required): keep trying instead of staying on memory.
                self._init_attempted = False
                self._retry_at = time.monotonic() + REDIS_RETRY_SECONDS
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
        self._retry_at = 0.0
        self._redis_expected = False

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

    def _memory_peek(self, key: str, limit: int, window_seconds: float) -> tuple[bool, int]:
        now = time.monotonic()
        with self._lock:
            bucket = self._hits.get(key)
            if not bucket:
                return False, 0
            while bucket and now - bucket[0] > window_seconds:
                bucket.popleft()
            if len(bucket) >= limit:
                return True, max(int(window_seconds - (now - bucket[0])) + 1, 1)
            return False, 0

    async def _redis_peek(self, key: str, limit: int, window_seconds: float) -> tuple[bool, int]:
        assert self._redis is not None
        now = time.time()
        redis_key = f"{settings.RATE_LIMIT_REDIS_PREFIX}:{key}"
        script = """
        redis.call('ZREMRANGEBYSCORE', KEYS[1], 0, ARGV[1])
        local count = redis.call('ZCARD', KEYS[1])
        if count < tonumber(ARGV[2]) then return {0, 0} end
        local oldest = redis.call('ZRANGE', KEYS[1], 0, 0, 'WITHSCORES')
        local retry = tonumber(ARGV[4])
        if oldest[2] then
          retry = math.floor(tonumber(ARGV[4]) - (tonumber(ARGV[3]) - tonumber(oldest[2]))) + 1
          if retry < 1 then retry = 1 end
        end
        return {1, retry}
        """
        result = await self._redis.eval(
            script, 1, redis_key, str(now - window_seconds), str(limit), str(now), str(int(window_seconds))
        )
        return int(result[0]) == 1, int(result[1] or 0)

    async def peek(
        self, key: str, limit: int, window_seconds: float = 60.0, *, fail_closed: bool = False
    ) -> tuple[bool, int]:
        """Return (full, retry_after_seconds) without counting this call."""
        try:
            await self.ensure_backend()
        except RuntimeError as exc:
            if fail_closed:
                raise RateLimitBackendUnavailable("Redis rate limiter unavailable") from None
            logger.error("Required Redis rate limiter unavailable; limiting in memory: %s", exc)
        if self._backend == "redis" and self._redis is not None:
            try:
                return await self._redis_peek(key, limit, window_seconds)
            except Exception as exc:
                logger.warning("Redis rate limit error; falling back to memory: %s", exc)
                self._backend = "memory"
                self._redis = None
                self._init_attempted = False
                self._retry_at = time.monotonic() + REDIS_RETRY_SECONDS
        if fail_closed and self.degraded:
            raise RateLimitBackendUnavailable("Redis rate limiter unavailable")
        return self._memory_peek(key, limit, window_seconds)

    async def allow(
        self,
        key: str,
        limit: int,
        window_seconds: float = 60.0,
        *,
        fail_closed: bool = False,
    ) -> tuple[bool, int, int]:
        """Return (allowed, retry_after_seconds, remaining).

        ``fail_closed`` raises RateLimitBackendUnavailable instead of counting in this worker's
        memory while Redis is expected but down (multi-worker counts would otherwise split).
        """
        try:
            await self.ensure_backend()
        except RuntimeError as exc:
            if fail_closed:
                raise RateLimitBackendUnavailable("Redis rate limiter unavailable") from None
            # Required Redis is down: keep limiting in memory (per worker) rather than answer 500.
            logger.error("Required Redis rate limiter unavailable; limiting in memory: %s", exc)
        if self._backend == "redis" and self._redis is not None:
            try:
                return await self._redis_allow(key, limit, window_seconds)
            except Exception as exc:
                logger.warning("Redis rate limit error; falling back to memory: %s", exc)
                self._backend = "memory"
                self._redis = None
                self._init_attempted = False
                self._retry_at = time.monotonic() + REDIS_RETRY_SECONDS
        if fail_closed and self.degraded:
            raise RateLimitBackendUnavailable("Redis rate limiter unavailable")
        return self._memory_allow(key, limit, window_seconds)


rate_limiter = RateLimiter()
