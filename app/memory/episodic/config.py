"""
Configuration for the episodic memory backend (event-based, session-scoped experiences).

Can be built from environment variables or from your app's settings.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class EpisodicMemoryConfig:
    """Configuration for episodic memory (MongoDB collection of episodes)."""

    mongodb_url: str = "mongodb://localhost:27017"
    mongodb_db: str = "agent_memory"
    episodic_collection: str = "agent_episodic"

    @classmethod
    def from_env(cls) -> "EpisodicMemoryConfig":
        """Build config from environment variables."""
        try:
            from pydantic_settings import BaseSettings, SettingsConfigDict

            class _EnvSettings(BaseSettings):
                model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
                mongodb_url: str = "mongodb://localhost:27017"
                mongodb_db: str = "agent_memory"
                episodic_collection: str = "agent_episodic"

            s = _EnvSettings()
            return cls(
                mongodb_url=s.mongodb_url,
                mongodb_db=s.mongodb_db,
                episodic_collection=s.episodic_collection,
            )
        except Exception:
            return cls()

    @classmethod
    def from_settings(cls, settings: Any) -> "EpisodicMemoryConfig":
        """Build from any object with mongodb_* and episodic_collection attributes."""
        return cls(
            mongodb_url=getattr(settings, "mongodb_url", "mongodb://localhost:27017"),
            mongodb_db=getattr(settings, "mongodb_db", "agent_memory"),
            episodic_collection=getattr(settings, "episodic_collection", "agent_episodic"),
        )
