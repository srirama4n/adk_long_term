"""Request/response schemas for the API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """POST /chat body."""

    user_id: str = Field(..., description="User identifier")
    session_id: str = Field(..., description="Session identifier")
    message: str = Field(..., description="User message")


class ChatResponse(BaseModel):
    """POST /chat response."""

    session_id: str
    intent: str = Field(..., description="weather_query | finance_query | general_query")
    response: dict[str, Any] = Field(default_factory=dict, description="Structured sub-agent output or message")


class MemoryResponse(BaseModel):
    """GET /memory/{user_id} response."""

    user_id: str
    memories: list[dict[str, Any]] = Field(default_factory=list)


# --- Episodic, semantic, procedural memory (separate from long-term) ---


class EpisodicResponse(BaseModel):
    """GET /memory/{user_id}/episodic response."""

    user_id: str
    episodes: list[dict[str, Any]] = Field(default_factory=list)


class AddEpisodicRequest(BaseModel):
    """POST /memory/{user_id}/episodic body."""

    session_id: str = Field(..., description="Session identifier")
    event_type: str = Field(..., description="e.g. turn, custom_event")
    content: str | dict[str, Any] = Field(..., description="Event content")
    summary: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SemanticResponse(BaseModel):
    """GET /memory/{user_id}/semantic response."""

    user_id: str
    facts: list[dict[str, Any]] = Field(default_factory=list)


class AddSemanticRequest(BaseModel):
    """POST /memory/{user_id}/semantic body."""

    fact: str = Field(..., description="Fact to store")
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProceduralResponse(BaseModel):
    """GET /memory/{user_id}/procedural response."""

    user_id: str
    procedures: list[dict[str, Any]] = Field(default_factory=list)


class AddProceduralRequest(BaseModel):
    """POST /memory/{user_id}/procedural body (procedural is separate; add only via API)."""

    name: str = Field(..., description="Procedure name")
    steps: list[str] = Field(..., description="Ordered steps")
    description: str | None = None
    conditions: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
