"""
Reusable short-term (session) memory for any agent.

Usage:
    from agent_memory import ShortTermMemory, ShortTermMemoryConfig

    config = ShortTermMemoryConfig.from_env()
    memory = ShortTermMemory(config=config)
    await memory.connect()
    await memory.save(session_id="s1", data={"messages": [...], "session_context": {}})
    ctx = await memory.get(session_id="s1")
    await memory.close()
"""

from agent_memory.short_term.config import ShortTermMemoryConfig
from agent_memory.short_term.store import ShortTermMemory, ShortTermMemoryError

__all__ = ["ShortTermMemory", "ShortTermMemoryConfig", "ShortTermMemoryError"]
