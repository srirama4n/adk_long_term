"""Configuration for semantic memory (facts; vector search via mem0)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class SemanticMemoryConfig:
    mongodb_url: str = "mongodb://localhost:27017"
    mongodb_db: str = "agent_memory"
    mem0_collection: str = "mem0_semantic"
    mem0_embedding_model: str = "gemini-embedding-001"
    mem0_embedding_dims: int = 768
    google_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"

    @classmethod
    def from_env(cls) -> "SemanticMemoryConfig":
        try:
            from pydantic_settings import BaseSettings, SettingsConfigDict

            class _EnvSettings(BaseSettings):
                model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
                mongodb_url: str = "mongodb://localhost:27017"
                mongodb_db: str = "agent_memory"
                mem0_semantic_collection: str = "mem0_semantic"
                mem0_embedding_model: str = "gemini-embedding-001"
                google_api_key: Optional[str] = None
                gemini_model: str = "gemini-2.0-flash"

            s = _EnvSettings()
            return cls(
                mongodb_url=s.mongodb_url,
                mongodb_db=s.mongodb_db,
                mem0_collection=getattr(s, "mem0_semantic_collection", "mem0_semantic"),
                mem0_embedding_model=s.mem0_embedding_model,
                google_api_key=s.google_api_key or "",
                gemini_model=s.gemini_model,
            )
        except Exception:
            return cls()

    @classmethod
    def from_settings(cls, settings: Any) -> "SemanticMemoryConfig":
        return cls(
            mongodb_url=getattr(settings, "mongodb_url", "mongodb://localhost:27017"),
            mongodb_db=getattr(settings, "mongodb_db", "agent_memory"),
            mem0_collection=getattr(settings, "mem0_semantic_collection", "mem0_semantic"),
            mem0_embedding_model=getattr(settings, "mem0_embedding_model", "gemini-embedding-001"),
            mem0_embedding_dims=getattr(settings, "mem0_embedding_dims", 768),
            google_api_key=getattr(settings, "google_api_key", None) or "",
            gemini_model=getattr(settings, "gemini_model", "gemini-2.0-flash"),
        )
