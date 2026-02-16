"""
agent_memory: reusable memory layer for agents.

Use in any app; config via env or constructor. No dependency on a host app.

Example (standalone, from env):
    from agent_memory import MemoryManager

    memory = MemoryManager()
    await memory.connect()
    await memory.save_short_term("s1", {"messages": [...]})
    await memory.close()

Example (with your app's settings):
    from agent_memory import MemoryManager, ShortTermMemoryConfig, LongTermMemoryConfig, ...

    settings = your_app.get_settings()
    memory = MemoryManager(
        short_term_config=ShortTermMemoryConfig.from_settings(settings),
        long_term_config=LongTermMemoryConfig.from_settings(settings),
        episodic_config=EpisodicMemoryConfig.from_settings(settings),
        semantic_config=SemanticMemoryConfig.from_settings(settings),
        procedural_config=ProceduralMemoryConfig.from_settings(settings),
    )
"""

from agent_memory.episodic import EpisodicMemory, EpisodicMemoryConfig, EpisodicMemoryError
from agent_memory.exceptions import MemoryConnectionError, MemoryError, MemoryReadError, MemoryWriteError
from agent_memory.long_term import LongTermMemory, LongTermMemoryConfig, LongTermMemoryError
from agent_memory.memory_manager import MemoryManager
from agent_memory.procedural import ProceduralMemory, ProceduralMemoryConfig, ProceduralMemoryError
from agent_memory.semantic import SemanticMemory, SemanticMemoryConfig, SemanticMemoryError
from agent_memory.short_term import ShortTermMemory, ShortTermMemoryConfig, ShortTermMemoryError

__all__ = [
    "MemoryManager",
    "MemoryError",
    "MemoryConnectionError",
    "MemoryReadError",
    "MemoryWriteError",
    "ShortTermMemory",
    "ShortTermMemoryConfig",
    "ShortTermMemoryError",
    "LongTermMemory",
    "LongTermMemoryConfig",
    "LongTermMemoryError",
    "EpisodicMemory",
    "EpisodicMemoryConfig",
    "EpisodicMemoryError",
    "SemanticMemory",
    "SemanticMemoryConfig",
    "SemanticMemoryError",
    "ProceduralMemory",
    "ProceduralMemoryConfig",
    "ProceduralMemoryError",
]
