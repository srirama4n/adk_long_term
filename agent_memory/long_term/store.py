"""
Reusable long-term memory store: MongoDB (raw docs) + mem0 (semantic search).
"""

from __future__ import annotations

import json
import traceback
import uuid
from datetime import datetime, timezone
from typing import Any, List, Optional

import certifi
from mem0 import AsyncMemory
from motor.motor_asyncio import AsyncIOMotorClient

from agent_memory.long_term.config import LongTermMemoryConfig

try:
    import structlog
    log = structlog.get_logger(__name__)
except Exception:
    import logging
    log = logging.getLogger(__name__)


class LongTermMemoryError(Exception):
    """Raised when long-term memory (MongoDB/mem0) operations fail."""

    def __init__(
        self,
        message: str,
        *,
        operation: str = "",
        user_id: str = "",
        session_id: str = "",
        cause: Optional[Exception] = None,
    ) -> None:
        super().__init__(message)
        self.operation = operation
        self.user_id = user_id
        self.session_id = session_id
        self.cause = cause


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _content_to_string(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        return json.dumps(content, default=str)
    return str(content)


def _mem0_config_from_cfg(cfg: LongTermMemoryConfig) -> dict[str, Any]:
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


def _mem0_result_to_item(item: Any) -> dict[str, Any]:
    if not isinstance(item, dict):
        item = getattr(item, "__dict__", {}) or {}
    meta = (item.get("metadata") if isinstance(item, dict) else getattr(item, "metadata", None)) or {}
    if not isinstance(meta, dict):
        meta = {}
    return {
        "id": str(item.get("id", "") if isinstance(item, dict) else getattr(item, "id", "")),
        "memory": str(item.get("memory", "") if isinstance(item, dict) else getattr(item, "memory", "")),
        "metadata": meta,
        "intent_history": meta.get("intent_history", []) if isinstance(meta, dict) else [],
        "messages": meta.get("messages", []) if isinstance(meta, dict) else [],
        "created_at": item.get("created_at") if isinstance(item, dict) else getattr(item, "created_at", None),
        "updated_at": item.get("updated_at") if isinstance(item, dict) else getattr(item, "updated_at", None),
    }


class LongTermMemory:
    """
    Reusable long-term memory for any agent.
    Persists conversations to MongoDB and mem0; use get_relevant() or get_all() to retrieve.
    """

    def __init__(self, config: Optional[LongTermMemoryConfig] = None) -> None:
        self._config = config or LongTermMemoryConfig.from_env()
        self._mem0: Optional[AsyncMemory] = None
        self._mem0_config = _mem0_config_from_cfg(self._config)
        self._mongo_client: Optional[AsyncIOMotorClient] = None

    async def connect(self) -> None:
        try:
            await self._ensure_mongo()
            log.info("long_term_connect_ok")
        except Exception as e:
            log.exception("long_term_connect_failed", error=str(e), error_type=type(e).__name__)
            raise LongTermMemoryError(f"Long-term memory connect failed: {e}", operation="connect", cause=e) from e

    async def close(self) -> None:
        try:
            if self._mongo_client:
                self._mongo_client.close()
                self._mongo_client = None
            self._mem0 = None
        except Exception as e:
            log.exception("long_term_close_failed", error=str(e), error_type=type(e).__name__)
            self._mongo_client = None
            self._mem0 = None

    async def _ensure_mongo(self) -> None:
        if self._mongo_client is not None:
            return
        try:
            client = AsyncIOMotorClient(
                self._config.mongodb_url,
                tlsCAFile=certifi.where(),
            )
            await client.admin.command("ping")
            self._mongo_client = client
        except Exception as e:
            log.exception("long_term_mongo_connect_failed", error=str(e), db=self._config.mongodb_db)
            self._mongo_client = None
            raise

    async def _ensure_mem0(self) -> None:
        if self._mem0 is not None:
            return
        try:
            self._mem0 = await AsyncMemory.from_config(self._mem0_config)
        except Exception as e:
            log.exception("long_term_mem0_connect_failed", error=str(e), error_type=type(e).__name__)
            raise LongTermMemoryError(f"mem0 init failed: {e}", operation="ensure_mem0", cause=e) from e

    async def save(
        self,
        user_id: str,
        session_id: str,
        messages: List[dict],
        *,
        metadata: Optional[dict] = None,
        extracted_entities: Optional[dict] = None,
        user_preferences: Optional[dict] = None,
        intent_history: Optional[list] = None,
    ) -> None:
        if not messages:
            return
        meta = metadata or {}
        extra = {
            "extracted_entities": extracted_entities or meta.get("extracted_entities", {}),
            "user_preferences": user_preferences or meta.get("user_preferences", {}),
            "intent_history": intent_history if intent_history is not None else meta.get("intent_history", []),
        }
        try:
            await self._ensure_mongo()
        except Exception as e:
            raise LongTermMemoryError(
                f"MongoDB not available: {e}",
                operation="save",
                user_id=user_id,
                session_id=session_id,
                cause=e,
            ) from e

        if self._mongo_client is not None:
            try:
                coll = self._mongo_client[self._config.mongodb_db][self._config.mongodb_collection]
                doc = {
                    "_id": str(uuid.uuid4()),
                    "user_id": user_id,
                    "session_id": session_id,
                    "messages": messages,
                    "extracted_entities": extra["extracted_entities"],
                    "user_preferences": extra["user_preferences"],
                    "intent_history": extra["intent_history"],
                    "created_at": _now_iso(),
                }
                await coll.insert_one(doc)
            except Exception as e:
                raise LongTermMemoryError(
                    "Long-term memory: MongoDB write failed.",
                    operation="save",
                    user_id=user_id,
                    session_id=session_id,
                    cause=e,
                ) from e
        else:
            raise LongTermMemoryError("MongoDB not connected.", operation="save", user_id=user_id, session_id=session_id)

        messages_for_mem0 = []
        for m in messages:
            if not isinstance(m, dict) or m.get("role") is None:
                continue
            messages_for_mem0.append({"role": m["role"], "content": _content_to_string(m.get("content"))})
        if messages_for_mem0:
            try:
                await self._ensure_mem0()
                mem0_meta = {
                    "session_id": session_id,
                    "intent_history": extra["intent_history"],
                    "extracted_entities": extra["extracted_entities"],
                    "user_preferences": extra["user_preferences"],
                }
                await self._mem0.add(
                    messages=messages_for_mem0,
                    user_id=user_id,
                    metadata=mem0_meta,
                    infer=False,
                )
            except Exception as e:
                tb = traceback.format_exc()
                log.warning("long_term_mem0_save_failed", error=str(e), traceback=tb)

    async def get_relevant(self, user_id: str, query: str, limit: int = 10) -> List[dict]:
        if not (user_id or "").strip():
            return []
        try:
            await self._ensure_mem0()
            if (query or "").strip():
                out = await self._mem0.search(query=(query or "").strip(), user_id=user_id.strip(), limit=limit)
            else:
                out = await self._mem0.get_all(user_id=user_id.strip(), limit=limit)
            raw = (out or {}).get("results") if isinstance(out, dict) else []
            if not isinstance(raw, list):
                raw = []
            results = []
            for r in raw[:limit]:
                try:
                    results.append(_mem0_result_to_item(r))
                except Exception as e:
                    log.warning("long_term_item_skip", user_id=user_id, error=str(e))
            return results
        except LongTermMemoryError:
            raise
        except Exception as e:
            log.exception("long_term_get_relevant_failed", user_id=user_id, error=str(e))
            return []

    async def get_all(self, user_id: str, limit: int = 50) -> List[dict]:
        return await self.get_relevant(user_id=user_id, query="", limit=limit)

    async def diagnose_mem0(self) -> dict[str, Any]:
        try:
            await self._ensure_mem0()
            await self._mem0.add(
                messages=[{"role": "user", "content": "mem0 diagnostic"}, {"role": "assistant", "content": "ok"}],
                user_id="__mem0_diagnostic__",
                metadata={"source": "diagnostic"},
                infer=False,
            )
            return {"ok": True, "message": "mem0 init and add succeeded", "db": self._config.mongodb_db, "collection": self._config.mem0_collection}
        except Exception as e:
            return {
                "ok": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "traceback": traceback.format_exc(),
                "db": self._config.mongodb_db,
                "collection": self._config.mem0_collection,
            }

