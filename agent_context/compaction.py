"""Context compaction: truncate context parts and total size."""

from __future__ import annotations


def apply_context_compaction(
    context_parts: list[str],
    max_chars_per_part: int,
    max_total_chars: int,
) -> str:
    """Truncate each part and total; keeps the end so current user message can be appended."""
    truncated = [s[:max_chars_per_part] for s in context_parts]
    joined = "\n\n".join(truncated)
    if len(joined) <= max_total_chars:
        return joined
    target = max_total_chars - 100
    if target <= 0:
        return joined[:max_total_chars]
    return joined[-target:] if len(joined) > target else joined
