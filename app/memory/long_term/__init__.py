"""Re-export from agent_memory for backward compatibility."""

from agent_memory.long_term import LongTermMemory, LongTermMemoryConfig, LongTermMemoryError

__all__ = ["LongTermMemory", "LongTermMemoryConfig", "LongTermMemoryError"]
