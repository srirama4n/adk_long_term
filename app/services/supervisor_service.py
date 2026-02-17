"""
Supervisor orchestration: memory → context pipeline → run ADK Supervisor agent → persist → response.

Uses BaseSupervisorService and app.context for modular, reusable flow; this class wires
the ADK Supervisor agent, session resolve, and procedure tool (PENDING_PROCEDURES).
"""

from __future__ import annotations

import json
import re
import time
from typing import Any

import structlog
from google.genai import types

from app.agents.supervisor import get_supervisor_agent
from app.config import get_settings
from app.context import ContextConfig
from app.exceptions import (
    AgentQuotaError,
    AgentRunnerError,
    AgentSessionError,
    AppException,
    MemoryConnectionError,
    MemoryError as AppMemoryError,
)
from app.memory.memory_manager import MemoryManager
from app.services.base_supervisor_service import BaseSupervisorService
from app.tools.procedure_tool import PENDING_PROCEDURES
from app.utils.context_cache import ContextCache

log = structlog.get_logger(__name__)

try:
    from google.adk.runners import InMemoryRunner
except ImportError:
    InMemoryRunner = None  # type: ignore[misc, assignment]


def _infer_intent_from_events(events: list[Any]) -> str:
    """Infer intent from event authors (which sub-agent responded)."""
    for ev in reversed(events):
        author = getattr(ev, "author", None) or ""
        if "Weather" in author:
            return "weather_query"
        if "Finance" in author:
            return "finance_query"
        if "Procedure" in author:
            return "procedure_query"
    return "general_query"


def _extract_response_payload(events: list[Any]) -> dict[str, Any]:
    """Extract final text or structured content from the last model response event."""
    for ev in reversed(events):
        content = getattr(ev, "content", None)
        if not content:
            continue
        parts = getattr(content, "parts", []) or []
        for part in parts:
            text = getattr(part, "text", None)
            if text and not getattr(part, "partial", False):
                text = text.strip()
                match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text, re.DOTALL)
                if match:
                    try:
                        return json.loads(match.group())
                    except json.JSONDecodeError:
                        pass
                return {"message": text}
    return {"message": "No response generated."}


