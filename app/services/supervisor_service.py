"""
Supervisor orchestration: memory retrieval → run ADK Supervisor agent → persist memory → return structured response.
"""

from __future__ import annotations

import json
import re
import time
from typing import Any

import structlog
from google.genai import types

from app.agents.supervisor import get_supervisor_agent
from app.exceptions import (
    AgentQuotaError,
    AgentRunnerError,
    AgentSessionError,
    AppException,
    MemoryConnectionError,
    MemoryError as AppMemoryError,
)
from app.memory.memory_manager import MemoryManager
from app.tools.procedure_tool import PENDING_PROCEDURES

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


def _format_procedures_for_context(procedures: list[dict[str, Any]]) -> str:
    """Format saved procedures for injection into supervisor context (name, description, steps)."""
    lines = []
    for p in procedures:
        name = p.get("name") or "unnamed"
        desc = p.get("description") or ""
        steps = p.get("steps") or []
        block = f"- Procedure: {name}"
        if desc:
            block += f"\n  Description: {desc}"
        if steps:
            block += "\n  Steps:\n" + "\n".join(f"    {i + 1}. {s}" for i, s in enumerate(steps))
        lines.append(block)
    return "\n\n".join(lines) if lines else ""


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
                # Try to parse as JSON for structured response
                text = text.strip()
                # Extract JSON object if present
                match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text, re.DOTALL)
                if match:
                    try:
                        return json.loads(match.group())
                    except json.JSONDecodeError:
                        pass
                return {"message": text}
    return {"message": "No response generated."}


