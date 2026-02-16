"""
Reusable short-term memory store: Redis, session-scoped with TTL.

Use this in any agent to keep recent conversation context per session.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

import redis.asyncio as aioredis

from app.memory.short_term.config import ShortTermMemoryConfig

try:
    import structlog
    log = structlog.get_logger(__name__)
except Exception:
    import logging
    log = logging.getLogger(__name__)


class ShortTermMemoryError(Exception):
    """Raised when short-term memory (Redis) operations fail."""

    def __init__(self, message: str, *, operation: str = "", session_id: str = "", cause: Optional[Exception] = None) -> None:
        super().__init__(message)
        self.operation = operation
        self.session_id = session_id
        self.cause = cause


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ShortTermMemory:
    """
    Reusable short-term (session) memory for any agent.

    - Stores session context in Redis with a TTL.
    - Call save() after each turn; use get() to load context; clear() to reset a session.
    """

    def __init__(self, config: Optional[ShortTermMemoryConfig] = None) -> None:
        self._config = config or ShortTermMemoryConfig.from_env()
        self._redis: Optional[aioredis.Redis] = None

    def _key(self, session_id: str) -> str:
        return f"{self._config.key_prefix}:{session_id}"

    async def connect(self) -> None:
        """Connect to Redis."""
        if self._redis is not None:
            log.debug("short_term_connect_skip", reason="already_connected")
            return
        log.info("short_term_connect_start", url_redacted="redis://***")
        try:
            self._redis = await aioredis.from_url(
                self._config.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            log.info("short_term_connected", url_redacted="redis://***")
        except Exception as e:
            log.exception("short_term_connect_failed", error=str(e), error_type=type(e).__name__)
            raise ShortTermMemoryError(
                f"Failed to connect to Redis: {e}",
                operation="connect",
                cause=e,
            ) from e

    async def close(self) -> None:
        """Close Redis connection."""
        log.info("short_term_close_start")
        try:
            if self._redis:
                await self._redis.aclose()
                self._redis = None
            log.info("short_term_closed")
        except Exception as e:
            log.exception("short_term_close_failed", error=str(e), error_type=type(e).__name__)
            self._redis = None

    async def save(self, session_id: str, data: dict[str, Any]) -> None:
        """
        Save session context. Truncates messages to max_messages and sets TTL.

        data typically has: messages, session_context, current_conversation_state (or any dict).
        """
        log.info("short_term_save_start", operation="save", session_id=session_id)
        try:
            if self._redis is None:
                await self.connect()
            key = self._key(session_id)
            messages = data.get("messages", [])[-self._config.max_messages:]
            payload = {
                "session_id": session_id,
                "session_context": data.get("session_context", {}),
                "messages": messages,
                "current_conversation_state": data.get("current_conversation_state", {}),
                "updated_at": _now_iso(),
            }
            await self._redis.setex(
                key,
                self._config.ttl_seconds,
                json.dumps(payload, default=str),
            )
            log.info(
                "short_term_saved",
                operation="save",
                session_id=session_id,
                key=key,
                ttl_seconds=self._config.ttl_seconds,
                messages_count=len(messages),
            )
        except ShortTermMemoryError:
            raise
        except Exception as e:
            log.exception(
                "short_term_save_failed",
                operation="save",
                session_id=session_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise ShortTermMemoryError(
                f"Failed to save session context: {e}",
                operation="save",
                session_id=session_id,
                cause=e,
            ) from e

    async def get(self, session_id: str) -> Optional[dict[str, Any]]:
        """Retrieve session context, or None if missing/expired."""
        log.info("short_term_get_start", operation="get", session_id=session_id)
        try:
            if self._redis is None:
                await self.connect()
            key = self._key(session_id)
            raw = await self._redis.get(key)
            if not raw:
                log.info("short_term_miss", operation="get", session_id=session_id, key=key)
                return None
            data = json.loads(raw)
            log.info(
                "short_term_hit",
                operation="get",
                session_id=session_id,
                key=key,
                messages_count=len(data.get("messages", [])),
            )
            return data
        except ShortTermMemoryError:
            raise
        except Exception as e:
            log.exception(
                "short_term_get_failed",
                operation="get",
                session_id=session_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise ShortTermMemoryError(
                f"Failed to retrieve session context: {e}",
                operation="get",
                session_id=session_id,
                cause=e,
            ) from e

    async def clear(self, session_id: str) -> None:
        """Remove session context from Redis."""
        log.info("short_term_clear_start", operation="clear", session_id=session_id)
        try:
            if self._redis is None:
                await self.connect()
            key = self._key(session_id)
            await self._redis.delete(key)
            log.info("short_term_cleared", operation="clear", session_id=session_id, key=key)
        except ShortTermMemoryError:
            raise
        except Exception as e:
            log.exception(
                "short_term_clear_failed",
                operation="clear",
                session_id=session_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise ShortTermMemoryError(
                f"Failed to clear session: {e}",
                operation="clear",
                session_id=session_id,
                cause=e,
            ) from e
