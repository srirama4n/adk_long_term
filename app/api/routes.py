"""FastAPI routes: /chat, /chat/stream, /memory, /session, /health."""

from __future__ import annotations

import json
from collections import defaultdict
from time import time
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.api.schemas import (
    AddEpisodicRequest,
    AddProceduralRequest,
    AddSemanticRequest,
    ChatRequest,
    ChatResponse,
    EpisodicResponse,
    MemoryResponse,
    ProceduralResponse,
    SemanticResponse,
)
from app.config import get_settings
from app.exceptions import AppException
from app.memory.memory_manager import MemoryManager
from app.services.supervisor_service import SupervisorService

log = structlog.get_logger(__name__)

# User-friendly messages for known errors (avoid leaking long API/ADK messages)
QUOTA_EXCEEDED_MESSAGE = (
    "Service is temporarily at capacity due to rate limits. "
    "Please wait a minute and try again, or check your API quota at https://ai.google.dev/gemini-api/docs/rate-limits."
)


def _normalize_error(exc: Exception) -> tuple[int, str]:
    """Map exceptions to (status_code, user-safe detail). Handles 429/quota from ADK or Gemini."""
    err_str = str(exc).lower()
    if "429" in err_str or "resource_exhausted" in err_str or "quota exceeded" in err_str:
        return 429, QUOTA_EXCEEDED_MESSAGE
    return 500, "An unexpected error occurred. Please try again."


router = APIRouter()

# In-memory rate limit (use Redis in production)
_rate_limit: dict[str, list[float]] = defaultdict(list)
_settings = get_settings()


def _rate_limit_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _check_rate_limit(request: Request) -> None:
    key = _rate_limit_key(request)
    now = time()
    window = _settings.rate_limit_window_seconds
    _rate_limit[key] = [t for t in _rate_limit[key] if now - t < window]
    if len(_rate_limit[key]) >= _settings.rate_limit_requests:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    _rate_limit[key].append(now)


def get_memory() -> MemoryManager:
    return MemoryManager()


def get_supervisor_service(memory: Annotated[MemoryManager, Depends(get_memory)]) -> SupervisorService:
    return SupervisorService(memory=memory)


@router.get("/health")
async def health() -> dict:
    """Health check for load balancers and Docker."""
    return {"status": "healthy", "service": "adk-multi-agent"}


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: Request,
    body: ChatRequest,
    service: Annotated[SupervisorService, Depends(get_supervisor_service)],
) -> ChatResponse:
    """
    Send a message through the Supervisor: memory retrieval → routing → sub-agent → response.
    """
    _check_rate_limit(request)
    log.info(
        "api_request",
        path="/chat",
        method="POST",
        user_id=body.user_id,
        session_id=body.session_id,
        message_preview=body.message[:80] if body.message else "",
    )
    try:
        result = await service.chat(body.user_id, body.session_id, body.message)
        log.info(
            "api_response",
            path="/chat",
            session_id=result.get("session_id"),
            intent=result.get("intent"),
            status="success",
        )
        return ChatResponse(**result)
    except AppException as e:
        log.warning(
            "api_error",
            path="/chat",
            error=e.detail,
            status_code=e.status_code,
            user_id=body.user_id,
            session_id=body.session_id,
        )
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
    except HTTPException:
        raise
    except Exception as e:
        log.exception("api_error", path="/chat", error=str(e), user_id=body.user_id, session_id=body.session_id)
        status_code, detail = _normalize_error(e)
        raise HTTPException(status_code=status_code, detail=detail) from e