class SupervisorService:
    """Orchestrates memory, ADK Supervisor run, and response formatting."""

    def __init__(self, memory: MemoryManager | None = None) -> None:
        self._memory = memory or MemoryManager()
        self._agent = get_supervisor_agent()
        self._runner = None
        if InMemoryRunner is not None:
            self._runner = InMemoryRunner(self._agent, app_name="supervisor")

    async def ensure_connections(self) -> None:
        try:
            await self._memory.connect()
        except AppMemoryError:
            raise
        except Exception as e:
            log.exception("supervisor_ensure_connections_failed", error=str(e))
            raise MemoryConnectionError(
                "Memory service unavailable.",
                internal_message=str(e),
            ) from e

    def _wrap_agent_error(self, e: Exception, flow_id: str | None = None) -> Exception:
        """Map low-level errors to app exceptions."""
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
        """Full flow with exception handling. Re-raises AppException / AppMemoryError."""
        flow_id = f"{session_id}:{int(time.time() * 1000)}"
        try:
            return await self._chat_impl(user_id, session_id, message, flow_id)
        except (AppException, AppMemoryError):
            raise
        except Exception as e:
            log.exception("chat_failed", flow_id=flow_id, user_id=user_id, session_id=session_id, error=str(e))
            raise self._wrap_agent_error(e, flow_id) from e

    async def _chat_impl(self, user_id: str, session_id: str, message: str, flow_id: str) -> dict[str, Any]:
        """Full flow: get memory → build message → run supervisor → save memory → return."""
        log.info(
            "flow_start",
            flow_id=flow_id,
            user_id=user_id,
            session_id=session_id,
            message_preview=message[:100] if message else "",
        )
        await self.ensure_connections()

        log.info("flow_step", flow_id=flow_id, step="memory_retrieve", description="Get short-term and long-term context")
        short_term = await self._memory.get_short_term(session_id)
        long_term = await self._memory.get_relevant_history(user_id, message, limit=5)
        log.info(
            "flow_step",
            flow_id=flow_id,
            step="memory_retrieved",
            short_term_hit=short_term is not None,
            short_term_messages=len((short_term or {}).get("messages", [])),
            long_term_count=len(long_term),
        )

        # Procedural recall: load user's saved procedures for context (best effort)
        procedures_for_context: list[dict[str, Any]] = []
        try:
            procedures_for_context = await self._memory.list_procedures(
                user_id, limit=10, include_docs=True
            )
            if procedures_for_context:
                log.info(
                    "flow_step",
                    flow_id=flow_id,
                    step="procedural_retrieved",
                    procedures_count=len(procedures_for_context),
                )
        except Exception as e:
            log.warning(
                "procedural_recall_skip",
                flow_id=flow_id,
                user_id=user_id,
                error=str(e),
                error_type=type(e).__name__,
            )

        context_parts = []
        if short_term and short_term.get("messages"):
            context_parts.append("[Recent context] " + json.dumps(short_term.get("messages", [])[-3:]))
        if long_term:
            context_parts.append("[Relevant history] " + json.dumps([h.get("intent_history", []) for h in long_term[:2]]))
        if procedures_for_context:
            procedures_text = _format_procedures_for_context(procedures_for_context)
            context_parts.append("[Saved procedures]\n" + procedures_text)

        user_message = message
        if context_parts:
            user_message = "\n\n".join(context_parts) + "\n\n[Current user message] " + message

        content = types.Content(parts=[types.Part(text=user_message)])

        events_list: list[Any] = []
        if self._runner:
            app_name = getattr(self._runner, "app_name", "supervisor") or "supervisor"
            session_service = getattr(self._runner, "session_service", None)
            if session_service:
                log.info("flow_step", flow_id=flow_id, step="session_resolve", app_name=app_name)
                existing = await session_service.get_session(
                    app_name=app_name,
                    user_id=user_id,
                    session_id=session_id,
                )
                if existing is None:
                    await session_service.create_session(
                        app_name=app_name,
                        user_id=user_id,
                        session_id=session_id,
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
            # Set request-scoped list for ProcedureAgent tool so we can persist after run
            pending_procedures_token = PENDING_PROCEDURES.set([])
            try:
                async for event in self._runner.run_async(
                    user_id=user_id,
                    session_id=session_id,
                    new_message=content,
                ):
                    events_list.append(event)
                    author = getattr(event, "author", None) or ""
                    if author:
                        log.debug(
                            "flow_event",
                            flow_id=flow_id,
                            event_author=author,
                            has_content=bool(getattr(event, "content", None)),
                        )
            finally:
                # Persist any procedures recorded by ProcedureAgent during the run
                try:
                    pending = PENDING_PROCEDURES.get()
                except LookupError:
                    pending = []
                if pending:
                    for p in pending:
                        try:
                            await self._memory.add_procedure(
                                user_id,
                                p.get("name", "unnamed"),
                                p.get("steps", []),
                                description=p.get("description"),
                            )
                            log.info(
                                "procedure_saved",
                                flow_id=flow_id,
                                user_id=user_id,
                                name=p.get("name"),
                                steps_count=len(p.get("steps", [])),
                            )
                        except Exception as e:
                            log.warning(
                                "procedure_save_skip",
                                flow_id=flow_id,
                                user_id=user_id,
                                name=p.get("name"),
                                error=str(e),
                                error_type=type(e).__name__,
                            )
                PENDING_PROCEDURES.reset(pending_procedures_token)
            elapsed = time.perf_counter() - t0
            authors = [getattr(e, "author", None) or "" for e in events_list if getattr(e, "author", None)]
            log.info(
                "flow_step",
                flow_id=flow_id,
                step="agent_invoke_done",
                agent="Supervisor",
                event_count=len(events_list),
                event_authors=authors,
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

        new_messages = (short_term or {}).get("messages", []) + [
            {"role": "user", "content": message},
            {"role": "assistant", "content": response_payload, "intent": intent},
        ]

        log.info("flow_step", flow_id=flow_id, step="memory_persist", description="Save short-term (Redis) and long-term (MongoDB)")
        await self._memory.save_short_term(
            session_id,
            {
                "session_context": (short_term or {}).get("session_context", {}),
                "messages": new_messages[-20:],
                "current_conversation_state": {"last_intent": intent},
            },
        )
        await self._memory.save_long_term(
            user_id,
            session_id,
            {
                "messages": [{"role": "user", "content": message}, {"role": "assistant", "content": response_payload}],
                "extracted_entities": {},
                "user_preferences": {},
                "intent_history": [(message, intent)],
            },
        )

        # Episodic: one episode per turn (best effort; do not fail chat)
        try:
            content = {"user_message": (message or "")[:300], "intent": intent, "response_preview": str(response_payload)[:200]}
            await self._memory.add_episode(user_id, session_id, event_type="turn", content=content)
        except Exception as e:
            log.warning("episodic_add_skip", flow_id=flow_id, user_id=user_id, error=str(e), error_type=type(e).__name__)

        # Semantic: one short fact per turn (best effort; do not fail chat)
        try:
            fact = f"User asked: {(message or '')[:100]}; intent was {intent}."
            await self._memory.add_fact(user_id, fact)
        except Exception as e:
            log.warning("semantic_add_skip", flow_id=flow_id, user_id=user_id, error=str(e), error_type=type(e).__name__)

        log.info(
            "flow_end",
            flow_id=flow_id,
            user_id=user_id,
            session_id=session_id,
            intent=intent,
            response_preview=str(response_payload)[:200],
        )
        return {
            "session_id": session_id,
            "intent": intent,
            "response": response_payload,
        }

    async def stream_chat(self, user_id: str, session_id: str, message: str):
        """Stream events from the supervisor (SSE). Raises AppException / AppMemoryError on failure."""
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
                    user_id=user_id,
                    session_id=session_id,
                    new_message=content,
                ):
                    event_count += 1
                    author = getattr(event, "author", None) or ""
                    log.debug("stream_event", event_index=event_count, author=author)
                    yield event
                log.info("stream_done", session_id=session_id, event_count=event_count)
            except (AppException, AppMemoryError):
                raise
            except Exception as e:
                log.exception("stream_chat_failed", user_id=user_id, session_id=session_id, error=str(e))
                raise self._wrap_agent_error(e) from e
