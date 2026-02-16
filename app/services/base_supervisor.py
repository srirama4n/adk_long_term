"""
Base supervisor service: context build → agent run → persist.

Subclass and implement _run_agent() to plug in any supervisor agent. Uses app.context
for pipeline and persist so the same flow works with any memory implementation.
"""

from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from typing import Any, Callable

import structlog

from app.context import ContextConfig, ContextPipeline, after_turn
from app.context.pipeline import BuildResult

log = structlog.get_logger(__name__)


class BaseSupervisorService(ABC):
    """
    Template for a supervisor that: builds context (memory + cache + filter + compaction),
    runs the agent, then persists (offload, short-term, long-term, episode, fact, procedures).
    Subclass and implement _run_agent() and optionally override _build_context().
    """

    def __init__(
        self,
        memory: Any,
        context_config: ContextConfig,
        *,
        context_cache: Any | None = None,
        get_pending_procedures: Callable[[], list[dict[str, Any]]] | None = None,
        invalidate_procedure_cache: Callable[[str], Any] | None = None,
        after_persist_hook: Callable[[], Any] | None = None,
    ) -> None:
        self._memory = memory
        self._context_config = context_config
        self._context_cache = context_cache
        self._get_pending_procedures = get_pending_procedures or (lambda: [])
        self._invalidate_procedure_cache = invalidate_procedure_cache
        self._after_persist_hook = after_persist_hook
        self._pipeline = ContextPipeline(memory, context_config, cache=context_cache)

    async def ensure_connections(self) -> None:
        """Connect memory and optional cache. Override if your agent needs more."""
        await self._memory.connect()
        if self._context_cache and hasattr(self._context_cache, "connect"):
            await self._context_cache.connect()

    def _wrap_agent_error(self, e: Exception, flow_id: str | None = None) -> Exception:
        """Map low-level errors to app exceptions. Override in subclass for your exceptions."""
        return e

    async def _build_context(self, user_id: str, session_id: str, message: str) -> BuildResult:
        """Build context for this turn. Override to use a different pipeline or sources."""
        return await self._pipeline.build(user_id, session_id, message)

    @abstractmethod
    async def _run_agent(
        self,
        user_id: str,
        session_id: str,
        user_message: str,
        flow_id: str,
    ) -> tuple[str, dict[str, Any]]:
        """
        Run the supervisor agent with the assembled user_message.
        Return (intent, response_payload). Raise on failure.
        """
        ...

    async def _persist_after_turn(
        self,
        build_result: BuildResult,
        user_id: str,
        session_id: str,
        message: str,
        intent: str,
        response_payload: dict[str, Any],
    ) -> None:
        """Persist short-term, long-term, episode, fact, and any pending procedures."""

        async def on_procedure_saved(uid: str) -> None:
            if self._invalidate_procedure_cache:
                try:
                    r = self._invalidate_procedure_cache(uid)
                    if hasattr(r, "__await__"):
                        await r
                except Exception:
                    pass
            elif self._context_cache and hasattr(self._context_cache, "delete"):
                await self._context_cache.delete("proc", uid)

        await after_turn(
            self._memory,
            self._context_config,
            user_id=user_id,
            session_id=session_id,
            message=message,
            short_term_before=build_result.short_term,
            response_payload=response_payload,
            intent=intent,
            pending_procedures=self._get_pending_procedures(),
            on_procedure_saved=on_procedure_saved,
        )

    async def chat(self, user_id: str, session_id: str, message: str) -> dict[str, Any]:
        """
        Full flow: ensure connections → build context → run agent → persist → return.
        Subclass can override to add exception handling and map errors via _wrap_agent_error.
        """
        flow_id = f"{session_id}:{int(time.time() * 1000)}"
        await self.ensure_connections()
        build_result = await self._build_context(user_id, session_id, message)
        intent, response_payload = await self._run_agent(user_id, session_id, build_result.user_message, flow_id)
        await self._persist_after_turn(build_result, user_id, session_id, message, intent, response_payload)
        if self._after_persist_hook:
            try:
                r = self._after_persist_hook()
                if asyncio.iscoroutine(r):
                    await r
            except Exception:
                pass
        return {
            "session_id": session_id,
            "intent": intent,
            "response": response_payload,
        }