@router.post("/chat/stream")
async def chat_stream(
    request: Request,
    body: ChatRequest,
    service: Annotated[SupervisorService, Depends(get_supervisor_service)],
):
    """Stream supervisor events as Server-Sent Events."""
    _check_rate_limit(request)
    log.info(
        "api_request",
        path="/chat/stream",
        method="POST",
        user_id=body.user_id,
        session_id=body.session_id,
        message_preview=body.message[:80] if body.message else "",
    )

    async def generate():
        try:
            async for event in service.stream_chat(body.user_id, body.session_id, body.message):
                data = _event_to_dict(event)
                yield f"data: {json.dumps(data, default=str)}\n\n"
        except AppException as e:
            log.warning("api_error", path="/chat/stream", error=e.detail, status_code=e.status_code)
            yield f"data: {json.dumps({'error': e.detail, 'status_code': e.status_code})}\n\n"
        except Exception as e:
            log.exception("api_error", path="/chat/stream", error=str(e))
            _, detail = _normalize_error(e)
            yield f"data: {json.dumps({'error': detail})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _event_to_dict(event) -> dict:
    """Convert ADK Event to a JSON-serializable dict."""
    d = {}
    if hasattr(event, "id"):
        d["id"] = event.id
    if hasattr(event, "author"):
        d["author"] = event.author
    if hasattr(event, "content"):
        c = event.content
        if c and hasattr(c, "parts"):
            d["parts"] = []
            for p in c.parts or []:
                if hasattr(p, "text"):
                    d["parts"].append({"text": p.text})
                elif hasattr(p, "function_call"):
                    d["parts"].append({"function_call": getattr(p, "function_call", None)})
    if hasattr(event, "timestamp"):
        d["timestamp"] = event.timestamp
    return d


@router.get("/memory/mem0-diagnostic")
async def mem0_diagnostic(
    memory: Annotated[MemoryManager, Depends(get_memory)],
) -> dict:
    """
    Run mem0 init + one add. Returns {ok, message} or {ok, error, traceback}.
    Use this to see why mem0_long_memory has no data (e.g. Atlas Search, API key).
    """
    try:
        result = await memory.run_mem0_diagnostic()
        return result
    except Exception as e:
        return {"ok": False, "error": str(e), "error_type": type(e).__name__, "traceback": ""}


