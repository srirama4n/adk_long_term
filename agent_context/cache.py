"""
Redis-backed cache for context components (e.g. procedures, long-term results).
No app dependency; use in any project with Redis.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

try:
    import redis.asyncio as aioredis
except ImportError:
    aioredis = None  # type: ignore[assignment]


class ContextCache:
    """Cache context components in Redis with TTL. Keys are strings; values are JSON-serialized."""

    def __init__(self, redis_url: str, ttl_seconds: int = 60) -> None:
        self._redis_url = redis_url
        self._ttl = ttl_seconds
        self._redis: Any = None

    async def connect(self) -> None:
        if aioredis is None:
            return
        if self._redis is None:
            self._redis = aioredis.from_url(self._redis_url, decode_responses=True)

    async def close(self) -> None:
        if self._redis:
            await self._redis.aclose()
            self._redis = None

    def _key(self, prefix: str, *parts: str) -> str:
        return f"ctx:{prefix}:{':'.join(parts)}"

    async def get(self, prefix: str, *key_parts: str) -> Any | None:
        if not self._redis:
            return None
        k = self._key(prefix, *key_parts)
        try:
            raw = await self._redis.get(k)
            if raw is None:
                return None
            return json.loads(raw)
        except Exception:
            return None

    async def set(self, prefix: str, key_parts: tuple[str, ...], value: Any) -> None:
        if not self._redis:
            return
        k = self._key(prefix, *key_parts)
        try:
            await self._redis.setex(k, self._ttl, json.dumps(value, default=str))
        except Exception:
            pass

    async def delete(self, prefix: str, *key_parts: str) -> None:
        if not self._redis:
            return
        k = self._key(prefix, *key_parts)
        try:
            await self._redis.delete(k)
        except Exception:
            pass

    @staticmethod
    def message_hash(message: str, length: int = 16) -> str:
        """Stable hash of message for cache key."""
        return hashlib.sha256((message or "").encode()).hexdigest()[:length]