class SupervisorService(BaseSupervisorService):
    """ADK Supervisor: context pipeline + InMemoryRunner + procedure tool; uses BaseSupervisorService."""

    def __init__(self, memory: MemoryManager | None = None) -> None:
        self._memory = memory or MemoryManager()
        settings = get_settings()
        context_config = ContextConfig.from_settings(settings)
        context_cache: ContextCache | None = None
        if settings.context_cache_enabled:
            context_cache = ContextCache(settings.redis_url, ttl_seconds=settings.context_cache_ttl_seconds)

        self._pending_token = None

        def get_pending() -> list[dict[str, Any]]:
            try:
                return PENDING_PROCEDURES.get() or []
            except LookupError:
                return []

        async def invalidate_proc(uid: str) -> None:
            if context_cache:
                await context_cache.delete("proc", uid)

        def after_persist() -> None:
            if self._pending_token is not None:
                try:
                    PENDING_PROCEDURES.reset(self._pending_token)
                except Exception:
                    pass
                self._pending_token = None

        super().__init__(
            self._memory,
            context_config,
            context_cache=context_cache,
            get_pending_procedures=get_pending,
            invalidate_procedure_cache=invalidate_proc,
            after_persist_hook=after_persist,
        )
        self._agent = get_supervisor_agent()
        self._runner = None
        if InMemoryRunner is not None:
            self._runner = InMemoryRunner(self._agent, app_name="supervisor")

    def _wrap_agent_error(self, e: Exception, flow_id: str | None = None) -> Exception:
        err_str = str(e).lower()
        if "429" in err_str or "resource_exhausted" in err_str or "quota" in err_str:
            return AgentQuotaError(
                "Service is temporarily at capacity. Please try again in a moment.",
                internal_message=str(e),
            )
        if "session not found" in err_str or "session_id" in err_str:
            return AgentSessionError(
                "Invalid or expired session. Please start a new conversation.",
                internal_message=str(e),
            )
        if isinstance(e, (AppException, AppMemoryError)):
            return e
        return AgentRunnerError(
            "Agent request failed. Please try again.",
            internal_message=str(e),
        )

    async def chat(self, user_id: str, session_id: str, message: str) -> dict[str, Any]:
        flow_id = f"{session_id}:{int(time.time() * 1000)}"
        try:
            return await super().chat(user_id, session_id, message)
        except (AppException, AppMemoryError):
            raise
        except Exception as e:
            log.exception("chat_failed", flow_id=flow_id, user_id=user_id, session_id=session_id, error=str(e))
            raise self._wrap_agent_error(e, flow_id) from e
        finally:
            if self._pending_token is not None:
                try:
                    PENDING_PROCEDURES.reset(self._pending_token)
                except Exception:
                    pass
                self._pending_token = None

    async def _run_agent(
        self,
        user_id: str,
        session_id: str,
        user_message: str,
        flow_id: str,
    ) -> tuple[str, dict[str, Any]]:
        content = types.Content(parts=[types.Part(text=user_message)])
        events_list: list[Any] = []
        if self._runner:
            app_name = getattr(self._runner, "app_name", "supervisor") or "supervisor"
            session_service = getattr(self._runner, "session_service", None)
            if session_service:
                log.info("flow_step", flow_id=flow_id, step="session_resolve", app_name=app_name)
                existing = await session_service.get_session(
                    app_name=app_name, user_id=user_id, session_id=session_id
                )
                if existing is None:
                    await session_service.create_session(
                        app_name=app_name, user_id=user_id, session_id=session_id
                    )
                    log.info("flow_step", flow_id=flow_id, step="session_created", session_id=session_id)
                else:
                    log.info("flow_step", flow_id=flow_id, step="session_found", session_id=session_id)
            log.info(
                "flow_step",
                flow_id=flow_id,
                step="agent_invoke_start",
                agent="Supervisor",
                description="Running Supervisor (routes to WeatherAgent/FinanceAgent/ProcedureAgent)",
            )
            t0 = time.perf_counter()
            self._pending_token = PENDING_PROCEDURES.set([])
            try:
                async for event in self._runner.run_async(
                    user_id=user_id, session_id=session_id, new_message=content
                ):
                    events_list.append(event)
            finally:
                pass  # token reset in after_persist_hook
            elapsed = time.perf_counter() - t0
            log.info(
                "flow_step",
                flow_id=flow_id,
                step="agent_invoke_done",
                agent="Supervisor",
                event_count=len(events_list),
                elapsed_seconds=round(elapsed, 3),
            )
        intent = _infer_intent_from_events(events_list)
        response_payload = _extract_response_payload(events_list)
        log.info(
            "flow_step",
            flow_id=flow_id,
            step="intent_and_response",
            intent=intent,
            response_keys=list(response_payload.keys()) if isinstance(response_payload, dict) else [],
        )
        return intent, response_payload

    async def stream_chat(self, user_id: str, session_id: str, message: str):
        """Stream events from the supervisor (SSE). Does not use context pipeline."""
        log.info("stream_start", user_id=user_id, session_id=session_id, message_preview=message[:80] or "")
        try:
            await self.ensure_connections()
        except AppMemoryError:
            raise
        content = types.Content(parts=[types.Part(text=message)])
        if self._runner:
            try:
                event_count = 0
                async for event in self._runner.run_async(
                    user_id=user_id, session_id=session_id, new_message=content
                ):
                    event_count += 1
                    log.debug("stream_event", event_index=event_count, author=getattr(event, "author", ""))
                    yield event
                log.info("stream_done", session_id=session_id, event_count=event_count)
            except (AppException, AppMemoryError):
                raise
            except Exception as e:
                log.exception("stream_chat_failed", user_id=user_id, session_id=session_id, error=str(e))
                raise self._wrap_agent_error(e) from e
