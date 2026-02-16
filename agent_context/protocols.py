"""Protocols for memory and cache used by the context pipeline and persist."""

from __future__ import annotations

from typing import Any, Protocol


class MemoryForContextProtocol(Protocol):
    """Minimal memory interface for context building: retrieve only."""

    async def get_short_term(self, session_id: str) -> dict[str, Any] | None: ...
    async def get_relevant_history(self, user_id: str, query: str, limit: int = 10) -> list[dict[str, Any]]: ...
    async def list_procedures(
        self, user_id: str, limit: int = 50, *, include_docs: bool = False
    ) -> list[dict[str, Any]]: ...


class MemoryForPersistProtocol(Protocol):
    """Minimal memory interface for after-turn persist: write and offload."""

    async def save_short_term(self, session_id: str, data: dict[str, Any]) -> None: ...
    async def save_long_term(self, user_id: str, session_id: str, data: dict[str, Any]) -> None: ...
    async def offload_context(self, user_id: str, session_id: str, messages: list[dict[str, Any]]) -> None: ...
    async def add_episode(
        self,
        user_id: str,
        session_id: str,
        event_type: str,
        content: str | dict[str, Any],
        *,
        summary: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str: ...
    async def add_fact(self, user_id: str, fact: str, *, metadata: dict[str, Any] | None = None) -> str: ...
    async def add_procedure(
        self,
        user_id: str,
        name: str,
        steps: list[str],
        *,
        description: str | None = None,
    ) -> str: ...


class ContextCacheProtocol(Protocol):
    """Optional cache for context components: get/set/delete by key parts."""

    async def get(self, prefix: str, *key_parts: str) -> Any | None: ...
    async def set(self, prefix: str, key_parts: tuple[str, ...], value: Any) -> None: ...
    async def delete(self, prefix: str, *key_parts: str) -> None: ...

    @staticmethod
    def message_hash(message: str, length: int = 16) -> str: ...
