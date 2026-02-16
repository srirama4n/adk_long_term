"""Procedure tool for the Procedure Agent: records procedures to be persisted by the supervisor."""

from __future__ import annotations

import contextvars
from typing import Any

# Request-scoped list of procedures to save. Supervisor sets this at start of chat and processes after run.
PENDING_PROCEDURES: contextvars.ContextVar[list[dict[str, Any]]] = contextvars.ContextVar(
    "pending_procedures",
    default=None,
)


def save_procedure(
    name: str,
    steps: list[str],
    description: str | None = None,
) -> dict[str, Any]:
    """
    Record a procedure to be saved for the current user. The supervisor persists it after the turn.

    Call this when the user asks to remember a how-to or procedure. The procedure will be stored
    in procedural memory (MongoDB) and associated with the current user.

    Args:
        name: Short name for the procedure (e.g. "check_weather", "order_coffee").
        steps: Ordered list of steps. Each step is a string.
        description: Optional longer description of what the procedure does.

    Returns:
        dict with status and message for the agent to show the user.
    """
    try:
        pending = PENDING_PROCEDURES.get()
    except LookupError:
        return {
            "status": "error",
            "message": "Could not save procedure (no request context).",
        }
    if pending is None:
        return {
            "status": "error",
            "message": "Could not save procedure (no request context).",
        }
    steps_list = list(steps) if steps else []
    pending.append({
        "name": (name or "").strip() or "unnamed",
        "steps": steps_list,
        "description": (description or "").strip() or None,
    })
    return {
        "status": "saved",
        "message": f"Procedure '{name or 'unnamed'}' recorded with {len(steps_list)} steps. The user can ask to recall it later.",
    }
