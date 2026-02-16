"""
agent_context: reusable context pipeline and persist for supervisor-style agents.

Use in any app; config via env, from_dict(), or from_settings(any_object). No dependency on a host app.

Example (standalone, from env):
    from agent_context import ContextConfig, ContextPipeline, after_turn

    config = ContextConfig.from_env()
    pipeline = ContextPipeline(memory, config, cache=optional_cache)
    result = await pipeline.build(user_id, session_id, message)
    # ... run your agent with result.user_message ...
    await after_turn(memory, config, user_id=..., short_term_before=result.short_term, ...)

Example (with your app's settings):
    from agent_context import ContextConfig, ContextPipeline

    config = ContextConfig.from_settings(your_app.get_settings())
    pipeline = ContextPipeline(memory, config, cache=cache)
"""

from agent_context.cache import ContextCache
from agent_context.compaction import apply_context_compaction
from agent_context.config import ContextConfig
from agent_context.filter import apply_context_filter
from agent_context.format import format_procedures_for_context
from agent_context.persist import after_turn
from agent_context.pipeline import BuildResult, ContextPipeline
from agent_context.protocols import (
    ContextCacheProtocol,
    MemoryForContextProtocol,
    MemoryForPersistProtocol,
)

__all__ = [
    "ContextConfig",
    "ContextPipeline",
    "BuildResult",
    "after_turn",
    "apply_context_filter",
    "apply_context_compaction",
    "format_procedures_for_context",
    "ContextCache",
    "MemoryForContextProtocol",
    "MemoryForPersistProtocol",
    "ContextCacheProtocol",
]
