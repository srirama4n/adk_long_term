# agent_memory

Reusable memory layer for agents: short-term (Redis), long-term (MongoDB + mem0), episodic, semantic, and procedural. No dependency on a host app; configure via environment variables or by passing config objects.

## Use in this repo

The app in `app/` uses this package via `app.memory.memory_manager`, which builds config from `app.config.get_settings()` and maps exceptions to `app.exceptions`.

## Use in another app

1. **Copy** the `agent_memory` package into your project, or add this repo as a path dependency in your `pyproject.toml`:
   ```toml
   [tool.setup]
   dependencies = []
   # In your app: pip install -e /path/to/adk_long_term  # so agent_memory is on path
   ```

2. **Configure** via env (same names as in `.env.example`: `REDIS_URL`, `MONGODB_URL`, `MONGODB_DB`, `GOOGLE_API_KEY`, `MEM0_COLLECTION`, `EPISODIC_COLLECTION`, `MEM0_SEMANTIC_COLLECTION`, `PROCEDURAL_COLLECTION`, etc.) or pass configs:

   ```python
   from agent_memory import MemoryManager, ShortTermMemoryConfig, LongTermMemoryConfig

   # From env only
   memory = MemoryManager()
   await memory.connect()
   # ...

   # Or from your app's settings object
   memory = MemoryManager(
       short_term_config=ShortTermMemoryConfig.from_settings(your_settings),
       long_term_config=LongTermMemoryConfig.from_settings(your_settings),
       episodic_config=EpisodicMemoryConfig.from_settings(your_settings),
       semantic_config=SemanticMemoryConfig.from_settings(your_settings),
       procedural_config=ProceduralMemoryConfig.from_settings(your_settings),
   )
   ```

3. **Exceptions**: `agent_memory` raises `MemoryConnectionError`, `MemoryReadError`, `MemoryWriteError` from `agent_memory.exceptions`. Catch these or map them to your app’s exceptions.

## Subpackages

- **short_term** — Redis, session-scoped, TTL
- **long_term** — MongoDB (raw docs) + mem0 (vectors)
- **episodic** — MongoDB, event-style episodes
- **semantic** — mem0, fact/concept store
- **procedural** — MongoDB, how-to / procedures

Each has a `*Config` with `from_env()` and `from_settings(any)` and a store class with `connect()` / `close()` and the relevant API.
