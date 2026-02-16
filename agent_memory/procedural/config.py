"""Configuration for procedural memory (how-to, skills)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class ProceduralMemoryConfig:
    mongodb_url: str = "mongodb://localhost:27017"
    mongodb_db: str = "agent_memory"
    procedural_collection: str = "agent_procedural"

    @classmethod
    def from_env(cls) -> "ProceduralMemoryConfig":
        try:
            from pydantic_settings import BaseSettings, SettingsConfigDict

            class _EnvSettings(BaseSettings):
                model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
                mongodb_url: str = "mongodb://localhost:27017"
                mongodb_db: str = "agent_memory"
                procedural_collection: str = "agent_procedural"

            s = _EnvSettings()
            return cls(mongodb_url=s.mongodb_url, mongodb_db=s.mongodb_db, procedural_collection=s.procedural_collection)
        except Exception:
            return cls()

    @classmethod
    def from_settings(cls, settings: Any) -> "ProceduralMemoryConfig":
        return cls(
            mongodb_url=getattr(settings, "mongodb_url", "mongodb://localhost:27017"),
            mongodb_db=getattr(settings, "mongodb_db", "agent_memory"),
            procedural_collection=getattr(settings, "procedural_collection", "agent_procedural"),
        )
