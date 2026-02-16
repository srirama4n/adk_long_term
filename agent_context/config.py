"""
Configuration for the context pipeline: offloading, filtering, caching, compaction.

Build from env, from_dict(), or from_settings(any_object). No dependency on a host app.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ContextConfig:
    """Immutable config for context pipeline and persist."""

    offload_enabled: bool = True
    offload_message_threshold: int = 12
    offload_keep_recent: int = 5
    filter_enabled: bool = True
    long_term_max_items: int = 5
    long_term_min_score: float | None = None
    procedure_max_items: int = 10
    short_term_recent_n: int = 3
    cache_enabled: bool = True
    cache_ttl_seconds: int = 60
    compaction_enabled: bool = True
    compaction_max_chars_per_part: int = 2800
    compaction_max_total_chars: int = 9000

    @classmethod
    def from_env(cls) -> ContextConfig:
        """Build from environment variables (CONTEXT_*)."""
        try:
            from pydantic_settings import BaseSettings, SettingsConfigDict

            class _Env(BaseSettings):
                model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
                context_offload_enabled: bool = True
                context_offload_message_threshold: int = 12
                context_offload_keep_recent: int = 5
                context_filter_enabled: bool = True
                context_long_term_max_items: int = 5
                context_long_term_min_score: float | None = None
                context_procedure_max_items: int = 10
                context_short_term_recent_n: int = 3
                context_cache_enabled: bool = True
                context_cache_ttl_seconds: int = 60
                context_compaction_enabled: bool = True
                context_compaction_max_chars_per_part: int = 2800
                context_compaction_max_total_chars: int = 9000

            s = _Env()
            return cls(
                offload_enabled=s.context_offload_enabled,
                offload_message_threshold=s.context_offload_message_threshold,
                offload_keep_recent=s.context_offload_keep_recent,
                filter_enabled=s.context_filter_enabled,
                long_term_max_items=s.context_long_term_max_items,
                long_term_min_score=s.context_long_term_min_score,
                procedure_max_items=s.context_procedure_max_items,
                short_term_recent_n=s.context_short_term_recent_n,
                cache_enabled=s.context_cache_enabled,
                cache_ttl_seconds=s.context_cache_ttl_seconds,
                compaction_enabled=s.context_compaction_enabled,
                compaction_max_chars_per_part=s.context_compaction_max_chars_per_part,
                compaction_max_total_chars=s.context_compaction_max_total_chars,
            )
        except Exception:
            return cls()

    @classmethod
    def from_settings(cls, settings: Any) -> ContextConfig:
        """Build from any object with context_* attributes."""
        return cls(
            offload_enabled=getattr(settings, "context_offload_enabled", True),
            offload_message_threshold=getattr(settings, "context_offload_message_threshold", 12),
            offload_keep_recent=getattr(settings, "context_offload_keep_recent", 5),
            filter_enabled=getattr(settings, "context_filter_enabled", True),
            long_term_max_items=getattr(settings, "context_long_term_max_items", 5),
            long_term_min_score=getattr(settings, "context_long_term_min_score", None),
            procedure_max_items=getattr(settings, "context_procedure_max_items", 10),
            short_term_recent_n=getattr(settings, "context_short_term_recent_n", 3),
            cache_enabled=getattr(settings, "context_cache_enabled", True),
            cache_ttl_seconds=getattr(settings, "context_cache_ttl_seconds", 60),
            compaction_enabled=getattr(settings, "context_compaction_enabled", True),
            compaction_max_chars_per_part=getattr(settings, "context_compaction_max_chars_per_part", 2800),
            compaction_max_total_chars=getattr(settings, "context_compaction_max_total_chars", 9000),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ContextConfig:
        """Build from a dict. Keys can be snake_case or UPPER."""

        def g(k: str, default: Any) -> Any:
            return data.get(k, data.get(k.upper(), default))

        return cls(
            offload_enabled=g("context_offload_enabled", True),
            offload_message_threshold=g("context_offload_message_threshold", 12),
            offload_keep_recent=g("context_offload_keep_recent", 5),
            filter_enabled=g("context_filter_enabled", True),
            long_term_max_items=g("context_long_term_max_items", 5),
            long_term_min_score=g("context_long_term_min_score", None),
            procedure_max_items=g("context_procedure_max_items", 10),
            short_term_recent_n=g("context_short_term_recent_n", 3),
            cache_enabled=g("context_cache_enabled", True),
            cache_ttl_seconds=g("context_cache_ttl_seconds", 60),
            compaction_enabled=g("context_compaction_enabled", True),
            compaction_max_chars_per_part=g("context_compaction_max_chars_per_part", 2800),
            compaction_max_total_chars=g("context_compaction_max_total_chars", 9000),
        )
