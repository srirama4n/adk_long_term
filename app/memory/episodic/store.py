"""
Episodic memory store: event-based experiences with session and timestamp.

Stores and retrieves episodes (user_id, session_id, event_type, content, metadata, created_at).
Backed by MongoDB.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, List, Optional

import certifi
from motor.motor_asyncio import AsyncIOMotorClient

from app.memory.episodic.config import EpisodicMemoryConfig

try:
    import structlog
    log = structlog.get_logger(__name__)
except Exception:
    import logging
    log = logging.getLogger(__name__)


class EpisodicMemoryError(Exception):
    """Raised when episodic memory operations fail."""

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


class EpisodicMemory:
    """
    Episodic memory: store and retrieve events (episodes) by user and session.

    - add_episode(): record an event (e.g. "user_asked_weather", "assistant_responded").
    - get_episodes(): list episodes for a user, optionally filtered by session or time.

    Example (standalone):
        config = EpisodicMemoryConfig.from_env()
        memory = EpisodicMemory(config=config)
        await memory.connect()
        await memory.add_episode(user_id="alice", session_id="s1", event_type="turn", content="...")
        episodes = await memory.get_episodes(user_id="alice", limit=10)
        await memory.close()
    """

    def __init__(self, config: Optional[EpisodicMemoryConfig] = None) -> None:
        self._config = config or EpisodicMemoryConfig.from_env()
        self._mongo_client: Optional[AsyncIOMotorClient] = None

    async def connect(self) -> None:
        """Pre-connect to MongoDB. Otherwise connection is lazy on first use."""
        log.info("episodic_connect_start")
        try:
            await self._ensure_mongo()
            log.info("episodic_connect_ok")
        except Exception as e:
            log.exception("episodic_connect_failed", error=str(e), error_type=type(e).__name__)
            raise EpisodicMemoryError(f"Episodic memory connect failed: {e}", operation="connect", cause=e) from e

    async def close(self) -> None:
        """Release MongoDB connection."""
        log.info("episodic_close_start")
        try:
            if self._mongo_client:
                self._mongo_client.close()
                self._mongo_client = None
            log.info("episodic_close_ok")
        except Exception as e:
            log.exception("episodic_close_failed", error=str(e), error_type=type(e).__name__)
            self._mongo_client = None

    async def _ensure_mongo(self) -> None:
        if self._mongo_client is not None:
            return
        log.info(
            "episodic_mongo_connect_start",
            db=self._config.mongodb_db,
            collection=self._config.episodic_collection,
        )
        try:
            client = AsyncIOMotorClient(
                self._config.mongodb_url,
                tlsCAFile=certifi.where(),
            )
            await client.admin.command("ping")
            self._mongo_client = client
            log.info(
                "episodic_mongo_connected",
                db=self._config.mongodb_db,
                collection=self._config.episodic_collection,
            )
        except Exception as e:
            log.exception(
                "episodic_mongo_connect_failed",
                error=str(e),
                error_type=type(e).__name__,
                db=self._config.mongodb_db,
            )
            self._mongo_client = None
            raise

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
        """
        Store one episode (event) for the user/session.

        Returns the episode id.
        """
        log.info(
            "episodic_add_start",
            operation="add_episode",
            user_id=user_id,
            session_id=session_id,
            event_type=event_type,
        )
        try:
            await self._ensure_mongo()
        except EpisodicMemoryError:
            raise
        except Exception as e:
            log.exception("episodic_add_connect_failed", user_id=user_id, error=str(e), error_type=type(e).__name__)
            raise EpisodicMemoryError(
                f"MongoDB not available: {e}",
                operation="add_episode",
                user_id=user_id,
                session_id=session_id,
                cause=e,
            ) from e

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
        try:
            coll = self._mongo_client[self._config.mongodb_db][self._config.episodic_collection]
            await coll.insert_one(doc)
            log.info(
                "episodic_add_ok",
                operation="add_episode",
                user_id=user_id,
                session_id=session_id,
                episode_id=episode_id,
            )
            return episode_id
        except Exception as e:
            log.exception(
                "episodic_add_failed",
                operation="add_episode",
                user_id=user_id,
                session_id=session_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise EpisodicMemoryError(
                f"Failed to store episode: {e}",
                operation="add_episode",
                user_id=user_id,
                session_id=session_id,
                cause=e,
            ) from e

    async def get_episodes(
        self,
        user_id: str,
        *,
        session_id: Optional[str] = None,
        since_iso: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[dict[str, Any]]:
        """
        Retrieve episodes for a user, optionally filtered by session, time, or event_type.

        Results are ordered by created_at descending (newest first).
        """
        log.info(
            "episodic_get_start",
            operation="get_episodes",
            user_id=user_id,
            session_id=session_id,
            limit=limit,
        )
        if not (user_id or "").strip():
            log.info("episodic_get_skip", operation="get_episodes", reason="empty_user_id")
            return []
        try:
            await self._ensure_mongo()
        except EpisodicMemoryError:
            raise
        except Exception as e:
            log.exception("episodic_get_connect_failed", user_id=user_id, error=str(e), error_type=type(e).__name__)
            return []

        query: dict[str, Any] = {"user_id": user_id.strip()}
        if session_id and (session_id or "").strip():
            query["session_id"] = session_id.strip()
        if since_iso:
            query["created_at"] = {"$gte": since_iso}
        if event_type and (event_type or "").strip():
            query["event_type"] = event_type.strip()

        try:
            coll = self._mongo_client[self._config.mongodb_db][self._config.episodic_collection]
            cursor = coll.find(query).sort("created_at", -1).limit(limit)
            results = []
            async for doc in cursor:
                results.append({
                    "id": doc.get("_id"),
                    "user_id": doc.get("user_id"),
                    "session_id": doc.get("session_id"),
                    "event_type": doc.get("event_type"),
                    "content": doc.get("content"),
                    "summary": doc.get("summary"),
                    "metadata": doc.get("metadata", {}),
                    "created_at": doc.get("created_at"),
                })
            log.info(
                "episodic_get_ok",
                operation="get_episodes",
                user_id=user_id,
                returned_count=len(results),
            )
            return results
        except Exception as e:
            log.exception(
                "episodic_get_failed",
                operation="get_episodes",
                user_id=user_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            return []
