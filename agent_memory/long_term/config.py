"""
Configuration for the reusable long-term memory backend.

Can be built from environment variables, from your app's settings, or passed explicitly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class LongTermMemoryConfig:
    """Configuration for MongoDB (raw docs) + mem0 (semantic search)."""

    mongodb_url: str = "mongodb://localhost:27017"
    mongodb_db: str = "agent_memory"
    mongodb_collection: str = "agent_long_memory"
    mem0_collection: str = "mem0_long_memory"
    mem0_embedding_model: str = "gemini-embedding-001"
    mem0_embedding_dims: int = 768
    google_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"

    @classmethod
    def from_env(cls) -> "LongTermMemoryConfig":
        """Build config from environment variables."""
        try:
            from pydantic_settings import BaseSettings, SettingsConfigDict

            class _EnvSettings(BaseSettings):
                model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
                mongodb_url: str = "mongodb://localhost:27017"
                mongodb_db: str = "agent_memory"
                mongodb_collection: str = "agent_long_memory"
                mem0_collection: str = "mem0_long_memory"
                mem0_embedding_model: str = "gemini-embedding-001"
                google_api_key: Optional[str] = None
                gemini_model: str = "gemini-2.0-flash"

            s = _EnvSettings()
            return cls(
                mongodb_url=s.mongodb_url,
                mongodb_db=s.mongodb_db,
                mongodb_collection=s.mongodb_collection,
                mem0_collection=s.mem0_collection,
                mem0_embedding_model=s.mem0_embedding_model,
                google_api_key=s.google_api_key or "",
                gemini_model=s.gemini_model,
            )
        except Exception:
            return cls()

    @classmethod
    def from_settings(cls, settings: Any) -> "LongTermMemoryConfig":
        """Build from any object with mongodb_*, mem0_*, google_api_key, gemini_model attributes."""
        return cls(
            mongodb_url=getattr(settings, "mongodb_url", "mongodb://localhost:27017"),
            mongodb_db=getattr(settings, "mongodb_db", "agent_memory"),
            mongodb_collection=getattr(settings, "mongodb_collection", "agent_long_memory"),
            mem0_collection=getattr(settings, "mem0_collection", "mem0_long_memory"),
            mem0_embedding_model=getattr(settings, "mem0_embedding_model", "gemini-embedding-001"),
            mem0_embedding_dims=getattr(settings, "mem0_embedding_dims", 768),
            google_api_key=getattr(settings, "google_api_key", None) or "",
            gemini_model=getattr(settings, "gemini_model", "gemini-2.0-flash"),
        )
