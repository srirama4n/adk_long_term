"""
After-turn persist: offload (if needed), save short-term, long-term, episode, fact, procedures.
Reusable with any memory that implements MemoryForPersistProtocol. No app dependency.
"""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable, Union

from agent_context.config import ContextConfig
from agent_context.protocols import MemoryForPersistProtocol


async def after_turn(
    memory: MemoryForPersistProtocol,
    config: ContextConfig,
    *,
    user_id: str,
    session_id: str,
    message: str,
    short_term_before: dict[str, Any] | None,
    response_payload: dict[str, Any],
    intent: str,
    pending_procedures: list[dict[str, Any]],
    on_procedure_saved: Callable[[str], Union[None, Awaitable[None]]] | None = None,
) -> None:
    """
    Persist state after one turn: offload old messages if over threshold, save short-term
    and long-term, add episode and fact, and persist each pending procedure.
    on_procedure_saved(user_id) is called after each procedure is saved (e.g. to invalidate cache).
    """
    new_messages = (short_term_before or {}).get("messages", []) + [
        {"role": "user", "content": message},
        {"role": "assistant", "content": response_payload, "intent": intent},
    ]

    messages_to_save = new_messages[-20:]
    if config.offload_enabled and len(new_messages) > config.offload_message_threshold:
        to_offload = new_messages[: -config.offload_keep_recent]
        if to_offload:
            await memory.offload_context(user_id, session_id, to_offload)
        messages_to_save = new_messages[-config.offload_keep_recent :]

    await memory.save_short_term(
        session_id,
        {
            "session_context": (short_term_before or {}).get("session_context", {}),
            "messages": messages_to_save,
            "current_conversation_state": {"last_intent": intent},
        },
    )
    await memory.save_long_term(
        user_id,
        session_id,
        {
            "messages": [
                {"role": "user", "content": message},
                {"role": "assistant", "content": response_payload},
            ],
            "extracted_entities": {},
            "user_preferences": {},
            "intent_history": [(message, intent)],
        },
    )

    try:
        await memory.add_episode(
            user_id,
            session_id,
            "turn",
            {"user_message": (message or "")[:300], "intent": intent, "response_preview": str(response_payload)[:200]},
        )
    except Exception:
        pass

    try:
        fact = f"User asked: {(message or '')[:100]}; intent was {intent}."
        await memory.add_fact(user_id, fact)
    except Exception:
        pass

    for p in pending_procedures:
        try:
            await memory.add_procedure(
                user_id,
                p.get("name", "unnamed"),
                p.get("steps", []),
                description=p.get("description"),
            )
            if on_procedure_saved:
                r = on_procedure_saved(user_id)
                if asyncio.iscoroutine(r):
                    await r
        except Exception:
            pass
