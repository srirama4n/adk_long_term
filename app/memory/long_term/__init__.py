"""
Reusable long-term memory for any agent.

Usage:
    from app.memory.long_term import LongTermMemory, LongTermMemoryConfig

    # From env (MONGODB_URL, GOOGLE_API_KEY, etc.)
    config = LongTermMemoryConfig.from_env()
    memory = LongTermMemory(config=config)

    # Or from your app's settings
    config = LongTermMemoryConfig.from_settings(my_app_settings)
    memory = LongTermMemory(config=config)

    await memory.connect()
    await memory.save(user_id="u1", session_id="s1", messages=[...], metadata={...})
    history = await memory.get_relevant(user_id="u1", query="...", limit=10)
    await memory.close()
"""

from app.memory.long_term.store import LongTermMemory, LongTermMemoryError
from app.memory.long_term.config import LongTermMemoryConfig

__all__ = ["LongTermMemory", "LongTermMemoryConfig", "LongTermMemoryError"]
