"""
Semantic memory store: facts and concepts with vector search (mem0).

Stores and retrieves semantic facts by user_id; search is embedding-based.
"""

from __future__ import annotations

from typing import Any, List, Optional

from mem0 import AsyncMemory

from app.memory.semantic.config import SemanticMemoryConfig

try:
    import structlog
    log = structlog.get_logger(__name__)
except Exception:
    import logging
    log = logging.getLogger(__name__)


class SemanticMemoryError(Exception):
    """Raised when semantic memory operations fail."""

    def __init__(
        self,
        message: str,
        *,
        operation: str = "",
        user_id: str = "",
        cause: Optional[Exception] = None,
    ) -> None:
        super().__init__(message)
        self.operation = operation
        self.user_id = user_id
        self.cause = cause


def _mem0_config_from_cfg(cfg: SemanticMemoryConfig) -> dict[str, Any]:
    """Build mem0 config dict from SemanticMemoryConfig."""
    return {
        "vector_store": {
            "provider": "mongodb",
            "config": {
                "db_name": cfg.mongodb_db,
                "collection_name": cfg.mem0_collection,
                "mongo_uri": cfg.mongodb_url,
                "embedding_model_dims": cfg.mem0_embedding_dims,
            },
        },
        "embedder": {
            "provider": "gemini",
            "config": {
                "model": cfg.mem0_embedding_model,
                "api_key": cfg.google_api_key,
                "embedding_dims": cfg.mem0_embedding_dims,
            },
        },
        "llm": {
            "provider": "gemini",
            "config": {
                "model": cfg.gemini_model,
                "api_key": cfg.google_api_key,
            },
        },
    }


def _mem0_result_to_fact(item: Any) -> dict[str, Any]:
    """Map mem0 result to a fact item dict."""
    if not isinstance(item, dict):
        item = getattr(item, "__dict__", {}) or {}
    meta = (item.get("metadata") if isinstance(item, dict) else getattr(item, "metadata", None)) or {}
    if not isinstance(meta, dict):
        meta = {}
    return {
        "id": str(item.get("id", "") if isinstance(item, dict) else getattr(item, "id", "")),
        "memory": str(item.get("memory", "") if isinstance(item, dict) else getattr(item, "memory", "")),
        "metadata": meta,
        "created_at": item.get("created_at") if isinstance(item, dict) else getattr(item, "created_at", None),
        "updated_at": item.get("updated_at") if isinstance(item, dict) else getattr(item, "updated_at", None),
    }


class SemanticMemory:
    """
    Semantic memory: store and search facts/concepts by user (vector search via mem0).

    - add_fact(): store a fact for a user (infer=False to avoid LLM extraction).
    - search_facts(): semantic search over the user's facts.
    - get_all_facts(): list all facts for a user (up to limit).

    Example (standalone):
        config = SemanticMemoryConfig.from_env()
        memory = SemanticMemory(config=config)
        await memory.connect()
        await memory.add_fact(user_id="alice", fact="User prefers dark mode.")
        results = await memory.search_facts(user_id="alice", query="UI preferences", limit=5)
        await memory.close()
    """

    def __init__(self, config: Optional[SemanticMemoryConfig] = None) -> None:
        self._config = config or SemanticMemoryConfig.from_env()
        self._mem0: Optional[AsyncMemory] = None
        self._mem0_config = _mem0_config_from_cfg(self._config)

    async def connect(self) -> None:
        """Pre-initialize mem0. Otherwise connection is lazy on first use."""
        log.info("semantic_connect_start")
        try:
            await self._ensure_mem0()
            log.info("semantic_connect_ok")
        except Exception as e:
            log.exception("semantic_connect_failed", error=str(e), error_type=type(e).__name__)
            raise SemanticMemoryError(f"Semantic memory connect failed: {e}", operation="connect", cause=e) from e

    async def close(self) -> None:
        """Release mem0 reference (no explicit close in mem0)."""
        log.info("semantic_close_start")
        self._mem0 = None
        log.info("semantic_close_ok")

    async def _ensure_mem0(self) -> None:
        if self._mem0 is not None:
            return
        log.info("semantic_mem0_connect_start", collection=self._config.mem0_collection)
        try:
            self._mem0 = await AsyncMemory.from_config(self._mem0_config)
            log.info("semantic_mem0_connected", collection=self._config.mem0_collection)
        except Exception as e:
            log.exception("semantic_mem0_connect_failed", error=str(e), error_type=type(e).__name__)
            raise SemanticMemoryError(f"mem0 init failed: {e}", operation="ensure_mem0", cause=e) from e

    async def add_fact(
        self,
        user_id: str,
        fact: str,
        *,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        Store a semantic fact for the user. Uses mem0 add with infer=False (no LLM extraction).
        """
        log.info("semantic_add_fact_start", operation="add_fact", user_id=user_id)
        if not (user_id or "").strip() or not (fact or "").strip():
            log.info("semantic_add_fact_skip", reason="empty_user_or_fact")
            return
        try:
            await self._ensure_mem0()
            await self._mem0.add(
                messages=[{"role": "user", "content": (fact or "").strip()}],
                user_id=user_id.strip(),
                metadata=metadata or {},
                infer=False,
            )
            log.info("semantic_add_fact_ok", operation="add_fact", user_id=user_id)
        except SemanticMemoryError:
            raise
        except Exception as e:
            log.exception(
                "semantic_add_fact_failed",
                operation="add_fact",
                user_id=user_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise SemanticMemoryError(
                f"Failed to add fact: {e}",
                operation="add_fact",
                user_id=user_id,
                cause=e,
            ) from e

    async def search_facts(
        self,
        user_id: str,
        query: str,
        limit: int = 10,
    ) -> List[dict[str, Any]]:
        """Semantic search over the user's facts. Returns list of fact dicts."""
        log.info(
            "semantic_search_start",
            operation="search_facts",
            user_id=user_id,
            query_preview=(query[:80] if query else "") or "(all)",
            limit=limit,
        )
        if not (user_id or "").strip():
            log.info("semantic_search_skip", operation="search_facts", reason="empty_user_id")
            return []
        try:
            await self._ensure_mem0()
            if (query or "").strip():
                out = await self._mem0.search(
                    query=(query or "").strip(),
                    user_id=user_id.strip(),
                    limit=limit,
                )
            else:
                out = await self._mem0.get_all(user_id=user_id.strip(), limit=limit)
            raw = (out or {}).get("results") if isinstance(out, dict) else []
            if not isinstance(raw, list):
                raw = []
            results = []
            for r in raw[:limit]:
                try:
                    results.append(_mem0_result_to_fact(r))
                except Exception as e:
                    log.warning(
                        "semantic_item_skip",
                        operation="search_facts",
                        user_id=user_id,
                        error=str(e),
                        error_type=type(e).__name__,
                    )
            log.info(
                "semantic_search_ok",
                operation="search_facts",
                user_id=user_id,
                returned_count=len(results),
            )
            return results
        except SemanticMemoryError:
            raise
        except Exception as e:
            log.exception(
                "semantic_search_failed",
                operation="search_facts",
                user_id=user_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            return []

    async def get_all_facts(self, user_id: str, limit: int = 50) -> List[dict[str, Any]]:
        """Retrieve all facts for a user (same as search_facts with empty query)."""
        return await self.search_facts(user_id=user_id, query="", limit=limit)
