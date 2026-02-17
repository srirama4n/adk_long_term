# app.context — Re-exports agent_context for this app

This package **re-exports** the [agent_context](../agent_context/README.md) package so the app can use `ContextConfig.from_settings(get_settings())` and the same APIs. The implementation lives in **agent_context** (no app dependency); use **agent_context** directly in other projects.

## Use in this app

- **BaseSupervisorService** (`app.services.base_supervisor_service`) runs: build context → run agent → persist. Subclass it and implement `_run_agent()`.
- **SupervisorService** extends `BaseSupervisorService` and wires the ADK Supervisor, procedure tool, and app exceptions.

## Use in another supervisor agent

1. **Implement the memory protocols** (or use a memory object that has the same methods):
   - **MemoryForContextProtocol**: `get_short_term(session_id)`, `get_relevant_history(user_id, query, limit)`, `list_procedures(user_id, limit, include_docs)`.
   - **MemoryForPersistProtocol**: `save_short_term`, `save_long_term`, `offload_context`, `add_episode`, `add_fact`, `add_procedure`.

2. **Build config** from your settings:
   ```python
   from app.context import ContextConfig
   config = ContextConfig.from_settings(your_settings)  # or ContextConfig.from_dict({...})
   ```

3. **Build context** for each turn:
   ```python
   from app.context import ContextPipeline
   pipeline = ContextPipeline(memory, config, cache=optional_cache)
   result = await pipeline.build(user_id, session_id, message)
   # result.user_message = assembled string; result.short_term, .long_term, .procedures for persist
   ```

4. **Persist after the turn**:
   ```python
   from app.context import after_turn
   await after_turn(
       memory, config,
       user_id=..., session_id=..., message=...,
       short_term_before=result.short_term,
       response_payload=..., intent=...,
       pending_procedures=...,
       on_procedure_saved=optional_async_callback,
   )
   ```

5. **Or extend BaseSupervisorService** and implement only `_run_agent(user_id, session_id, user_message, flow_id) -> (intent, response_payload)`.

## Public API

- **ContextConfig** — from_settings(settings) / from_dict(data)
- **ContextPipeline** — build(user_id, session_id, message) → BuildResult
- **BuildResult** — user_message, short_term, long_term, procedures
- **after_turn** — persist short-term, long-term, episode, fact, procedures
- **apply_context_filter**, **apply_context_compaction**, **format_procedures_for_context**
- **MemoryForContextProtocol**, **MemoryForPersistProtocol**, **ContextCacheProtocol**
