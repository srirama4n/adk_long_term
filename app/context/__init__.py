"""
Re-export from agent_context for app use. The app uses ContextConfig.from_settings(get_settings()).
See agent_context README for use in other projects.
"""

from agent_context import (
    BuildResult,
    ContextCache,
    ContextConfig,
    ContextPipeline,
    after_turn,
    apply_context_compaction,
    apply_context_filter,
    format_procedures_for_context,
)
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
