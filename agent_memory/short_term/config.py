"""
Configuration for the reusable short-term memory backend (Redis).

Can be built from environment variables, from your app's settings, or passed explicitly
so any agent can use it without depending on this project's config.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class ShortTermMemoryConfig:
    """Configuration for Redis-backed session-scoped short-term memory."""

    redis_url: str = "redis://localhost:6379/0"
    ttl_seconds: int = 1800  # 30 minutes
    max_messages: int = 20
    key_prefix: str = "agent:short"

    @classmethod
    def from_env(cls) -> "ShortTermMemoryConfig":
        """Build config from environment variables (REDIS_URL, SHORT_TERM_TTL_SECONDS, etc.)."""
        try:
            from pydantic_settings import BaseSettings, SettingsConfigDict

            class _EnvSettings(BaseSettings):
                model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
                redis_url: str = "redis://localhost:6379/0"
                short_term_ttl_seconds: int = 1800
                short_term_max_messages: int = 20

            s = _EnvSettings()
            return cls(
                redis_url=s.redis_url,
                ttl_seconds=s.short_term_ttl_seconds,
                max_messages=s.short_term_max_messages,
            )
        except Exception:
            return cls()

    @classmethod
    def from_settings(cls, settings: Any) -> "ShortTermMemoryConfig":
        """Build from any object with redis_url, short_term_ttl_seconds, short_term_max_messages."""
        return cls(
            redis_url=getattr(settings, "redis_url", "redis://localhost:6379/0"),
            ttl_seconds=getattr(settings, "short_term_ttl_seconds", 1800),
            max_messages=getattr(settings, "short_term_max_messages", 20),
            key_prefix=getattr(settings, "short_term_key_prefix", "agent:short"),
        )
