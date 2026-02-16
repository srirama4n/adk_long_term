"""
Application-specific exceptions with HTTP status codes and safe user-facing messages.
"""

from __future__ import annotations


class AppException(Exception):
    """Base exception for the application."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int = 500,
        detail: str | None = None,
        internal_message: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.detail = detail or message
        self.internal_message = internal_message


# ---------------------------------------------------------------------------
# Memory (Redis / MongoDB)
# ---------------------------------------------------------------------------


class MemoryError(AppException):
    """Base for memory layer errors."""

    def __init__(self, message: str, **kwargs: object) -> None:
        super().__init__(message, status_code=503, **kwargs)


class MemoryConnectionError(MemoryError):
    """Failed to connect to Redis or MongoDB."""


class MemoryReadError(MemoryError):
    """Failed to read from memory (get_short_term, get_relevant_history)."""


class MemoryWriteError(MemoryError):
    """Failed to write to memory (save_short_term, save_long_term)."""


# ---------------------------------------------------------------------------
# Agent / Supervisor / LLM
# ---------------------------------------------------------------------------


class AgentError(AppException):
    """Base for agent/runner/LLM errors."""

    def __init__(self, message: str, *, status_code: int = 502, **kwargs: object) -> None:
        super().__init__(message, status_code=status_code, **kwargs)


class AgentSessionError(AgentError):
    """Session not found or invalid (e.g. ADK session)."""

    def __init__(self, message: str, **kwargs: object) -> None:
        super().__init__(message, status_code=400, **kwargs)


class AgentQuotaError(AgentError):
    """LLM quota exceeded (e.g. 429 from Gemini)."""

    def __init__(self, message: str, **kwargs: object) -> None:
        super().__init__(message, status_code=429, **kwargs)


class AgentRunnerError(AgentError):
    """Runner or agent execution failed."""
