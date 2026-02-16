"""Procedural memory store: how-to and skills. Stored in MongoDB; keyed by user_id and procedure name."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, List, Optional

import certifi
from motor.motor_asyncio import AsyncIOMotorClient

from agent_memory.procedural.config import ProceduralMemoryConfig

try:
    import structlog
    log = structlog.get_logger(__name__)
except Exception:
    import logging
    log = logging.getLogger(__name__)


class ProceduralMemoryError(Exception):
    def __init__(self, message: str, *, operation: str = "", user_id: str = "", cause: Optional[Exception] = None) -> None:
        super().__init__(message)
        self.operation = operation
        self.user_id = user_id
        self.cause = cause


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ProceduralMemory:
    """Procedural memory: add_procedure(), get_procedure(), list_procedures()."""

    def __init__(self, config: Optional[ProceduralMemoryConfig] = None) -> None:
        self._config = config or ProceduralMemoryConfig.from_env()
        self._mongo_client: Optional[AsyncIOMotorClient] = None

    async def connect(self) -> None:
        await self._ensure_mongo()

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
        if not (user_id or "").strip() or not (name or "").strip():
            raise ProceduralMemoryError("user_id and name are required", operation="add_procedure", user_id=user_id or "")
        await self._ensure_mongo()
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
        coll = self._mongo_client[self._config.mongodb_db][self._config.procedural_collection]
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
        return str((existing or {}).get("_id", procedure_id))

    async def get_procedure(self, user_id: str, name: str) -> Optional[dict[str, Any]]:
        if not (user_id or "").strip() or not (name or "").strip():
            return None
        await self._ensure_mongo()
        coll = self._mongo_client[self._config.mongodb_db][self._config.procedural_collection]
        doc = await coll.find_one({"user_id": user_id.strip(), "name": name.strip()})
        if not doc:
            return None
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

    async def list_procedures(
        self,
        user_id: str,
        limit: int = 50,
        *,
        include_docs: bool = False,
    ) -> List[dict[str, Any]]:
        if not (user_id or "").strip():
            return []
        await self._ensure_mongo()
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
        return results

