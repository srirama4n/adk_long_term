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


@lru_cache
def get_settings() -> Settings:
    return Settings()
