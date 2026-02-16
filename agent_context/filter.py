"""Context filtering: limit and score-threshold long-term, procedures, short-term."""

from __future__ import annotations

from typing import Any


def apply_context_filter(
    long_term: list[dict[str, Any]],
    procedures: list[dict[str, Any]],
    short_term_messages: list[dict[str, Any]],
    *,
    long_term_max: int,
    long_term_min_score: float | None,
    procedure_max: int,
    short_term_recent_n: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Apply limits and optional score threshold. Returns (lt, proc, st)."""
    lt = long_term[:long_term_max]
    if long_term_min_score is not None:
        lt = [h for h in lt if h.get("score") is not None and float(h["score"]) >= long_term_min_score]
    proc = procedures[:procedure_max]
    st = (short_term_messages or [])[-short_term_recent_n:]
    return lt, proc, st
