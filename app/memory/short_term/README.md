# Short-term memory (reusable)

This package provides **short-term (session) memory** for any agent using Redis with TTL. Use it in this app or in another agent by importing and configuring it.

## Quick start

```python
from app.memory.short_term import ShortTermMemory, ShortTermMemoryConfig

# Config from environment (REDIS_URL, SHORT_TERM_TTL_SECONDS, SHORT_TERM_MAX_MESSAGES)
config = ShortTermMemoryConfig.from_env()
memory = ShortTermMemory(config=config)

await memory.connect()
await memory.save(
    session_id="s1",
    data={
        "messages": [{"role": "user", "content": "Hi"}, {"role": "assistant", "content": "Hello!"}],
        "session_context": {},
        "current_conversation_state": {},
    },
)
ctx = await memory.get(session_id="s1")
await memory.clear(session_id="s1")
await memory.close()
```

## Config

- **From env**: `ShortTermMemoryConfig.from_env()` reads `REDIS_URL`, `SHORT_TERM_TTL_SECONDS`, `SHORT_TERM_MAX_MESSAGES`.
- **From your settings**: `ShortTermMemoryConfig.from_settings(your_settings)` uses any object with `redis_url`, `short_term_ttl_seconds`, `short_term_max_messages`, optional `short_term_key_prefix`.
- **Explicit**: `ShortTermMemoryConfig(redis_url="...", ttl_seconds=1800, max_messages=20, key_prefix="agent:short")`.

## API

- `save(session_id, data)`  
  Stores `data` (dict with e.g. `messages`, `session_context`, `current_conversation_state`). Keeps only the last `max_messages` messages. Sets TTL to `ttl_seconds`.
- `get(session_id)`  
  Returns the stored dict or `None` if missing/expired.
- `clear(session_id)`  
  Deletes the session key.
- `connect()` / `close()`  
  Connect and cleanup.

## Dependencies

- `redis` (async: `redis.asyncio`). No other app-specific deps.
