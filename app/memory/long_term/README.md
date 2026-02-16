# Long-term memory (reusable)

This package provides **long-term memory** for any agent: MongoDB (raw docs) + mem0 (semantic search). Use it in this app or in another agent by importing and configuring it.

## Quick start

```python
from app.memory.long_term import LongTermMemory, LongTermMemoryConfig

# Config from environment (MONGODB_URL, GOOGLE_API_KEY, MONGODB_DB, etc.)
config = LongTermMemoryConfig.from_env()
memory = LongTermMemory(config=config)

await memory.connect()
await memory.save(
    user_id="alice",
    session_id="s1",
    messages=[
        {"role": "user", "content": "I prefer tea over coffee."},
        {"role": "assistant", "content": "Noted, I'll remember that."},
    ],
    metadata={"source": "chat"},
)
history = await memory.get_relevant(user_id="alice", query="drinks", limit=5)
await memory.close()
```

## Config

- **From env**: `LongTermMemoryConfig.from_env()` reads `MONGODB_URL`, `MONGODB_DB`, `MONGODB_COLLECTION`, `MEM0_COLLECTION`, `MEM0_EMBEDDING_MODEL`, `GOOGLE_API_KEY`, `GEMINI_MODEL`.
- **From your settings**: `LongTermMemoryConfig.from_settings(your_settings)` uses any object with `mongodb_url`, `mongodb_db`, `google_api_key`, `gemini_model`, etc.
- **Explicit**: `LongTermMemoryConfig(mongodb_url="...", mongodb_db="...", ...)`.

## API

- `save(user_id, session_id, messages, *, metadata=..., extracted_entities=..., user_preferences=..., intent_history=...)`  
  Persists one turn. `messages` is a list of `{"role": "user"|"assistant", "content": str|dict}`; content is normalized to string for mem0.
- `get_relevant(user_id, query, limit=10)`  
  Semantic search over that user’s memories. Returns list of `{id, memory, metadata, intent_history, ...}`.
- `get_all(user_id, limit=50)`  
  Same as `get_relevant(user_id, "", limit)`.
- `connect()` / `close()`  
  Optional connect and cleanup.

## MongoDB collections

- **Database**: `MONGODB_DB` (default `agent_memory`).
- **Raw docs**: `MONGODB_COLLECTION` (default `agent_long_memory`) — plain conversation JSON.
- **mem0 vectors**: `MEM0_COLLECTION` (default `mem0_long_memory`) — created when mem0 first writes; uses **Atlas Vector Search** (Atlas only).

If you don’t see the mem0 collection in MongoDB:

1. **Run the diagnostic**: `GET /memory/mem0-diagnostic` — returns `{ok: true}` or `{ok: false, error, traceback}` so you can see the exact failure (e.g. Atlas Search, API key, or embedder error).
2. Send at least one **POST /chat** request so long-term save runs.
3. Check app logs for `long_term_mem0_connected` (success) or `long_term_mem0_save_failed` / `long_term_mem0_connect_failed` (failure). On failure, a WARNING will log the collection name (`mem0_collection`, `mem0_db`).
3. mem0’s vector store requires **MongoDB Atlas** with **Atlas Search** (vector index). Self-hosted MongoDB or Atlas without Search will not create the mem0 collection.
5. Ensure `GOOGLE_API_KEY` is set and valid; mem0 uses it for embeddings.

## Dependencies

- `mem0ai`, `motor`, `pymongo`, `certifi` (and `google-genai` for Gemini). Set `GOOGLE_API_KEY` (or pass it in config) for mem0.
