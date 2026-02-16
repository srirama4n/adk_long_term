"""
Configuration for the procedural memory backend (how-to, skills, procedures).

Stored in a dedicated MongoDB collection.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class ProceduralMemoryConfig:
    """Configuration for procedural memory (MongoDB collection of procedures)."""

    mongodb_url: str = "mongodb://localhost:27017"
    mongodb_db: str = "agent_memory"
    procedural_collection: str = "agent_procedural"

    @classmethod
    def from_env(cls) -> "ProceduralMemoryConfig":
        """Build config from environment variables."""
        try:
            from pydantic_settings import BaseSettings, SettingsConfigDict

            class _EnvSettings(BaseSettings):
                model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
                mongodb_url: str = "mongodb://localhost:27017"
                mongodb_db: str = "agent_memory"
                procedural_collection: str = "agent_procedural"

            s = _EnvSettings()
            return cls(
                mongodb_url=s.mongodb_url,
                mongodb_db=s.mongodb_db,
                procedural_collection=s.procedural_collection,
            )
        except Exception:
            return cls()

    @classmethod
    def from_settings(cls, settings: Any) -> "ProceduralMemoryConfig":
        """Build from any object with mongodb_* and procedural_collection attributes."""
        return cls(
            mongodb_url=getattr(settings, "mongodb_url", "mongodb://localhost:27017"),
            mongodb_db=getattr(settings, "mongodb_db", "agent_memory"),
            procedural_collection=getattr(settings, "procedural_collection", "agent_procedural"),
        )
