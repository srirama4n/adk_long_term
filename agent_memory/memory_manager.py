"""
Unified memory: short-term, long-term, episodic, semantic, procedural.

Config via constructor (all optional) or from_env() when a config is not passed.
No dependency on any host app; use in any project.
"""

from __future__ import annotations

from typing import Any

from agent_memory.episodic import EpisodicMemory, EpisodicMemoryConfig, EpisodicMemoryError
from agent_memory.exceptions import MemoryConnectionError, MemoryReadError, MemoryWriteError
from agent_memory.long_term import LongTermMemory, LongTermMemoryConfig, LongTermMemoryError
from agent_memory.procedural import ProceduralMemory, ProceduralMemoryConfig, ProceduralMemoryError
from agent_memory.semantic import SemanticMemory, SemanticMemoryConfig, SemanticMemoryError
from agent_memory.short_term import ShortTermMemory, ShortTermMemoryConfig, ShortTermMemoryError

try:
    import structlog
    log = structlog.get_logger(__name__)
except Exception:
    import logging
    log = logging.getLogger(__name__)


class MemoryManager:
    """
    Single entry point for short-term, long-term, episodic, semantic, and procedural memory.

    Pass configs explicitly or leave None to use from_env() for each layer.
    Use from_settings(settings) on each config class when integrating with your app's settings.
    """

    def __init__(
        self,
        *,
        short_term_config: ShortTermMemoryConfig | None = None,
        long_term_config: LongTermMemoryConfig | None = None,
        episodic_config: EpisodicMemoryConfig | None = None,
        semantic_config: SemanticMemoryConfig | None = None,
        procedural_config: ProceduralMemoryConfig | None = None,
    ) -> None:
        self._short_term = ShortTermMemory(config=short_term_config or ShortTermMemoryConfig.from_env())
        self._long_term = LongTermMemory(config=long_term_config or LongTermMemoryConfig.from_env())
        self._episodic = EpisodicMemory(config=episodic_config or EpisodicMemoryConfig.from_env())
        self._semantic = SemanticMemory(config=semantic_config or SemanticMemoryConfig.from_env())
        self._procedural = ProceduralMemory(config=procedural_config or ProceduralMemoryConfig.from_env())

    async def connect(self) -> None:
        try:
            await self._short_term.connect()
        except ShortTermMemoryError as e:
            raise MemoryConnectionError(str(e), internal_message=str(e)) from e
        except Exception as e:
            raise MemoryConnectionError(str(e), internal_message=str(e)) from e

    async def close(self) -> None:
        await self._short_term.close()
        await self._long_term.close()
        await self._episodic.close()
        await self._semantic.close()
        await self._procedural.close()

    async def save_short_term(self, session_id: str, data: dict[str, Any]) -> None:
        try:
            await self._short_term.save(session_id=session_id, data=data)
        except ShortTermMemoryError as e:
            raise MemoryWriteError(str(e), internal_message=str(e)) from e

    async def get_short_term(self, session_id: str) -> dict[str, Any] | None:
        try:
            return await self._short_term.get(session_id=session_id)
        except ShortTermMemoryError as e:
            raise MemoryReadError(str(e), internal_message=str(e)) from e

    async def save_long_term(
        self,
        user_id: str,
        session_id: str,
        data: dict[str, Any],
    ) -> None:
        messages = data.get("messages", [])
        if not messages:
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
        except LongTermMemoryError as e:
            raise MemoryWriteError(str(e), internal_message=str(e)) from e

    async def get_relevant_history(self, user_id: str, query: str, limit: int = 10) -> list[dict[str, Any]]:
        try:
            return await self._long_term.get_relevant(user_id=user_id, query=query, limit=limit)
        except LongTermMemoryError as e:
            raise MemoryReadError(str(e), internal_message=str(e)) from e

    async def clear_session(self, session_id: str) -> None:
        try:
            await self._short_term.clear(session_id=session_id)
        except ShortTermMemoryError as e:
            raise MemoryWriteError(str(e), internal_message=str(e)) from e

    async def run_mem0_diagnostic(self) -> dict:
        return await self._long_term.diagnose_mem0()

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
            return await self._episodic.add_episode(
                user_id=user_id,
                session_id=session_id,
                event_type=event_type,
                content=content,
                summary=summary,
                metadata=metadata,
            )
        except EpisodicMemoryError as e:
            raise MemoryWriteError(str(e), internal_message=str(e)) from e

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
            return await self._episodic.get_episodes(
                user_id=user_id,
                session_id=session_id,
                since_iso=since_iso,
                event_type=event_type,
                limit=limit,
            )
        except EpisodicMemoryError as e:
            raise MemoryReadError(str(e), internal_message=str(e)) from e

    async def add_fact(self, user_id: str, fact: str, *, metadata: dict[str, Any] | None = None) -> None:
        try:
            await self._semantic.add_fact(user_id=user_id, fact=fact, metadata=metadata)
        except SemanticMemoryError as e:
            raise MemoryWriteError(str(e), internal_message=str(e)) from e

    async def search_facts(self, user_id: str, query: str, limit: int = 10) -> list[dict[str, Any]]:
        try:
            return await self._semantic.search_facts(user_id=user_id, query=query, limit=limit)
        except SemanticMemoryError as e:
            raise MemoryReadError(str(e), internal_message=str(e)) from e

    async def get_all_facts(self, user_id: str, limit: int = 50) -> list[dict[str, Any]]:
        try:
            return await self._semantic.get_all_facts(user_id=user_id, limit=limit)
        except SemanticMemoryError as e:
            raise MemoryReadError(str(e), internal_message=str(e)) from e

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
            return await self._procedural.add_procedure(
                user_id=user_id,
                name=name,
                steps=steps,
                description=description,
                conditions=conditions,
                metadata=metadata,
            )
        except ProceduralMemoryError as e:
            raise MemoryWriteError(str(e), internal_message=str(e)) from e

    async def get_procedure(self, user_id: str, name: str) -> dict[str, Any] | None:
        try:
            return await self._procedural.get_procedure(user_id=user_id, name=name)
        except ProceduralMemoryError as e:
            raise MemoryReadError(str(e), internal_message=str(e)) from e

    async def list_procedures(
        self,
        user_id: str,
        limit: int = 50,
        *,
        include_docs: bool = False,
    ) -> list[dict[str, Any]]:
        try:
            return await self._procedural.list_procedures(
                user_id=user_id,
                limit=limit,
                include_docs=include_docs,
            )
        except ProceduralMemoryError as e:
            raise MemoryReadError(str(e), internal_message=str(e)) from e
