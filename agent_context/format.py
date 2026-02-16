"""Format context components (e.g. procedures) for injection into the prompt."""

from __future__ import annotations

from typing import Any


def format_procedures_for_context(procedures: list[dict[str, Any]]) -> str:
    """Format saved procedures for supervisor context (name, description, steps)."""
    lines = []
    for p in procedures:
        name = p.get("name") or "unnamed"
        desc = p.get("description") or ""
        steps = p.get("steps") or []
        block = f"- Procedure: {name}"
        if desc:
            block += f"\n  Description: {desc}"
        if steps:
            block += "\n  Steps:\n" + "\n".join(f"    {i + 1}. {s}" for i, s in enumerate(steps))
        lines.append(block)
    return "\n\n".join(lines) if lines else ""
