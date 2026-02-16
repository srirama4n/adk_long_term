"""
Unified memory abstraction: short-term and long-term (reusable modules).

Delegates to app.memory.short_term (Redis) and app.memory.long_term (MongoDB + mem0).
Any agent can use ShortTermMemory and/or LongTermMemory directly.
"""

from __future__ import annotations

from typing import Any

from app.config import get_settings
from app.exceptions import MemoryConnectionError, MemoryReadError, MemoryWriteError
from app.memory.long_term import LongTermMemory, LongTermMemoryConfig, LongTermMemoryError
from app.memory.short_term import ShortTermMemory, ShortTermMemoryConfig, ShortTermMemoryError
import structlog

log = structlog.get_logger(__name__)


class MemoryManager:
    """
    Short-term (ShortTermMemory) + long-term (LongTermMemory) for this app.

    Both backends are reusable; see app.memory.short_term and app.memory.long_term.
    """

    def __init__(
        self,
        redis_url: str | None = None,
        mongodb_url: str | None = None,
        mongodb_db: str | None = None,
        mongodb_collection: str | None = None,
        short_term_ttl_seconds: int | None = None,
        short_term_max_messages: int | None = None,
        short_term_config: ShortTermMemoryConfig | None = None,
        long_term_config: LongTermMemoryConfig | None = None,
    ) -> None:
        settings = get_settings()
        # Short-term
        st_cfg = short_term_config or ShortTermMemoryConfig.from_settings(settings)
        if redis_url is not None or short_term_ttl_seconds is not None or short_term_max_messages is not None:
            st_cfg = ShortTermMemoryConfig(
                redis_url=redis_url if redis_url is not None else st_cfg.redis_url,
                ttl_seconds=short_term_ttl_seconds if short_term_ttl_seconds is not None else st_cfg.ttl_seconds,
                max_messages=short_term_max_messages if short_term_max_messages is not None else st_cfg.max_messages,
                key_prefix=st_cfg.key_prefix,
            )
        self._short_term = ShortTermMemory(config=st_cfg)
        # Long-term
        lt_cfg = long_term_config or LongTermMemoryConfig.from_settings(settings)
        if mongodb_url is not None or mongodb_db is not None or mongodb_collection is not None:
            lt_cfg = LongTermMemoryConfig(
                mongodb_url=mongodb_url if mongodb_url is not None else lt_cfg.mongodb_url,
                mongodb_db=mongodb_db if mongodb_db is not None else lt_cfg.mongodb_db,
                mongodb_collection=mongodb_collection if mongodb_collection is not None else lt_cfg.mongodb_collection,
                mem0_collection=lt_cfg.mem0_collection,
                mem0_embedding_model=lt_cfg.mem0_embedding_model,
                mem0_embedding_dims=lt_cfg.mem0_embedding_dims,
                google_api_key=lt_cfg.google_api_key,
                gemini_model=lt_cfg.gemini_model,
            )
        self._long_term = LongTermMemory(config=lt_cfg)

    async def connect(self) -> None:
        """Initialize short-term (Redis). Long-term connects lazily on first use."""
        log.info("memory_manager_connect_start", backends=["short_term"])
        try:
            await self._short_term.connect()
            log.info("memory_manager_connect_ok", backends=["short_term"])
        except MemoryConnectionError:
            raise
        except ShortTermMemoryError as e:
            log.exception(
                "memory_manager_connect_failed",
                backend="short_term",
                error=str(e),
                error_type=type(e).__name__,
            )
            raise MemoryConnectionError(
                "Unable to connect to memory storage. Please try again later.",
                internal_message=str(e),
            ) from e
        except Exception as e:
            log.exception("memory_manager_connect_failed", backend="short_term", error=str(e), error_type=type(e).__name__)
            raise MemoryConnectionError(
                "Unable to connect to memory storage. Please try again later.",
                internal_message=str(e),
            ) from e

    async def close(self) -> None:
        """Close short-term and long-term connections."""
        log.info("memory_manager_close_start", backends=["short_term", "long_term"])
        try:
            await self._short_term.close()
            await self._long_term.close()
            log.info("memory_manager_close_ok")
        except Exception as e:
            log.exception("memory_manager_close_failed", error=str(e), error_type=type(e).__name__)
            raise

    async def save_short_term(self, session_id: str, data: dict[str, Any]) -> None:
        """Save short-term session context via ShortTermMemory."""
        log.info("memory_manager_save_short_term_start", operation="save_short_term", session_id=session_id)
        try:
            await self._short_term.save(session_id=session_id, data=data)
            log.info("memory_manager_save_short_term_ok", operation="save_short_term", session_id=session_id)
        except MemoryConnectionError:
            raise
        except ShortTermMemoryError as e:
            log.exception(
                "memory_manager_save_short_term_failed",
                operation="save_short_term",
                session_id=session_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise MemoryWriteError(
                "Failed to save session context.",
                internal_message=str(e),
            ) from e
        except Exception as e:
            log.exception(
                "memory_manager_save_short_term_failed",
                operation="save_short_term",
                session_id=session_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise MemoryWriteError(
                "Failed to save session context.",
                internal_message=str(e),
            ) from e

    async def get_short_term(self, session_id: str) -> dict[str, Any] | None:
        """Retrieve short-term context via ShortTermMemory."""
        log.info("memory_manager_get_short_term_start", operation="get_short_term", session_id=session_id)
        try:
            data = await self._short_term.get(session_id=session_id)
            log.info(
                "memory_manager_get_short_term_ok",
                operation="get_short_term",
                session_id=session_id,
                hit=data is not None,
                messages_count=len((data or {}).get("messages", [])),
            )
            return data
        except MemoryConnectionError:
            raise
        except ShortTermMemoryError as e:
            log.exception(
                "memory_manager_get_short_term_failed",
                operation="get_short_term",
                session_id=session_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise MemoryReadError(
                "Failed to retrieve session context.",
                internal_message=str(e),
            ) from e
        except Exception as e:
            log.exception(
                "memory_manager_get_short_term_failed",
                operation="get_short_term",
                session_id=session_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise MemoryReadError(
                "Failed to retrieve session context.",
                internal_message=str(e),
            ) from e

    async def save_long_term(
        self,
        user_id: str,
        session_id: str,
        data: dict[str, Any],
    ) -> None:
        """Persist interaction via LongTermMemory."""
        messages = data.get("messages", [])
        log.info(
            "memory_manager_save_long_term_start",
            operation="save_long_term",
            user_id=user_id,
            session_id=session_id,
            messages_count=len(messages),
        )
        if not messages:
            log.info("memory_manager_save_long_term_skip", operation="save_long_term", user_id=user_id, reason="no_messages")
            return
        try:
            await self._long_term.save(
                user_id=user_id,
                session_id=session_id,
                messages=messages,
                extracted_entities=data.get("extracted_entities", {}),
                user_preferences=data.get("user_preferences", {}),
                intent_history=data.get("intent_history", []),
            )
            log.info(
                "memory_manager_save_long_term_ok",
                operation="save_long_term",
                user_id=user_id,
                session_id=session_id,
                messages_count=len(messages),
            )
        except (LongTermMemoryError, RuntimeError) as e:
            log.exception(
                "memory_manager_save_long_term_failed",
                operation="save_long_term",
                user_id=user_id,
                session_id=session_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise MemoryWriteError(
                "Failed to persist conversation.",
                internal_message=str(e),
            ) from e
        except Exception as e:
            log.exception(
                "memory_manager_save_long_term_failed",
                operation="save_long_term",
                user_id=user_id,
                session_id=session_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise MemoryWriteError(
                "Failed to persist conversation.",
                internal_message=str(e),
            ) from e

    async def get_relevant_history(self, user_id: str, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Retrieve relevant long-term history via LongTermMemory."""
        log.info(
            "memory_manager_get_relevant_history_start",
            operation="get_relevant_history",
            user_id=user_id,
            query_preview=(query[:80] if query else "") or "(all)",
            limit=limit,
        )
        try:
            results = await self._long_term.get_relevant(user_id=user_id, query=query, limit=limit)
            log.info(
                "memory_manager_get_relevant_history_ok",
                operation="get_relevant_history",
                user_id=user_id,
                returned_count=len(results),
            )
            return results
        except LongTermMemoryError as e:
            log.exception(
                "memory_manager_get_relevant_history_failed",
                operation="get_relevant_history",
                user_id=user_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise MemoryReadError(
                "Failed to retrieve conversation history.",
                internal_message=str(e),
            ) from e
        except Exception as e:
            log.exception(
                "memory_manager_get_relevant_history_failed",
                operation="get_relevant_history",
                user_id=user_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise MemoryReadError(
                "Failed to retrieve conversation history.",
                internal_message=str(e),
            ) from e

    async def clear_session(self, session_id: str) -> None:
        """Clear short-term memory for the session via ShortTermMemory."""
        log.info("memory_manager_clear_session_start", operation="clear_session", session_id=session_id)
        try:
            await self._short_term.clear(session_id=session_id)
            log.info("memory_manager_clear_session_ok", operation="clear_session", session_id=session_id)
        except MemoryConnectionError:
            raise
        except ShortTermMemoryError as e:
            log.exception(
                "memory_manager_clear_session_failed",
                operation="clear_session",
                session_id=session_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise MemoryWriteError(
                "Failed to clear session.",
                internal_message=str(e),
            ) from e
        except Exception as e:
            log.exception(
                "memory_manager_clear_session_failed",
                operation="clear_session",
                session_id=session_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise MemoryWriteError(
                "Failed to clear session.",
                internal_message=str(e),
            ) from e

    async def run_mem0_diagnostic(self) -> dict:
        """Run mem0 init + one add and return result or error (for GET /memory/mem0-diagnostic)."""
        return await self._long_term.diagnose_mem0()
