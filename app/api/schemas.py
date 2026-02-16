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
