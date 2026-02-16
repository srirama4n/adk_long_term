"""
Procedural memory store: how-to and skills (name, steps, conditions).

Stored in MongoDB; keyed by user_id and procedure name.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, List, Optional

import certifi
from motor.motor_asyncio import AsyncIOMotorClient

from app.memory.procedural.config import ProceduralMemoryConfig

try:
    import structlog
    log = structlog.get_logger(__name__)
except Exception:
    import logging
    log = logging.getLogger(__name__)


class ProceduralMemoryError(Exception):
    """Raised when procedural memory operations fail."""

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


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ProceduralMemory:
    """
    Procedural memory: store and retrieve procedures (how-to, skills) by user.

    - add_procedure(): create or replace a procedure (name, steps, optional description/conditions).
    - get_procedure(): fetch one procedure by user_id and name.
    - list_procedures(): list procedure names (and optionally full docs) for a user.

    Example (standalone):
        config = ProceduralMemoryConfig.from_env()
        memory = ProceduralMemory(config=config)
        await memory.connect()
        await memory.add_procedure(user_id="alice", name="check_weather", steps=["Get location", "Call API", "Format"])
        proc = await memory.get_procedure(user_id="alice", name="check_weather")
        await memory.close()
    """

    def __init__(self, config: Optional[ProceduralMemoryConfig] = None) -> None:
        self._config = config or ProceduralMemoryConfig.from_env()
        self._mongo_client: Optional[AsyncIOMotorClient] = None

    async def connect(self) -> None:
        """Pre-connect to MongoDB. Otherwise connection is lazy on first use."""
        log.info("procedural_connect_start")
        try:
            await self._ensure_mongo()
            log.info("procedural_connect_ok")
        except Exception as e:
            log.exception("procedural_connect_failed", error=str(e), error_type=type(e).__name__)
            raise ProceduralMemoryError(f"Procedural memory connect failed: {e}", operation="connect", cause=e) from e

    async def close(self) -> None:
        """Release MongoDB connection."""
        log.info("procedural_close_start")
        try:
            if self._mongo_client:
                self._mongo_client.close()
                self._mongo_client = None
            log.info("procedural_close_ok")
        except Exception as e:
            log.exception("procedural_close_failed", error=str(e), error_type=type(e).__name__)
            self._mongo_client = None

    async def _ensure_mongo(self) -> None:
        if self._mongo_client is not None:
            return
        log.info(
            "procedural_mongo_connect_start",
            db=self._config.mongodb_db,
            collection=self._config.procedural_collection,
        )
        try:
            client = AsyncIOMotorClient(
                self._config.mongodb_url,
                tlsCAFile=certifi.where(),
            )
            await client.admin.command("ping")
            self._mongo_client = client
            log.info(
                "procedural_mongo_connected",
                db=self._config.mongodb_db,
                collection=self._config.procedural_collection,
            )
        except Exception as e:
            log.exception(
                "procedural_mongo_connect_failed",
                error=str(e),
                error_type=type(e).__name__,
                db=self._config.mongodb_db,
            )
            self._mongo_client = None
            raise

    async def add_procedure(
        self,
        user_id: str,
        name: str,
        steps: List[str],
        *,
        description: Optional[str] = None,
        conditions: Optional[List[str]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> str:
        """
        Create or replace a procedure for the user. Steps are ordered. Returns procedure id.
        """
        log.info(
            "procedural_add_start",
            operation="add_procedure",
            user_id=user_id,
            name=name,
        )
        if not (user_id or "").strip() or not (name or "").strip():
            log.warning("procedural_add_skip", reason="empty_user_or_name")
            raise ProceduralMemoryError(
                "user_id and name are required",
                operation="add_procedure",
                user_id=user_id or "",
            )
        try:
            await self._ensure_mongo()
        except ProceduralMemoryError:
            raise
        except Exception as e:
            log.exception("procedural_add_connect_failed", user_id=user_id, error=str(e), error_type=type(e).__name__)
            raise ProceduralMemoryError(
                f"MongoDB not available: {e}",
                operation="add_procedure",
                user_id=user_id,
                cause=e,
            ) from e

        procedure_id = str(uuid.uuid4())
        doc = {
            "_id": procedure_id,
            "user_id": user_id.strip(),
            "name": name.strip(),
            "steps": list(steps) if steps else [],
            "description": description,
            "conditions": conditions or [],
            "metadata": metadata or {},
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
        }
        try:
            coll = self._mongo_client[self._config.mongodb_db][self._config.procedural_collection]
            # Upsert by user_id + name
            await coll.update_one(
                {"user_id": user_id.strip(), "name": name.strip()},
                {
                    "$set": {
                        "steps": doc["steps"],
                        "description": doc["description"],
                        "conditions": doc["conditions"],
                        "metadata": doc["metadata"],
                        "updated_at": doc["updated_at"],
                    },
                    "$setOnInsert": {
                        "_id": procedure_id,
                        "user_id": doc["user_id"],
                        "name": doc["name"],
                        "created_at": doc["created_at"],
                    },
                },
                upsert=True,
            )
            existing = await coll.find_one({"user_id": user_id.strip(), "name": name.strip()})
            out_id = (existing or {}).get("_id", procedure_id)
            log.info(
                "procedural_add_ok",
                operation="add_procedure",
                user_id=user_id,
                name=name,
                procedure_id=out_id,
            )
            return str(out_id)
        except ProceduralMemoryError:
            raise
        except Exception as e:
            log.exception(
                "procedural_add_failed",
                operation="add_procedure",
                user_id=user_id,
                name=name,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise ProceduralMemoryError(
                f"Failed to store procedure: {e}",
                operation="add_procedure",
                user_id=user_id,
                cause=e,
            ) from e

    async def get_procedure(self, user_id: str, name: str) -> Optional[dict[str, Any]]:
        """Retrieve one procedure by user_id and name. Returns None if not found."""
        log.info("procedural_get_start", operation="get_procedure", user_id=user_id, name=name)
        if not (user_id or "").strip() or not (name or "").strip():
            return None
        try:
            await self._ensure_mongo()
        except ProceduralMemoryError:
            raise
        except Exception as e:
            log.exception("procedural_get_connect_failed", user_id=user_id, error=str(e), error_type=type(e).__name__)
            return None

        try:
            coll = self._mongo_client[self._config.mongodb_db][self._config.procedural_collection]
            doc = await coll.find_one({"user_id": user_id.strip(), "name": name.strip()})
            if not doc:
                log.info("procedural_get_miss", operation="get_procedure", user_id=user_id, name=name)
                return None
            log.info("procedural_get_ok", operation="get_procedure", user_id=user_id, name=name)
            return {
                "id": doc.get("_id"),
                "user_id": doc.get("user_id"),
                "name": doc.get("name"),
                "steps": doc.get("steps", []),
                "description": doc.get("description"),
                "conditions": doc.get("conditions", []),
                "metadata": doc.get("metadata", {}),
                "created_at": doc.get("created_at"),
                "updated_at": doc.get("updated_at"),
            }
        except Exception as e:
            log.exception(
                "procedural_get_failed",
                operation="get_procedure",
                user_id=user_id,
                name=name,
                error=str(e),
                error_type=type(e).__name__,
            )
            return None

    async def list_procedures(
        self,
        user_id: str,
        limit: int = 50,
        *,
        include_docs: bool = False,
    ) -> List[dict[str, Any]]:
        """
        List procedures for a user. Each item has at least name (and id if include_docs);
        if include_docs is True, full procedure docs are returned.
        """
        log.info("procedural_list_start", operation="list_procedures", user_id=user_id, limit=limit)
        if not (user_id or "").strip():
            log.info("procedural_list_skip", reason="empty_user_id")
            return []
        try:
            await self._ensure_mongo()
        except ProceduralMemoryError:
            raise
        except Exception as e:
            log.exception("procedural_list_connect_failed", user_id=user_id, error=str(e), error_type=type(e).__name__)
            return []

        try:
            coll = self._mongo_client[self._config.mongodb_db][self._config.procedural_collection]
            cursor = coll.find({"user_id": user_id.strip()}).sort("updated_at", -1).limit(limit)
            results = []
            async for doc in cursor:
                if include_docs:
                    results.append({
                        "id": doc.get("_id"),
                        "user_id": doc.get("user_id"),
                        "name": doc.get("name"),
                        "steps": doc.get("steps", []),
                        "description": doc.get("description"),
                        "conditions": doc.get("conditions", []),
                        "metadata": doc.get("metadata", {}),
                        "created_at": doc.get("created_at"),
                        "updated_at": doc.get("updated_at"),
                    })
                else:
                    results.append({"id": doc.get("_id"), "name": doc.get("name")})
            log.info("procedural_list_ok", operation="list_procedures", user_id=user_id, returned_count=len(results))
            return results
        except Exception as e:
            log.exception(
                "procedural_list_failed",
                operation="list_procedures",
                user_id=user_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            return []
