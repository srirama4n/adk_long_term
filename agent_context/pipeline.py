"""
Context pipeline: retrieve (with optional cache) → filter → build parts → compact.

Produces the final user_message string and context data for persist. Reusable with any memory/cache.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from agent_context.compaction import apply_context_compaction
from agent_context.config import ContextConfig
from agent_context.filter import apply_context_filter
from agent_context.format import format_procedures_for_context


@dataclass
class BuildResult:
    """Result of building context: assembled user message and raw data for persist."""

    user_message: str
    short_term: dict[str, Any] | None
    long_term: list[dict[str, Any]]
    procedures: list[dict[str, Any]]


class ContextPipeline:
    """
    Build context for a supervisor turn: memory + optional cache + filter + compaction.
    Use with any memory that implements MemoryForContextProtocol.
    """

    def __init__(
        self,
        memory: Any,
        config: ContextConfig,
        cache: Any | None = None,
    ) -> None:
        self._memory = memory
        self._config = config
        self._cache = cache

    async def build(self, user_id: str, session_id: str, message: str) -> BuildResult:
        """
        Retrieve short-term, long-term, procedures; apply filter and compaction; return
        the assembled user_message and the data needed for after_turn persist.
        """
        short_term = await self._memory.get_short_term(session_id)
        short_term_messages = (short_term or {}).get("messages", [])

        long_term: list[dict[str, Any]] = []
        msg_hash = self._cache.message_hash(message) if self._cache else ""
        if self._cache and msg_hash:
            cached = await self._cache.get("lt", user_id, msg_hash)
            if cached is not None:
                long_term = cached
        if not long_term:
            long_term = await self._memory.get_relevant_history(
                user_id, message, limit=self._config.long_term_max_items
            )
            if self._cache and msg_hash:
                await self._cache.set("lt", (user_id, msg_hash), long_term)

        procedures: list[dict[str, Any]] = []
        try:
            if self._cache:
                cached = await self._cache.get("proc", user_id)
                if cached is not None:
                    procedures = cached
            if not procedures:
                procedures = await self._memory.list_procedures(
                    user_id,
                    limit=self._config.procedure_max_items,
                    include_docs=True,
                )
                if self._cache and procedures:
                    await self._cache.set("proc", (user_id,), procedures)
        except Exception:
            procedures = []

        if self._config.filter_enabled:
            long_term, procedures, short_term_messages = apply_context_filter(
                long_term,
                procedures,
                short_term_messages,
                long_term_max=self._config.long_term_max_items,
                long_term_min_score=self._config.long_term_min_score,
                procedure_max=self._config.procedure_max_items,
                short_term_recent_n=self._config.short_term_recent_n,
            )

        context_parts: list[str] = []
        if short_term_messages:
            context_parts.append("[Recent context] " + json.dumps(short_term_messages))
        if long_term:
            context_parts.append(
                "[Relevant history] "
                + json.dumps([h.get("intent_history", []) for h in long_term[: self._config.long_term_max_items]])
            )
        if procedures:
            context_parts.append("[Saved procedures]\n" + format_procedures_for_context(procedures))

        if not context_parts:
            return BuildResult(user_message=message, short_term=short_term, long_term=long_term, procedures=procedures)

        if self._config.compaction_enabled:
            compressed = apply_context_compaction(
                context_parts,
                self._config.compaction_max_chars_per_part,
                self._config.compaction_max_total_chars,
            )
            user_message = compressed + "\n\n[Current user message] " + message
        else:
            user_message = "\n\n".join(context_parts) + "\n\n[Current user message] " + message

        return BuildResult(user_message=user_message, short_term=short_term, long_term=long_term, procedures=procedures)
