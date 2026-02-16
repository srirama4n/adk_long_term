"""
Exceptions for the agent_memory package.

Use these in any app that uses agent_memory; no dependency on host app.
"""

from __future__ import annotations


class MemoryError(Exception):
    """Base exception for memory layer errors."""

    def __init__(self, message: str, *, internal_message: str | None = None, **kwargs: object) -> None:
        super().__init__(message)
        self.internal_message = internal_message


class MemoryConnectionError(MemoryError):
    """Failed to connect to Redis or MongoDB."""


class MemoryReadError(MemoryError):
    """Failed to read from memory."""


class MemoryWriteError(MemoryError):
    """Failed to write to memory."""
