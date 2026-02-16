"""
Offload old session messages to MongoDB so active context stays small.
Used when context_offload_enabled and message count exceeds threshold.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import structlog
from motor.motor_asyncio import AsyncIOMotorClient

log = structlog.get_logger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def offload_messages(
    mongodb_url: str,
    mongodb_db: str,
    collection: str,
    user_id: str,
    session_id: str,
    messages: list[dict[str, Any]],
) -> None:
    """
    Append a chunk of messages to the offloaded-context collection.
    Does not raise; logs on failure.
    """
    if not messages:
        return
    try:
        client = AsyncIOMotorClient(mongodb_url)
        coll = client[mongodb_db][collection]
        doc = {
            "user_id": user_id.strip(),
            "session_id": session_id.strip(),
            "messages": messages,
            "message_count": len(messages),
            "created_at": _now_iso(),
        }
        await coll.insert_one(doc)
        log.info(
            "context_offload_ok",
            user_id=user_id,
            session_id=session_id,
            message_count=len(messages),
        )
    except Exception as e:
        log.warning(
            "context_offload_failed",
            user_id=user_id,
            session_id=session_id,
            error=str(e),
            error_type=type(e).__name__,
        )
