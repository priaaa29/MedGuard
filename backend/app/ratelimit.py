"""Sliding-window rate limiter.

Uses Redis when REDIS_URL is set (required in production, so limits are shared
by every worker and instance) and an in-memory store otherwise (dev and tests).
"""

import logging
import threading
import time
import uuid
from collections import defaultdict, deque
from typing import Protocol

from app.config import REDIS_URL

logger = logging.getLogger(__name__)


class Limiter(Protocol):
    def hit(self, key: str, limit: int, window_seconds: int) -> bool: ...
    def reset(self) -> None: ...


class MemoryRateLimiter:
    def __init__(self):
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str, limit: int, window_seconds: int) -> bool:
        """Record an attempt. Returns False if the key is over its limit."""
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] >= window_seconds:
                hits.popleft()
            if len(hits) >= limit:
                return False
            hits.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


class RedisRateLimiter:
    """One sorted set per key: members are attempts, scores are timestamps."""

    PREFIX = "medguard:ratelimit:"

    def __init__(self, client):
        self._redis = client

    def hit(self, key: str, limit: int, window_seconds: int) -> bool:
        if window_seconds <= 0:
            return True
        redis_key = self.PREFIX + key
        now = time.time()
        try:
            pipe = self._redis.pipeline()
            pipe.zremrangebyscore(redis_key, 0, now - window_seconds)
            pipe.zcard(redis_key)
            _, count = pipe.execute()
            if count >= limit:
                return False
            pipe = self._redis.pipeline()
            pipe.zadd(redis_key, {f"{now}:{uuid.uuid4().hex}": now})
            pipe.expire(redis_key, window_seconds)
            pipe.execute()
            return True
        except Exception:  # noqa: BLE001 - never lock people out because Redis hiccuped
            logger.exception("rate limiter unavailable; allowing request")
            return True

    def reset(self) -> None:
        for redis_key in self._redis.scan_iter(self.PREFIX + "*"):
            self._redis.delete(redis_key)


def _build() -> Limiter:
    if REDIS_URL:
        import redis

        return RedisRateLimiter(redis.Redis.from_url(REDIS_URL, socket_timeout=2, socket_connect_timeout=2))
    return MemoryRateLimiter()


# Kept for the existing tests and imports.
RateLimiter = MemoryRateLimiter
limiter: Limiter = _build()
