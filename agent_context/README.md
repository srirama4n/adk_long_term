# agent_context

Reusable context pipeline and after-turn persist for supervisor-style agents. No dependency on a host app; configure via environment variables, a dict, or any settings object.

## Contents

- **ContextConfig** — Offload, filter, cache, compaction settings. `from_env()`, `from_dict()`, `from_settings(any_object)`.
- **ContextPipeline** — Retrieve (with optional cache) → filter → build → compact. `build(user_id, session_id, message)` → `BuildResult(user_message, short_term, long_term, procedures)`.
- **after_turn** — Persist: offload (if needed), save_short_term, save_long_term, add_episode, add_fact, add_procedure. Use with any memory that implements `MemoryForPersistProtocol`.
- **ContextCache** — Optional Redis cache for long-term and procedure lookups (`get`/`set`/`delete`, `message_hash`).
- **Protocols** — `MemoryForContextProtocol`, `MemoryForPersistProtocol`, `ContextCacheProtocol` so you can plug in any implementation.

## Use in this repo

The app in `app/` uses this package via `app.context`, which re-exports from `agent_context` and adds `ContextConfig.from_settings(get_settings())` for the FastAPI app.

## Use in another project

1. Copy the `agent_context` package into your project, or add this repo as a path dependency so `agent_context` is on `sys.path`.

2. Implement the memory protocols (or use an object that already has these methods):
   - **MemoryForContextProtocol**: `get_short_term(session_id)`, `get_relevant_history(user_id, query, limit)`, `list_procedures(user_id, limit, include_docs)`.
   - **MemoryForPersistProtocol**: `save_short_term`, `save_long_term`, `offload_context`, `add_episode`, `add_fact`, `add_procedure`.

3. Build config and pipeline:
   ```python
   from agent_context import ContextConfig, ContextPipeline, ContextCache

   config = ContextConfig.from_env()  # or from_dict({...}) or from_settings(your_settings)
   cache = ContextCache(redis_url="redis://...", ttl_seconds=60) if config.cache_enabled else None
   pipeline = ContextPipeline(memory, config, cache=cache)
   result = await pipeline.build(user_id, session_id, message)
   ```

4. Run your agent with `result.user_message`, then persist:
   ```python
   from agent_context import after_turn

   await after_turn(
       memory, config,
       user_id=user_id, session_id=session_id, message=message,
       short_term_before=result.short_term,
       response_payload=..., intent=...,
       pending_procedures=...,
       on_procedure_saved=optional_async_callback,
   )
   ```

## Dependencies

- No required dependencies for config, filter, compaction, format, protocols, pipeline, persist.
- **ContextCache** requires `redis` (e.g. `redis>=5.0` with async support). If Redis is not installed, the cache is a no-op (connect/get/set/delete do nothing).
- **ContextConfig.from_env()** uses `pydantic-settings` if available; otherwise falls back to default config.

## See also

- **agent_memory** — Reusable memory layer (short-term, long-term, episodic, semantic, procedural) in the same repo. Use with `agent_context` by passing `MemoryManager` as the memory object; it satisfies both protocols.
