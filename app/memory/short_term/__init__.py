"""
Reusable short-term (session) memory for any agent.

Usage:
    from app.memory.short_term import ShortTermMemory, ShortTermMemoryConfig

    # From env (REDIS_URL, SHORT_TERM_TTL_SECONDS, SHORT_TERM_MAX_MESSAGES)
    config = ShortTermMemoryConfig.from_env()
    memory = ShortTermMemory(config=config)

    # Or from your app's settings
    config = ShortTermMemoryConfig.from_settings(my_app_settings)
    memory = ShortTermMemory(config=config)

    await memory.connect()
    await memory.save(session_id="s1", data={"messages": [...], "session_context": {}})
    ctx = await memory.get(session_id="s1")
    await memory.clear(session_id="s1")
    await memory.close()
"""

from app.memory.short_term.store import ShortTermMemory, ShortTermMemoryError
from app.memory.short_term.config import ShortTermMemoryConfig

__all__ = ["ShortTermMemory", "ShortTermMemoryConfig", "ShortTermMemoryError"]