@router.get("/memory/{user_id}", response_model=MemoryResponse)
async def get_memory_for_user(
    user_id: str,
    memory: Annotated[MemoryManager, Depends(get_memory)],
) -> MemoryResponse:
    """Return stored long-term memory for the user."""
    log.info("api_request", path="/memory/{user_id}", method="GET", user_id=user_id)
    try:
        await memory.connect()
        memories = await memory.get_relevant_history(user_id, "", limit=50)
        log.info("api_response", path="/memory/{user_id}", user_id=user_id, memories_count=len(memories))
        return MemoryResponse(user_id=user_id, memories=memories)
    except AppException as e:
        log.warning("api_error", path="/memory/{user_id}", error=e.detail, status_code=e.status_code)
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
    except Exception as e:
        log.exception("api_error", path="/memory/{user_id}", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve memory.") from e


# --- Episodic memory (populated from chat + optional manual add) ---


@router.get("/memory/{user_id}/episodic", response_model=EpisodicResponse)
async def get_episodic(
    user_id: str,
    memory: Annotated[MemoryManager, Depends(get_memory)],
    session_id: str | None = None,
    since_iso: str | None = None,
    event_type: str | None = None,
    limit: int = 50,
) -> EpisodicResponse:
    """Return episodic memory (events) for the user. Populated from chat; optional filters."""
    try:
        await memory.connect()
        episodes = await memory.get_episodes(
            user_id, session_id=session_id, since_iso=since_iso, event_type=event_type, limit=limit
        )
        return EpisodicResponse(user_id=user_id, episodes=episodes)
    except Exception as e:
        log.exception("api_error", path="/memory/{user_id}/episodic", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve episodic memory.") from e


@router.post("/memory/{user_id}/episodic")
async def add_episodic(
    user_id: str,
    body: AddEpisodicRequest,
    memory: Annotated[MemoryManager, Depends(get_memory)],
) -> dict:
    """Manually add one episode (optional; chat already adds one per turn)."""
    try:
        await memory.connect()
        episode_id = await memory.add_episode(
            user_id, body.session_id, body.event_type, body.content, summary=body.summary, metadata=body.metadata
        )
        return {"user_id": user_id, "episode_id": episode_id}
    except Exception as e:
        log.exception("api_error", path="POST /memory/{user_id}/episodic", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to add episode.") from e


# --- Semantic memory (populated from chat + optional manual add) ---


@router.get("/memory/{user_id}/semantic", response_model=SemanticResponse)
async def get_semantic(
    user_id: str,
    memory: Annotated[MemoryManager, Depends(get_memory)],
    query: str = "",
    limit: int = 50,
) -> SemanticResponse:
    """Return semantic memory (facts) for the user. Populated from chat; optional search query."""
    try:
        await memory.connect()
        if query.strip():
            facts = await memory.search_facts(user_id, query.strip(), limit=limit)
        else:
            facts = await memory.get_all_facts(user_id, limit=limit)
        return SemanticResponse(user_id=user_id, facts=facts)
    except Exception as e:
        log.exception("api_error", path="/memory/{user_id}/semantic", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve semantic memory.") from e


@router.post("/memory/{user_id}/semantic")
async def add_semantic(
    user_id: str,
    body: AddSemanticRequest,
    memory: Annotated[MemoryManager, Depends(get_memory)],
) -> dict:
    """Manually add one fact (optional; chat already adds one per turn)."""
    try:
        await memory.connect()
        await memory.add_fact(user_id, body.fact, metadata=body.metadata)
        return {"user_id": user_id, "status": "added"}
    except Exception as e:
        log.exception("api_error", path="POST /memory/{user_id}/semantic", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to add fact.") from e


# --- Procedural memory (separate: not populated from chat; add only via API) ---


@router.get("/memory/{user_id}/procedural", response_model=ProceduralResponse)
async def get_procedural(
    user_id: str,
    memory: Annotated[MemoryManager, Depends(get_memory)],
    include_docs: bool = True,
    limit: int = 50,
) -> ProceduralResponse:
    """Return procedural memory (how-to / skills) for the user. Not auto-populated; add via POST."""
    try:
        await memory.connect()
        procedures = await memory.list_procedures(user_id, limit=limit, include_docs=include_docs)
        return ProceduralResponse(user_id=user_id, procedures=procedures)
    except Exception as e:
        log.exception("api_error", path="/memory/{user_id}/procedural", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve procedural memory.") from e


@router.post("/memory/{user_id}/procedural")
async def add_procedural(
    user_id: str,
    body: AddProceduralRequest,
    memory: Annotated[MemoryManager, Depends(get_memory)],
) -> dict:
    """Add or update a procedure (procedural is separate from chat; only via this API)."""
    try:
        await memory.connect()
        procedure_id = await memory.add_procedure(
            user_id,
            body.name,
            body.steps,
            description=body.description,
            conditions=body.conditions,
            metadata=body.metadata,
        )
        return {"user_id": user_id, "procedure_id": procedure_id, "name": body.name}
    except Exception as e:
        log.exception("api_error", path="POST /memory/{user_id}/procedural", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to add procedure.") from e


@router.delete("/session/{session_id}")
async def clear_session(
    session_id: str,
    memory: Annotated[MemoryManager, Depends(get_memory)],
) -> dict:
    """Clear Redis short-term session memory."""
    log.info("api_request", path="/session/{session_id}", method="DELETE", session_id=session_id)
    try:
        await memory.connect()
        await memory.clear_session(session_id)
        log.info("api_response", path="/session/{session_id}", session_id=session_id, status="cleared")
        return {"status": "cleared", "session_id": session_id}
    except AppException as e:
        log.warning("api_error", path="/session/{session_id}", error=e.detail, status_code=e.status_code)
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
    except Exception as e:
        log.exception("api_error", path="/session/{session_id}", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to clear session.") from e
