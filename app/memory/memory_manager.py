"""
App wrapper around the reusable agent_memory package.

Builds config from app.config.get_settings() and maps agent_memory exceptions
to app.exceptions so the rest of the app is unchanged.
"""

from __future__ import annotations

from typing import Any

import structlog

from app.config import get_settings
from app.exceptions import MemoryConnectionError, MemoryReadError, MemoryWriteError
from agent_memory import (
    EpisodicMemoryConfig,
    LongTermMemoryConfig,
    MemoryManager as AgentMemoryManager,
    ProceduralMemoryConfig,
    SemanticMemoryConfig,
    ShortTermMemoryConfig,
)
from agent_memory.exceptions import (
    MemoryConnectionError as AgentMemoryConnectionError,
    MemoryReadError as AgentMemoryReadError,
    MemoryWriteError as AgentMemoryWriteError,
)

log = structlog.get_logger(__name__)


class MemoryManager:
    """
    Short-term, long-term, episodic, semantic, and procedural memory for this app.

    Uses the agent_memory package; config from get_settings() or constructor overrides.
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
        episodic_config: EpisodicMemoryConfig | None = None,
        semantic_config: SemanticMemoryConfig | None = None,
        procedural_config: ProceduralMemoryConfig | None = None,
    ) -> None:
        settings = get_settings()
        st_cfg = short_term_config or ShortTermMemoryConfig.from_settings(settings)
        if redis_url is not None or short_term_ttl_seconds is not None or short_term_max_messages is not None:
            st_cfg = ShortTermMemoryConfig(
                redis_url=redis_url if redis_url is not None else st_cfg.redis_url,
                ttl_seconds=short_term_ttl_seconds if short_term_ttl_seconds is not None else st_cfg.ttl_seconds,
                max_messages=short_term_max_messages if short_term_max_messages is not None else st_cfg.max_messages,
                key_prefix=st_cfg.key_prefix,
            )
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
        ep_cfg = episodic_config or EpisodicMemoryConfig.from_settings(settings)
        sem_cfg = semantic_config or SemanticMemoryConfig.from_settings(settings)
        proc_cfg = procedural_config or ProceduralMemoryConfig.from_settings(settings)
        self._backend = AgentMemoryManager(
            short_term_config=st_cfg,
            long_term_config=lt_cfg,
            episodic_config=ep_cfg,
            semantic_config=sem_cfg,
            procedural_config=proc_cfg,
        )

    def _map_exception(self, e: Exception, default_message: str = "Memory operation failed.") -> Exception:
        if isinstance(e, AgentMemoryConnectionError):
            return MemoryConnectionError(default_message, internal_message=str(e))
        if isinstance(e, AgentMemoryReadError):
            return MemoryReadError(default_message, internal_message=str(e))
        if isinstance(e, AgentMemoryWriteError):
            return MemoryWriteError(default_message, internal_message=str(e))
        return MemoryReadError(default_message, internal_message=str(e))

    async def connect(self) -> None:
        try:
            await self._backend.connect()
        except AgentMemoryConnectionError as e:
            raise MemoryConnectionError(
                "Unable to connect to memory storage. Please try again later.",
                internal_message=str(e),
            ) from e
        except Exception as e:
            log.exception("memory_manager_connect_failed", error=str(e), error_type=type(e).__name__)
            raise MemoryConnectionError(
                "Unable to connect to memory storage. Please try again later.",
                internal_message=str(e),
            ) from e

    async def close(self) -> None:
        await self._backend.close()

    async def save_short_term(self, session_id: str, data: dict[str, Any]) -> None:
        try:
            await self._backend.save_short_term(session_id=session_id, data=data)
        except AgentMemoryWriteError as e:
            raise MemoryWriteError("Failed to save session context.", internal_message=str(e)) from e
        except Exception as e:
            log.exception("memory_manager_save_short_term_failed", session_id=session_id, error=str(e))
            raise MemoryWriteError("Failed to save session context.", internal_message=str(e)) from e

    async def get_short_term(self, session_id: str) -> dict[str, Any] | None:
        try:
            return await self._backend.get_short_term(session_id=session_id)
        except AgentMemoryReadError as e:
            raise MemoryReadError("Failed to retrieve session context.", internal_message=str(e)) from e
        except Exception as e:
            log.exception("memory_manager_get_short_term_failed", session_id=session_id, error=str(e))
            raise MemoryReadError("Failed to retrieve session context.", internal_message=str(e)) from e

    async def save_long_term(self, user_id: str, session_id: str, data: dict[str, Any]) -> None:
        try:
            await self._backend.save_long_term(user_id=user_id, session_id=session_id, data=data)
        except AgentMemoryWriteError as e:
            raise MemoryWriteError("Failed to persist conversation.", internal_message=str(e)) from e
        except Exception as e:
            log.exception("memory_manager_save_long_term_failed", user_id=user_id, session_id=session_id, error=str(e))
            raise MemoryWriteError("Failed to persist conversation.", internal_message=str(e)) from e

    async def get_relevant_history(self, user_id: str, query: str, limit: int = 10) -> list[dict[str, Any]]:
        try:
            return await self._backend.get_relevant_history(user_id=user_id, query=query, limit=limit)
        except AgentMemoryReadError as e:
            raise MemoryReadError("Failed to retrieve conversation history.", internal_message=str(e)) from e
        except Exception as e:
            log.exception("memory_manager_get_relevant_history_failed", user_id=user_id, error=str(e))
            raise MemoryReadError("Failed to retrieve conversation history.", internal_message=str(e)) from e

    async def clear_session(self, session_id: str) -> None:
        try:
            await self._backend.clear_session(session_id=session_id)
        except AgentMemoryWriteError as e:
            raise MemoryWriteError("Failed to clear session.", internal_message=str(e)) from e
        except Exception as e:
            log.exception("memory_manager_clear_session_failed", session_id=session_id, error=str(e))
            raise MemoryWriteError("Failed to clear session.", internal_message=str(e)) from e

    async def run_mem0_diagnostic(self) -> dict:
        return await self._backend.run_mem0_diagnostic()

    async def add_episode(
        self,
        user_id: str,
        session_id: str,
        event_type: str,
        content: str | dict[str, Any],
        *,
        summary: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        try:
            return await self._backend.add_episode(
                user_id=user_id,
                session_id=session_id,
                event_type=event_type,
                content=content,
                summary=summary,
                metadata=metadata,
            )
        except AgentMemoryWriteError as e:
            raise MemoryWriteError("Failed to store episode.", internal_message=str(e)) from e

    async def get_episodes(
        self,
        user_id: str,
        *,
        session_id: str | None = None,
        since_iso: str | None = None,
        event_type: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        try:
            return await self._backend.get_episodes(
                user_id=user_id,
                session_id=session_id,
                since_iso=since_iso,
                event_type=event_type,
                limit=limit,
            )
        except AgentMemoryReadError as e:
            raise MemoryReadError("Failed to retrieve episodes.", internal_message=str(e)) from e

    async def add_fact(self, user_id: str, fact: str, *, metadata: dict[str, Any] | None = None) -> None:
        try:
            await self._backend.add_fact(user_id=user_id, fact=fact, metadata=metadata)
        except AgentMemoryWriteError as e:
            raise MemoryWriteError("Failed to store fact.", internal_message=str(e)) from e

    async def search_facts(self, user_id: str, query: str, limit: int = 10) -> list[dict[str, Any]]:
        try:
            return await self._backend.search_facts(user_id=user_id, query=query, limit=limit)
        except AgentMemoryReadError as e:
            raise MemoryReadError("Failed to search facts.", internal_message=str(e)) from e

    async def get_all_facts(self, user_id: str, limit: int = 50) -> list[dict[str, Any]]:
        try:
            return await self._backend.get_all_facts(user_id=user_id, limit=limit)
        except AgentMemoryReadError as e:
            raise MemoryReadError("Failed to retrieve facts.", internal_message=str(e)) from e

    async def add_procedure(
        self,
        user_id: str,
        name: str,
        steps: list[str],
        *,
        description: str | None = None,
        conditions: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        try:
            return await self._backend.add_procedure(
                user_id=user_id,
                name=name,
                steps=steps,
                description=description,
                conditions=conditions,
                metadata=metadata,
            )
        except AgentMemoryWriteError as e:
            raise MemoryWriteError("Failed to store procedure.", internal_message=str(e)) from e

    async def get_procedure(self, user_id: str, name: str) -> dict[str, Any] | None:
        try:
            return await self._backend.get_procedure(user_id=user_id, name=name)
        except AgentMemoryReadError as e:
            raise MemoryReadError("Failed to retrieve procedure.", internal_message=str(e)) from e

    async def list_procedures(
        self,
        user_id: str,
        limit: int = 50,
        *,
        include_docs: bool = False,
    ) -> list[dict[str, Any]]:
        try:
            return await self._backend.list_procedures(
                user_id=user_id,
                limit=limit,
                include_docs=include_docs,
            )
        except AgentMemoryReadError as e:
            raise MemoryReadError("Failed to list procedures.", internal_message=str(e)) from e
