"""Episodic memory store: event-based experiences with session and timestamp. Backed by MongoDB."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, List, Optional

import certifi
from motor.motor_asyncio import AsyncIOMotorClient

from agent_memory.episodic.config import EpisodicMemoryConfig

try:
    import structlog
    log = structlog.get_logger(__name__)
except Exception:
    import logging
    log = logging.getLogger(__name__)


class EpisodicMemoryError(Exception):
    def __init__(self, message: str, *, operation: str = "", user_id: str = "", session_id: str = "", cause: Optional[Exception] = None) -> None:
        super().__init__(message)
        self.operation = operation
        self.user_id = user_id
        self.session_id = session_id
        self.cause = cause


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class EpisodicMemory:
    """Episodic memory: add_episode(), get_episodes() by user/session. Backed by MongoDB."""

    def __init__(self, config: Optional[EpisodicMemoryConfig] = None) -> None:
        self._config = config or EpisodicMemoryConfig.from_env()
        self._mongo_client: Optional[AsyncIOMotorClient] = None

    async def connect(self) -> None:
        try:
            await self._ensure_mongo()
        except Exception as e:
            raise EpisodicMemoryError(f"Episodic memory connect failed: {e}", operation="connect", cause=e) from e

    async def close(self) -> None:
        if self._mongo_client:
            self._mongo_client.close()
            self._mongo_client = None

    async def _ensure_mongo(self) -> None:
        if self._mongo_client is not None:
            return
        client = AsyncIOMotorClient(self._config.mongodb_url, tlsCAFile=certifi.where())
        await client.admin.command("ping")
        self._mongo_client = client

    async def add_episode(
        self,
        user_id: str,
        session_id: str,
        event_type: str,
        content: str | dict[str, Any],
        *,
        summary: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> str:
        episode_id = str(uuid.uuid4())
        doc = {
            "_id": episode_id,
            "user_id": user_id,
            "session_id": session_id,
            "event_type": event_type,
            "content": content,
            "summary": summary,
            "metadata": metadata or {},
            "created_at": _now_iso(),
        }
        await self._ensure_mongo()
        coll = self._mongo_client[self._config.mongodb_db][self._config.episodic_collection]
        await coll.insert_one(doc)
        return episode_id

    async def get_episodes(
        self,
        user_id: str,
        *,
        session_id: Optional[str] = None,
        since_iso: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[dict[str, Any]]:
        if not (user_id or "").strip():
            return []
        await self._ensure_mongo()
        query: dict[str, Any] = {"user_id": user_id.strip()}
        if session_id and (session_id or "").strip():
            query["session_id"] = session_id.strip()
        if since_iso:
            query["created_at"] = {"$gte": since_iso}
        if event_type and (event_type or "").strip():
            query["event_type"] = event_type.strip()
        coll = self._mongo_client[self._config.mongodb_db][self._config.episodic_collection]
        cursor = coll.find(query).sort("created_at", -1).limit(limit)
        return [
            {
                "id": doc.get("_id"),
                "user_id": doc.get("user_id"),
                "session_id": doc.get("session_id"),
                "event_type": doc.get("event_type"),
                "content": doc.get("content"),
                "summary": doc.get("summary"),
                "metadata": doc.get("metadata", {}),
                "created_at": doc.get("created_at"),
            }
            async for doc in cursor
        ]

