"""Semantic memory store: facts/concepts with vector search (mem0)."""

from __future__ import annotations

from typing import Any, List, Optional

from mem0 import AsyncMemory

from agent_memory.semantic.config import SemanticMemoryConfig

try:
    import structlog
    log = structlog.get_logger(__name__)
except Exception:
    import logging
    log = logging.getLogger(__name__)


class SemanticMemoryError(Exception):
    def __init__(self, message: str, *, operation: str = "", user_id: str = "", cause: Optional[Exception] = None) -> None:
        super().__init__(message)
        self.operation = operation
        self.user_id = user_id
        self.cause = cause


def _mem0_config_from_cfg(cfg: SemanticMemoryConfig) -> dict[str, Any]:
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
            "config": {"model": cfg.gemini_model, "api_key": cfg.google_api_key},
        },
    }


def _mem0_result_to_fact(item: Any) -> dict[str, Any]:
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
    """Semantic memory: add_fact(), search_facts(), get_all_facts(). Uses mem0."""

    def __init__(self, config: Optional[SemanticMemoryConfig] = None) -> None:
        self._config = config or SemanticMemoryConfig.from_env()
        self._mem0: Optional[AsyncMemory] = None
        self._mem0_config = _mem0_config_from_cfg(self._config)

    async def connect(self) -> None:
        await self._ensure_mem0()

    async def close(self) -> None:
        self._mem0 = None

    async def _ensure_mem0(self) -> None:
        if self._mem0 is not None:
            return
        self._mem0 = await AsyncMemory.from_config(self._mem0_config)

    async def add_fact(self, user_id: str, fact: str, *, metadata: Optional[dict[str, Any]] = None) -> None:
        if not (user_id or "").strip() or not (fact or "").strip():
            return
        await self._ensure_mem0()
        await self._mem0.add(
            messages=[{"role": "user", "content": (fact or "").strip()}],
            user_id=user_id.strip(),
            metadata=metadata or {},
            infer=False,
        )

    async def search_facts(self, user_id: str, query: str, limit: int = 10) -> List[dict[str, Any]]:
        if not (user_id or "").strip():
            return []
        await self._ensure_mem0()
        if (query or "").strip():
            out = await self._mem0.search(query=(query or "").strip(), user_id=user_id.strip(), limit=limit)
        else:
            out = await self._mem0.get_all(user_id=user_id.strip(), limit=limit)
        raw = (out or {}).get("results") if isinstance(out, dict) else []
        if not isinstance(raw, list):
            raw = []
        return [_mem0_result_to_fact(r) for r in raw[:limit]]

    async def get_all_facts(self, user_id: str, limit: int = 50) -> List[dict[str, Any]]:
        return await self.search_facts(user_id=user_id, query="", limit=limit)

