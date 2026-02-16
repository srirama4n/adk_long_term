"""Configuration via environment variables."""

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # API
    app_name: str = "adk-multi-agent"
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"
    log_file: str = "logs/app.log"  # set empty to disable file logging

    # Memory feature flags (set false to disable a memory layer)
    short_term_enabled: bool = True
    long_term_enabled: bool = True
    episodic_enabled: bool = True
    semantic_enabled: bool = True
    procedural_enabled: bool = True

    # Redis (short-term memory)
    redis_url: str = "redis://localhost:6379/0"
    short_term_ttl_seconds: int = 1800  # 30 minutes
    short_term_max_messages: int = 20

    # MongoDB (long-term memory: raw docs + mem0 vector store)
    mongodb_url: str = "mongodb://localhost:27017"
    mongodb_db: str = "agent_memory"
    mongodb_collection: str = "agent_long_memory"
    # mem0 uses a dedicated collection for vector-backed semantic memory
    mem0_collection: str = "mem0_long_memory"
    mem0_embedding_model: str = "gemini-embedding-001"
    # Episodic, semantic, procedural memory collections
    episodic_collection: str = "agent_episodic"
    mem0_semantic_collection: str = "mem0_semantic"
    procedural_collection: str = "agent_procedural"
    offloaded_context_collection: str = "agent_offloaded_context"

    # LLM / ADK
    google_api_key: Optional[str] = None
    google_genai_use_vertexai: bool = False
    gemini_model: str = "gemini-2.0-flash"

    # Rate limiting
    rate_limit_requests: int = 100
    rate_limit_window_seconds: int = 60

    # Retry / circuit breaker
    tool_retry_attempts: int = 3
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_recovery_seconds: int = 60

    # OpenTelemetry
    otel_enabled: bool = False
    otel_service_name: str = "adk-multi-agent"

    # Context: offloading, filtering, caching, compaction
    context_offload_enabled: bool = True
    context_offload_message_threshold: int = 12  # offload when short-term messages exceed this
    context_offload_keep_recent: int = 5  # keep this many messages in active context when offloading

    context_filter_enabled: bool = True
    context_long_term_max_items: int = 5
    context_long_term_min_score: Optional[float] = None  # filter mem0 results by score (e.g. 0.3)
    context_procedure_max_items: int = 10
    context_short_term_recent_n: int = 3  # how many recent messages to include

    context_cache_enabled: bool = True
    context_cache_ttl_seconds: int = 60

    context_compaction_enabled: bool = True
    context_compaction_max_chars_per_part: int = 2800  # truncate each context part
    context_compaction_max_total_chars: int = 9000  # truncate total assembled context


@lru_cache
def get_settings() -> Settings:
    return Settings()
